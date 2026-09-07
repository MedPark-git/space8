from urllib.parse import urlparse

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError

import app as core_app
from app import Department, WorkCategory, audit, db

app = core_app.app

CATEGORY_ENDPOINTS = {
    "/tasks/departments/add",
    "/tasks/work-categories/add",
}


def _is_effective_admin():
    role_name = str(getattr(getattr(current_user, "role", None), "name", "") or "").strip()
    return bool(
        role_name in {"관리자", "시스템관리자"}
        or "관리자" in role_name
        or current_user.role.allows("admin")
        or current_user.role.allows("task_manage_all")
    )


def _error(message, status=400, code=None):
    payload = {"ok": False, "message": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


def _validate_category_csrf():
    token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    try:
        validate_csrf(token)
    except ValidationError:
        return _error(
            "요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
            400,
            "CSRF_VALIDATION_FAILED",
        )
    return None


def _department_payload(department):
    return {
        "id": department.id,
        "name": department.name,
        "active": bool(department.active),
    }


def _category_payload(category):
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
    }


def _safe_local_path(value, default="/tasks/new"):
    candidate = str(value or "").strip()
    if not candidate:
        return default
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith("/"):
        return default
    return candidate


def _employee_category_department():
    department = db.session.get(Department, current_user.department_id)
    if not department or not department.active:
        return None
    return department


def _employee_active_categories(department_id):
    return db.session.scalars(
        select(WorkCategory)
        .where(
            WorkCategory.department_id == department_id,
            WorkCategory.active.is_(True),
        )
        .order_by(
            WorkCategory.middle_name,
            WorkCategory.small_name,
            WorkCategory.id,
        )
    ).all()


def _employee_category_create(department):
    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()
    if not middle_name:
        flash("중분류명을 입력해 주세요.", "error")
        return
    if len(middle_name) > 100:
        flash("중분류명은 100자 이하로 입력해 주세요.", "error")
        return
    if len(small_name) > 150:
        flash("소분류명은 150자 이하로 입력해 주세요.", "error")
        return

    category = db.session.scalar(
        select(WorkCategory).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == middle_name,
            WorkCategory.small_name == small_name,
        )
    )
    if category:
        if category.active:
            flash("이미 등록된 업무구분입니다.", "info")
        else:
            flash("관리자가 미사용 처리한 업무구분입니다. 관리자에게 재사용 전환을 요청해 주세요.", "error")
        return

    try:
        category = WorkCategory(
            department_id=department.id,
            middle_name=middle_name,
            small_name=small_name,
            active=True,
            sort_order=0,
        )
        db.session.add(category)
        db.session.flush()
        audit(
            "EMPLOYEE_WORK_CATEGORY_CREATE",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
                "source": "employee_work_category_page",
            },
        )
        db.session.commit()
        flash("업무구분 기초자료를 등록했습니다.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("같은 업무구분이 이미 등록되어 있습니다.", "error")
    except Exception:
        db.session.rollback()
        raise


def _employee_middle_rename(department):
    old_middle_name = str(request.form.get("old_middle_name") or "").strip()
    new_middle_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_middle_name or not new_middle_name:
        flash("수정할 중분류명과 새 중분류명을 확인해 주세요.", "error")
        return
    if len(new_middle_name) > 100:
        flash("중분류명은 100자 이하로 입력해 주세요.", "error")
        return
    if old_middle_name == new_middle_name:
        flash("변경된 내용이 없습니다.", "info")
        return

    rows = db.session.scalars(
        select(WorkCategory).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == old_middle_name,
            WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        flash("수정할 중분류를 찾을 수 없습니다.", "error")
        return

    row_ids = [row.id for row in rows]
    small_names = [row.small_name for row in rows]
    conflict = db.session.scalar(
        select(WorkCategory.id).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == new_middle_name,
            WorkCategory.small_name.in_(small_names),
            ~WorkCategory.id.in_(row_ids),
        ).limit(1)
    )
    if conflict:
        flash("변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.", "error")
        return

    try:
        for row in rows:
            row.middle_name = new_middle_name
        audit(
            "EMPLOYEE_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "previous_middle_name": old_middle_name,
                "new_middle_name": new_middle_name,
                "affected_category_ids": row_ids,
                "source": "employee_work_category_page",
            },
        )
        db.session.commit()
        flash("중분류명을 수정했습니다. 해당 중분류 아래 소분류에도 함께 반영했습니다.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", "error")
    except Exception:
        db.session.rollback()
        raise


