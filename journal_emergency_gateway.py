import json
from urllib.parse import parse_qs

from flask import Response, redirect, request
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from markupsafe import escape
from sqlalchemy import text

import journal_board_stable_manager as stable_manager
import app as core_app

flask_app = stable_manager.app


def _role_info():
    role_id = getattr(current_user, "role_id", None)
    if not role_id:
        return "", {}, False
    row = core_app.db.session.execute(
        text("SELECT name, permissions FROM roles WHERE id = :role_id"),
        {"role_id": int(role_id)},
    ).mappings().first()
    if not row:
        return "", {}, False
    role_name = str(row["name"] or "").strip()
    permissions = row["permissions"] or {}
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except Exception:
            permissions = {}
    if not isinstance(permissions, dict):
        permissions = {}
    is_admin = (
        role_name in {"관리자", "시스템관리자"}
        or "관리자" in role_name
        or bool(permissions.get("admin"))
        or bool(permissions.get("task_manage_all"))
    )
    return role_name, permissions, is_admin


def _viewer_context():
    role_name, permissions, is_admin = _role_info()
    return {
        "id": int(current_user.id),
        "department_id": int(current_user.department_id) if current_user.department_id else None,
        "role_name": role_name,
        "permissions": permissions,
        "is_admin": is_admin,
    }


def _visibility_sql(viewer, alias="j"):
    if viewer["is_admin"]:
        return "1=1", {}
    if viewer["role_name"] in {"팀장", "부서장"} and viewer["department_id"]:
        return (
            f"({alias}.document_type = 'major' OR {alias}.author_id = :viewer_id "
            f"OR ({alias}.document_type = 'daily' AND {alias}.department_id = :viewer_department_id))",
            {
                "viewer_id": viewer["id"],
                "viewer_department_id": viewer["department_id"],
            },
        )
    return (
        f"({alias}.document_type = 'major' OR {alias}.author_id = :viewer_id)",
        {"viewer_id": viewer["id"]},
    )


def _load_journals(viewer, selected_type=None):
    visibility, params = _visibility_sql(viewer)
    conditions = [visibility]
    if selected_type in core_app.JOURNAL_DOCUMENT_TYPES:
        conditions.append("j.document_type = :document_type")
        params["document_type"] = selected_type
    return core_app.db.session.execute(
        text(
            f"""
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
            WHERE {' AND '.join(conditions)}
            ORDER BY j.work_date DESC, j.created_at DESC, j.id DESC
            """
        ),
        params,
    ).mappings().all()


def _load_detail(viewer, journal_id):
    visibility, params = _visibility_sql(viewer)
    params["journal_id"] = int(journal_id)
    journal = core_app.db.session.execute(
        text(
            f"""
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
            WHERE j.id = :journal_id AND {visibility}
            """
        ),
        params,
    ).mappings().first()
    if not journal:
        return None, []

    tasks = core_app.db.session.execute(
        text(
            """
            SELECT
                t.id,
                t.title,
                COALESCE(dtc.content, t.content, '') AS document_content,
                t.target_date,
                t.progress,
                t.status,
                COALESCE(e.name, '-') AS assignee_name
            FROM work_journal_document_items AS link
            JOIN tasks AS t ON t.id = link.task_id
            LEFT JOIN employees AS e ON e.id = t.assignee_id
            LEFT JOIN document_task_contents AS dtc
              ON dtc.document_kind = 'journal'
             AND dtc.document_id = link.journal_id
             AND dtc.task_id = link.task_id
            WHERE link.journal_id = :journal_id
            ORDER BY t.target_date, t.id
            """
        ),
        {"journal_id": int(journal_id)},
    ).mappings().all()

    result = []
    for task in tasks:
        logs = []
        if journal["document_type"] == "daily":
            try:
                logs = core_app.db.session.execute(
                    text(
                        """
                        SELECT content
                        FROM task_daily_logs
                        WHERE task_id = :task_id
                          AND work_date = :work_date
                          AND author_id = :author_id
                        ORDER BY created_at, id
                        """
                    ),
                    {
                        "task_id": task["id"],
                        "work_date": journal["work_date"],
                        "author_id": journal["author_id"],
                    },
                ).mappings().all()
            except Exception:
                core_app.db.session.rollback()
                logs = []
        result.append((task, logs))
    return journal, result


def _csrf():
    try:
        return str(generate_csrf())
    except Exception:
        return ""


def _e(value):
    return str(escape("" if value is None else str(value)))


