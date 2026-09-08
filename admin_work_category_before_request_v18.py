from flask import flash, redirect, request, url_for
from flask_login import current_user

import app as core
import admin_work_category_entry as crud

ALLOWED_OPERATIONS = {
    "add_middle",
    "add_small",
    "rename_middle",
    "rename_small",
    "delete",
}


def _return_url():
    query = request.query_string.decode("utf-8", errors="ignore")
    path = request.path or "/admin"
    return path + (f"?{query}" if query else "")


def _result_message(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _admin_work_category_before_request_v18():
    if request.method != "POST" or not request.path.startswith("/admin"):
        return None

    # V18: the canonical operation value itself is authoritative.  Existing
    # employee/role/department admin forms use `action`, not these operation
    # values, so they pass through untouched.
    operation = str(request.form.get("operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        return None

    return_url = _return_url()

    # This handler is deliberately inserted before every existing Flask
    # before_request handler.  Because it may return early, run CSRF explicitly.
    try:
        core.csrf.protect()
    except Exception:
        flash("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", "error")
        return redirect(return_url)

    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if not crud._is_admin():
        flash("관리자 권한이 필요합니다.", "error")
        return redirect(return_url)

    try:
        if operation == "delete":
            result = crud._handle_delete()
        else:
            result = crud._handle_manage()
        ok, message = _result_message(result)
        flash(message, "success" if ok else "error")
    except Exception as exc:
        core.db.session.rollback()
        flash(
            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
            "error",
        )

    # Never fall through to the legacy admin validator for an AWC operation.
    return redirect(return_url)


_before = core.app.before_request_funcs.setdefault(None, [])
_before[:] = [
    fn for fn in _before
    if getattr(fn, "__name__", "") != "_admin_work_category_before_request_v18"
]
_before.insert(0, _admin_work_category_before_request_v18)


@core.app.get("/__health/admin-work-category-v18")
def admin_work_category_v18_health():
    funcs = core.app.before_request_funcs.get(None, [])
    first_name = getattr(funcs[0], "__name__", "") if funcs else ""
    return (
        "admin_work_category=v18 active=1 "
        f"first={first_name} "
        "dispatch=operation-before-admin-validator "
        "legacy_bootstrap=off",
        200,
        {"Cache-Control": "no-store"},
    )
