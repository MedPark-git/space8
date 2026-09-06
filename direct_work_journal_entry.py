import hashlib
import hmac
import json
from datetime import date
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, quote

from sqlalchemy import text

import app as core_app
import work_journal_safe_entry as legacy_entry

flask_app = legacy_entry.app

JOURNAL_GET_PATHS = {
    "/journals",
    "/work-journals",
    "/work-journal",
    "/journal",
    "/journal-board",
}


def _response(start_response, body, status="200 OK", headers=None):
    if isinstance(body, str):
        body = body.encode("utf-8")
    base_headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-MedPark-Direct-Work-Journal", "1"),
    ]
    if headers:
        base_headers.extend(headers)
    start_response(status, base_headers)
    return [body]


def _redirect(start_response, location, status="302 FOUND"):
    body = (
        "<!doctype html><meta charset='utf-8'>"
        f"<meta http-equiv='refresh' content='0;url={_e(location)}'>"
        f"<a href='{_e(location)}'>이동</a>"
    )
    return _response(start_response, body, status=status, headers=[("Location", location)])


def _e(value):
    import html

    return html.escape("" if value is None else str(value), quote=True)


def _cookie_value(environ):
    raw = environ.get("HTTP_COOKIE") or ""
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return ""
    cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
    morsel = cookie.get(cookie_name)
    return morsel.value if morsel else ""


def _session_payload(environ):
    cookie_value = _cookie_value(environ)
    if not cookie_value:
        return None, ""
    serializer = flask_app.session_interface.get_signing_serializer(flask_app)
    if serializer is None:
        return None, cookie_value
    try:
        payload = serializer.loads(cookie_value)
    except Exception:
        return None, cookie_value
    return payload, cookie_value


