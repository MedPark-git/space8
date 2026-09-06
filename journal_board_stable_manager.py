from datetime import date
from functools import wraps

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


def _is_admin():
    return preview_manager._is_admin(current_user)


def _load_admin_journals(selected_type=None):
    where_clause = ""
    params = {}
    if selected_type in core_app.JOURNAL_DOCUMENT_TYPES:
        where_clause = "WHERE j.document_type = :document_type"
        params["document_type"] = selected_type

    return core_app.db.session.execute(
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


def _stable_context(selected_type=None):
    rows = _load_admin_journals(selected_type)
    journals = []
    for row in rows:
        journals.append(
            {
                "id": row["id"],
                "work_date": row["work_date"],
                "document_type": row["document_type"],
                "document_label": core_app.JOURNAL_DOCUMENT_TYPES.get(
                    row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
                ),
                "title": row["title"],
                "department_name": row["department_name"],
                "author_name": row["author_name"],
                "task_count": int(row["task_count"] or 0),
                "created_at": row["created_at"],
            }
        )
    return {
        "journals": journals,
        "selected_type": selected_type,
        "today": date.today(),
        # Per user requirement, related-work selection starts empty.
        "major_tasks": [],
        "daily_tasks": [],
        "default_major_task_ids": set(),
        "default_daily_task_ids": set(),
        "show_create_dialog": False,
        "TASK_STATUSES": core_app.TASK_STATUSES,
    }


def _fallback_board(selected_type=None):
    try:
        rows = _load_admin_journals(selected_type)
    except Exception:
        core_app.db.session.rollback()
        rows = []

    try:
        csrf = str(generate_csrf())
    except Exception:
        csrf = ""

    body_rows = []
    for index, row in enumerate(rows, start=1):
        journal_id = int(row["id"])
        title = escape(row["title"] or "업무일지")
        document_label = escape(
            core_app.JOURNAL_DOCUMENT_TYPES.get(
                row["document_type"], core_app.JOURNAL_DOCUMENT_TYPES["daily"]
            )
        )
        department = escape(row["department_name"] or "-")
        author = escape(row["author_name"] or "-")
        created = row["created_at"].strftime("%Y-%m-%d") if row["created_at"] else "-"
        body_rows.append(
            f"""
            <tr>
              <td><input type='checkbox' name='document_ids' value='{journal_id}' form='bulk-delete'></td>
              <td>{index}</td><td>{document_label}</td><td>{escape(str(row['work_date']))}</td>
              <td><a href='/journals/{journal_id}'>{title}</a></td><td>{department}</td><td>{author}</td>
              <td>{int(row['task_count'] or 0)}건</td><td>{created}</td>
              <td><form method='post' action='/document-control/journals/{journal_id}/delete'>
                <input type='hidden' name='csrf_token' value='{escape(csrf)}'>
                <button type='submit'>삭제</button></form></td>
            </tr>
            """
        )

    html = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>업무일지 게시판</title><style>body{{font-family:Arial,sans-serif;margin:24px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:8px}}a{{color:#1559c9}}button{{padding:6px 10px}}</style></head><body>
    <h1>업무일지 게시판</h1><p><a href='/'>통합현황</a> · <a href='/tasks'>각 부서(팀) 업무 현황</a></p>
    <form id='bulk-delete' method='post' action='/document-control/journals/bulk-delete'>
      <input type='hidden' name='csrf_token' value='{escape(csrf)}'><button type='submit'>선택 문서 삭제</button>
    </form>
    <table><thead><tr><th>선택</th><th>No.</th><th>문서구분</th><th>작성일</th><th>제목</th><th>부서(팀)</th><th>작성자</th><th>업무</th><th>등록일</th><th>관리</th></tr></thead>
    <tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="10">저장된 업무일지가 없습니다.</td></tr>'}</tbody></table></body></html>"""
    return Response(html, status=200, mimetype="text/html")


# The administrator journal board now owns its controls directly. Legacy response-time
# injectors are unnecessary here and have previously caused authenticated-only 500s.
_SKIP_ON_ADMIN_JOURNAL_GET = {
    "apply_document_access_controls",
    "inject_document_task_content_assets",
    "inject_document_task_content_guard",
    "inject_admin_bulk_document_delete",
    "render_admin_document_delete_controls",
}


def _guard_after_request(func):
    @wraps(func)
    def guarded(response):
        if (
            request.method == "GET"
            and request.path == "/journals"
            and current_user.is_authenticated
            and _is_admin()
        ):
            return response
        return func(response)
    return guarded


_funcs = app.after_request_funcs.get(None, [])
for _index, _func in enumerate(list(_funcs)):
    if getattr(_func, "__name__", "") in _SKIP_ON_ADMIN_JOURNAL_GET:
        _funcs[_index] = _guard_after_request(_func)


@login_required
def journals_stable():
    # Preserve the existing validated write path and all non-admin behavior.
    if request.method == "POST" or not _is_admin():
        return _original_journals()

    selected_type = request.args.get("document_type", "").strip()
    if selected_type not in core_app.JOURNAL_DOCUMENT_TYPES:
        selected_type = None

    try:
        context = _stable_context(selected_type)
        return _original_render_template("journals_admin_stable.html", **context)
    except Exception:
        core_app.db.session.rollback()
        # Never let an administrator GET /journals die with HTTP 500 again.
        return _fallback_board(selected_type)


app.view_functions["journals"] = journals_stable
