from flask import request

import admin_work_category_server_v19 as api
import task_category_wsgi_guard as guard

core = guard.core
TARGET_PATH = "/tasks/new"
MARKER = "v45"


def _operation():
    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or ""
    ).strip()
    if operation in api.HANDLERS:
        return operation

    action = str(
        request.args.get("category_action")
        or request.form.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    if action == "rename_middle":
        return "rename_middle"
    if action == "rename_small":
        return "rename_small"
    if action == "delete":
        return "delete"
    if action == "add":
        return "add_small" if str(request.form.get("small_name") or "").strip() else "add_middle"
    return ""


def _is_category_request():
    if request.method != "POST":
        return False
    if (request.path.rstrip("/") or "/") != TARGET_PATH:
        return False

    signaled = bool(
        request.args.get("category_manager") == "1"
        or request.form.get("category_manager") == "1"
        or str(request.args.get("awc_admin") or request.form.get("awc_admin") or "").startswith("v")
        or request.headers.get("X-MedPark-Category-JSON") == "1"
        or request.form.get("operation")
        or request.form.get("awc_operation")
    )
    return signaled and bool(_operation())


def _response(result):
    response = core.app.make_response(result)
    response.headers["X-MedPark-Admin-Work-Category"] = MARKER
    response.headers["Cache-Control"] = "no-store"
    return response


def _admin_work_category_v45_before_request():
    if not _is_category_request():
        return None

    try:
        core.csrf.protect()
    except Exception:
        return _response(
            api._json(
                "요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                False,
                400,
            )
        )

    if not api.current_user.is_authenticated:
        return _response(api._json("로그인이 필요합니다.", False, 401))
    if not api._is_admin():
        return _response(api._json("관리자 권한이 필요합니다.", False, 403))

    operation = _operation()
    handler = api.HANDLERS.get(operation)
    if handler is None:
        return _response(api._json("지원하지 않는 업무구분 작업입니다.", False, 400))

    try:
        result = handler()
    except Exception as exc:
        core.db.session.rollback()
        result = api._json(
            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            500,
        )
    return _response(result)


_hooks = core.app.before_request_funcs.setdefault(None, [])
_hooks[:] = [
    fn for fn in _hooks
    if getattr(fn, "__name__", "") != "_admin_work_category_v45_before_request"
]
_hooks.insert(0, _admin_work_category_v45_before_request)


@core.app.get("/__health/admin-work-category-v45")
def admin_work_category_v45_health():
    names = [getattr(fn, "__name__", "") for fn in core.app.before_request_funcs.get(None, [])[:6]]
    return {
        "ok": True,
        "transport": MARKER,
        "target": TARGET_PATH,
        "first_before_request": names[0] if names else "",
        "hooks": names,
        "operations": sorted(api.HANDLERS),
        "detection": "query-or-form-signal plus operation; multipart-safe",
    }