def _viewer(environ):
    session_payload, cookie_value = _session_payload(environ)
    if not session_payload:
        return None, cookie_value
    raw_user_id = session_payload.get("_user_id")
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None, cookie_value

    row = core_app.db.session.execute(
        text(
            """
            SELECT
                e.id,
                e.name,
                e.department_id,
                e.status,
                e.approval_status,
                COALESCE(d.name, '-') AS department_name,
                r.name AS role_name,
                r.permissions
            FROM employees AS e
            JOIN roles AS r ON r.id = e.role_id
            LEFT JOIN departments AS d ON d.id = e.department_id
            WHERE e.id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row or row["status"] != "재직" or row["approval_status"] != "승인완료":
        return None, cookie_value

    permissions = row["permissions"] or {}
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except Exception:
            permissions = {}
    if not isinstance(permissions, dict):
        permissions = {}

    role_name = str(row["role_name"] or "").strip()
    is_admin = (
        role_name in {"관리자", "시스템관리자"}
        or "관리자" in role_name
        or bool(permissions.get("admin"))
        or bool(permissions.get("task_manage_all"))
    )
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "department_id": int(row["department_id"]) if row["department_id"] else None,
        "department_name": row["department_name"],
        "role_name": role_name,
        "permissions": permissions,
        "is_admin": is_admin,
    }, cookie_value


def _csrf(viewer_id, cookie_value):
    secret = str(flask_app.secret_key or "").encode("utf-8")
    message = f"work-journal:{viewer_id}:{cookie_value}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _valid_csrf(viewer, cookie_value, submitted):
    expected = _csrf(viewer["id"], cookie_value)
    return bool(submitted and hmac.compare_digest(str(submitted), expected))


def _visibility(viewer, alias="j"):
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


def _query_params(environ):
    return parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)


def _selected_type(environ):
    values = _query_params(environ).get("document_type") or []
    value = str(values[0] if values else "").strip()
    return value if value in {"major", "daily"} else None


def _open_id(environ):
    values = _query_params(environ).get("open") or []
    try:
        return int(values[0]) if values else None
    except (TypeError, ValueError):
        return None


def _compose_type(environ):
    values = _query_params(environ).get("compose") or []
    value = str(values[0] if values else "").strip()
    return value if value in {"major", "daily"} else None


def _load_journals(viewer, selected_type=None):
    visibility, params = _visibility(viewer)
    conditions = [visibility]
    if selected_type:
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
    visibility, params = _visibility(viewer)
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

    try:
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
    except Exception:
        core_app.db.session.rollback()
        tasks = core_app.db.session.execute(
            text(
                """
                SELECT
                    t.id,
                    t.title,
                    COALESCE(t.content, '') AS document_content,
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
            {"journal_id": int(journal_id)},
        ).mappings().all()
    return journal, tasks


def _candidate_tasks(viewer, document_type):
    conditions = ["t.deleted_at IS NULL"]
    params = {}
    if document_type == "daily":
        conditions.append("t.assignee_id = :viewer_id")
        params["viewer_id"] = viewer["id"]
    return core_app.db.session.execute(
        text(
            f"""
            SELECT
                t.id,
                t.title,
                t.target_date,
                t.progress,
                t.status,
                COALESCE(e.name, '-') AS assignee_name,
                COALESCE(d.name, '-') AS department_name
            FROM tasks AS t
            LEFT JOIN employees AS e ON e.id = t.assignee_id
            LEFT JOIN departments AS d ON d.id = t.department_id
            WHERE {' AND '.join(conditions)}
            ORDER BY t.target_date, t.id
            LIMIT 500
            """
        ),
        params,
    ).mappings().all()


def _render_header(viewer):
    return f"""
    <header class='topbar'>
      <a class='brand' href='/'><span class='mark'>M</span><strong>MedPark</strong></a>
      <nav>
        <a href='/'>통합현황</a><a href='/tasks'>각 부서(팀) 업무 현황</a><a href='/tasks/new'>업무등록</a>
        <a href='/calendar'>일정(캘린더)</a><a href='/meetings'>일일회의</a><a class='active' href='/work-journals'>업무일지</a><a href='/admin'>관리자</a>
      </nav>
      <div class='user'><strong>{_e(viewer['name'])}</strong><small>{_e(viewer['department_name'])} · {_e(viewer['role_name'])}</small></div>
    </header>
    """


def _styles():
    return """
    *{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#14233c;font-family:Arial,'Noto Sans KR',sans-serif}
    .topbar{height:68px;background:#fff;border-bottom:1px solid #dce3ee;display:flex;align-items:center;padding:0 18px;gap:26px;position:sticky;top:0;z-index:5}
    .brand{display:flex;gap:10px;align-items:center;color:#12213a;text-decoration:none;font-size:18px}.mark{display:inline-flex;width:38px;height:38px;border-radius:10px;background:#1f4f91;color:#fff;align-items:center;justify-content:center;font-weight:800}
    nav{display:flex;gap:6px;align-items:center;flex:1}nav a{color:#374762;text-decoration:none;font-size:13px;font-weight:700;padding:9px 10px;border-radius:8px;white-space:nowrap}nav a.active{background:#edf4ff;color:#2166dc}.user{display:flex;flex-direction:column;text-align:right;font-size:13px}.user small{color:#77859a;margin-top:3px}
    .shell{max-width:1240px;margin:0 auto;padding:28px 18px 70px}.heading{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:18px}.eyebrow{font-size:12px;font-weight:900;letter-spacing:1.7px;color:#2468d9}h1{font-size:32px;margin:5px 0}.muted{color:#718096;font-size:14px}.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .btn{border:1px solid #d4deeb;background:#fff;color:#2457a7;padding:9px 13px;border-radius:9px;text-decoration:none;font-weight:800;font-size:13px;cursor:pointer}.btn.primary{background:#2166dc;color:#fff;border-color:#2166dc}.btn.danger{color:#bd3434;background:#fff8f8;border-color:#efc9c9}
    .tabs{display:flex;gap:5px;margin:14px 0}.tabs a{padding:9px 15px;border-radius:8px;color:#4d5d74;text-decoration:none;font-weight:700}.tabs a.active{background:#fff;color:#2166dc;box-shadow:0 1px 4px #d9e1ed}
    .panel{background:#fff;border:1px solid #dce4ef;border-radius:15px;overflow:hidden}.panel-head{padding:17px 19px;border-bottom:1px solid #e4e9f1;display:flex;justify-content:space-between;align-items:center;gap:12px}.panel-head h2{margin:0 0 3px;font-size:19px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:960px}th,td{padding:11px 10px;border-bottom:1px solid #e7ebf2;text-align:left;font-size:13px;vertical-align:top}th{background:#f8f9fb;color:#5c6b81;white-space:nowrap}
    .badge{display:inline-block;background:#edf4ff;color:#2166dc;border-radius:999px;padding:5px 9px;font-weight:800}.title{font-weight:800;color:#14233c;text-decoration:none}.title small{display:block;color:#2166dc;margin-top:4px;font-weight:600}.detail,.compose{margin-top:18px;background:#fff;border:1px solid #dce4ef;border-radius:15px;padding:21px}.meta{display:flex;gap:15px;color:#6d7c91;font-size:13px;flex-wrap:wrap}.section{margin-top:20px}.section h3{font-size:16px}.pre{white-space:pre-wrap;background:#f8fafc;border-radius:9px;padding:12px;line-height:1.6}.task-content{white-space:pre-wrap;color:#53647c;margin-top:6px}
    .compose-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.compose label{display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:800}.compose input,.compose select,.compose textarea{border:1px solid #ccd6e4;border-radius:8px;padding:9px 10px;font:inherit}.compose textarea{min-height:100px}.task-list{max-height:320px;overflow:auto;border:1px solid #dce3ed;border-radius:10px;padding:8px}.task-option{display:grid;grid-template-columns:28px 1fr auto;gap:8px;padding:9px;border-bottom:1px solid #edf0f5;align-items:center}.task-option:last-child{border:0}.task-option small{color:#738096}.error{padding:13px;border:1px solid #efbcbc;background:#fff1f1;color:#a62d2d;border-radius:10px;margin-bottom:12px}
    @media(max-width:900px){.topbar nav{display:none}.compose-grid{grid-template-columns:1fr}.heading{flex-direction:column}}
    @media print{.topbar,.no-print{display:none!important}.shell{max-width:none;padding:0}.detail{border:0}}
    """


def _render_board(viewer, cookie_value, environ, message=None):
    selected_type = _selected_type(environ)
    open_id = _open_id(environ)
    compose_type = _compose_type(environ)
    rows = _load_journals(viewer, selected_type)
    csrf = _csrf(viewer["id"], cookie_value)

    row_html = []
    for index, row in enumerate(rows, 1):
        jid = int(row["id"])
        select_cell = f"<td><input type='checkbox' name='document_ids' value='{jid}' form='bulk-delete'></td>" if viewer["is_admin"] else ""
        manage_cell = ""
        if viewer["is_admin"]:
            manage_cell = (
                f"<td><form method='post' action='/work-journals/delete/{jid}' onsubmit=\"return confirm('이 업무일지를 삭제하시겠습니까?');\">"
                f"<input type='hidden' name='_journal_csrf' value='{_e(csrf)}'><button class='btn danger' type='submit'>삭제</button></form></td>"
            )
        created = row["created_at"].strftime("%Y-%m-%d") if row["created_at"] else "-"
        label = "주요 업무" if row["document_type"] == "major" else "일일업무 일지"
        row_html.append(
            f"<tr>{select_cell}<td>{index}</td><td><span class='badge'>{label}</span></td><td>{_e(row['work_date'])}</td>"
            f"<td><a class='title' href='/work-journals?open={jid}'>{_e(row['title'])}<small>상세보기</small></a></td>"
            f"<td>{_e(row['department_name'])}</td><td>{_e(row['author_name'])}</td><td>{int(row['task_count'] or 0)}건</td><td>{_e(created)}</td>{manage_cell}</tr>"
        )

    bulk = ""
    select_head = manage_head = ""
    if viewer["is_admin"]:
        select_head = "<th>선택</th>"
        manage_head = "<th>관리</th>"
        bulk = (
            "<form id='bulk-delete' method='post' action='/work-journals/delete-bulk' onsubmit=\"return confirm('선택한 업무일지를 삭제하시겠습니까?');\">"
            f"<input type='hidden' name='_journal_csrf' value='{_e(csrf)}'><button class='btn danger' type='submit'>선택 문서 삭제</button></form>"
        )

    detail_html = ""
    if open_id:
        journal, tasks = _load_detail(viewer, open_id)
        if journal:
            task_rows = []
            for idx, task in enumerate(tasks, 1):
                task_rows.append(
                    f"<tr><td>{idx}</td><td><strong>{_e(task['title'])}</strong><div class='task-content'>{_e(task['document_content'])}</div></td>"
                    f"<td>{_e(task['assignee_name'])}</td><td>{_e(task['target_date'])}</td><td>{int(task['progress'] or 0)}%</td><td>{_e(task['status'])}</td></tr>"
                )
            label = "주요 업무" if journal["document_type"] == "major" else "일일업무 일지"
            detail_html = f"""
            <section class='detail'>
              <div class='actions no-print' style='justify-content:space-between'><div><span class='badge'>{label}</span><h2>{_e(journal['title'])}</h2></div><div class='actions'><button class='btn primary' onclick='window.print()'>인쇄</button><a class='btn' href='/work-journals'>닫기</a></div></div>
              <div class='meta'><span>작성일 {_e(journal['work_date'])}</span><span>부서(팀) {_e(journal['department_name'])}</span><span>작성자 {_e(journal['author_name'])}</span></div>
              <div class='section'><h3>1. {label} 현황</h3><div class='table-wrap'><table><thead><tr><th>No.</th><th>업무명/내용</th><th>담당자</th><th>목표일</th><th>진행률</th><th>상태</th></tr></thead><tbody>{''.join(task_rows) if task_rows else '<tr><td colspan=6>추가된 업무가 없습니다.</td></tr>'}</tbody></table></div></div>
              <div class='section'><h3>2. {'주요 업무 진행 요약' if journal['document_type']=='major' else '금일 진행 내용'}</h3><div class='pre'>{_e(journal['work_summary'] or '작성된 내용이 없습니다.')}</div></div>
              <div class='section'><h3>3. {'향후 추진 계획' if journal['document_type']=='major' else '익일·향후 계획'}</h3><div class='pre'>{_e(journal['next_plan'] or '작성된 내용이 없습니다.')}</div></div>
              <div class='section'><h3>4. 특이사항</h3><div class='pre'>{_e(journal['special_notes'] or '-')}</div></div>
            </section>"""
        else:
            detail_html = "<div class='error'>열람할 수 없거나 존재하지 않는 업무일지입니다.</div>"

    compose_html = ""
    if compose_type:
        candidates = _candidate_tasks(viewer, compose_type)
        options = []
        for task in candidates:
            options.append(
                f"<label class='task-option'><input type='checkbox' name='task_ids' value='{int(task['id'])}'>"
                f"<span><strong>{_e(task['title'])}</strong><small>{_e(task['department_name'])} · {_e(task['assignee_name'])} · 목표 {_e(task['target_date'])}</small></span>"
                f"<span>{_e(task['status'])} · {int(task['progress'] or 0)}%</span></label>"
            )
        label = "주요 업무" if compose_type == "major" else "일일업무 일지"
        compose_html = f"""
        <section class='compose'>
          <div class='actions' style='justify-content:space-between'><div><span class='badge'>{label}</span><h2>{label} 작성</h2></div><a class='btn' href='/work-journals'>취소</a></div>
          <form method='post' action='/work-journals/create'>
            <input type='hidden' name='_journal_csrf' value='{_e(csrf)}'><input type='hidden' name='document_type' value='{compose_type}'>
            <div class='compose-grid'><label>작성일<input type='date' name='work_date' value='{date.today().isoformat()}' required></label><label>문서 제목<input name='title' maxlength='200' placeholder='미입력 시 자동 생성'></label></div>
            <div class='section'><h3>관련 업무 추가 <span class='muted'>기본 미선택</span></h3><div class='task-list'>{''.join(options) if options else '<div class="muted">추가할 수 있는 등록 업무가 없습니다.</div>'}</div></div>
            <div class='compose-grid section'><label>{'주요 업무 진행 요약' if compose_type=='major' else '금일 진행 내용'}<textarea name='work_summary'></textarea></label><label>{'향후 추진 계획' if compose_type=='major' else '익일·향후 계획'}<textarea name='next_plan'></textarea></label></div>
            <label class='section'>특이사항<textarea name='special_notes'></textarea></label>
            <div class='actions section'><button class='btn primary' type='submit'>저장하고 게시판에서 보기</button></div>
          </form>
        </section>"""

    col_count = 10 if viewer["is_admin"] else 8
    message_html = f"<div class='error'>{_e(message)}</div>" if message else ""
    html = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>업무일지 게시판</title><style>{_styles()}</style></head><body>
    {_render_header(viewer)}<main class='shell'>{message_html}
    <div class='heading'><div><span class='eyebrow'>WORK JOURNAL</span><h1>업무일지 게시판</h1><div class='muted'>주요 업무와 일일업무 일지를 조회·작성합니다.</div></div><div class='actions'><a class='btn' href='/work-journals?compose=major'>주요 업무 작성</a><a class='btn primary' href='/work-journals?compose=daily'>일일업무 일지 작성</a></div></div>
    <div class='tabs'><a class={'active' if not selected_type else ''} href='/work-journals'>전체</a><a class={'active' if selected_type=='major' else ''} href='/work-journals?document_type=major'>주요 업무</a><a class={'active' if selected_type=='daily' else ''} href='/work-journals?document_type=daily'>일일업무 일지</a></div>
    <section class='panel'><div class='panel-head'><div><h2>저장된 업무일지</h2><div class='muted'>{len(rows)}건</div></div>{bulk}</div><div class='table-wrap'><table><thead><tr>{select_head}<th>No.</th><th>문서구분</th><th>작성일</th><th>제목</th><th>부서(팀)</th><th>작성자</th><th>업무</th><th>등록일</th>{manage_head}</tr></thead><tbody>{''.join(row_html) if row_html else f'<tr><td colspan={col_count}>저장된 업무일지가 없습니다.</td></tr>'}</tbody></table></div></section>{detail_html}{compose_html}</main></body></html>"""
    return html


def _read_form(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    raw = environ["wsgi.input"].read(max(0, min(length, 2_000_000))) if length else b""
    return parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)


def _one(form, key, default=""):
    values = form.get(key) or []
    return str(values[0]) if values else default


def _audit(environ, user_id, action, target, details):
    try:
        core_app.db.session.execute(
            text(
                """
                INSERT INTO audit_logs (user_id, action, target, details, ip_address, created_at)
                VALUES (:user_id, :action, :target, CAST(:details AS jsonb), :ip_address, NOW())
                """
            ),
            {
                "user_id": user_id,
                "action": action,
                "target": target,
                "details": json.dumps(details, ensure_ascii=False),
                "ip_address": environ.get("HTTP_X_FORWARDED_FOR") or environ.get("REMOTE_ADDR"),
            },
        )
    except Exception:
        core_app.db.session.rollback()


def _create(environ, start_response, viewer, cookie_value):
    form = _read_form(environ)
    if not _valid_csrf(viewer, cookie_value, _one(form, "_journal_csrf")):
        return _response(start_response, "<h1>요청 검증에 실패했습니다.</h1>", status="403 FORBIDDEN")
    document_type = _one(form, "document_type")
    if document_type not in {"major", "daily"}:
        return _redirect(start_response, "/work-journals")
    try:
        work_date = date.fromisoformat(_one(form, "work_date"))
    except Exception:
        return _redirect(start_response, f"/work-journals?compose={document_type}")
    title = _one(form, "title").strip()[:200]
    label = "주요 업무" if document_type == "major" else "일일업무 일지"
    if not title:
        title = f"{work_date.isoformat()} {label} - {viewer['name']}"
    summary = _one(form, "work_summary")[:30000]
    next_plan = _one(form, "next_plan")[:30000]
    notes = _one(form, "special_notes")[:30000]

    selected_ids = []
    for raw in form.get("task_ids") or []:
        try:
            task_id = int(raw)
        except (TypeError, ValueError):
            continue
        if task_id > 0 and task_id not in selected_ids:
            selected_ids.append(task_id)
        if len(selected_ids) >= 500:
            break

    valid_tasks = []
    for task_id in selected_ids:
        row = core_app.db.session.execute(
            text("SELECT id, COALESCE(content, '') AS content, assignee_id FROM tasks WHERE id=:task_id AND deleted_at IS NULL"),
            {"task_id": task_id},
        ).mappings().first()
        if not row:
            continue
        if document_type == "daily" and int(row["assignee_id"]) != viewer["id"]:
            continue
        valid_tasks.append(row)

    doc_id = core_app.db.session.execute(
        text(
            """
            INSERT INTO work_journal_documents
                (work_date, document_type, title, work_summary, next_plan, special_notes,
                 author_id, department_id, created_at, updated_at)
            VALUES
                (:work_date, :document_type, :title, :work_summary, :next_plan, :special_notes,
                 :author_id, :department_id, NOW(), NOW())
            ON CONFLICT (work_date, document_type, author_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                work_summary = EXCLUDED.work_summary,
                next_plan = EXCLUDED.next_plan,
                special_notes = EXCLUDED.special_notes,
                department_id = EXCLUDED.department_id,
                updated_at = NOW()
            RETURNING id
            """
        ),
        {
            "work_date": work_date,
            "document_type": document_type,
            "title": title,
            "work_summary": summary,
            "next_plan": next_plan,
            "special_notes": notes,
            "author_id": viewer["id"],
            "department_id": viewer["department_id"],
        },
    ).scalar_one()
    core_app.db.session.execute(text("DELETE FROM work_journal_document_items WHERE journal_id=:journal_id"), {"journal_id": doc_id})
    try:
        core_app.db.session.execute(
            text("DELETE FROM document_task_contents WHERE document_kind='journal' AND document_id=:journal_id"),
            {"journal_id": doc_id},
        )
    except Exception:
        core_app.db.session.rollback()
        # Re-establish the document transaction after rollback if the snapshot table is unavailable.
        doc_id = core_app.db.session.execute(
            text(
                """
                SELECT id FROM work_journal_documents
                WHERE work_date=:work_date AND document_type=:document_type AND author_id=:author_id
                """
            ),
            {"work_date": work_date, "document_type": document_type, "author_id": viewer["id"]},
        ).scalar_one()
        core_app.db.session.execute(text("DELETE FROM work_journal_document_items WHERE journal_id=:journal_id"), {"journal_id": doc_id})

    for task in valid_tasks:
        core_app.db.session.execute(
            text("INSERT INTO work_journal_document_items (journal_id, task_id) VALUES (:journal_id, :task_id) ON CONFLICT DO NOTHING"),
            {"journal_id": doc_id, "task_id": int(task["id"])},
        )
        try:
            core_app.db.session.execute(
                text(
                    """
                    INSERT INTO document_task_contents
                        (document_kind, document_id, task_id, content, created_at, updated_at)
                    VALUES ('journal', :document_id, :task_id, :content, NOW(), NOW())
                    ON CONFLICT (document_kind, document_id, task_id)
                    DO UPDATE SET content=EXCLUDED.content, updated_at=NOW()
                    """
                ),
                {"document_id": doc_id, "task_id": int(task["id"]), "content": task["content"] or ""},
            )
        except Exception:
            core_app.db.session.rollback()
            # Keep the journal itself usable even when snapshot persistence is unavailable.
            core_app.db.session.execute(
                text("INSERT INTO work_journal_document_items (journal_id, task_id) VALUES (:journal_id, :task_id) ON CONFLICT DO NOTHING"),
                {"journal_id": doc_id, "task_id": int(task["id"])},
            )

    _audit(environ, viewer["id"], "WORK_JOURNAL_DOCUMENT_SAVE", f"journal:{doc_id}", {"journal_id": doc_id, "document_type": document_type, "related_task_ids": [int(t["id"]) for t in valid_tasks], "save_mode": "direct_wsgi"})
    core_app.db.session.commit()
    return _redirect(start_response, f"/work-journals?open={doc_id}")


def _delete_one(environ, start_response, viewer, cookie_value, journal_id):
    form = _read_form(environ)
    if not viewer["is_admin"]:
        return _response(start_response, "Forbidden", status="403 FORBIDDEN")
    if not _valid_csrf(viewer, cookie_value, _one(form, "_journal_csrf")):
        return _response(start_response, "Forbidden", status="403 FORBIDDEN")
    row = core_app.db.session.execute(text("SELECT id, title, document_type, author_id FROM work_journal_documents WHERE id=:id"), {"id": journal_id}).mappings().first()
    if row:
        task_ids = core_app.db.session.execute(text("SELECT task_id FROM work_journal_document_items WHERE journal_id=:id"), {"id": journal_id}).scalars().all()
        try:
            core_app.db.session.execute(text("DELETE FROM document_task_contents WHERE document_kind='journal' AND document_id=:id"), {"id": journal_id})
        except Exception:
            core_app.db.session.rollback()
        core_app.db.session.execute(text("DELETE FROM work_journal_documents WHERE id=:id"), {"id": journal_id})
        _audit(environ, viewer["id"], "WORK_JOURNAL_DOCUMENT_DELETE", f"journal:{journal_id}", {"journal_id": journal_id, "related_task_ids": list(task_ids), "original_tasks_preserved": True, "delete_mode": "direct_wsgi"})
        core_app.db.session.commit()
    return _redirect(start_response, "/work-journals")


def _delete_bulk(environ, start_response, viewer, cookie_value):
    form = _read_form(environ)
    if not viewer["is_admin"]:
        return _response(start_response, "Forbidden", status="403 FORBIDDEN")
    if not _valid_csrf(viewer, cookie_value, _one(form, "_journal_csrf")):
        return _response(start_response, "Forbidden", status="403 FORBIDDEN")
    ids = []
    for raw in form.get("document_ids") or []:
        try:
            jid = int(raw)
        except (TypeError, ValueError):
            continue
        if jid > 0 and jid not in ids:
            ids.append(jid)
        if len(ids) >= 500:
            break
    for jid in ids:
        try:
            core_app.db.session.execute(text("DELETE FROM document_task_contents WHERE document_kind='journal' AND document_id=:id"), {"id": jid})
        except Exception:
            core_app.db.session.rollback()
        core_app.db.session.execute(text("DELETE FROM work_journal_documents WHERE id=:id"), {"id": jid})
    _audit(environ, viewer["id"], "WORK_JOURNAL_DOCUMENT_BULK_DELETE", "journals:bulk", {"journal_ids": ids, "original_tasks_preserved": True, "delete_mode": "direct_wsgi"})
    core_app.db.session.commit()
    return _redirect(start_response, "/work-journals")


class DirectWorkJournalApplication:
    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        path = environ.get("PATH_INFO") or ""

        if path == "/__health/direct-work-journals":
            return _response(start_response, "direct_work_journals=active", headers=[("Content-Type", "text/plain; charset=utf-8")])

        is_journal_get = method == "GET" and path in JOURNAL_GET_PATHS
        is_create = method == "POST" and path == "/work-journals/create"
        is_bulk_delete = method == "POST" and path == "/work-journals/delete-bulk"
        is_single_delete = method == "POST" and path.startswith("/work-journals/delete/")

        if not (is_journal_get or is_create or is_bulk_delete or is_single_delete):
            return self.downstream(environ, start_response)

        try:
            with flask_app.app_context():
                viewer, cookie_value = _viewer(environ)
                if not viewer:
                    next_url = "/work-journals"
                    return _redirect(start_response, f"/login?next={quote(next_url)}")

                if is_create:
                    return _create(environ, start_response, viewer, cookie_value)
                if is_bulk_delete:
                    return _delete_bulk(environ, start_response, viewer, cookie_value)
                if is_single_delete:
                    try:
                        journal_id = int(path.rsplit("/", 1)[-1])
                    except ValueError:
                        return _redirect(start_response, "/work-journals")
                    return _delete_one(environ, start_response, viewer, cookie_value, journal_id)

                html = _render_board(viewer, cookie_value, environ)
                return _response(start_response, html)
        except Exception as exc:
            try:
                with flask_app.app_context():
                    core_app.db.session.rollback()
            except Exception:
                pass
            body = (
                "<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>업무일지 안전 화면</title><style>body{font-family:Arial,sans-serif;background:#f5f7fb;color:#18263c;margin:0}.box{max-width:760px;margin:70px auto;padding:28px;background:#fff;border:1px solid #dce4ef;border-radius:16px}a{color:#2166dc;font-weight:800}</style></head>"
                f"<body><div class='box'><h1>업무일지 안전 화면</h1><p>업무일지를 불러오는 중 오류가 발생했습니다.</p><p>진단코드: <strong>{_e(type(exc).__name__)}</strong></p><p><a href='/'>통합현황으로 이동</a></p></div></body></html>"
            )
            return _response(start_response, body, status="200 OK", headers=[("X-MedPark-Direct-Error", type(exc).__name__)])


app = DirectWorkJournalApplication(flask_app.wsgi_app)
