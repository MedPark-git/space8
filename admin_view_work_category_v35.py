from flask import request
from flask_login import current_user

import app as core
import admin_work_category_server_v19 as v19


_original_admin = core.app.view_functions.get("admin")
if _original_admin is None:
    raise RuntimeError("admin endpoint not found")

# Remove the older work-category before_request hook. V35 handles administrator
# work-category writes inside the actual /admin endpoint instead.
hooks = core.app.before_request_funcs.setdefault(None, [])
hooks[:] = [
    fn
    for fn in hooks
    if getattr(fn, "__name__", "") not in {
        "_admin_work_category_before_request_v19",
        "_handle_v22",
    }
]


def _is_work_category_write():
    if request.method != "POST":
        return False
    if request.args.get("section") != "work-categories":
        return False
    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.headers.get("X-MedPark-Admin-Operation")
        or ""
    ).strip()
    return operation in v19.HANDLERS


def _operation():
    return str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.headers.get("X-MedPark-Admin-Operation")
        or ""
    ).strip()


def _json_error(message, status):
    response = core.app.make_response(v19._json(message, False, status))
    response.headers["X-MedPark-Admin-Work-Category"] = "view-v35"
    response.headers["Cache-Control"] = "no-store"
    return response


def _admin_v35(*args, **kwargs):
    work_category_write = _is_work_category_write()

    if request.method == "POST":
        try:
            core.csrf.protect()
        except Exception:
            if work_category_write:
                return _json_error(
                    "요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
                    400,
                )
            raise

    if not work_category_write:
        return _original_admin(*args, **kwargs)

    if not current_user.is_authenticated:
        return _json_error("로그인이 필요합니다.", 401)
    if not v19._is_admin():
        return _json_error("관리자 권한이 필요합니다.", 403)

    operation = _operation()
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
    response.headers["X-MedPark-Admin-Work-Category"] = "view-v35"
    response.headers["Cache-Control"] = "no-store"
    return response


# Exempt the endpoint from Flask-WTF's automatic before_request CSRF handler,
# then enforce CSRF explicitly above for every POST before delegating to the
# original admin view. This preserves CSRF protection for all admin writes while
# preventing the legacy global handler from converting work-category failures
# into a generic 404 page.
_admin_v35 = core.csrf.exempt(_admin_v35)
core.app.view_functions["admin"] = _admin_v35


@core.app.get("/__health/admin-work-category-view-v35")
def admin_work_category_view_v35_health():
    active = core.app.view_functions.get("admin") is _admin_v35
    return (
        f"admin_work_category_view=v35 active={int(active)} ",
        200,
        {"Cache-Control": "no-store"},
    )
