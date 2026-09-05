from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

import document_task_content_guard_manager  # noqa: F401
from app import DailyMeeting, WorkJournalDocument, audit, db
from document_task_content_manager import DocumentTaskContent

app = document_task_content_guard_manager.app

ADMIN_ROLE = "관리자"
MAX_BULK_DELETE = 500


def _admin_only():
    if not current_user.is_authenticated or current_user.role.name != ADMIN_ROLE:
        abort(403)


def _selected_document_ids():
    ids = []
    seen = set()
    for raw in request.form.getlist("document_ids"):
        for part in str(raw or "").split(","):
            try:
                document_id = int(part.strip())
            except (TypeError, ValueError):
                continue
            if document_id <= 0 or document_id in seen:
                continue
            seen.add(document_id)
            ids.append(document_id)
            if len(ids) >= MAX_BULK_DELETE:
                return ids
    return ids


def _delete_snapshots(document_kind, document_ids):
    if not document_ids:
        return 0
    rows = db.session.scalars(
        select(DocumentTaskContent).where(
            DocumentTaskContent.document_kind == document_kind,
            DocumentTaskContent.document_id.in_(document_ids),
        )
    ).all()
    for row in rows:
        db.session.delete(row)
    return len(rows)


@app.post("/document-control/meetings/bulk-delete")
@login_required
def admin_bulk_meeting_delete():
    _admin_only()
    document_ids = _selected_document_ids()
    if not document_ids:
        flash("삭제할 일일회의 문서를 선택해 주세요.", "error")
        return redirect(url_for("meetings"))

    meetings = db.session.scalars(
        select(DailyMeeting).where(DailyMeeting.id.in_(document_ids)).order_by(DailyMeeting.id)
    ).all()
    if not meetings:
        flash("삭제할 일일회의 문서를 찾을 수 없습니다.", "error")
        return redirect(url_for("meetings"))

    deleted = []
    for meeting in meetings:
        deleted.append(
            {
                "id": meeting.id,
                "document_type": meeting.document_type,
                "document_label": meeting.document_label,
                "title": meeting.title,
                "meeting_date": meeting.meeting_date.isoformat(),
                "author_id": meeting.author_id,
                "author_name": meeting.author.name if meeting.author else None,
                "related_task_ids": [task.id for task in meeting.tasks],
            }
        )
        meeting.tasks.clear()
        meeting.attendees.clear()
        db.session.delete(meeting)

    snapshot_count = _delete_snapshots("meeting", [item["id"] for item in deleted])
    audit(
        "MEETING_DOCUMENT_BULK_DELETE",
        "meetings:bulk",
        {
            "count": len(deleted),
            "document_ids": [item["id"] for item in deleted],
            "documents": deleted,
            "snapshot_rows_deleted": snapshot_count,
            "original_tasks_preserved": True,
        },
    )
    db.session.commit()

    flash(f"일일회의 문서 {len(deleted)}건을 삭제했습니다. 연결된 원본 업무는 유지됩니다.", "success")
    return redirect(url_for("meetings"))


@app.post("/document-control/journals/bulk-delete")
@login_required
def admin_bulk_journal_delete():
    _admin_only()
    document_ids = _selected_document_ids()
    if not document_ids:
        flash("삭제할 업무일지 문서를 선택해 주세요.", "error")
        return redirect(url_for("journals"))

    journals = db.session.scalars(
        select(WorkJournalDocument)
        .where(WorkJournalDocument.id.in_(document_ids))
        .order_by(WorkJournalDocument.id)
    ).all()
    if not journals:
        flash("삭제할 업무일지 문서를 찾을 수 없습니다.", "error")
        return redirect(url_for("journals"))

    deleted = []
    for journal in journals:
        deleted.append(
            {
                "id": journal.id,
                "document_type": journal.document_type,
                "document_label": journal.document_label,
                "title": journal.title,
                "work_date": journal.work_date.isoformat(),
                "author_id": journal.author_id,
                "author_name": journal.author.name if journal.author else None,
                "related_task_ids": [task.id for task in journal.tasks],
            }
        )
        journal.tasks.clear()
        db.session.delete(journal)

    snapshot_count = _delete_snapshots("journal", [item["id"] for item in deleted])
    audit(
        "WORK_JOURNAL_DOCUMENT_BULK_DELETE",
        "journals:bulk",
        {
            "count": len(deleted),
            "document_ids": [item["id"] for item in deleted],
            "documents": deleted,
            "snapshot_rows_deleted": snapshot_count,
            "original_tasks_preserved": True,
        },
    )
    db.session.commit()

    flash(f"업무일지 문서 {len(deleted)}건을 삭제했습니다. 연결된 원본 업무는 유지됩니다.", "success")
    return redirect(url_for("journals"))


@app.after_request
def inject_admin_bulk_document_delete(response):
    if (
        response.mimetype == "text/html"
        and response.status_code < 400
        and current_user.is_authenticated
        and current_user.role.name == ADMIN_ROLE
        and request.path in {"/meetings", "/journals"}
    ):
        page = response.get_data(as_text=True)
        asset = '<script src="/static/admin_bulk_document_delete.js?v=20260905-admin-bulk-delete" defer></script>'
        if asset not in page and "</body>" in page:
            page = page.replace("</body>", asset + "</body>")
            response.set_data(page)
            response.headers.pop("Content-Length", None)
    return response
