from datetime import date

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


def _admin_journal_payload(journal_id):
    """Read one saved journal without ORM relationships.

    This intentionally avoids the accumulated permission/snapshot extension chain so an
    administrator can always open a saved document even if one optional relation fails.
    """
    journal_row = core_app.db.session.execute(
        text(
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
            """
        ),
        {"journal_id": journal_id},
    ).mappings().first()
    if not journal_row:
        return None, []

    task_rows_raw = core_app.db.session.execute(
        text(
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
            """
        ),
        {"journal_id": journal_id},
    ).mappings().all()

    task_ids = [row["id"] for row in task_rows_raw]
    classifications = {}
    logs = {}
    if task_ids:
        classification_rows = core_app.db.session.execute(
            text(
                """
                SELECT task_id, name
                FROM task_classifications
                WHERE task_id = ANY(:task_ids)
                ORDER BY task_id, id
                """
            ),
            {"task_ids": task_ids},
        ).mappings().all()
        for row in classification_rows:
            classifications.setdefault(row["task_id"], []).append(row["name"])

        if journal_row["document_type"] == "daily":
            log_rows = core_app.db.session.execute(
                text(
                    """
                    SELECT task_id, content
                    FROM task_daily_logs
                    WHERE task_id = ANY(:task_ids)
                      AND work_date = :work_date
                      AND author_id = :author_id
                    ORDER BY task_id, created_at, id
                    """
                ),
                {
                    "task_ids": task_ids,
                    "work_date": journal_row["work_date"],
                    "author_id": journal_row["author_id"],
                },
            ).mappings().all()
            for row in log_rows:
                logs.setdefault(row["task_id"], []).append({"content": row["content"]})

    # Snapshot contents are optional. Failure here must never block the preview.
    snapshots = {}
    if task_ids:
        try:
            snapshot_rows = core_app.db.session.execute(
                text(
                    """
                    SELECT task_id, content
                    FROM document_task_contents
                    WHERE document_kind = 'journal'
                      AND document_id = :journal_id
                      AND task_id = ANY(:task_ids)
                    """
                ),
                {"journal_id": journal_id, "task_ids": task_ids},
            ).mappings().all()
            snapshots = {row["task_id"]: row["content"] for row in snapshot_rows}
        except Exception:
            core_app.db.session.rollback()
            snapshots = {}

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
    for row in task_rows_raw:
        task_rows.append(
            {
                "id": row["id"],
                "title": row["title"],
                "content": snapshots.get(row["id"], row["content"]),
                "classification_names": classifications.get(row["id"], []),
                "assignee_name": row["assignee_name"],
                "target_date": row["target_date"],
                "progress": row["progress"],
                "status": row["status"],
                "status_class": core_app.STATUS_CLASS.get(row["status"], "progress"),
                "logs": logs.get(row["id"], []),
            }
        )
    return journal, task_rows


def _render_admin_preview(journal_id):
    try:
        journal, task_rows = _admin_journal_payload(journal_id)
    except Exception:
        core_app.db.session.rollback()
        raise
    if not journal:
        abort(404)
    return render_template(
        "journal_preview_admin_safe.html",
        journal=journal,
        task_rows=task_rows,
        today=date.today(),
    )


# Preserve the original endpoint for non-admin users, but force administrators through
# the direct-SQL renderer even when the old URL is used.
_original_journal_preview = app.view_functions.get("journal_preview")


@login_required
def journal_preview_admin_safe(journal_id):
    if _is_admin(current_user):
        return _render_admin_preview(journal_id), 200, {
            "X-MedPark-Journal-Preview": "admin-direct-sql"
        }
    if _original_journal_preview is None:
        abort(404)
    return _original_journal_preview(journal_id)


app.view_functions["journal_preview"] = journal_preview_admin_safe


@app.get("/admin-safe/journals/<int:journal_id>/preview")
@login_required
def admin_safe_journal_preview(journal_id):
    if not _is_admin(current_user):
        abort(403)
    return _render_admin_preview(journal_id), 200, {
        "X-MedPark-Journal-Preview": "admin-direct-sql-isolated"
    }
