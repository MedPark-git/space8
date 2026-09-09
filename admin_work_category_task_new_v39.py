import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import request
from flask_login import current_user
from sqlalchemy import select

import app as core
import admin_work_category_server_v19 as v19


_original_task_new = core.app.view_functions.get("task_new")
if _original_task_new is None:
    raise RuntimeError("task_new endpoint not found")

hooks = core.app.before_request_funcs.setdefault(None, [])
hooks[:] = [
    fn
    for fn in hooks
    if getattr(fn, "__name__", "") not in {
        "_admin_work_category_before_request_v19",
        "_handle_v22",
    }
]


def _query_operation():
    return str(request.args.get("awc_operation") or "").strip()


def _is_admin_work_category_write():
    return (
        request.method == "POST"
        and request.args.get("awc_admin") == "v39"
        and _query_operation() in v19.HANDLERS
    )


def _json_error(message, status):
    response = core.app.make_response(v19._json(message, False, status))
    response.headers["X-MedPark-Admin-Work-Category"] = "task-new-v39"
    response.headers["Cache-Control"] = "no-store"
    return response


def _task_new_v39(*args, **kwargs):
    if not _is_admin_work_category_write():
        return _original_task_new(*args, **kwargs)

    if not current_user.is_authenticated:
        return _json_error("로그인이 필요합니다.", 401)
    if not v19._is_admin():
        return _json_error("관리자 권한이 필요합니다.", 403)

    operation = _query_operation()
    handler = v19.HANDLERS.get(operation)
    if handler is None:
        return _json_error("지원하지 않는 업무구분 작업입니다.", 400)

    try:
        result = handler()
    except Exception as exc:
        core.db.session.rollback()
        result = v19._json(
            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            500,
        )

    response = core.app.make_response(result)
    response.headers["X-MedPark-Admin-Work-Category"] = "task-new-v39"
    response.headers["Cache-Control"] = "no-store"
    return response


core.app.view_functions["task_new"] = _task_new_v39


@core.app.get("/__health/admin-work-category-v39")
def admin_work_category_v39_health():
    active = core.app.view_functions.get("task_new") is _task_new_v39
    return (
        f"admin_work_category=v39 active={int(active)} route=/tasks/new csrf=normal",
        200,
        {"Cache-Control": "no-store"},
    )


@core.app.get("/__health/admin-work-category-v39-post")
def admin_work_category_v39_post_health():
    admin = core.db.session.scalar(
        select(core.Employee)
        .join(core.Role, core.Employee.role_id == core.Role.id)
        .where(core.Role.name == "관리자")
        .limit(1)
    )
    category = core.db.session.scalar(
        select(core.WorkCategory)
        .where(core.WorkCategory.active.is_(True), core.WorkCategory.small_name != "")
        .limit(1)
    )
    if not admin or not category:
        return "fixture missing", 500, {"Cache-Control": "no-store"}

    session_name = core.app.config.get("SESSION_COOKIE_NAME", "session")
    with core.app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(admin.id)
            session["_fresh"] = True
        page = client.get("/admin?section=work-categories")
        html = page.get_data(as_text=True)
        match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
        cookie = client.get_cookie(session_name)

    if not match or cookie is None:
        return "session/csrf unavailable", 500, {"Cache-Control": "no-store"}

    token = match.group(1)
    cookie_value = getattr(cookie, "value", str(cookie))
    body = urlencode({
        "csrf_token": token,
        "operation": "rename_small",
        "awc_operation": "rename_small",
        "work_category_id": str(category.id),
        "new_small_name": category.small_name,
        "awc_source": "v39-self-test",
        "awc_response": "json",
    }).encode("utf-8")
    req = Request(
        "https://medprk-management-task.mycafe24.ai/tasks/new?awc_admin=v39&awc_operation=rename_small",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Category-JSON": "1",
            "Cookie": f"{session_name}={cookie_value}",
            "User-Agent": "MedPark-V39-SelfTest/1.0",
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            marker = response.headers.get("X-MedPark-Admin-Work-Category", "")
            preview = response.read(240).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        marker = exc.headers.get("X-MedPark-Admin-Work-Category", "") if exc.headers else ""
        preview = exc.read(240).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"exception={type(exc).__name__}:{exc}", 500, {"Cache-Control": "no-store"}

    ok = (
        status == 200
        and "application/json" in content_type.lower()
        and marker == "task-new-v39"
        and '"ok":true' in preview.replace(" ", "").lower()
    )
    return (
        f"status={status} type={content_type} marker={marker} preview={preview[:120]}",
        200 if ok else 500,
        {"Cache-Control": "no-store"},
    )