def _base_css():
    return """
    body{font-family:Arial,'Noto Sans KR',sans-serif;background:#f5f7fb;color:#17233c;margin:0}
    .shell{max-width:1220px;margin:0 auto;padding:28px 20px 60px}.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:20px}
    h1{margin:4px 0 6px;font-size:34px}.eyebrow{font-size:12px;font-weight:800;letter-spacing:2px;color:#2463d4}.muted{color:#6f7d93;font-size:14px}
    .actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.btn{display:inline-flex;align-items:center;justify-content:center;border:1px solid #d5ddea;border-radius:9px;padding:9px 13px;background:#fff;color:#1d4fb4;text-decoration:none;font-weight:700;cursor:pointer}.btn.primary{background:#1764da;color:white;border-color:#1764da}.btn.danger{color:#c43d3d;border-color:#efcaca;background:#fff8f8}
    .tabs{display:flex;gap:4px;margin:16px 0}.tabs a{padding:9px 16px;text-decoration:none;color:#4c5f78;border-radius:8px}.tabs a.active{background:#fff;color:#1764da;font-weight:800;box-shadow:0 1px 4px #dce3ee}
    .panel{background:white;border:1px solid #dde4ef;border-radius:16px;overflow:hidden}.panel-head{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid #e3e9f2;gap:12px}.panel-head h2{margin:0 0 4px;font-size:20px}
    .table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:920px}th,td{padding:12px 10px;border-bottom:1px solid #e7ebf2;text-align:left;font-size:13px;vertical-align:top}th{background:#f8f9fc;color:#5c6c82;white-space:nowrap}.title-link{font-weight:800;color:#12233f;text-decoration:none}.title-link small{display:block;color:#1764da;font-weight:500;margin-top:5px}
    .badge{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef4ff;color:#1764da;font-weight:800;font-size:12px}.detail{margin-top:18px;background:#fff;border:1px solid #dce4ef;border-radius:16px;padding:22px}.detail h2{margin-top:0}.meta{display:flex;gap:14px;flex-wrap:wrap;color:#68788f;font-size:13px}.section{margin-top:20px}.section h3{font-size:16px;margin:0 0 8px}.pre{white-space:pre-wrap;line-height:1.6;background:#f8fafc;border-radius:10px;padding:12px}.task-content{white-space:pre-wrap;color:#52647d;margin-top:6px}.notice{background:#fff7df;border:1px solid #f0d896;border-radius:12px;padding:14px;margin-bottom:16px}.error{background:#fff0f0;border:1px solid #efb9b9;color:#a62d2d;border-radius:12px;padding:14px}
    @media(max-width:760px){.top{flex-direction:column}.shell{padding:18px 10px}h1{font-size:28px}}
    """


