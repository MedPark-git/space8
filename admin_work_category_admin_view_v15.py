from functools import wraps

from flask import flash, redirect, request
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


def _current_admin_url():
    query = request.query_string.decode("utf-8", errors="ignore")
    return request.path + (f"?{query}" if query else "")


def _result_message(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _install_admin_view_wrapper():
    original = core.app.view_functions.get("admin")
    if original is None:
        raise RuntimeError("Flask admin endpoint를 찾을 수 없습니다.")
    if getattr(original, "_medpark_awc_v15", False):
        return

    @wraps(original)
    def wrapped_admin(*args, **kwargs):
        operation = str(request.form.get("awc_operation") or "").strip() if request.method == "POST" else ""
        if operation not in ALLOWED_OPERATIONS:
            return original(*args, **kwargs)

        # The request has already passed Flask/CSRF exactly like the existing
        # employee/role admin forms.  Handle only work-category operations here
        # immediately before the original admin view would run.
        return_url = _current_admin_url()

        if not current_user.is_authenticated:
            return original(*args, **kwargs)
        if not crud._is_admin():
            flash("관리자 권한이 필요합니다.", "error")
            return redirect(return_url)

        try:
            if operation == "delete":
                result = crud._handle_delete()
            else:
                form_operation = str(request.form.get("operation") or "").strip()
                if form_operation != operation:
                    flash("업무구분 요청 값이 일치하지 않습니다.", "error")
                    return redirect(return_url)
                result = crud._handle_manage()

            ok, message = _result_message(result)
            flash(message, "success" if ok else "error")
        except Exception as exc:
            core.db.session.rollback()
            flash(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", "error")

        return redirect(return_url)

    wrapped_admin._medpark_awc_v15 = True
    core.app.view_functions["admin"] = wrapped_admin


_install_admin_view_wrapper()


@core.app.get("/__health/admin-work-category-v15")
def admin_work_category_v15_health():
    current = core.app.view_functions.get("admin")
    active = bool(getattr(current, "_medpark_awc_v15", False))
    return (
        "admin_work_category_admin_view=v15 active=" + ("1" if active else "0"),
        200,
        {"Cache-Control": "no-store"},
    )
