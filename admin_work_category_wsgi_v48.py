from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as api

flask_app = api.core.app
TARGET_PATH = "/admin/work-categories/manage-v48"
LEGACY_PATH = "/admin/work-categories/manage"
TARGET_PATHS = {TARGET_PATH, LEGACY_PATH}
HEALTH_PATH = "/__health/admin-work-category-v48"
MARKER = "wsgi-v48"


class AdminWorkCategoryWSGIV48:
    """Handle administrator work-category CRUD before Flask URL routing.

    Both the new V48 path and the previous dedicated path are intercepted here,
    so stale browser tabs cannot fall through to a Flask 404.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _text(start_response, text, status="200 OK"):
        body = text.encode("utf-8")
        start_response(
            status,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-MedPark-Admin-Work-Category", MARKER),
            ],
        )
        return [body]

    @staticmethod
    def _json_response(result, environ, start_response):
        response = flask_app.make_response(result)
        response.headers["X-MedPark-Admin-Work-Category"] = MARKER
        response.headers["Cache-Control"] = "no-store"
        response = flask_app.process_response(response)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == HEALTH_PATH:
            return self._text(
                start_response,
                "admin_work_category_wsgi=v48 active=1 targets=" + ",".join(sorted(TARGET_PATHS)),
            )

        if path not in TARGET_PATHS:
            return self.downstream(environ, start_response)

        if method != "POST":
            with flask_app.request_context(environ):
                return self._json_response(
                    api._json("POST 요청만 허용됩니다.", False, 405),
                    environ,
                    start_response,
                )

        with flask_app.request_context(environ):
            token = (
                request.form.get("csrf_token")
                or request.headers.get("X-CSRFToken")
                or request.headers.get("X-CSRF-Token")
            )
            try:
                validate_csrf(token)
            except ValidationError:
                result = api._json(
                    "요청 보안 검증에 실패했습니다. 관리자 화면을 새로고침한 뒤 다시 시도해 주세요.",
                    False,
                    400,
                )
            else:
                if not current_user.is_authenticated:
                    result = api._json("로그인이 필요합니다.", False, 401)
                elif not api._is_admin():
                    result = api._json("관리자 권한이 필요합니다.", False, 403)
                else:
                    operation = str(
                        request.form.get("operation")
                        or request.form.get("awc_operation")
                        or ""
                    ).strip()
                    handler = api.HANDLERS.get(operation)
                    if handler is None:
                        result = api._json("지원하지 않는 업무구분 작업입니다.", False, 400)
                    else:
                        try:
                            result = handler()
                        except Exception as exc:
                            api.core.db.session.rollback()
                            result = api._json(
                                f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                                False,
                                500,
                            )

            return self._json_response(result, environ, start_response)


def wrap(downstream):
    return AdminWorkCategoryWSGIV48(downstream)
