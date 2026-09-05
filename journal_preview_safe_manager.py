from datetime import date

from flask import abort, render_template
from flask_login import current_user, login_required

import app as core_app
import admin_document_ui_fix as admin_ui
import document_task_content_manager as content_manager

app = admin_ui.app


def _is_admin(user):
    return admin_ui.is_effective_administrator(user)


# Keep every daily-journal permission path consistent for administrator accounts.
_previous_can_view_daily_journal_author = core_app.can_view_daily_journal_author
_previous_can_view_work_journal = core_app.can_view_work_journal
_previous_can_edit_work_journal = core_app.can_edit_work_journal


def can_view_daily_journal_author_with_admin(author_id, department_id):
    if _is_admin(current_user):
        return True
    return _previous_can_view_daily_journal_author(author_id, department_id)


def can_view_work_journal_with_admin(journal):
    if _is_admin(current_user):
        return True
    return _previous_can_view_work_journal(journal)


def can_edit_work_journal_with_admin(journal):
    if _is_admin(current_user):
        return True
    return _previous_can_edit_work_journal(journal)


core_app.can_view_daily_journal_author = can_view_daily_journal_author_with_admin
core_app.can_view_work_journal = can_view_work_journal_with_admin
core_app.can_edit_work_journal = can_edit_work_journal_with_admin


# Snapshot lookup must never make an otherwise readable saved document fail to open.
_original_document_task_content = content_manager.document_task_content


def safe_document_task_content(document_kind, document_id, task):
    try:
        return _original_document_task_content(document_kind, document_id, task)
    except Exception:
        core_app.db.session.rollback()
        return (task.content or "") if task else ""


content_manager.document_task_content = safe_document_task_content
app.jinja_env.globals["document_task_content"] = safe_document_task_content


# Replace only the preview endpoint. Non-admin behavior stays on the original route.
_original_journal_preview = app.view_functions.get("journal_preview")


@login_required
def journal_preview_admin_safe(journal_id):
    if not _is_admin(current_user):
        if _original_journal_preview is None:
            abort(404)
        return _original_journal_preview(journal_id)

    journal = core_app.db.session.get(core_app.WorkJournalDocument, journal_id)
    if not journal:
        abort(404)

    try:
        logs_by_task = core_app.journal_logs_by_task(journal)
    except Exception:
        core_app.db.session.rollback()
        logs_by_task = {}

    response = render_template(
        "journal_preview.html",
        journal=journal,
        logs_by_task=logs_by_task,
        can_edit=True,
        today=date.today(),
    )
    return response, 200, {"X-MedPark-Journal-Preview": "admin-safe"}


app.view_functions["journal_preview"] = journal_preview_admin_safe
