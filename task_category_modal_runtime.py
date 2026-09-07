from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import task_category_runtime as base_runtime
from app import Department, WorkCategory, audit, db

app = base_runtime.app


def _is_admin():
    role_name = str(getattr(getattr(current_user, "role", None), "name", "") or "").strip()
    return bool(
        role_name in {"관리자", "시스템관리자"}
        or "관리자" in role_name
        or current_user.role.allows("admin")
        or current_user.role.allows("task_manage_all")
    )


def _json_error(message, status=400, code=None):
    payload = {"ok": False, "message": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


def _allowed_department(requested_id):
    department_id = int(requested_id or 0)
    if not department_id:
        return None, _json_error("대분류(부서(팀))를 선택해 주세요.", 400, "DEPARTMENT_REQUIRED")
    department = db.session.get(Department, department_id)
    if not department or not department.active:
        return None, _json_error("사용 가능한 부서(팀)를 찾을 수 없습니다.", 404, "DEPARTMENT_NOT_FOUND")
    if not _is_admin() and current_user.department_id != department.id:
        return None, _json_error("본인 소속 부서(팀)의 업무구분만 관리할 수 있습니다.", 403, "CATEGORY_FORBIDDEN")
    return department, None


def _category_payload(category):
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
        "task_count": sum(1 for task in category.tasks if task.deleted_at is None),
    }


@app.get("/__health/task-category-modal")
def task_category_modal_health():
    return jsonify({"ok": True, "runtime": "task_category_modal_runtime"})


@app.get("/tasks/work-categories/list")
@login_required
def task_work_category_list_inline():
    department, error = _allowed_department(request.args.get("department_id", type=int))
    if error:
        return error
    rows = db.session.scalars(
        select(WorkCategory)
        .where(
            WorkCategory.department_id == department.id,
            WorkCategory.active.is_(True),
        )
        .order_by(
            WorkCategory.middle_name,
            WorkCategory.small_name,
            WorkCategory.id,
        )
    ).all()
    return jsonify({
        "ok": True,
        "department": {"id": department.id, "name": department.name},
        "categories": [_category_payload(row) for row in rows],
    })


@app.post("/tasks/work-categories/rename-middle")
@base_runtime.core_app.csrf.exempt
@login_required
def task_work_category_rename_middle_inline():
    csrf_error = base_runtime._validate_category_csrf()
    if csrf_error:
        return csrf_error

    department, error = _allowed_department(request.form.get("department_id", type=int))
    if error:
        return error

    old_name = str(request.form.get("old_middle_name") or "").strip()
    new_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _json_error("기존 중분류명과 새 중분류명을 확인해 주세요.", 400, "MIDDLE_NAME_REQUIRED")
    if len(new_name) > 100:
        return _json_error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_NAME_TOO_LONG")
    if old_name == new_name:
        return jsonify({"ok": True, "message": "변경된 내용이 없습니다."})

    rows = db.session.scalars(
        select(WorkCategory).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == old_name,
            WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        return _json_error("수정할 중분류를 찾을 수 없습니다.", 404, "MIDDLE_NOT_FOUND")

    row_ids = [row.id for row in rows]
    small_names = [row.small_name for row in rows]
    conflict = db.session.scalar(
        select(WorkCategory.id).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == new_name,
            WorkCategory.small_name.in_(small_names),
            ~WorkCategory.id.in_(row_ids),
        ).limit(1)
    )
    if conflict:
        return _json_error("변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.", 409, "MIDDLE_NAME_CONFLICT")

    try:
        for row in rows:
            row.middle_name = new_name
        audit(
            "TASK_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "previous_middle_name": old_name,
                "new_middle_name": new_name,
                "affected_category_ids": row_ids,
                "source": "task_registration_modal",
            },
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _json_error("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", 409, "MIDDLE_RENAME_CONFLICT")
    except Exception as exc:
        db.session.rollback()
        return _json_error(f"중분류 수정 중 서버 오류가 발생했습니다. ({type(exc).__name__})", 500, "MIDDLE_RENAME_ERROR")

    return jsonify({"ok": True, "message": "중분류명을 수정했습니다."})


@app.post("/tasks/work-categories/rename-small")
@base_runtime.core_app.csrf.exempt
@login_required
def task_work_category_rename_small_inline():
    csrf_error = base_runtime._validate_category_csrf()
    if csrf_error:
        return csrf_error

    category_id = request.form.get("work_category_id", type=int)
    new_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id or not new_name:
        return _json_error("수정할 소분류와 새 소분류명을 확인해 주세요.", 400, "SMALL_NAME_REQUIRED")
    if len(new_name) > 150:
        return _json_error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_NAME_TOO_LONG")

    category = db.session.get(WorkCategory, category_id)
    if not category or not category.active:
        return _json_error("수정할 소분류를 찾을 수 없습니다.", 404, "SMALL_NOT_FOUND")
    department, error = _allowed_department(category.department_id)
    if error:
        return error
    if not category.small_name:
        return _json_error("소분류 미지정 항목은 소분류 수정 대상이 아닙니다.", 400, "SMALL_PLACEHOLDER")
    if category.small_name == new_name:
        return jsonify({"ok": True, "message": "변경된 내용이 없습니다."})

    conflict = db.session.scalar(
        select(WorkCategory.id).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == category.middle_name,
            WorkCategory.small_name == new_name,
            WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _json_error("같은 중분류 아래에 동일한 소분류가 이미 존재합니다.", 409, "SMALL_NAME_CONFLICT")

    previous = category.small_name
    try:
        category.small_name = new_name
        audit(
            "TASK_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": category.middle_name,
                "previous_small_name": previous,
                "new_small_name": new_name,
                "source": "task_registration_modal",
            },
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _json_error("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", 409, "SMALL_RENAME_CONFLICT")
    except Exception as exc:
        db.session.rollback()
        return _json_error(f"소분류 수정 중 서버 오류가 발생했습니다. ({type(exc).__name__})", 500, "SMALL_RENAME_ERROR")

    return jsonify({"ok": True, "message": "소분류명을 수정했습니다."})
