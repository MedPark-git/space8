from urllib.parse import urlparse

from flask import flash, jsonify, redirect, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core_app
from app import Department, Task, WorkCategory, app, audit, db


CATEGORY_DEPTH = 3
_ORIGINAL_JOURNAL_CANDIDATE_TASKS = core_app.journal_candidate_tasks
_ORIGINAL_DEFAULT_JOURNAL_TASK_IDS = core_app.default_journal_task_ids
_ORIGINAL_CAN_VIEW_WORK_JOURNAL = core_app.can_view_work_journal


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


def _normalize_task_identity_value(value):
    return " ".join(str(value or "").split()).strip().casefold()


def _request_selected_task_ids(explicit_ids=None):
    selected_ids = set()
    values = explicit_ids if explicit_ids is not None else request.values.getlist("task_ids")
    for value in values or []:
        try:
            selected_ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return selected_ids


def _task_document_identity(task):
    """Business-level identity for document pickers only.

    The production hierarchy remains three levels:
    department(team) -> middle -> small.  Keeping this identity isolated means a future
    fourth category level can be added without changing task/document persistence.
    """
    return (
        task.department_id,
        _normalize_task_identity_value(task.middle_category_name),
        _normalize_task_identity_value(task.small_category_name),
        _normalize_task_identity_value(task.title),
    )


def _deduplicate_document_tasks(tasks, selected_ids=None):
    selected_ids = _request_selected_task_ids(selected_ids)
    selected_by_identity = {}
    first_by_identity = {}
    for task in tasks:
        identity = _task_document_identity(task)
        first_by_identity.setdefault(identity, task)
        if task.id in selected_ids:
            selected_by_identity.setdefault(identity, task)
    representatives = [
        selected_by_identity.get(identity, task)
        for identity, task in first_by_identity.items()
    ]
    return sorted(
        representatives,
        key=lambda task: (
            task.department.name,
            task.middle_category_name or "",
            task.small_category_name or "",
            task.title,
            task.id,
        ),
    )


def _selected_registered_document_tasks(selected_ids=None):
    """Return only tasks explicitly transferred from task-status/registration screens."""
    selected_ids = _request_selected_task_ids(selected_ids)
    if not selected_ids:
        return []
    return db.session.scalars(
        select(Task)
        .where(
            Task.deleted_at.is_(None),
            Task.id.in_(selected_ids),
        )
        .order_by(Task.id.asc())
    ).all()


def _all_registered_document_tasks(selected_ids=None):
    tasks = db.session.scalars(
        select(Task)
        .where(Task.deleted_at.is_(None))
        .order_by(Task.id.asc())
    ).all()
    return _deduplicate_document_tasks(tasks, selected_ids)


def global_meeting_candidate_tasks(user, selected_task_ids=None):
    """Daily-meeting create starts empty and accepts company-wide registered tasks.

    New agenda/minutes forms receive only task ids explicitly transferred from task
    status/registration screens. Edit screens may browse the de-duplicated company-wide
    task catalog so existing documents remain maintainable.
    """
    if request.path == "/meetings":
        return _selected_registered_document_tasks(selected_task_ids)
    return _all_registered_document_tasks(selected_task_ids)


def global_major_journal_candidate_tasks(user, document_type):
    """Major-work is company-wide; daily journal keeps its existing personal scope."""
    if document_type == "major":
        if request.path == "/journals":
            return _selected_registered_document_tasks()
        return _all_registered_document_tasks()
    return _ORIGINAL_JOURNAL_CANDIDATE_TASKS(user, document_type)


def document_default_journal_task_ids(user, document_type, work_date):
    """Major-work compose starts empty; daily journal keeps its existing defaults."""
    if document_type == "major":
        return set()
    return _ORIGINAL_DEFAULT_JOURNAL_TASK_IDS(user, document_type, work_date)


def global_daily_meeting_visibility(meeting):
    """Daily meeting agenda/minutes are management-wide documents."""
    return True


def global_major_work_visibility(journal):
    """Major-work documents are shared; daily work journals keep private rules."""
    if journal.document_type == "major":
        return True
    return _ORIGINAL_CAN_VIEW_WORK_JOURNAL(journal)


# Patch only document selection/view helpers. Task CRUD and daily-journal privacy stay intact.
core_app.meeting_candidate_tasks = global_meeting_candidate_tasks
core_app.journal_candidate_tasks = global_major_journal_candidate_tasks
core_app.default_journal_task_ids = document_default_journal_task_ids
core_app.can_view_meeting = global_daily_meeting_visibility
core_app.can_view_work_journal = global_major_work_visibility


@app.post("/tasks/work-categories/add")
@login_required
def department_work_category_add():
    """Create a middle/small category inside the existing department-level major category."""
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
        return _category_error("본인 소속 부서(팀)의 업무구분만 추가할 수 있습니다.", 403)

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
            else (
                "미사용 업무구분을 다시 활성화했습니다."
                if reactivated
                else "이미 등록된 업무구분입니다. 해당 항목을 선택했습니다."
            )
        )
        return jsonify({"ok": True, "message": message, "category": payload})

    flash("업무구분을 저장했습니다.", "success")
    return redirect(_safe_return_to(request.form.get("return_to")))