def _employee_small_rename(department):
    category_id = request.form.get("work_category_id", type=int)
    new_small_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id:
        flash("수정할 소분류를 확인해 주세요.", "error")
        return
    if not new_small_name:
        flash("새 소분류명을 입력해 주세요.", "error")
        return
    if len(new_small_name) > 150:
        flash("소분류명은 150자 이하로 입력해 주세요.", "error")
        return

    category = db.session.get(WorkCategory, category_id)
    if (
        not category
        or category.department_id != department.id
        or not category.active
    ):
        flash("본인 부서(팀)에서 수정할 수 있는 소분류가 아닙니다.", "error")
        return
    if not category.small_name:
        flash("중분류 전용 항목은 소분류 수정 대상이 아닙니다.", "error")
        return
    if category.small_name == new_small_name:
        flash("변경된 내용이 없습니다.", "info")
        return

    conflict = db.session.scalar(
        select(WorkCategory.id).where(
            WorkCategory.department_id == department.id,
            WorkCategory.middle_name == category.middle_name,
            WorkCategory.small_name == new_small_name,
            WorkCategory.id != category.id,
        )
    )
    if conflict:
        flash("같은 중분류 아래에 동일한 소분류가 이미 존재합니다.", "error")
        return

    previous_small_name = category.small_name
    try:
        category.small_name = new_small_name
        audit(
            "EMPLOYEE_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": category.middle_name,
                "previous_small_name": previous_small_name,
                "new_small_name": new_small_name,
                "source": "employee_work_category_page",
            },
        )
        db.session.commit()
        flash("소분류명을 수정했습니다.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", "error")
    except Exception:
        db.session.rollback()
        raise


@app.get("/__health/task-category-runtime")
def task_category_runtime_health():
    try:
        db.session.execute(select(WorkCategory.id).limit(1)).first()
        table_state = "ready"
    except Exception:
        db.session.rollback()
        table_state = "error"
    return jsonify({"ok": True, "runtime": "task_category_runtime", "work_categories": table_state})


@app.route("/task-categories", methods=["GET", "POST"])
@login_required
def employee_work_categories():
    if _is_effective_admin():
        return redirect(url_for("admin", section="work-categories"))

    department = _employee_category_department()
    if department is None:
        flash("사용 가능한 소속 부서(팀)를 찾을 수 없습니다.", "error")
        return redirect(url_for("task_new"))

    return_to = _safe_local_path(request.values.get("return_to"), "/tasks/new")
    if request.method == "POST":
        action = str(request.form.get("action") or "create").strip()
        if action == "create":
            _employee_category_create(department)
        elif action == "rename_middle":
            _employee_middle_rename(department)
        elif action == "rename_small":
            _employee_small_rename(department)
        else:
            flash("지원하지 않는 업무구분 작업입니다.", "error")
        return redirect(url_for("employee_work_categories", return_to=return_to))

    categories = _employee_active_categories(department.id)
    return render_template(
        "task_categories_employee.html",
        department=department,
        work_categories=categories,
        return_to=return_to,
    )


