from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

import app as core
import admin_work_category_manager as manager
import admin_work_category_delete_manager as delete_manager

ROUTE_PATH = "/admin/work-category-action-v14"
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
    return url_for("admin", section="work-categories")


def _message_from_result(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


@core.app.route(ROUTE_PATH, methods=["GET", "POST"])
def admin_work_category_action_v14():
    # GET doubles as a deployment/route registration health probe.
    if request.method == "GET":
        return (
            "admin_work_category_route=v14 active target=" + _work_category_url(),
            200,
            {"Cache-Control": "no-store"},
        )

    # CSRFProtect handles this native browser POST globally. The hidden
    # csrf_token field is supplied by the page script, just like existing admin forms.
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if not _is_admin():
        flash("관리자 권한이 필요합니다.", "error")
        return redirect(_work_category_url())

    operation = str(request.form.get("awc_operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        flash("지원하지 않는 업무구분 작업입니다.", "error")
        return redirect(_work_category_url())

    try:
        if operation == "delete":
            result = delete_manager.admin_work_category_delete_v2()
        else:
            form_operation = str(request.form.get("operation") or "").strip()
            if form_operation != operation:
                flash("업무구분 요청 값이 일치하지 않습니다.", "error")
                return redirect(_work_category_url())
            result = manager.admin_work_category_manage()

        ok, message = _message_from_result(result)
        flash(message, "success" if ok else "error")
    except Exception as exc:
        core.db.session.rollback()
        flash(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", "error")

    return redirect(_work_category_url())
