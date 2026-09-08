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
    path = request.path or "/admin"
    return path + (f"?{query}" if query else "")


def _result_message(result):
    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        return bool(payload.get("ok")), str(payload.get("message") or "처리가 완료되었습니다.")
    return response.status_code < 400, "업무구분 처리가 완료되었습니다."


def _work_category_operation():
    if request.method != "POST":
        return ""

    explicit = str(request.form.get("awc_operation") or "").strip()
    if explicit in ALLOWED_OPERATIONS:
        return explicit

    # V17 fallback: on the work-category admin screen, the standard
    # ``operation`` field is authoritative even when a proxy/browser drops the
    # extra awc_operation marker. Existing employee/role forms use ``action``
    # rather than these operation values, so they pass through untouched.
    is_work_category_context = (
        request.path.rstrip("/") == "/admin/work-categories"
        or request.args.get("section") == "work-categories"
    )
    fallback = str(request.form.get("operation") or "").strip()
    if is_work_category_context and fallback in ALLOWED_OPERATIONS:
        return fallback
    return ""


def _build_wrapper(original, endpoint):
    @wraps(original)
    def wrapped(*args, **kwargs):
        operation = _work_category_operation()
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
                # Normalize the canonical operation value for the CRUD handler.
                # ImmutableMultiDict cannot be assigned directly, but the native
                # V17 form always sends ``operation``; this check catches stale
                # clients without passing them into the legacy admin validator.
                form_operation = str(request.form.get("operation") or "").strip()
                if form_operation not in ALLOWED_OPERATIONS:
                    flash("업무구분 요청 값을 확인해 주세요.", "error")
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

    wrapped._medpark_awc_v17 = True
    wrapped._medpark_awc_endpoint = endpoint
    return wrapped


def _install_wrappers():
    endpoints = []
    rules = []
    for rule in core.app.url_map.iter_rules():
        normalized = rule.rule.rstrip("/") or "/"
        if normalized in TARGET_RULES and "POST" in rule.methods:
            rules.append(f"{rule.rule}:{rule.endpoint}")
            endpoints.append(rule.endpoint)

    for endpoint in sorted(set(endpoints)):
        original = core.app.view_functions.get(endpoint)
        if original is None:
            continue
        if getattr(original, "_medpark_awc_v17", False):
            WRAPPED_ENDPOINTS.append(endpoint)
            continue
        core.app.view_functions[endpoint] = _build_wrapper(original, endpoint)
        WRAPPED_ENDPOINTS.append(endpoint)

    MATCHED_RULES.extend(sorted(set(rules)))


_install_wrappers()


@core.app.get("/__health/admin-work-category-v17")
def admin_work_category_v17_health():
    wrapped = sorted(set(WRAPPED_ENDPOINTS))
    return (
        "admin_work_category=v17 "
        + ("active=1" if wrapped else "active=0")
        + f" wrapped_count={len(wrapped)}"
        + " fallback=operation"
        + " legacy_bootstrap=off"
        + " endpoints=" + ",".join(wrapped)
        + " rules=" + ",".join(MATCHED_RULES),
        200,
        {"Cache-Control": "no-store"},
    )
