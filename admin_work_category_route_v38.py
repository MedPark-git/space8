from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import jsonify, request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core
ROUTE = "/api/admin/work-category-v38"
PUBLIC_URL = "https://medprk-management-task.mycafe24.ai" + ROUTE


def _json(message, ok=True, status=200):
    return jsonify({
        "ok": bool(ok),
        "message": message,
        "transport": "admin-work-category-v38",
    }), status


@core.app.route(ROUTE, methods=["GET", "POST"])
def admin_work_category_v38():
    if request.method == "GET":
        return jsonify({"ok": True, "transport": "admin-work-category-v38", "method": "POST"})

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        return _json(
            "요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
            False,
            400,
        )

    if not current_user.is_authenticated:
        return _json("로그인이 필요합니다.", False, 401)
    if not v19._is_admin():
        return _json("관리자 권한이 필요합니다.", False, 403)

    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or ""
    ).strip()
    handler = v19.HANDLERS.get(operation)
    if handler is None:
        return _json("지원하지 않는 업무구분 작업입니다.", False, 400)

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
    response.headers["X-MedPark-Admin-Category"] = "v38"
    response.headers["Cache-Control"] = "no-store"
    return response


core.csrf.exempt(admin_work_category_v38)


@core.app.get("/__health/admin-work-category-v38")
def admin_work_category_v38_health():
    return (
        "admin_work_category_route=v38 active=1 route=/api/admin/work-category-v38 csrf=manual",
        200,
        {"Cache-Control": "no-store"},
    )


@core.app.get("/__health/admin-work-category-v38-post")
def admin_work_category_v38_post_health():
    payload = urlencode({
        "operation": "rename_small",
        "work_category_id": "999999999",
        "new_small_name": "diagnostic-only",
    }).encode("utf-8")
    req = Request(
        PUBLIC_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "MedPark-V38-SelfTest/1.0",
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            marker = response.headers.get("X-MedPark-Admin-Category", "")
            preview = response.read(160).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        marker = exc.headers.get("X-MedPark-Admin-Category", "") if exc.headers else ""
        preview = exc.read(160).decode("utf-8", errors="replace")
    except Exception as exc:
        status = 0
        content_type = type(exc).__name__
        marker = ""
        preview = str(exc)
    return (
        f"post_status={status} post_type={content_type} marker={marker} preview={preview[:120]}",
        200,
        {"Cache-Control": "no-store"},
    )
