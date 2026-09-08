from functools import wraps

from flask import flash, redirect, request, url_for
from flask_login import current_user

import app as core
import admin_work_category_entry as crud

TARGET_RULES = {"/admin", "/admin/work-categories"}
ALLOWED_OPERATIONS = {
    "add_middle",
    "add_small",
    "rename_middle",
    "rename_small",
    "delete",
}

WRAPPED_ENDPOINTS = []
MATCHED_RULES = []


def _return_url():
    query = request.query_string.decode("utf-8", errors="ignore")
    if request.path.rstrip("/") in TARGET_RULES:
        return request.path + (f"?{query}" if query else "")
    return url_for("admin", section="work-categories")


def _result_message(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _build_wrapper(original, endpoint):
    @wraps(original)
    def wrapped(*args, **kwargs):
        operation = (
            str(request.form.get("awc_operation") or "").strip()
            if request.method == "POST"
            else ""
        )
        if operation not in ALLOWED_OPERATIONS:
            return original(*args, **kwargs)

        return_url = _return_url()

        if not current_user.is_authenticated:
            return redirect(url_for("login"))
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
            flash(
                f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                "error",
            )

        return redirect(return_url)

    wrapped._medpark_awc_v16 = True
    wrapped._medpark_awc_endpoint = endpoint
    return wrapped


def _install_wrappers():
    endpoints = []
    rules = []

    for rule in core.app.url_map.iter_rules():
        normalized = rule.rule.rstrip("/") or "/"
        if normalized in TARGET_RULES:
            rules.append(f"{rule.rule}:{rule.endpoint}")
            endpoints.append(rule.endpoint)

    for endpoint in sorted(set(endpoints)):
        original = core.app.view_functions.get(endpoint)
        if original is None:
            continue
        if getattr(original, "_medpark_awc_v16", False):
            WRAPPED_ENDPOINTS.append(endpoint)
            continue
        core.app.view_functions[endpoint] = _build_wrapper(original, endpoint)
        WRAPPED_ENDPOINTS.append(endpoint)

    MATCHED_RULES.extend(sorted(set(rules)))


_install_wrappers()


@core.app.get("/__health/admin-work-category-v16")
def admin_work_category_v16_health():
    wrapped = sorted(set(WRAPPED_ENDPOINTS))
    active = bool(wrapped)
    return (
        "admin_work_category=v16 "
        + ("active=1" if active else "active=0")
        + f" wrapped_count={len(wrapped)}"
        + " endpoints=" + ",".join(wrapped)
        + " rules=" + ",".join(MATCHED_RULES),
        200,
        {"Cache-Control": "no-store"},
    )
