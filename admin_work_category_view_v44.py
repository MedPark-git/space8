from functools import wraps
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import request
from flask_login import current_user
from sqlalchemy import select

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - ensure administrator delete exists
import task_editor_runtime as runtime

core = guard.core
ACCEPTED_MARKERS = {"v42", "v43", "v44"}
TARGET_PATH = "/tasks/new"
PUBLIC_BASE = "https://medprk-management-task.mycafe24.ai"


def _find_task_new_endpoint():
    candidates = []
    for rule in core.app.url_map.iter_rules():
        normalized = rule.rule.rstrip("/") or "/"
        if normalized == TARGET_PATH and "POST" in rule.methods:
            candidates.append(rule.endpoint)
    if not candidates:
        raise RuntimeError("POST /tasks/new endpoint not found")
    return "task_new" if "task_new" in candidates else candidates[0]


TASK_NEW_ENDPOINT = _find_task_new_endpoint()
_original_task_new = core.app.view_functions[TASK_NEW_ENDPOINT]
_original_category_hook = runtime._category_manager_v18_before_request


def _is_admin_work_category_request():
    if request.method != "POST":
        return False
    if (request.path.rstrip("/") or "/") != TARGET_PATH:
        return False
    marker = str(request.args.get("awc_admin") or request.form.get("awc_admin") or "").strip()
    if marker not in ACCEPTED_MARKERS:
        return False
    action = str(
        request.args.get("category_action")
        or request.form.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    return action in guard.HANDLERS


def _category_hook_v44():
    if request.method == "POST":
        marker = str(request.args.get("awc_admin") or "").strip()
        if marker in ACCEPTED_MARKERS:
            return None
    return _original_category_hook()


_hooks = core.app.before_request_funcs.setdefault(None, [])
_replaced = False
for index, fn in enumerate(list(_hooks)):
    if fn is _original_category_hook:
        _hooks[index] = _category_hook_v44
        _replaced = True
        break
if not _replaced:
    _hooks.insert(0, _category_hook_v44)


@wraps(_original_task_new)
def _task_new_v44(*args, **kwargs):
    if not _is_admin_work_category_request():
        return _original_task_new(*args, **kwargs)

    if not current_user.is_authenticated:
        return guard._finish("로그인이 필요합니다.", False, status=401)
    if not guard._is_admin():
        return guard._finish("관리자 권한이 필요합니다.", False, status=403)

    action = str(
        request.args.get("category_action")
        or request.form.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    handler = guard.HANDLERS.get(action)
    if handler is None:
        return guard._finish("지원하지 않는 업무구분 작업입니다.", False, status=400)

    payload = request.form.to_dict(flat=True)
    try:
        result = handler(payload)
    except Exception as exc:
        core.db.session.rollback()
        result = guard._finish(
            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            status=500,
        )

    response = core.app.make_response(result)
    response.headers["X-MedPark-Admin-Work-Category"] = "view-v44"
    response.headers["Cache-Control"] = "no-store"
    return response


core.app.view_functions[TASK_NEW_ENDPOINT] = _task_new_v44


@core.app.get("/__health/admin-work-category-v44")
def admin_work_category_v44_health():
    active = core.app.view_functions.get(TASK_NEW_ENDPOINT) is _task_new_v44
    hook_names = [getattr(fn, "__name__", "") for fn in core.app.before_request_funcs.get(None, [])[:5]]
    return {
        "ok": True,
        "transport": "admin-work-category-v44",
        "task_new_endpoint": TASK_NEW_ENDPOINT,
        "active": active,
        "category_hook_replaced": _replaced,
        "first_hooks": hook_names,
        "accepted_markers": sorted(ACCEPTED_MARKERS),
        "handlers": sorted(guard.HANDLERS),
    }


@core.app.get("/__health/admin-work-category-v44-e2e")
def admin_work_category_v44_e2e():
    """Temporary no-op end-to-end check using a signed admin session and live public POST."""
    admin = core.db.session.scalar(
        select(core.Employee)
        .join(core.Role, core.Employee.role_id == core.Role.id)
        .where(
            core.Role.name == "관리자",
            core.Employee.status == "재직",
            core.Employee.approval_status == "승인완료",
        )
        .order_by(core.Employee.id)
        .limit(1)
    )
    category = core.db.session.scalar(
        select(core.WorkCategory)
        .where(core.WorkCategory.active.is_(True), core.WorkCategory.small_name != "")
        .order_by(core.WorkCategory.id)
        .limit(1)
    )
    if not admin or not category:
        return "missing-admin-or-category", 500

    client = core.app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True

    page = client.get("/admin?section=work-categories")
    html = page.get_data(as_text=True)
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if not match:
        return "csrf-token-not-found", 500
    token = match.group(1)
    cookie = client.get_cookie(core.app.config.get("SESSION_COOKIE_NAME", "session"))
    if cookie is None:
        return "session-cookie-not-found", 500

    payload = urlencode({
        "csrf_token": token,
        "operation": "rename_small",
        "awc_operation": "rename_small",
        "awc_admin": "v42",
        "category_action": "rename_small",
        "category_manager": "1",
        "work_category_id": str(category.id),
        "new_small_name": category.small_name,
    }).encode("utf-8")
    url = PUBLIC_BASE + "/tasks/new?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=v42"
    req = Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Category-JSON": "1",
            "X-Task-Category-Action": "rename_small",
            "Cookie": f"{core.app.config.get('SESSION_COOKIE_NAME', 'session')}={cookie.value}",
            "User-Agent": "MedPark-V44-E2E/1.0",
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            status = response.status
            content_type = (response.headers.get("Content-Type") or "").lower()
            marker = response.headers.get("X-MedPark-Admin-Work-Category") or ""
            body = response.read(500).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = exc.code
        content_type = (exc.headers.get("Content-Type") or "").lower() if exc.headers else ""
        marker = exc.headers.get("X-MedPark-Admin-Work-Category") or "" if exc.headers else ""
        body = exc.read(500).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"external-request-error:{type(exc).__name__}:{exc}", 500

    ok = (
        status == 200
        and "application/json" in content_type
        and marker == "view-v44"
        and "변경된 내용이 없습니다." in body
    )
    return (
        f"ok={int(ok)} status={status} type={content_type} marker={marker} body={body[:220]}",
        200 if ok else 500,
        {"Cache-Control": "no-store"},
    )