@app.post("/tasks/departments/add")
@core_app.csrf.exempt
@login_required
def task_department_add_inline():
    csrf_error = _validate_category_csrf()
    if csrf_error:
        return csrf_error

    if not _is_effective_admin():
        return _error("대분류(부서(팀)) 추가는 관리자만 가능합니다.", 403, "DEPARTMENT_FORBIDDEN")

    name = str(request.form.get("name") or "").strip()
    if not name:
        return _error("새 대분류(부서(팀))명을 입력해 주세요.", 400, "DEPARTMENT_NAME_REQUIRED")
    if len(name) > 100:
        return _error("대분류(부서(팀))명은 100자 이하로 입력해 주세요.", 400, "DEPARTMENT_NAME_TOO_LONG")

    created = False
    reactivated = False
    try:
        department = db.session.scalar(select(Department).where(Department.name == name))
        if department is None:
            department = Department(name=name, parent_id=None, active=True)
            db.session.add(department)
            db.session.flush()
            created = True
        elif not department.active:
            department.active = True
            department.parent_id = None
            reactivated = True

        audit(
            "TASK_DEPARTMENT_INLINE_CREATE" if created else "TASK_DEPARTMENT_INLINE_REUSE",
            f"department:{department.id}",
            {
                "name": name,
                "created": created,
                "reactivated": reactivated,
                "source": "task_registration",
            },
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        department = db.session.scalar(select(Department).where(Department.name == name))
        if department is None:
            return _error(
                "대분류 저장 중 중복 충돌이 발생했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                409,
                "DEPARTMENT_INTEGRITY_ERROR",
            )
    except Exception as exc:
        db.session.rollback()
        return _error(
            f"대분류 저장 중 서버 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "DEPARTMENT_SAVE_ERROR",
        )

    if created:
        message = "새 대분류(부서(팀))를 추가했습니다."
    elif reactivated:
        message = "기존 대분류(부서(팀))를 다시 활성화했습니다."
    else:
        message = "이미 등록된 대분류(부서(팀))입니다. 해당 항목을 선택했습니다."
    return jsonify({"ok": True, "message": message, "department": _department_payload(department)})


@app.post("/tasks/work-categories/add")
@core_app.csrf.exempt
@login_required
def task_work_category_add_inline():
    csrf_error = _validate_category_csrf()
    if csrf_error:
        return csrf_error

    department_id = request.form.get("department_id", type=int)
    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()

    if not department_id:
        return _error("대분류(부서(팀))를 먼저 선택해 주세요.", 400, "DEPARTMENT_REQUIRED")
    if not middle_name:
        return _error("중분류명을 입력해 주세요.", 400, "MIDDLE_NAME_REQUIRED")
    if len(middle_name) > 100:
        return _error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_NAME_TOO_LONG")
    if len(small_name) > 150:
        return _error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_NAME_TOO_LONG")

    department = db.session.get(Department, department_id)
    if not department or not department.active:
        return _error("사용 가능한 대분류(부서(팀))를 찾을 수 없습니다.", 404, "DEPARTMENT_NOT_FOUND")

    if not _is_effective_admin() and current_user.department_id != department_id:
        return _error(
            "본인 소속 부서(팀)의 중분류·소분류만 추가할 수 있습니다.",
            403,
            "CATEGORY_FORBIDDEN",
        )

    created = False
    reactivated = False
    try:
        category = db.session.scalar(
            select(WorkCategory).where(
                WorkCategory.department_id == department_id,
                WorkCategory.middle_name == middle_name,
                WorkCategory.small_name == small_name,
            )
        )
        if category is None:
            category = WorkCategory(
                department_id=department_id,
                middle_name=middle_name,
                small_name=small_name,
                active=True,
                sort_order=0,
            )
            db.session.add(category)
            db.session.flush()
            created = True
        elif not category.active:
            category.active = True
            reactivated = True

        audit(
            "TASK_WORK_CATEGORY_INLINE_CREATE" if created else "TASK_WORK_CATEGORY_INLINE_REUSE",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
                "created": created,
                "reactivated": reactivated,
                "source": "task_registration",
            },
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        category = db.session.scalar(
            select(WorkCategory).where(
                WorkCategory.department_id == department_id,
                WorkCategory.middle_name == middle_name,
                WorkCategory.small_name == small_name,
            )
        )
        if category is None:
            return _error(
                "업무구분 저장 중 중복 충돌이 발생했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                409,
                "CATEGORY_INTEGRITY_ERROR",
            )
    except Exception as exc:
        db.session.rollback()
        return _error(
            f"업무구분 저장 중 서버 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "CATEGORY_SAVE_ERROR",
        )

    if created:
        message = "새 업무구분을 추가했습니다."
    elif reactivated:
        message = "기존 업무구분을 다시 활성화했습니다."
    else:
        message = "이미 등록된 업무구분입니다. 해당 항목을 선택했습니다."
    return jsonify({"ok": True, "message": message, "category": _category_payload(category)})
