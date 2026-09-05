from datetime import date
import html as html_lib

from flask import abort, render_template
from flask_login import current_user, login_required
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


def _admin_journal_payload(journal_id):
    journal_row = _one(
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
    if not journal_row:
        return None, []

    base_tasks = _all(
        """
        SELECT
            t.id,
            t.title,
            COALESCE(t.content, '') AS content,
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

    journal = {
        "id": journal_row["id"],
        "work_date": journal_row["work_date"],
        "document_type": journal_row["document_type"],
        "document_label": core_app.JOURNAL_DOCUMENT_TYPES.get(
            journal_row["document_type"],
            core_app.JOURNAL_DOCUMENT_TYPES["daily"],
        ),
        "title": journal_row["title"],
        "work_summary": journal_row["work_summary"],
        "next_plan": journal_row["next_plan"],
        "special_notes": journal_row["special_notes"],
        "department": {"name": journal_row["department_name"]},
        "author": {"name": journal_row["author_name"]},
    }

    task_rows = []
    for task in base_tasks:
        classification_names = [
            row["name"]
            for row in _all(
                """
                SELECT name
                FROM task_classifications
                WHERE task_id = :task_id
                ORDER BY id
                """,
                {"task_id": task["id"]},
            )
        ]

        task_logs = []
        if journal_row["document_type"] == "daily":
            task_logs = [
                {"content": row["content"]}
                for row in _all(
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

        content = task["content"]
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
            content = task["content"]

        task_rows.append(
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
                "logs": task_logs,
            }
        )

    return journal, task_rows


def _render_admin_preview(journal_id):
    journal, task_rows = _admin_journal_payload(journal_id)
    if not journal:
        abort(404)
    return render_template(
        "journal_preview_admin_safe.html",
        journal=journal,
        task_rows=task_rows,
        today=date.today(),
    )


def _render_minimal_admin_preview(journal_id):
    """Last-resort preview that depends only on the journal row itself.

    It intentionally avoids task links, snapshot rows and template relationships so an
    optional child-data problem can never block an administrator from opening a saved
    journal document.
    """
    row = _one(
        """
        SELECT
            j.id,
            j.work_date,
            j.document_type,
            j.title,
            j.work_summary,
            j.next_plan,
            j.special_notes,
            COALESCE(d.name, '-') AS department_name,
            COALESCE(e.name, '-') AS author_name
        FROM work_journal_documents AS j
        LEFT JOIN departments AS d ON d.id = j.department_id
        LEFT JOIN employees AS e ON e.id = j.author_id
        WHERE j.id = :journal_id
        """,
        {"journal_id": journal_id},
    )
    if not row:
        abort(404)

    label = core_app.JOURNAL_DOCUMENT_TYPES.get(
        row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
    )

    esc = lambda value: html_lib.escape(str(value or ""))
    work_summary = esc(row["work_summary"] or "작성된 내용이 없습니다.")
    next_plan = esc(row["next_plan"] or "작성된 내용이 없습니다.")
    special = esc(row["special_notes"] or "-")
    title = esc(row["title"] or label)
    department = esc(row["department_name"])
    author = esc(row["author_name"])
    work_date = esc(row["work_date"])

    return f"""
    <div class="meeting-preview-shell">
      <div class="meeting-preview-head no-print">
        <div><span class="journal-document-badge {esc(row['document_type'])}">{esc(label)}</span><strong>{title}</strong><small>{work_date} · {department} · {author}</small></div>
        <button type="button" data-close aria-label="상세 창 닫기">×</button>
      </div>
      <div class="meeting-preview-actions no-print">
        <a class="button ghost" href="/journals/{int(row['id'])}/edit">수정</a>
      </div>
      <article class="print-sheet journal-sheet journal-document {esc(row['document_type'])}">
        <header><span>MEDPARK</span><h1>{title}</h1><div><b>문서구분</b> {esc(label)} <b>작성일</b> {work_date} <b>부서(팀)</b> {department} <b>작성자</b> {author}</div></header>
        <section class="journal-document-section"><h2>1. 업무 현황</h2><div class="meeting-written-content">연결 업무 세부정보는 일시적으로 표시하지 못했지만 저장된 업무일지 본문은 정상적으로 열었습니다.</div></section>
        <section class="journal-document-section"><h2>2. 금일 진행 내용</h2><div class="meeting-written-content">{work_summary}</div></section>
        <section class="journal-document-section"><h2>3. 익일·향후 계획</h2><div class="meeting-written-content">{next_plan}</div></section>
        <section class="journal-document-section"><h2>4. 특이사항</h2><div class="meeting-written-content">{special}</div></section>
      </article>
    </div>
    """


_original_journal_preview = app.view_functions.get("journal_preview")


@login_required
def journal_preview_admin_safe(journal_id):
    if _is_admin(current_user):
        try:
            return _render_admin_preview(journal_id), 200, {
                "X-MedPark-Journal-Preview": "admin-direct-sql"
            }
        except Exception:
            core_app.db.session.rollback()
            return _render_minimal_admin_preview(journal_id), 200, {
                "X-MedPark-Journal-Preview": "admin-minimal-fallback"
            }
    if _original_journal_preview is None:
        abort(404)
    return _original_journal_preview(journal_id)


app.view_functions["journal_preview"] = journal_preview_admin_safe


# Kept only for backward compatibility with previously cached links. New frontend code
# no longer rewrites to this path.
@app.get("/admin-safe/journals/<int:journal_id>/preview")
@login_required
def admin_safe_journal_preview(journal_id):
    if not _is_admin(current_user):
        abort(403)
    try:
        return _render_admin_preview(journal_id), 200, {
            "X-MedPark-Journal-Preview": "admin-direct-sql-legacy-safe"
        }
    except Exception:
        core_app.db.session.rollback()
        return _render_minimal_admin_preview(journal_id), 200, {
            "X-MedPark-Journal-Preview": "admin-minimal-fallback-legacy-safe"
        }
