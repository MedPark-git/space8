from flask import flash, redirect, request
from flask_login import current_user

import app as core
import admin_work_category_entry as previous

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


def _redirect_to_work_categories():
    return redirect("/admin?section=work-categories")


def _message_from_result(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _admin_work_category_native_before_request_v12():
    if request.method != "POST" or not request.path.startswith("/admin"):
        return None

    operation = str(request.form.get("awc_operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        return None

    # Run before the normal admin handler. Native browser form POSTs are parsed
    # by Flask exactly like the already-working employee/role admin forms.
    try:
        core.csrf.protect()
    except Exception:
        flash("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", "error")
        return _redirect_to_work_categories()

    if not current_user.is_authenticated:
        return redirect("/login")
    if not _is_admin():
        flash("관리자 권한이 필요합니다.", "error")
        return _redirect_to_work_categories()

    try:
        if operation == "delete":
            result = previous._handle_delete()
        else:
            form_operation = str(request.form.get("operation") or "").strip()
            if form_operation != operation:
                flash("업무구분 요청 값이 일치하지 않습니다.", "error")
                return _redirect_to_work_categories()
            result = previous._handle_manage()
        ok, message = _message_from_result(result)
        flash(message, "success" if ok else "error")
    except Exception as exc:
        core.db.session.rollback()
        flash(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", "error")

    return _redirect_to_work_categories()


_before = core.app.before_request_funcs.setdefault(None, [])
if _admin_work_category_native_before_request_v12 not in _before:
    _before.insert(0, _admin_work_category_native_before_request_v12)


@core.app.get("/__health/admin-work-category-v12")
def admin_work_category_v12_health():
    funcs = core.app.before_request_funcs.get(None, [])
    first = bool(funcs and funcs[0] is _admin_work_category_native_before_request_v12)
    return (
        "admin_work_category_native=v12 active first=" + ("1" if first else "0"),
        200,
        {"Cache-Control": "no-store"},
    )
