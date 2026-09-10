from functools import wraps

from flask import request
from flask_login import current_user

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - ensure administrator delete exists
import task_editor_runtime as runtime

core = guard.core
ACCEPTED_MARKERS = {"v42", "v43", "v44"}
TARGET_PATH = "/tasks/new"


def _find_task_new_endpoint():
    candidates = []
    for rule in core.app.url_map.iter_rules():
        normalized = rule.rule.rstrip("/") or "/"
        if normalized == TARGET_PATH and "POST" in rule.methods:
            candidates.append(rule.endpoint)
    if not candidates:
        raise RuntimeError("POST /tasks/new endpoint not found")
    # Prefer the conventional endpoint if present, otherwise use the actual rule endpoint.
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
    # Administrator work-category writes are handled in the actual task_new view
    # below. Other employee category-manager requests continue using the existing
    # proven runtime hook unchanged.
    if request.method == "POST":
        marker = str(request.args.get("awc_admin") or "").strip()
        if marker in ACCEPTED_MARKERS:
            return None
    return _original_category_hook()


# Replace only the exact category-manager hook object already registered.
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
