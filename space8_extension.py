from urllib.parse import urlparse

from flask import flash, jsonify, redirect, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import Department, WorkCategory, app, audit, db


CATEGORY_DEPTH = 3


def _is_ajax_request():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _safe_return_to(value):
    candidate = str(value or "").strip()
    if not candidate:
        return "/tasks/new"
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith("/"):
        return "/tasks/new"
    return candidate


def _category_payload(category):
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
        "depth": CATEGORY_DEPTH,
        "path": [
            category.department.name,
            category.middle_name,
            category.small_name or "",
        ],
    }


def _category_error(message, status_code=400):
    if _is_ajax_request():
        return jsonify({"ok": False, "message": message}), status_code
    flash(message, "error")
    return redirect(_safe_return_to(request.form.get("return_to")))


@app.post("/tasks/work-categories/add")
@login_required
def department_work_category_add():
    """Create a middle/small category inside an existing department-level major category.

    The current production hierarchy remains exactly three levels:
    department(team) -> middle -> small.  This endpoint is deliberately isolated from
    task CRUD so a future fourth level can be introduced without coupling it to Task.
    """
    department_id = request.form.get("department_id", type=int)
    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()

    if not department_id:
        return _category_error("대분류(부서(팀))를 확인해 주세요.")
    if not middle_name:
        return _category_error("중분류명을 입력해 주세요.")
    if len(middle_name) > 100:
        return _category_error("중분류명은 100자 이하로 입력해 주세요.")
    if len(small_name) > 150:
        return _category_error("소분류명은 150자 이하로 입력해 주세요.")

    department = db.session.get(Department, department_id)
    if not department or not department.active:
        return _category_error("사용 가능한 부서(팀)를 찾을 수 없습니다.", 404)

    is_admin = current_user.role.name == "관리자"
    if not is_admin and current_user.department_id != department_id:
        return _category_error(
            "본인 소속 부서(팀)의 업무구분만 추가할 수 있습니다.",
            403,
        )

    try:
        category = db.session.scalar(
            select(WorkCategory).where(
                WorkCategory.department_id == department_id,
                WorkCategory.middle_name == middle_name,
                WorkCategory.small_name == small_name,
            )
        )
        created = category is None
        reactivated = False

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
        elif not category.active:
            category.active = True
            reactivated = True

        audit(
            "WORK_CATEGORY_CREATE" if created else "WORK_CATEGORY_REUSE",
            f"work-category:{category.id}",
            {
                "department_id": department_id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
                "created": created,
                "reactivated": reactivated,
                "hierarchy_depth": CATEGORY_DEPTH,
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
            return _category_error("업무구분 저장 중 충돌이 발생했습니다. 다시 시도해 주세요.", 409)
    except Exception:
        db.session.rollback()
        raise

    payload = _category_payload(category)
    if _is_ajax_request():
        message = (
            "새 업무구분을 추가했습니다."
            if created
            else ("미사용 업무구분을 다시 활성화했습니다." if reactivated else "이미 등록된 업무구분입니다. 해당 항목을 선택했습니다.")
        )
        return jsonify({"ok": True, "message": message, "category": payload})

    flash("업무구분을 저장했습니다.", "success")
    return redirect(_safe_return_to(request.form.get("return_to")))
