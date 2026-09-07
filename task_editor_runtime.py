from functools import wraps

from flask import flash, redirect, request, url_for, jsonify
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core

FLASK_APP = core.app
TRANSPORT_VERSION = "task-category-form-v7"


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("task_manage_all")
        )
    )


def _redirect_manager(message, category="success", middle_name="", category_id=""):
    flash(message, category)
    return redirect(
        url_for(
            "task_new",
            category_manager="1",
            category_result=category,
            category_middle=middle_name or None,
            category_id=category_id or None,
        )
    )


def _allowed_department(department_id):
    try:
        department_id = int(department_id or 0)
    except (TypeError, ValueError):
        department_id = 0
    if not department_id:
        return None, _redirect_manager("대분류(부서·팀)를 확인해 주세요.", "error")

    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None, _redirect_manager("사용 가능한 부서(팀)를 찾을 수 없습니다.", "error")

    if not _is_admin() and current_user.department_id != department.id:
        return None, _redirect_manager(
            "본인 소속 부서(팀)의 중분류·소분류만 관리할 수 있습니다.",
            "error",
        )
    return department, None


def _handle_add():
    department, error = _allowed_department(request.form.get("department_id"))
    if error:
        return error

    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()
    if not middle_name:
        return _redirect_manager("중분류명을 확인해 주세요.", "error")
    if len(middle_name) > 100:
        return _redirect_manager("중분류명은 100자 이하로 입력해 주세요.", "error")
    if len(small_name) > 150:
        return _redirect_manager("소분류명은 150자 이하로 입력해 주세요.", "error")

    category = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.small_name == small_name,
        )
    )

    if category and category.active:
        return _redirect_manager(
            "이미 등록된 업무구분입니다. 저장된 항목을 선택했습니다.",
            "success",
            middle_name,
            category.id,
        )

    created = category is None
    if category:
        category.active = True
    else:
        category = core.WorkCategory(
            department_id=department.id,
            middle_name=middle_name,
            small_name=small_name,
            active=True,
        )
        core.db.session.add(category)

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
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        existing = core.db.session.scalar(
            select(core.WorkCategory).where(
                core.WorkCategory.department_id == department.id,
                core.WorkCategory.middle_name == middle_name,
                core.WorkCategory.small_name == small_name,
            )
        )
        if existing:
            return _redirect_manager(
                "이미 등록된 업무구분입니다. 저장된 항목을 선택했습니다.",
                "success",
                middle_name,
                existing.id,
            )
        return _redirect_manager("업무구분 저장 중 충돌이 발생했습니다. 다시 시도해 주세요.", "error")
    except Exception as exc:
        core.db.session.rollback()
        return _redirect_manager(
            f"업무구분 등록 중 오류가 발생했습니다. ({type(exc).__name__})",
            "error",
        )

    return _redirect_manager("업무구분을 등록했습니다.", "success", middle_name, category.id)


def _handle_rename_middle():
    department, error = _allowed_department(request.form.get("department_id"))
    if error:
        return error

    old_name = str(request.form.get("old_middle_name") or "").strip()
    new_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _redirect_manager("수정할 중분류와 새 중분류명을 확인해 주세요.", "error")
    if len(new_name) > 100:
        return _redirect_manager("중분류명은 100자 이하로 입력해 주세요.", "error")
    if old_name == new_name:
        return _redirect_manager("변경된 내용이 없습니다.", "success", new_name)

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == old_name,
            core.WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        return _redirect_manager("수정할 중분류를 찾을 수 없습니다.", "error")

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
        return _redirect_manager(
            "변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.",
            "error",
            old_name,
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
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _redirect_manager("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", "error", old_name)
    except Exception as exc:
        core.db.session.rollback()
        return _redirect_manager(
            f"중분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            "error",
            old_name,
        )

    return _redirect_manager("중분류명을 수정했습니다.", "success", new_name)


def _handle_rename_small():
    try:
        category_id = int(request.form.get("work_category_id") or 0)
    except (TypeError, ValueError):
        category_id = 0
    new_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id or not new_name:
        return _redirect_manager("수정할 소분류와 새 소분류명을 확인해 주세요.", "error")
    if len(new_name) > 150:
        return _redirect_manager("소분류명은 150자 이하로 입력해 주세요.", "error")

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category or not category.active:
        return _redirect_manager("수정할 소분류를 찾을 수 없습니다.", "error")

    department, error = _allowed_department(category.department_id)
    if error:
        return error
    if not category.small_name:
        return _redirect_manager("소분류 미지정 항목은 수정할 수 없습니다.", "error", category.middle_name)
    if category.small_name == new_name:
        return _redirect_manager("변경된 내용이 없습니다.", "success", category.middle_name, category.id)

    conflict = core.db.session.scalar(
        select(core.WorkCategory.id).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == category.middle_name,
            core.WorkCategory.small_name == new_name,
            core.WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _redirect_manager(
            "같은 중분류 아래에 동일한 소분류가 이미 존재합니다.",
            "error",
            category.middle_name,
            category.id,
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
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _redirect_manager("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", "error", category.middle_name)
    except Exception as exc:
        core.db.session.rollback()
        return _redirect_manager(
            f"소분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            "error",
            category.middle_name,
        )

    return _redirect_manager("소분류명을 수정했습니다.", "success", category.middle_name, category.id)


CATEGORY_HANDLERS = {
    "add": _handle_add,
    "rename_middle": _handle_rename_middle,
    "rename_small": _handle_rename_small,
}


_original_task_new = FLASK_APP.view_functions.get("task_new")
if _original_task_new is None:
    raise RuntimeError("task_new view function을 찾을 수 없습니다.")


@wraps(_original_task_new)
@login_required
def _task_new_v7(*args, **kwargs):
    if request.method == "POST" and request.form.get("_category_transport") == "v7":
        action = str(request.form.get("category_action") or "").strip()
        handler = CATEGORY_HANDLERS.get(action)
        if handler is None:
            return _redirect_manager("지원하지 않는 업무구분 작업입니다.", "error")
        return handler()
    return _original_task_new(*args, **kwargs)


FLASK_APP.view_functions["task_new"] = _task_new_v7


@FLASK_APP.get("/__health/task-category-form-v7")
def task_category_form_v7_health():
    return jsonify(
        {
            "ok": True,
            "transport": TRANSPORT_VERSION,
            "route": "/tasks/new",
            "mode": "standard_html_form_post",
            "actions": sorted(CATEGORY_HANDLERS),
        }
    )


app = FLASK_APP
