from datetime import date
from types import SimpleNamespace

from flask import render_template as flask_render_template, request
from flask_login import current_user, login_required
from sqlalchemy import text

import app as core_app
import journal_preview_safe_manager as preview_manager

app = preview_manager.app
_original_journals = app.view_functions.get("journals")
_original_render_template = core_app.render_template


def _is_admin():
    return preview_manager._is_admin(current_user)


def _load_admin_journals(selected_type=None):
    where_clause = ""
    params = {}
    if selected_type in core_app.JOURNAL_DOCUMENT_TYPES:
        where_clause = "WHERE j.document_type = :document_type"
        params["document_type"] = selected_type

    rows = core_app.db.session.execute(
        text(
            f"""
            SELECT
                j.id,
                j.work_date,
                j.document_type,
                j.title,
                j.created_at,
                COALESCE(d.name, '-') AS department_name,
                COALESCE(e.name, '-') AS author_name,
                (
                    SELECT COUNT(*)
                    FROM work_journal_document_items AS link
                    WHERE link.journal_id = j.id
                ) AS task_count
            FROM work_journal_documents AS j
            LEFT JOIN departments AS d ON d.id = j.department_id
            LEFT JOIN employees AS e ON e.id = j.author_id
            {where_clause}
            ORDER BY j.work_date DESC, j.created_at DESC, j.id DESC
            """
        ),
        params,
    ).mappings().all()

    return [
        SimpleNamespace(
            id=row["id"],
            work_date=row["work_date"],
            document_type=row["document_type"],
            document_label=core_app.JOURNAL_DOCUMENT_TYPES.get(
                row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
            ),
            title=row["title"],
            department_name=row["department_name"],
            author_name=row["author_name"],
            task_count=int(row["task_count"] or 0),
            created_at=row["created_at"],
        )
        for row in rows
    ]


def _candidate_tasks(document_type):
    try:
        tasks = core_app.journal_candidate_tasks(current_user, document_type)
        return tasks
    except Exception:
        core_app.db.session.rollback()
        return []


def _stable_context(selected_type=None):
    return {
        "journals": _load_admin_journals(selected_type),
        "selected_type": selected_type,
        "today": date.today(),
        "major_tasks": _candidate_tasks("major"),
        "daily_tasks": _candidate_tasks("daily"),
        # Related tasks must start empty. Users explicitly choose only the work
        # they want to include in the saved document.
        "default_major_task_ids": set(),
        "default_daily_task_ids": set(),
        "show_create_dialog": False,
        "TASK_STATUSES": core_app.TASK_STATUSES,
    }


def stable_render_template(template_name, *args, **context):
    """Render all administrator journal list responses with the standalone template.

    This also catches validation-error renders from the original POST handler, so an
    invalid form cannot fall back to the unstable legacy administrator board.
    """
    if template_name == "journals.html" and context.get("mode") == "list" and _is_admin():
        stable = _stable_context(context.get("selected_type"))
        stable.update({key: value for key, value in context.items() if key not in stable})
        # Preserve POST form choices supplied by the original handler while keeping
        # the standalone journal list and empty default task selection contract.
        stable["journals"] = _load_admin_journals(context.get("selected_type"))
        stable["TASK_STATUSES"] = core_app.TASK_STATUSES
        return _original_render_template("journals_admin_stable.html", *args, **stable)
    return _original_render_template(template_name, *args, **context)


core_app.render_template = stable_render_template


@login_required
def journals_stable():
    # Keep the existing, validated write path. Only GET is isolated.
    if request.method == "POST" or not _is_admin():
        return _original_journals()

    selected_type = request.args.get("document_type", "").strip()
    if selected_type not in core_app.JOURNAL_DOCUMENT_TYPES:
        selected_type = None

    try:
        context = _stable_context(selected_type)
    except Exception:
        core_app.db.session.rollback()
        # Even if optional task candidates fail, the saved-document board should
        # remain available to administrators.
        context = {
            "journals": _load_admin_journals(selected_type),
            "selected_type": selected_type,
            "today": date.today(),
            "major_tasks": [],
            "daily_tasks": [],
            "default_major_task_ids": set(),
            "default_daily_task_ids": set(),
            "show_create_dialog": False,
            "TASK_STATUSES": core_app.TASK_STATUSES,
        }

    return flask_render_template("journals_admin_stable.html", **context)


# The Flask rule already accepts GET/POST; replacing its endpoint function keeps the
# URL contract while isolating administrator GET requests from the legacy handler.
app.view_functions["journals"] = journals_stable
