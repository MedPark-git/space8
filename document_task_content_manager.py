import re
from urllib.parse import parse_qs, urlparse

from flask import g, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import UniqueConstraint, select

import app as core_app
import document_access_manager  # noqa: F401
from app import DailyMeeting, Task, WorkJournalDocument, audit, db, utcnow

app = document_access_manager.app


class DocumentTaskContent(db.Model):
    __tablename__ = "document_task_contents"
    id = db.Column(db.Integer, primary_key=True)
    document_kind = db.Column(db.String(20), nullable=False, index=False)
    document_id = db.Column(db.Integer, nullable=False, index=False)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    task = db.relationship("Task")
    __table_args__ = (
        UniqueConstraint(
            "document_kind",
            "document_id",
            "task_id",
            name="uq_document_task_content",
        ),
    )


MEETING_EDIT_RE = re.compile(r"^/meetings/(?P<id>\d+)/edit$")
JOURNAL_EDIT_RE = re.compile(r"^/journals/(?P<id>\d+)/edit$")
MEETING_DELETE_RE = re.compile(r"^/document-control/meetings/(?P<id>\d+)/delete$")
JOURNAL_DELETE_RE = re.compile(r"^/document-control/journals/(?P<id>\d+)/delete$")


def _parse_task_ids(values):
    task_ids = []
    seen = set()
    for raw in values or []:
        for part in str(raw or "").split(","):
            try:
                task_id = int(part.strip())
            except (TypeError, ValueError):
                continue
            if task_id <= 0 or task_id in seen:
                continue
            seen.add(task_id)
            task_ids.append(task_id)
            if len(task_ids) >= 500:
                return task_ids
    return task_ids


def _snapshot_map(document_kind, document_id):
    cache = getattr(g, "_document_task_content_cache", None)
    if cache is None:
        cache = {}
        g._document_task_content_cache = cache
    key = (document_kind, int(document_id))
    if key not in cache:
        rows = db.session.scalars(
            select(DocumentTaskContent).where(
                DocumentTaskContent.document_kind == document_kind,
                DocumentTaskContent.document_id == document_id,
            )
        ).all()
        cache[key] = {row.task_id: row.content for row in rows}
    return cache[key]


def document_task_content(document_kind, document_id, task):
    if not task:
        return ""
    contents = _snapshot_map(document_kind, document_id)
    if task.id in contents:
        return contents[task.id]
    return task.content or ""


app.jinja_env.globals["document_task_content"] = document_task_content


def _meeting_detail_text_with_snapshots(meeting):
    sections = []
    if meeting.tasks:
        task_lines = []
        for index, task in enumerate(
            sorted(meeting.tasks, key=lambda item: (item.department.name, item.target_date, item.id)),
            start=1,
        ):
            task_lines.append(
                f"{index}. [{task.department.name}] {task.title}\n"
                f"   담당자: {task.display_assignees} | 분류: {', '.join(task.type_names) or '-'} | "
                f"목표일: {task.target_date} | 상태: {task.status} ({task.progress}%)"
            )
            snapshot_content = document_task_content("meeting", meeting.id, task)
            if snapshot_content:
                task_lines.append(f"   업무내용: {snapshot_content.strip()}")
        sections.append("■ 선택 업무\n" + "\n".join(task_lines))
    for heading, content in (
        ("추가 아젠다 및 사전 공유사항", meeting.agenda_content),
        ("주요 논의사항", meeting.discussion_notes),
        ("결정사항", meeting.decisions),
        ("후속 조치사항", meeting.action_items),
    ):
        if content:
            sections.append(f"■ {heading}\n{content.strip()}")
    return "\n\n".join(sections) or "작성된 회의내용이 없습니다."


core_app.meeting_detail_text = _meeting_detail_text_with_snapshots


def _document_id_from_response(response, document_kind):
    location = response.headers.get("Location") or ""
    if location:
        parsed = urlparse(location)
        open_values = parse_qs(parsed.query).get("open") or []
        if open_values:
            try:
                return int(open_values[0])
            except (TypeError, ValueError):
                pass
        pattern = r"^/meetings/(\d+)" if document_kind == "meeting" else r"^/journals/(\d+)"
        match = re.match(pattern, parsed.path or "")
        if match:
            return int(match.group(1))

    path_match = MEETING_EDIT_RE.match(request.path) if document_kind == "meeting" else JOURNAL_EDIT_RE.match(request.path)
    if path_match:
        return int(path_match.group("id"))
    return None


