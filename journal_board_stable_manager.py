from datetime import date
from functools import wraps
from types import SimpleNamespace

from flask import Response, request
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from markupsafe import escape
from sqlalchemy import text

import app as core_app
import journal_preview_safe_manager as preview_manager

app = preview_manager.app
_original_journals = app.view_functions.get("journals")
_original_render_template = core_app.render_template


def _is_admin_user(user=None):
    user = user or current_user
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if not role:
        return False
    role_name = str(getattr(role, "name", "") or "").strip()
    if role_name in {"관리자", "시스템관리자"} or "관리자" in role_name:
        return True
    try:
        if role.allows("admin") or role.allows("task_manage_all"):
            return True
    except Exception:
        pass
    permissions = getattr(role, "permissions", None) or {}
    return bool(permissions.get("admin") or permissions.get("task_manage_all"))


def _journal_visibility_sql():
    if _is_admin_user():
        return "", {}

    role_name = str(getattr(getattr(current_user, "role", None), "name", "") or "").strip()
    user_id = int(current_user.id)
    department_id = int(current_user.department_id)

    # Major-work documents are company-wide. Daily journals stay private:
    # author, same-department team lead/department head, and administrators.
    if role_name in {"팀장", "부서장"}:
        return (
            "(j.document_type = 'major' OR j.author_id = :viewer_id "
            "OR (j.document_type = 'daily' AND j.department_id = :viewer_department_id))",
            {"viewer_id": user_id, "viewer_department_id": department_id},
        )
    return (
        "(j.document_type = 'major' OR j.author_id = :viewer_id)",
        {"viewer_id": user_id},
    )


def _load_journals(selected_type=None):
    visibility_sql, params = _journal_visibility_sql()
    conditions = []
    if visibility_sql:
        conditions.append(visibility_sql)
    if selected_type in core_app.JOURNAL_DOCUMENT_TYPES:
        conditions.append("j.document_type = :document_type")
        params["document_type"] = selected_type
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

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


def _parse_selected_task_ids():
    values = []
    for raw in request.args.getlist("task_ids"):
        values.extend(str(raw or "").split(","))
    result = []
    seen = set()
    for value in values:
        try:
            task_id = int(value)
        except (TypeError, ValueError):
            continue
        if task_id <= 0 or task_id in seen:
            continue
        seen.add(task_id)
        result.append(task_id)
        if len(result) >= 200:
            break
    return result


def _load_selected_candidate_tasks(document_type, task_ids):
    if not task_ids:
        return []

    params = {"task_ids": task_ids}
    extra = ""
    if document_type == "daily":
        extra = " AND t.assignee_id = :viewer_id"
        params["viewer_id"] = int(current_user.id)

    try:
        rows = core_app.db.session.execute(
            text(
                f"""
                SELECT
                    t.id,
                    t.title,
                    COALESCE(t.content, '') AS content,
                    t.target_date,
                    t.progress,
                    t.status,
                    COALESCE(e.name, '-') AS assignee_name
                FROM tasks AS t
                LEFT JOIN employees AS e ON e.id = t.assignee_id
                WHERE t.deleted_at IS NULL
                  AND t.id = ANY(:task_ids)
                  {extra}
                ORDER BY t.target_date, t.id
                """
            ),
            params,
        ).mappings().all()
    except Exception:
        # psycopg/SQLAlchemy array binding can vary by runtime. Fall back to
        # per-id lookups so GET /journals never fails because of task candidates.
        core_app.db.session.rollback()
        rows = []
        for task_id in task_ids:
            task = core_app.db.session.execute(
                text(
                    """
                    SELECT t.id, t.title, COALESCE(t.content, '') AS content,
                           t.target_date, t.progress, t.status,
                           COALESCE(e.name, '-') AS assignee_name,
                           t.assignee_id
                    FROM tasks AS t
                    LEFT JOIN employees AS e ON e.id = t.assignee_id
                    WHERE t.deleted_at IS NULL AND t.id = :task_id
                    """
                ),
                {"task_id": task_id},
            ).mappings().first()
            if task and (document_type != "daily" or int(task["assignee_id"]) == int(current_user.id)):
                rows.append(task)

    return [
        SimpleNamespace(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            target_date=row["target_date"],
            progress=int(row["progress"] or 0),
            status=row["status"],
            status_class=core_app.STATUS_CLASS.get(row["status"], "progress"),
            display_assignees=row["assignee_name"],
        )
        for row in rows
    ]


def _stable_context(selected_type=None):
    selected_ids = _parse_selected_task_ids()
    return {
        "journals": _load_journals(selected_type),
        "selected_type": selected_type,
        "today": date.today(),
        "major_tasks": _load_selected_candidate_tasks("major", selected_ids),
        "daily_tasks": _load_selected_candidate_tasks("daily", selected_ids),
        "default_major_task_ids": set(selected_ids),
        "default_daily_task_ids": set(selected_ids),
        "show_create_dialog": bool(selected_ids),
        "TASK_STATUSES": core_app.TASK_STATUSES,
        "is_admin_user": _is_admin_user(),
    }


