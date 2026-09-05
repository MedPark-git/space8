from datetime import date
from types import SimpleNamespace

from flask import abort, render_template
from flask_login import current_user, login_required
from markupsafe import escape
from sqlalchemy import text

import app as core_app
import admin_document_ui_fix as admin_ui

app = admin_ui.app


def _is_admin(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if not role:
        return False
    role_name = str(getattr(role, "name", "") or "")
    if role_name in {"관리자", "시스템관리자"} or "관리자" in role_name:
        return True
    try:
        return bool(role.allows("admin") or role.allows("task_manage_all"))
    except Exception:
        permissions = getattr(role, "permissions", None) or {}
        return bool(permissions.get("admin") or permissions.get("task_manage_all"))


# Administrator accounts must be able to open every saved work journal.
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


def _one(sql, params):
    return core_app.db.session.execute(text(sql), params).mappings().first()


def _all(sql, params):
    return core_app.db.session.execute(text(sql), params).mappings().all()


def _load_journal_header(journal_id):
    return _one(
        """
        SELECT
            j.id,
            j.work_date,
            j.document_type,
            j.title,
            j.work_summary,
            j.next_plan,
            j.special_notes,
            j.author_id,
            j.department_id,
            COALESCE(d.name, '-') AS department_name,
            COALESCE(e.name, '-') AS author_name
        FROM work_journal_documents AS j
        LEFT JOIN departments AS d ON d.id = j.department_id
        LEFT JOIN employees AS e ON e.id = j.author_id
        WHERE j.id = :journal_id
        """,
        {"journal_id": journal_id},
    )


def _load_task_rows(journal_row):
    journal_id = journal_row["id"]
    rows = _all(
        """
        SELECT
            t.id,
            t.title,
            COALESCE(t.content, '') AS original_content,
            t.target_date,
            t.progress,
            t.status,
            COALESCE(e.name, '-') AS assignee_name
        FROM work_journal_document_items AS link
        JOIN tasks AS t ON t.id = link.task_id
        LEFT JOIN employees AS e ON e.id = t.assignee_id
        WHERE link.journal_id = :journal_id
        ORDER BY t.target_date, t.id
        """,
        {"journal_id": journal_id},
    )

    result = []
    for task in rows:
        try:
            classification_names = [
                item["name"]
                for item in _all(
                    "SELECT name FROM task_classifications WHERE task_id = :task_id ORDER BY id",
                    {"task_id": task["id"]},
                )
            ]
        except Exception:
            core_app.db.session.rollback()
            classification_names = []

        content = task["original_content"]
        try:
            snapshot = _one(
                """
                SELECT content
                FROM document_task_contents
                WHERE document_kind = 'journal'
                  AND document_id = :journal_id
                  AND task_id = :task_id
                LIMIT 1
                """,
                {"journal_id": journal_id, "task_id": task["id"]},
            )
            if snapshot is not None:
                content = snapshot["content"]
        except Exception:
            core_app.db.session.rollback()

        logs = []
        if journal_row["document_type"] == "daily":
            try:
                logs = [
                    {"content": item["content"]}
                    for item in _all(
                        """
                        SELECT content
                        FROM task_daily_logs
                        WHERE task_id = :task_id
                          AND work_date = :work_date
                          AND author_id = :author_id
                        ORDER BY created_at, id
                        """,
                        {
                            "task_id": task["id"],
                            "work_date": journal_row["work_date"],
                            "author_id": journal_row["author_id"],
                        },
                    )
                ]
            except Exception:
                core_app.db.session.rollback()
                logs = []

        result.append(
            {
                "id": task["id"],
                "title": task["title"],
                "content": content,
                "classification_names": classification_names,
                "assignee_name": task["assignee_name"],
                "target_date": task["target_date"],
                "progress": task["progress"],
                "status": task["status"],
                "status_class": core_app.STATUS_CLASS.get(task["status"], "progress"),
                "logs": logs,
            }
        )
    return result


def _journal_namespace(row):
    return SimpleNamespace(
        id=row["id"],
        work_date=row["work_date"],
        document_type=row["document_type"],
        document_label=core_app.JOURNAL_DOCUMENT_TYPES.get(
            row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
        ),
        title=row["title"],
        work_summary=row["work_summary"],
        next_plan=row["next_plan"],
        special_notes=row["special_notes"],
        department=SimpleNamespace(name=row["department_name"]),
        author=SimpleNamespace(name=row["author_name"]),
    )


def _minimal_fallback_html(row):
    title = escape(row["title"] or "업무일지")
    document_label = escape(
        core_app.JOURNAL_DOCUMENT_TYPES.get(
            row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
        )
    )
    work_date = escape(str(row["work_date"]))
    department = escape(row["department_name"] or "-")
    author = escape(row["author_name"] or "-")
    summary = escape(row["work_summary"] or "작성된 내용이 없습니다.")
    next_plan = escape(row["next_plan"] or "작성된 내용이 없습니다.")
    notes = escape(row["special_notes"] or "-")
    return f"""
    <div class="meeting-preview-shell">
      <div class="meeting-preview-head no-print">
        <div><span class="journal-document-badge">{document_label}</span><strong>{title}</strong><small>{work_date} · {department} · {author}</small></div>
        <button type="button" data-close aria-label="상세 창 닫기">×</button>
      </div>
      <article class="print-sheet journal-sheet journal-document">
        <header><span>MEDPARK</span><h1>{title}</h1><div><b>문서구분</b> {document_label} <b>작성일</b> {work_date} <b>부서(팀)</b> {department} <b>작성자</b> {author}</div></header>
        <section class="journal-document-section"><h2>금일 진행 내용</h2><div class="meeting-written-content">{summary}</div></section>
        <section class="journal-document-section"><h2>익일·향후 계획</h2><div class="meeting-written-content">{next_plan}</div></section>
        <section class="journal-document-section"><h2>특이사항</h2><div class="meeting-written-content">{notes}</div></section>
      </article>
    </div>
    """


@app.get("/document-control/journals/<int:journal_id>/preview")
@login_required
def journal_preview_direct(journal_id):
    """Stable administrator preview endpoint using the exact DB document id.

    This path deliberately avoids every /journals after-request extension. It must
    return a readable document for any administrator-visible row in the board.
    """
    if not _is_admin(current_user):
        abort(403)

    try:
        row = _load_journal_header(journal_id)
    except Exception:
        core_app.db.session.rollback()
        raise
    if not row:
        abort(404)

    try:
        task_rows = _load_task_rows(row)
        return render_template(
            "journal_preview_admin_safe.html",
            journal=_journal_namespace(row),
            task_rows=task_rows,
            today=date.today(),
        ), 200, {"X-MedPark-Journal-Preview": "direct-template-id"}
    except Exception:
        core_app.db.session.rollback()
        return _minimal_fallback_html(row), 200, {
            "X-MedPark-Journal-Preview": "direct-minimal-fallback"
        }