def _sync_document_snapshots(document_kind, document_id):
    if document_kind == "meeting":
        document = db.session.get(DailyMeeting, document_id)
    else:
        document = db.session.get(WorkJournalDocument, document_id)
    if not document:
        return

    linked_tasks = list(document.tasks)
    linked_ids = {task.id for task in linked_tasks}
    existing_rows = db.session.scalars(
        select(DocumentTaskContent).where(
            DocumentTaskContent.document_kind == document_kind,
            DocumentTaskContent.document_id == document_id,
        )
    ).all()
    existing_by_task = {row.task_id: row for row in existing_rows}

    changed = 0
    removed = 0
    for row in existing_rows:
        if row.task_id not in linked_ids:
            db.session.delete(row)
            removed += 1

    for task in linked_tasks:
        field_name = f"task_content_{task.id}"
        row = existing_by_task.get(task.id)
        if field_name in request.form:
            value = request.form.get(field_name, "")
        elif row is not None:
            continue
        else:
            value = task.content or ""

        if row is None:
            db.session.add(
                DocumentTaskContent(
                    document_kind=document_kind,
                    document_id=document_id,
                    task_id=task.id,
                    content=value,
                )
            )
            changed += 1
        elif row.content != value:
            row.content = value
            row.updated_at = utcnow()
            changed += 1

    if changed or removed:
        audit(
            "DOCUMENT_TASK_CONTENT_SAVE",
            f"{document_kind}:{document_id}",
            {
                "document_kind": document_kind,
                "document_id": document_id,
                "linked_task_ids": sorted(linked_ids),
                "changed_count": changed,
                "removed_count": removed,
                "snapshot_mode": "per_document",
            },
        )
        db.session.commit()
        if hasattr(g, "_document_task_content_cache"):
            delattr(g, "_document_task_content_cache")


def _cleanup_document_snapshots(document_kind, document_id):
    rows = db.session.scalars(
        select(DocumentTaskContent).where(
            DocumentTaskContent.document_kind == document_kind,
            DocumentTaskContent.document_id == document_id,
        )
    ).all()
    if not rows:
        return
    for row in rows:
        db.session.delete(row)
    db.session.commit()


def _metadata_task_allowed(task, document_kind, document_type):
    if not task or task.deleted_at is not None:
        return False
    if document_kind == "meeting":
        return True
    if document_type == "major":
        return True
    return task.assignee_id == current_user.id


@app.get("/document-task-content/metadata")
@login_required
def document_task_content_metadata():
    task_ids = _parse_task_ids(request.args.getlist("task_ids"))
    document_kind = str(request.args.get("kind") or "").strip()
    document_type = str(request.args.get("document_type") or "").strip()
    document_id = request.args.get("document_id", type=int)

    if document_kind not in {"meeting", "journal"}:
        return jsonify({"ok": False, "message": "문서 종류가 올바르지 않습니다."}), 400
    if document_kind == "journal" and document_id:
        journal = db.session.get(WorkJournalDocument, document_id)
        if journal:
            document_type = journal.document_type
    if document_kind == "journal" and document_type not in {"major", "daily"}:
        document_type = "major"

    tasks = db.session.scalars(
        select(Task).where(Task.id.in_(task_ids), Task.deleted_at.is_(None)).order_by(Task.id)
    ).all() if task_ids else []
    snapshot = _snapshot_map(document_kind, document_id) if document_id else {}

    payload = {}
    for task in tasks:
        if not _metadata_task_allowed(task, document_kind, document_type):
            continue
        payload[str(task.id)] = {
            "id": task.id,
            "title": task.title,
            "department": task.department.name,
            "middle_category": task.middle_category_name or "",
            "small_category": task.small_category_name or "",
            "original_content": task.content or "",
            "content": snapshot[task.id] if task.id in snapshot else (task.content or ""),
        }
    return jsonify({"ok": True, "tasks": payload})


@app.after_request
def persist_document_task_contents(response):
    if request.method == "POST" and response.status_code < 400:
        if request.path == "/meetings" or MEETING_EDIT_RE.match(request.path):
            document_id = _document_id_from_response(response, "meeting")
            if document_id:
                _sync_document_snapshots("meeting", document_id)
        elif request.path == "/journals" or JOURNAL_EDIT_RE.match(request.path):
            document_id = _document_id_from_response(response, "journal")
            if document_id:
                _sync_document_snapshots("journal", document_id)
        else:
            meeting_delete = MEETING_DELETE_RE.match(request.path)
            journal_delete = JOURNAL_DELETE_RE.match(request.path)
            if meeting_delete:
                _cleanup_document_snapshots("meeting", int(meeting_delete.group("id")))
            elif journal_delete:
                _cleanup_document_snapshots("journal", int(journal_delete.group("id")))
    return response


@app.after_request
def inject_document_task_content_assets(response):
    if (
        response.mimetype == "text/html"
        and response.status_code < 400
        and current_user.is_authenticated
        and request.path.startswith(("/tasks", "/meetings", "/journals"))
    ):
        page = response.get_data(as_text=True)
        css = '<link rel="stylesheet" href="/static/document_task_content_editor.css?v=20260905-document-snapshot">'
        js = '<script src="/static/document_task_content_editor.js?v=20260905-document-snapshot" defer></script>'
        if css not in page and "</head>" in page:
            page = page.replace("</head>", css + "</head>")
        if js not in page and "</body>" in page:
            page = page.replace("</body>", js + "</body>")
        response.set_data(page)
        response.headers.pop("Content-Length", None)
    return response