def _fallback_board(selected_type=None):
    try:
        rows = _load_journals(selected_type)
    except Exception:
        core_app.db.session.rollback()
        rows = []

    try:
        csrf = str(generate_csrf())
    except Exception:
        csrf = ""
    is_admin = _is_admin_user()

    body_rows = []
    for index, item in enumerate(rows, start=1):
        journal_id = int(item.id)
        title = escape(item.title or "업무일지")
        document_label = escape(item.document_label)
        department = escape(item.department_name or "-")
        author = escape(item.author_name or "-")
        created = item.created_at.strftime("%Y-%m-%d") if item.created_at else "-"
        select_cell = (
            f"<td><input type='checkbox' name='document_ids' value='{journal_id}' form='bulk-delete'></td>"
            if is_admin else ""
        )
        manage_cell = ""
        if is_admin:
            manage_cell = (
                f"<td><form method='post' action='/document-control/journals/{journal_id}/delete'>"
                f"<input type='hidden' name='csrf_token' value='{escape(csrf)}'>"
                "<button type='submit'>삭제</button></form></td>"
            )
        body_rows.append(
            f"<tr>{select_cell}<td>{index}</td><td>{document_label}</td>"
            f"<td>{escape(str(item.work_date))}</td><td><a href='/journals/{journal_id}'>{title}</a></td>"
            f"<td>{department}</td><td>{author}</td><td>{int(item.task_count)}건</td><td>{created}</td>{manage_cell}</tr>"
        )

    bulk = ""
    select_header = ""
    manage_header = ""
    if is_admin:
        bulk = (
            "<form id='bulk-delete' method='post' action='/document-control/journals/bulk-delete'>"
            f"<input type='hidden' name='csrf_token' value='{escape(csrf)}'><button type='submit'>선택 문서 삭제</button></form>"
        )
        select_header = "<th>선택</th>"
        manage_header = "<th>관리</th>"

    colspan = 10 if is_admin else 8
    html = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>업무일지 게시판</title><style>body{{font-family:Arial,sans-serif;margin:24px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:8px}}a{{color:#1559c9}}button{{padding:6px 10px}}</style></head><body>
    <h1>업무일지 게시판</h1><p><a href='/'>통합현황</a> · <a href='/tasks'>각 부서(팀) 업무 현황</a></p>{bulk}
    <table><thead><tr>{select_header}<th>No.</th><th>문서구분</th><th>작성일</th><th>제목</th><th>부서(팀)</th><th>작성자</th><th>업무</th><th>등록일</th>{manage_header}</tr></thead>
    <tbody>{''.join(body_rows) if body_rows else f'<tr><td colspan="{colspan}">저장된 업무일지가 없습니다.</td></tr>'}</tbody></table></body></html>"""
    return Response(html, status=200, mimetype="text/html")


def _safe_after_request(func):
    @wraps(func)
    def wrapped(response):
        if request.method == "GET" and request.path == "/journals" and current_user.is_authenticated:
            try:
                return func(response)
            except Exception:
                core_app.db.session.rollback()
                return response
        return func(response)
    return wrapped


# Any response-time enhancement on the journal list is optional. It must never
# turn a successfully rendered journal board into HTTP 500 for a logged-in user.
_funcs = app.after_request_funcs.get(None, [])
for index, func in enumerate(list(_funcs)):
    if getattr(func, "_journal_safe_wrapped", False):
        continue
    wrapped = _safe_after_request(func)
    wrapped._journal_safe_wrapped = True
    _funcs[index] = wrapped


def stable_render_template(template_name, *args, **context):
    # Validation-error renders from the legacy POST handler are redirected to the
    # same stable board template for every authenticated user.
    if template_name == "journals.html" and context.get("mode") == "list" and current_user.is_authenticated:
        try:
            stable = _stable_context(context.get("selected_type"))
            # Preserve user-entered values and flags where safe.
            stable["show_create_dialog"] = True
            return _original_render_template("journals_admin_stable.html", *args, **stable)
        except Exception:
            core_app.db.session.rollback()
            return _fallback_board(context.get("selected_type"))
    return _original_render_template(template_name, *args, **context)


core_app.render_template = stable_render_template


@login_required
def journals_stable():
    # Keep existing validated write logic. Every authenticated GET uses one stable
    # read path, so role-name differences can no longer fall back to legacy GET.
    if request.method == "POST":
        return _original_journals()

    selected_type = request.args.get("document_type", "").strip()
    if selected_type not in core_app.JOURNAL_DOCUMENT_TYPES:
        selected_type = None

    try:
        return _original_render_template("journals_admin_stable.html", **_stable_context(selected_type))
    except Exception:
        core_app.db.session.rollback()
        return _fallback_board(selected_type)


app.view_functions["journals"] = journals_stable
