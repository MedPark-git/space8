from flask import abort
from flask_login import current_user

import app as core_app
import admin_bulk_document_delete_manager as bulk_delete
import document_access_manager as document_access

app = bulk_delete.app
ADMIN_ROLE_NAMES = {"관리자", "시스템관리자"}


def is_effective_administrator(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if not role:
        return False

    role_name = str(getattr(role, "name", "") or "").strip()
    if role_name in ADMIN_ROLE_NAMES or "관리자" in role_name:
        return True

    try:
        if role.allows("admin") or role.allows("task_manage_all"):
            return True
    except Exception:
        pass

    permissions = getattr(role, "permissions", None) or {}
    return bool(permissions.get("admin") or permissions.get("task_manage_all"))


# Expose the same administrator rule to templates and all document permission checks.
app.jinja_env.globals["is_effective_administrator"] = is_effective_administrator
core_app.is_administrator = is_effective_administrator

_original_can_view_work_journal = core_app.can_view_work_journal
_original_can_view_meeting = core_app.can_view_meeting
_original_can_view_daily_journal_author = core_app.can_view_daily_journal_author


def can_view_daily_journal_author_with_admin(author_id, department_id):
    if is_effective_administrator(current_user):
        return True
    return _original_can_view_daily_journal_author(author_id, department_id)


def can_view_work_journal_with_admin(journal):
    if is_effective_administrator(current_user):
        return True
    return _original_can_view_work_journal(journal)


def can_view_meeting_with_admin(meeting):
    if is_effective_administrator(current_user):
        return True
    return _original_can_view_meeting(meeting)


def can_edit_work_journal_for_visible(journal):
    return bool(current_user.is_authenticated and core_app.can_view_work_journal(journal))


def can_edit_meeting_for_visible(meeting):
    return bool(current_user.is_authenticated and core_app.can_view_meeting(meeting))


core_app.can_view_daily_journal_author = can_view_daily_journal_author_with_admin
core_app.can_view_work_journal = can_view_work_journal_with_admin
core_app.can_view_meeting = can_view_meeting_with_admin
core_app.can_edit_work_journal = can_edit_work_journal_for_visible
core_app.can_edit_meeting = can_edit_meeting_for_visible


def _can_delete_meeting(meeting):
    if not current_user.is_authenticated:
        return False
    if is_effective_administrator(current_user):
        return True
    return bool(
        current_user.role.name in {"팀장", "부서장"}
        and core_app.can_view_meeting(meeting)
    )


def _can_delete_journal(journal):
    if not current_user.is_authenticated:
        return False
    if is_effective_administrator(current_user):
        return True
    return bool(
        current_user.role.name in {"팀장", "부서장"}
        and core_app.can_view_work_journal(journal)
    )


document_access._can_delete_meeting = _can_delete_meeting
document_access._can_delete_journal = _can_delete_journal
document_access.DELETE_ROLES.update(ADMIN_ROLE_NAMES)


def _admin_only():
    if not is_effective_administrator(current_user):
        abort(403)


bulk_delete._admin_only = _admin_only

# Disable previous response-time UI injection. Delete routes remain active;
# the board controls are loaded directly from base.html instead.
for _func in list(app.after_request_funcs.get(None, [])):
    if getattr(_func, "__name__", "") in {
        "inject_admin_bulk_document_delete",
        "render_admin_document_delete_controls",
    }:
        app.after_request_funcs[None].remove(_func)
