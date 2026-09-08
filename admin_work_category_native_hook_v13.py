from flask import flash, redirect, request, url_for
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


def _work_category_url():
    try:
        return url_for("admin", section="work-categories")
    except Exception:
        return request.path or "/"


def _redirect_to_work_categories():
    return redirect(_work_category_url())


def _message_from_result(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _admin_work_category_native_before_request_v13():
    if request.method != "POST":
        return None

    operation = str(request.form.get("awc_operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        return None

    # Native browser POST: Flask has already parsed request.form, exactly like
    # the working employee/role/department admin forms. Do not depend on a
    # hard-coded admin URL, custom header, query marker, or JSON/AJAX transport.
    try:
        core.csrf.protect()
    except Exception:
        flash("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", "error")
        return _redirect_to_work_categories()

    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if not _is_admin():
        flash("관리자 권한이 필요합니다.", "error")
        return _redirect_to_work_categories()

    try:
        if operation == "delete":
            result = delete_manager.admin_work_category_delete_v2()
        else:
            form_operation = str(request.form.get("operation") or "").strip()
            if form_operation != operation:
                flash("업무구분 요청 값이 일치하지 않습니다.", "error")
                return _redirect_to_work_categories()
            result = manager.admin_work_category_manage()
        ok, message = _message_from_result(result)
        flash(message, "success" if ok else "error")
    except Exception as exc:
        core.db.session.rollback()
        flash(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", "error")

    return _redirect_to_work_categories()


_before = core.app.before_request_funcs.setdefault(None, [])
if _admin_work_category_native_before_request_v13 not in _before:
    _before.insert(0, _admin_work_category_native_before_request_v13)


@core.app.get("/__health/admin-work-category-v13")
def admin_work_category_v13_health():
    funcs = core.app.before_request_funcs.get(None, [])
    first = bool(funcs and funcs[0] is _admin_work_category_native_before_request_v13)
    target = _work_category_url()
    return (
        f"admin_work_category_native=v13 active first={1 if first else 0} target={target}",
        200,
        {"Cache-Control": "no-store"},
    )
