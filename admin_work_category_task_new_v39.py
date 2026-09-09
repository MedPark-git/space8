from flask import request
from flask_login import current_user

import app as core
import admin_work_category_server_v19 as v19


_original_task_new = core.app.view_functions.get("task_new")
if _original_task_new is None:
    raise RuntimeError("task_new endpoint not found")

# Remove legacy administrator work-category hooks. V39 handles these writes
# inside the proven task_new POST view instead.
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
    # Keep the application's normal Flask-WTF CSRF before_request protection.
    # If execution reaches here, the POST already passed the same CSRF check as
    # an ordinary task registration POST.
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
