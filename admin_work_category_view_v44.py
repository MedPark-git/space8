from functools import wraps
import re

from flask import request
from flask_login import current_user
from sqlalchemy import select

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - ensure administrator delete handler exists

core = guard.core
ACCEPTED_MARKERS = {"v42", "v44"}
ACTION_MAP = {
    "add_middle": "add",
    "add_small": "add",
    "rename_middle": "rename_middle",
    "rename_small": "rename_small",
    "delete": "delete",
}


def _find_task_new_endpoint():
    candidates = []
    for rule in core.app.url_map.iter_rules():
        if rule.rule.rstrip("/") == "/tasks/new" and "POST" in rule.methods:
            candidates.append(rule.endpoint)
    if not candidates:
        raise RuntimeError("POST /tasks/new endpoint not found")
    if "task_new" in candidates:
        return "task_new"
    return candidates[0]


TASK_NEW_ENDPOINT = _find_task_new_endpoint()
ORIGINAL_TASK_NEW = core.app.view_functions[TASK_NEW_ENDPOINT]

hooks = core.app.before_request_funcs.setdefault(None, [])
hooks[:] = [
    fn for fn in hooks
    if getattr(fn, "__name__", "") not in {
        "_category_manager_v18_before_request",
        "_admin_work_category_before_request_v19",
        "_handle_v22",
    }
]


def _action():
    explicit = str(
        request.args.get("category_action")
        or request.form.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    if explicit in guard.HANDLERS:
        return explicit

    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.args.get("awc_operation")
        or ""
    ).strip()
    return ACTION_MAP.get(operation, "")


def _is_admin_write():
    if request.method != "POST":
        return False
    marker = str(request.args.get("awc_admin") or request.form.get("awc_admin") or "").strip()
    if marker not in ACCEPTED_MARKERS:
        return False
    return bool(_action())


def _json_error(message, status):
    response = core.app.make_response(guard._finish(message, False, status=status))
    response.headers["X-MedPark-Admin-Work-Category"] = "view-v44"
    response.headers["Cache-Control"] = "no-store"
    return response


@wraps(ORIGINAL_TASK_NEW)
def task_new_v44(*args, **kwargs):
    if not _is_admin_write():
        return ORIGINAL_TASK_NEW(*args, **kwargs)

    if not current_user.is_authenticated:
        return _json_error("로그인이 필요합니다.", 401)
    if not guard._is_admin():
        return _json_error("관리자 권한이 필요합니다.", 403)

    action = _action()
    handler = guard.HANDLERS.get(action)
    if handler is None:
        return _json_error("지원하지 않는 업무구분 작업입니다.", 400)

    payload = guard._payload()
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


core.app.view_functions[TASK_NEW_ENDPOINT] = task_new_v44


@core.app.get("/__health/admin-work-category-v44")
def admin_work_category_v44_health():
    active = core.app.view_functions.get(TASK_NEW_ENDPOINT) is task_new_v44
    return {
        "ok": True,
        "transport": "admin-work-category-v44",
        "task_new_endpoint": TASK_NEW_ENDPOINT,
        "view_replaced": active,
        "accepted_markers": sorted(ACCEPTED_MARKERS),
        "handlers": sorted(guard.HANDLERS),
        "legacy_category_hooks_removed": True,
    }


@core.app.get("/__health/admin-work-category-v44-noop")
def admin_work_category_v44_noop():
    admin = core.db.session.scalar(
        select(core.Employee)
        .join(core.Role, core.Employee.role_id == core.Role.id)
        .where(core.Role.name == "관리자", core.Employee.status == "재직")
        .order_by(core.Employee.id)
    )
    category = core.db.session.scalar(
        select(core.WorkCategory)
        .where(core.WorkCategory.active.is_(True), core.WorkCategory.small_name != "")
        .order_by(core.WorkCategory.id)
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

    response = client.post(
        "/tasks/new?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=v42",
        data={
            "csrf_token": token,
            "operation": "rename_small",
            "awc_operation": "rename_small",
            "awc_admin": "v42",
            "category_action": "rename_small",
            "category_manager": "1",
            "work_category_id": str(category.id),
            "new_small_name": category.small_name,
        },
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Category-JSON": "1",
            "X-Task-Category-Action": "rename_small",
        },
        follow_redirects=False,
    )
    content_type = response.headers.get("Content-Type", "")
    marker = response.headers.get("X-MedPark-Admin-Work-Category", "")
    body = response.get_data(as_text=True)
    ok = (
        response.status_code == 200
        and "application/json" in content_type.lower()
        and marker == "view-v44"
        and "변경된 내용이 없습니다" in body
    )
    return (
        f"ok={int(ok)} status={response.status_code} type={content_type} marker={marker} body={body[:160]}",
        200 if ok else 500,
        {"Cache-Control": "no-store"},
    )
