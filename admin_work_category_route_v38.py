from flask import jsonify, request
from flask_login import current_user

import admin_work_category_server_v19 as v19

core = v19.core
MARKER = "v38"
ROUTE = "/api/admin/work-category-v38"


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

    if (request.headers.get("X-MedPark-Admin-Category") or "").strip().lower() != MARKER:
        return _json("허용되지 않은 업무구분 요청입니다.", False, 403)
    if (request.headers.get("X-Requested-With") or "").strip().lower() != "xmlhttprequest":
        return _json("허용되지 않은 요청 형식입니다.", False, 403)

    if not current_user.is_authenticated:
        return _json("로그인이 필요합니다.", False, 401)
    if not v19._is_admin():
        return _json("관리자 권한이 필요합니다.", False, 403)

    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.headers.get("X-MedPark-Admin-Operation")
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
    response.headers["X-MedPark-Admin-Category"] = MARKER
    response.headers["Cache-Control"] = "no-store"
    return response


core.csrf.exempt(admin_work_category_v38)


@core.app.get("/__health/admin-work-category-v38")
def admin_work_category_v38_health():
    return (
        "admin_work_category_route=v38 active=1 route=/api/admin/work-category-v38",
        200,
        {"Cache-Control": "no-store"},
    )
