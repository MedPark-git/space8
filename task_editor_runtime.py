from functools import wraps

from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core

app = core.app


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("task_manage_all")
        )
    )


def _json_error(message, status=400, code=None):
    payload = {"ok": False, "message": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


def _allowed_department(department_id):
    department_id = int(department_id or 0)
    if not department_id:
        return None, _json_error("대분류(부서·팀)를 선택해 주세요.", 400, "DEPARTMENT_REQUIRED")

    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None, _json_error("사용 가능한 부서(팀)를 찾을 수 없습니다.", 404, "DEPARTMENT_NOT_FOUND")

    if not _is_admin() and current_user.department_id != department.id:
        return None, _json_error(
            "본인 소속 부서(팀)의 중분류·소분류만 관리할 수 있습니다.",
            403,
            "CATEGORY_FORBIDDEN",
        )

    return department, None


def _visible_categories():
    if _is_admin():
        categories = core.active_work_categories()
    else:
        categories = core.active_work_categories([current_user.department_id])
    return core.build_work_category_catalog(categories)


def _category_payload(category):
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
    }


def _handle_add():
    department, error = _allowed_department(request.form.get("department_id", type=int))
    if error:
        return error

    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()
    if not middle_name:
        return _json_error("중분류명을 입력해 주세요.", 400, "MIDDLE_REQUIRED")
    if len(middle_name) > 100:
        return _json_error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_TOO_LONG")
    if len(small_name) > 150:
        return _json_error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_TOO_LONG")

    category = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.small_name == small_name,
        )
    )

    created = False
    if category:
        if not category.active:
            category.active = True
        else:
            return _json_error("이미 등록된 업무구분입니다.", 409, "CATEGORY_EXISTS")
    else:
        category = core.WorkCategory(
            department_id=department.id,
            middle_name=middle_name,
            small_name=small_name,
            active=True,
        )
        core.db.session.add(category)
        created = True

    try:
        core.db.session.flush()
        core.audit(
            "TASK_WORK_CATEGORY_CREATE" if created else "TASK_WORK_CATEGORY_REACTIVATE",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
                "source": "task_registration_page",
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error("동일한 업무구분이 이미 존재합니다.", 409, "CATEGORY_CONFLICT")
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"업무구분 등록 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "CATEGORY_ADD_ERROR",
        )

    return jsonify(
        {
            "ok": True,
            "message": "업무구분을 등록했습니다.",
            "category": _category_payload(category),
            "categories": _visible_categories(),
        }
    )


def _handle_rename_middle():
    department, error = _allowed_department(request.form.get("department_id", type=int))
    if error:
        return error

    old_name = str(request.form.get("old_middle_name") or "").strip()
    new_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _json_error(
            "기존 중분류명과 새 중분류명을 확인해 주세요.",
            400,
            "MIDDLE_REQUIRED",
        )
    if len(new_name) > 100:
        return _json_error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_TOO_LONG")
    if old_name == new_name:
        return jsonify(
            {"ok": True, "message": "변경된 내용이 없습니다.", "categories": _visible_categories()}
        )

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == old_name,
            core.WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        return _json_error("수정할 중분류를 찾을 수 없습니다.", 404, "MIDDLE_NOT_FOUND")

    row_ids = {row.id for row in rows}
    small_names = {row.small_name for row in rows}
    conflict = core.db.session.scalar(
        select(core.WorkCategory.id)
        .where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == new_name,
            core.WorkCategory.small_name.in_(small_names),
            core.WorkCategory.id.not_in(row_ids),
        )
        .limit(1)
    )
    if conflict:
        return _json_error(
            "변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.",
            409,
            "MIDDLE_CONFLICT",
        )

    try:
        for row in rows:
            row.middle_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "previous_middle_name": old_name,
                "new_middle_name": new_name,
                "category_ids": sorted(row_ids),
                "source": "task_registration_page",
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error(
            "중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.",
            409,
            "MIDDLE_CONFLICT",
        )
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"중분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "MIDDLE_RENAME_ERROR",
        )

    return jsonify(
        {"ok": True, "message": "중분류명을 수정했습니다.", "categories": _visible_categories()}
    )


def _handle_rename_small():
    category_id = request.form.get("work_category_id", type=int)
    new_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id or not new_name:
        return _json_error(
            "수정할 소분류와 새 소분류명을 확인해 주세요.",
            400,
            "SMALL_REQUIRED",
        )
    if len(new_name) > 150:
        return _json_error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_TOO_LONG")

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category or not category.active:
        return _json_error("수정할 소분류를 찾을 수 없습니다.", 404, "SMALL_NOT_FOUND")

    department, error = _allowed_department(category.department_id)
    if error:
        return error
    if not category.small_name:
        return _json_error(
            "소분류 미지정 항목은 소분류명 수정 대상이 아닙니다.",
            400,
            "SMALL_PLACEHOLDER",
        )
    if category.small_name == new_name:
        return jsonify(
            {"ok": True, "message": "변경된 내용이 없습니다.", "categories": _visible_categories()}
        )

    conflict = core.db.session.scalar(
        select(core.WorkCategory.id).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == category.middle_name,
            core.WorkCategory.small_name == new_name,
            core.WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _json_error(
            "같은 중분류 아래에 동일한 소분류가 이미 존재합니다.",
            409,
            "SMALL_CONFLICT",
        )

    previous = category.small_name
    try:
        category.small_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": category.middle_name,
                "previous_small_name": previous,
                "new_small_name": new_name,
                "source": "task_registration_page",
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error(
            "중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.",
            409,
            "SMALL_CONFLICT",
        )
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"소분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "SMALL_RENAME_ERROR",
        )

    return jsonify(
        {"ok": True, "message": "소분류명을 수정했습니다.", "categories": _visible_categories()}
    )


_CATEGORY_ACTION_HANDLERS = {
    "add": _handle_add,
    "rename_middle": _handle_rename_middle,
    "rename_small": _handle_rename_small,
    "list": lambda: jsonify({"ok": True, "categories": _visible_categories()}),
}


_original_task_new = app.view_functions.get("task_new")
if _original_task_new is None:
    raise RuntimeError("task_new view function을 찾을 수 없습니다.")


@wraps(_original_task_new)
def _task_new_with_category_management(*args, **kwargs):
    if request.method == "POST":
        action = str(request.form.get("category_action") or "").strip()
        if action:
            if not current_user.is_authenticated:
                return _json_error("로그인이 필요합니다.", 401, "LOGIN_REQUIRED")
            handler = _CATEGORY_ACTION_HANDLERS.get(action)
            if handler is None:
                return _json_error(
                    "지원하지 않는 업무구분 작업입니다.",
                    400,
                    "UNKNOWN_CATEGORY_ACTION",
                )
            return handler()

    return _original_task_new(*args, **kwargs)


app.view_functions["task_new"] = _task_new_with_category_management


@app.get("/__health/task-editor-runtime")
def task_editor_runtime_health():
    return jsonify(
        {
            "ok": True,
            "runtime": "task_editor_runtime",
            "category_management_path": "/tasks/new",
            "category_dispatch": "task_new_view_wrapper",
            "actions": sorted(_CATEGORY_ACTION_HANDLERS),
        }
    )
