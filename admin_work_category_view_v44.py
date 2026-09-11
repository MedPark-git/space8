from functools import wraps

from flask import request
from flask_login import current_user

import app as core
import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - ensure delete handler is registered

TARGET_RULE = "/tasks/new"
ACCEPTED_ADMIN_MARKERS = {"v42", "v44"}


def _find_task_new_endpoint():
    for rule in core.app.url_map.iter_rules():
        normalized = (rule.rule.rstrip("/") or "/")
        if normalized == TARGET_RULE and "POST" in rule.methods:
            return rule.endpoint
    raise RuntimeError("POST /tasks/new endpoint not found")


TASK_NEW_ENDPOINT = _find_task_new_endpoint()
ORIGINAL_TASK_NEW = core.app.view_functions[TASK_NEW_ENDPOINT]

# Remove older category-specific request hooks. Flask-WTF/global request hooks
# remain untouched; V44 only replaces the actual POST /tasks/new view.
_hooks = core.app.before_request_funcs.setdefault(None, [])
_hooks[:] = [
    fn for fn in _hooks
    if getattr(fn, "__name__", "") not in {
        "_category_manager_v18_before_request",
        "_admin_work_category_before_request_v19",
        "_handle_v22",
    }
]


def _is_admin_category_request():
    if request.method != "POST":
        return False
    marker = str(request.args.get("awc_admin") or request.form.get("awc_admin") or "").strip()
    category_manager = str(request.args.get("category_manager") or request.form.get("category_manager") or "").strip()
    return marker in ACCEPTED_ADMIN_MARKERS or category_manager == "1"


def _resolve_action():
    action = str(
        request.args.get("category_action")
        or request.form.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    if action in guard.HANDLERS:
        return action

    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.args.get("awc_operation")
        or ""
    ).strip()
    return {
        "add_middle": "add",
        "add_small": "add",
        "rename_middle": "rename_middle",
        "rename_small": "rename_small",
        "delete": "delete",
    }.get(operation, "")


@wraps(ORIGINAL_TASK_NEW)
def task_new_v44(*args, **kwargs):
    if not _is_admin_category_request():
        return ORIGINAL_TASK_NEW(*args, **kwargs)

    if not current_user.is_authenticated:
        return guard._finish("로그인이 필요합니다.", False, status=401)
    if not guard._is_admin():
        return guard._finish("관리자 권한이 필요합니다.", False, status=403)

    action = _resolve_action()
    handler = guard.HANDLERS.get(action)
    if handler is None:
        return guard._finish("지원하지 않는 업무구분 작업입니다.", False, status=400)

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
        "active": active,
        "handlers": sorted(guard.HANDLERS),
        "legacy_category_hooks_remaining": [
            getattr(fn, "__name__", "")
            for fn in core.app.before_request_funcs.get(None, [])
            if getattr(fn, "__name__", "") in {
                "_category_manager_v18_before_request",
                "_admin_work_category_before_request_v19",
                "_handle_v22",
            }
        ],
    }
