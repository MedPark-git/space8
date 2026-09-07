from flask import jsonify, request
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


@app.get("/__health/task-category-runtime")
def task_category_runtime_health():
    try:
        db.session.execute(select(WorkCategory.id).limit(1)).first()
        table_state = "ready"
    except Exception:
        db.session.rollback()
        table_state = "error"
    return jsonify({"ok": True, "runtime": "task_category_runtime", "work_categories": table_state})


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
