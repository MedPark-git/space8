import html
import re

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

import app as core_app
import task_assignee_manager  # noqa: F401
from app import DailyMeeting, WorkJournalDocument, audit, db

app = task_assignee_manager.app

DELETE_ROLES = {"팀장", "부서장", "관리자"}


def _can_edit_meeting_for_all_visible(meeting):
    return bool(
        current_user.is_authenticated
        and core_app.can_view_meeting(meeting)
    )


def _can_edit_journal_for_all_visible(journal):
    return bool(
        current_user.is_authenticated
        and core_app.can_view_work_journal(journal)
    )


def _can_delete_meeting(meeting):
    return bool(
        current_user.is_authenticated
        and current_user.role.name in DELETE_ROLES
        and core_app.can_view_meeting(meeting)
    )


def _can_delete_journal(journal):
    return bool(
        current_user.is_authenticated
        and current_user.role.name in DELETE_ROLES
        and core_app.can_view_work_journal(journal)
    )


# All employees who can open a document may edit it.
# Daily-work-journal privacy remains unchanged because can_view_work_journal
# keeps the existing private visibility rule for document_type='daily'.
core_app.can_edit_meeting = _can_edit_meeting_for_all_visible
core_app.can_edit_work_journal = _can_edit_journal_for_all_visible


@app.post("/document-control/meetings/<int:meeting_id>/delete")
@login_required
def meeting_document_delete(meeting_id):
    meeting = db.session.get(DailyMeeting, meeting_id)
    if not meeting:
        abort(404)
    if not _can_delete_meeting(meeting):
        abort(403)

    details = {
        "meeting_id": meeting.id,
        "document_type": meeting.document_type,
        "document_label": meeting.document_label,
        "title": meeting.title,
        "meeting_date": meeting.meeting_date.isoformat(),
        "department_id": meeting.department_id,
        "department_name": meeting.department.name if meeting.department else None,
        "author_id": meeting.author_id,
        "author_name": meeting.author.name if meeting.author else None,
        "related_task_ids": [task.id for task in meeting.tasks],
    }

    # Remove only document links. Original tasks remain intact.
    meeting.tasks.clear()
    meeting.attendees.clear()
    db.session.delete(meeting)
    audit("MEETING_DOCUMENT_DELETE", f"meeting:{meeting_id}", details)
    db.session.commit()

    flash("일일회의 문서를 삭제했습니다. 연결된 원본 업무는 유지됩니다.", "success")
    return redirect(url_for("meetings"))


@app.post("/document-control/journals/<int:journal_id>/delete")
@login_required
def journal_document_delete(journal_id):
    journal = db.session.get(WorkJournalDocument, journal_id)
    if not journal:
        abort(404)
    if not _can_delete_journal(journal):
        abort(403)

    details = {
        "journal_id": journal.id,
        "document_type": journal.document_type,
        "document_label": journal.document_label,
        "title": journal.title,
        "work_date": journal.work_date.isoformat(),
        "department_id": journal.department_id,
        "department_name": journal.department.name if journal.department else None,
        "author_id": journal.author_id,
        "author_name": journal.author.name if journal.author else None,
        "related_task_ids": [task.id for task in journal.tasks],
    }

    # Remove only document links. Original tasks and task logs remain intact.
    journal.tasks.clear()
    db.session.delete(journal)
    audit("WORK_JOURNAL_DOCUMENT_DELETE", f"journal:{journal_id}", details)
    db.session.commit()

    flash("업무일지 문서를 삭제했습니다. 연결된 원본 업무는 유지됩니다.", "success")
    return redirect(url_for("journals"))


_MEETING_EDIT_LINK = re.compile(
    r'(<a\b[^>]*href="/meetings/(?P<id>\d+)/edit"[^>]*>\s*수정\s*</a>)'
)
_JOURNAL_EDIT_LINK = re.compile(
    r'(<a\b[^>]*href="/journals/(?P<id>\d+)/edit"[^>]*>\s*수정\s*</a>)'
)


def _delete_form(kind, document_id, csrf_token):
    if kind == "meeting":
        action = f"/document-control/meetings/{document_id}/delete"
        message = "이 일일회의 문서를 삭제하시겠습니까? 연결된 원본 업무는 삭제되지 않습니다."
    else:
        action = f"/document-control/journals/{document_id}/delete"
        message = "이 업무일지 문서를 삭제하시겠습니까? 연결된 원본 업무는 삭제되지 않습니다."
    return (
        f'<form method="post" action="{action}" class="document-delete-form" '
        f'style="display:inline" onsubmit="return confirm(\'{html.escape(message, quote=True)}\');">'
        f'<input type="hidden" name="csrf_token" value="{html.escape(csrf_token, quote=True)}">'
        '<button class="button danger" type="submit">삭제</button>'
        '</form>'
    )


def _inject_delete_controls(page):
    if current_user.role.name not in DELETE_ROLES:
        return page
    csrf_token = generate_csrf()

    def meeting_replacement(match):
        document_id = int(match.group("id"))
        if f"/document-control/meetings/{document_id}/delete" in page:
            return match.group(1)
        meeting = db.session.get(DailyMeeting, document_id)
        if not meeting or not _can_delete_meeting(meeting):
            return match.group(1)
        return match.group(1) + _delete_form("meeting", document_id, csrf_token)

    def journal_replacement(match):
        document_id = int(match.group("id"))
        if f"/document-control/journals/{document_id}/delete" in page:
            return match.group(1)
        journal = db.session.get(WorkJournalDocument, document_id)
        if not journal or not _can_delete_journal(journal):
            return match.group(1)
        return match.group(1) + _delete_form("journal", document_id, csrf_token)

    page = _MEETING_EDIT_LINK.sub(meeting_replacement, page)
    page = _JOURNAL_EDIT_LINK.sub(journal_replacement, page)
    return page


@app.after_request
def apply_document_access_controls(response):
    if (
        response.mimetype == "text/html"
        and response.status_code < 400
        and current_user.is_authenticated
        and (
            request.path.startswith("/meetings")
            or request.path.startswith("/journals")
        )
    ):
        page = response.get_data(as_text=True)
        page = _inject_delete_controls(page)
        response.set_data(page)
        response.headers.pop("Content-Length", None)
    return response
