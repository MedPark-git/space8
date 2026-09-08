from flask import jsonify, request
from flask_login import current_user

import app as core
import admin_work_category_manager as manager
import admin_work_category_delete_manager as delete_manager

ALLOWED_OPERATIONS = {
    "add_middle",
    "add_small",
    "rename_middle",
    "rename_small",
    "delete",
}


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("admin")
            or current_user.role.allows("task_manage_all")
        )
    )


def _json(message, ok=True, status=200):
    return jsonify({
        "ok": bool(ok),
        "message": message,
        "transport": "admin-work-category-flask-hook-v11",
    }), status


def _admin_work_category_before_request_v11():
    if request.method != "POST" or not request.path.startswith("/admin"):
        return None

    operation = str(request.form.get("awc_operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        return None

    # This hook is inserted at index 0, before the normal admin request handler.
    # Protect CSRF here because returning a response stops later before_request hooks.
    core.csrf.protect()

    if not current_user.is_authenticated:
        return _json("로그인이 필요합니다.", False, 401)
    if not _is_admin():
        return _json("관리자 권한이 필요합니다.", False, 403)

    try:
        if operation == "delete":
            result = delete_manager.admin_work_category_delete_v2()
        else:
            form_operation = str(request.form.get("operation") or "").strip()
            if form_operation != operation:
                return _json("업무구분 요청 값이 일치하지 않습니다.", False, 400)
            result = manager.admin_work_category_manage()
    except Exception as exc:
        core.db.session.rollback()
        return _json(
            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            500,
        )

    response = core.app.make_response(result)
    response.headers["X-MedPark-Admin-Work-Category"] = "v11-flask-before-request"
    response.headers["Cache-Control"] = "no-store"
    return response


# Force this handler to run before every existing before_request handler,
# including the normal admin handler and Flask-WTF CSRF hook.
_before = core.app.before_request_funcs.setdefault(None, [])
if _admin_work_category_before_request_v11 not in _before:
    _before.insert(0, _admin_work_category_before_request_v11)


@core.app.get("/__health/admin-work-category-v11")
def admin_work_category_v11_health():
    funcs = core.app.before_request_funcs.get(None, [])
    first = bool(funcs and funcs[0] is _admin_work_category_before_request_v11)
    return (
        "admin_work_category_flask_hook=v11 active first=" + ("1" if first else "0"),
        200,
        {"Cache-Control": "no-store"},
    )