def _render_board(viewer, selected_type=None, open_id=None, error_message=None):
    rows = _load_journals(viewer, selected_type)
    csrf = _csrf()
    admin = viewer["is_admin"]

    row_html = []
    for index, row in enumerate(rows, 1):
        jid = int(row["id"])
        select_cell = (
            f"<td><input type='checkbox' name='document_ids' value='{jid}' form='bulk-delete'></td>"
            if admin else ""
        )
        manage_cell = ""
        if admin:
            manage_cell = (
                f"<td><form method='post' action='/__safe-journal-delete/{jid}' onsubmit=\"return confirm('이 업무일지를 삭제하시겠습니까?');\">"
                f"<input type='hidden' name='csrf_token' value='{_e(csrf)}'><button class='btn danger' type='submit'>삭제</button></form></td>"
            )
        created = row["created_at"].strftime("%Y-%m-%d") if row["created_at"] else "-"
        row_html.append(
            f"<tr>{select_cell}<td>{index}</td><td><span class='badge'>{_e(core_app.JOURNAL_DOCUMENT_TYPES.get(row['document_type'], '일일업무 일지'))}</span></td>"
            f"<td>{_e(row['work_date'])}</td><td><a class='title-link' href='/journals?open={jid}'>{_e(row['title'])}<small>상세보기</small></a></td>"
            f"<td>{_e(row['department_name'])}</td><td>{_e(row['author_name'])}</td><td>{int(row['task_count'] or 0)}건</td><td>{_e(created)}</td>{manage_cell}</tr>"
        )

    selected_query = "" if not selected_type else f"?document_type={_e(selected_type)}"
    bulk = ""
    select_head = ""
    manage_head = ""
    if admin:
        select_head = "<th>선택</th>"
        manage_head = "<th>관리</th>"
        bulk = (
            "<form id='bulk-delete' method='post' action='/__safe-journal-delete-bulk' onsubmit=\"return confirm('선택한 업무일지를 삭제하시겠습니까?');\">"
            f"<input type='hidden' name='csrf_token' value='{_e(csrf)}'><button class='btn danger' type='submit'>선택 문서 삭제</button></form>"
        )

    detail_html = ""
    if open_id:
        journal, task_rows = _load_detail(viewer, open_id)
        if journal:
            task_html = []
            for idx, (task, logs) in enumerate(task_rows, 1):
                log_html = "<br>".join(_e(log["content"]) for log in logs) if logs else "-"
                task_html.append(
                    f"<tr><td>{idx}</td><td><strong>{_e(task['title'])}</strong><div class='task-content'>{_e(task['document_content'])}</div></td>"
                    f"<td>{_e(task['assignee_name'])}</td><td>{_e(task['target_date'])}</td><td>{int(task['progress'] or 0)}%</td><td>{_e(task['status'])}</td>"
                    + (f"<td>{log_html}</td>" if journal["document_type"] == "daily" else "")
                    + "</tr>"
                )
            extra_head = "<th>업무별 진행 기록</th>" if journal["document_type"] == "daily" else ""
            colspan = 7 if journal["document_type"] == "daily" else 6
            detail_html = f"""
            <section class='detail'>
              <div class='actions' style='justify-content:space-between'><div><span class='badge'>{_e(core_app.JOURNAL_DOCUMENT_TYPES.get(journal['document_type'], '일일업무 일지'))}</span><h2>{_e(journal['title'])}</h2></div><a class='btn' href='/journals{selected_query}'>닫기</a></div>
              <div class='meta'><span>작성일 {_e(journal['work_date'])}</span><span>부서(팀) {_e(journal['department_name'])}</span><span>작성자 {_e(journal['author_name'])}</span></div>
              <div class='section'><h3>1. {'주요 업무 현황' if journal['document_type']=='major' else '일일업무 현황'}</h3><div class='table-wrap'><table><thead><tr><th>No.</th><th>업무명/내용</th><th>담당자</th><th>목표일</th><th>진행률</th><th>상태</th>{extra_head}</tr></thead><tbody>{''.join(task_html) if task_html else f'<tr><td colspan={colspan}>추가된 업무가 없습니다.</td></tr>'}</tbody></table></div></div>
              <div class='section'><h3>2. {'주요 업무 진행 요약' if journal['document_type']=='major' else '금일 진행 내용'}</h3><div class='pre'>{_e(journal['work_summary'] or '작성된 내용이 없습니다.')}</div></div>
              <div class='section'><h3>3. {'향후 추진 계획' if journal['document_type']=='major' else '익일·향후 계획'}</h3><div class='pre'>{_e(journal['next_plan'] or '작성된 내용이 없습니다.')}</div></div>
              <div class='section'><h3>4. 특이사항</h3><div class='pre'>{_e(journal['special_notes'] or '-')}</div></div>
            </section>"""
        else:
            detail_html = "<div class='error'>해당 업무일지를 열람할 수 없거나 문서가 없습니다.</div>"

    error_html = f"<div class='error'>{_e(error_message)}</div>" if error_message else ""
    empty_colspan = 10 if admin else 8
    html = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>업무일지 게시판</title><style>{_base_css()}</style></head><body><main class='shell'>
    <div class='top'><div><span class='eyebrow'>WORK JOURNAL · SAFE MODE</span><h1>업무일지 게시판</h1><div class='muted'>업무일지 조회·상세·관리 기능을 안전 경로로 제공하고 있습니다.</div></div><div class='actions'><a class='btn' href='/'>통합현황</a><a class='btn' href='/tasks'>각 부서(팀) 업무 현황</a><a class='btn primary' href='/journals?legacy=1'>업무일지 작성</a></div></div>
    {error_html}
    <nav class='tabs'><a class={'active' if not selected_type else ''} href='/journals'>전체</a><a class={'active' if selected_type=='major' else ''} href='/journals?document_type=major'>주요 업무</a><a class={'active' if selected_type=='daily' else ''} href='/journals?document_type=daily'>일일업무 일지</a></nav>
    <section class='panel'><div class='panel-head'><div><h2>저장된 업무일지</h2><div class='muted'>{len(rows)}건</div></div><div class='actions'>{bulk}</div></div><div class='table-wrap'><table><thead><tr>{select_head}<th>No.</th><th>문서구분</th><th>작성일</th><th>제목</th><th>부서(팀)</th><th>작성자</th><th>업무</th><th>등록일</th>{manage_head}</tr></thead><tbody>{''.join(row_html) if row_html else f'<tr><td colspan={empty_colspan}>저장된 업무일지가 없습니다.</td></tr>'}</tbody></table></div></section>{detail_html}
    </main></body></html>"""
    return Response(html, status=200, mimetype="text/html")


@flask_app.get("/__safe-journal-board")
@login_required
def safe_journal_board():
    selected_type = str(request.args.get("document_type") or "").strip()
    if selected_type not in core_app.JOURNAL_DOCUMENT_TYPES:
        selected_type = None
    open_id = request.args.get("open", type=int)
    try:
        viewer = _viewer_context()
        return _render_board(viewer, selected_type, open_id)
    except Exception as exc:
        core_app.db.session.rollback()
        # Never return the generic Flask 500 page for the emergency journal board.
        try:
            viewer = _viewer_context()
            return _render_board(viewer, selected_type, None, type(exc).__name__)
        except Exception:
            core_app.db.session.rollback()
            return Response(
                "<!doctype html><meta charset='utf-8'><title>업무일지</title><h1>업무일지 안전 모드</h1><p>업무일지 조회 중 오류가 발생했습니다. 통합현황은 정상 이용할 수 있습니다.</p><p><a href='/'>통합현황으로 이동</a></p>",
                status=200,
                mimetype="text/html",
            )


def _admin_required_safe():
    viewer = _viewer_context()
    if not viewer["is_admin"]:
        return None
    return viewer


@flask_app.post("/__safe-journal-delete/<int:journal_id>")
@login_required
def safe_journal_delete(journal_id):
    viewer = _admin_required_safe()
    if viewer is None:
        return Response("Forbidden", status=403)
    row = core_app.db.session.execute(
        text("SELECT id, title, document_type, author_id FROM work_journal_documents WHERE id = :journal_id"),
        {"journal_id": journal_id},
    ).mappings().first()
    if not row:
        return redirect("/journals")
    task_ids = core_app.db.session.execute(
        text("SELECT task_id FROM work_journal_document_items WHERE journal_id = :journal_id"),
        {"journal_id": journal_id},
    ).scalars().all()
    core_app.db.session.execute(
        text("DELETE FROM document_task_contents WHERE document_kind = 'journal' AND document_id = :journal_id"),
        {"journal_id": journal_id},
    )
    core_app.db.session.execute(
        text("DELETE FROM work_journal_documents WHERE id = :journal_id"),
        {"journal_id": journal_id},
    )
    core_app.audit(
        "WORK_JOURNAL_DOCUMENT_DELETE",
        f"journal:{journal_id}",
        {
            "journal_id": journal_id,
            "document_type": row["document_type"],
            "title": row["title"],
            "author_id": row["author_id"],
            "related_task_ids": list(task_ids),
            "original_tasks_preserved": True,
            "delete_mode": "safe_gateway",
        },
    )
    core_app.db.session.commit()
    return redirect("/journals")


@flask_app.post("/__safe-journal-delete-bulk")
@login_required
def safe_journal_delete_bulk():
    viewer = _admin_required_safe()
    if viewer is None:
        return Response("Forbidden", status=403)
    ids = []
    seen = set()
    for raw in request.form.getlist("document_ids"):
        try:
            journal_id = int(raw)
        except Exception:
            continue
        if journal_id > 0 and journal_id not in seen:
            seen.add(journal_id)
            ids.append(journal_id)
        if len(ids) >= 500:
            break
    for journal_id in ids:
        row = core_app.db.session.execute(
            text("SELECT id, title, document_type, author_id FROM work_journal_documents WHERE id = :journal_id"),
            {"journal_id": journal_id},
        ).mappings().first()
        if not row:
            continue
        task_ids = core_app.db.session.execute(
            text("SELECT task_id FROM work_journal_document_items WHERE journal_id = :journal_id"),
            {"journal_id": journal_id},
        ).scalars().all()
        core_app.db.session.execute(
            text("DELETE FROM document_task_contents WHERE document_kind = 'journal' AND document_id = :journal_id"),
            {"journal_id": journal_id},
        )
        core_app.db.session.execute(
            text("DELETE FROM work_journal_documents WHERE id = :journal_id"),
            {"journal_id": journal_id},
        )
        core_app.audit(
            "WORK_JOURNAL_DOCUMENT_DELETE",
            f"journal:{journal_id}",
            {
                "journal_id": journal_id,
                "document_type": row["document_type"],
                "title": row["title"],
                "author_id": row["author_id"],
                "related_task_ids": list(task_ids),
                "original_tasks_preserved": True,
                "delete_mode": "safe_gateway_bulk",
            },
        )
    core_app.db.session.commit()
    return redirect("/journals")


class JournalPathGateway:
    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        if environ.get("REQUEST_METHOD") == "GET" and environ.get("PATH_INFO") == "/journals":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            if query.get("legacy") != ["1"]:
                environ = environ.copy()
                environ["ORIGINAL_PATH_INFO"] = "/journals"
                environ["PATH_INFO"] = "/__safe-journal-board"
        return self.downstream(environ, start_response)


# Wrap the Flask WSGI app itself so browser GET /journals never reaches the legacy route.
flask_app.wsgi_app = JournalPathGateway(flask_app.wsgi_app)
app = flask_app
