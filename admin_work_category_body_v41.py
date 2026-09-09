from io import BytesIO
from urllib.parse import parse_qs

from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core
MARKER = "v41"


class AdminWorkCategoryBodyV41:
    """Intercept admin work-category writes by POST body marker, not URL/header.

    Cafe24's proxy has shown inconsistent behavior for custom POST paths,
    query-string dispatch and custom headers. The form body itself reliably
    reaches the application, so V41 identifies only URL-encoded requests that
    contain awc_admin=v41 and a supported operation. The original body is
    restored before creating Flask's request context or delegating downstream.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _restore_body(environ, raw):
        environ["wsgi.input"] = BytesIO(raw)
        environ["CONTENT_LENGTH"] = str(len(raw))

    @staticmethod
    def _candidate(environ):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        content_type = (environ.get("CONTENT_TYPE") or "").lower()
        return method == "POST" and content_type.startswith("application/x-www-form-urlencoded")

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/admin-work-category-v41":
            body = b"admin_work_category_body=v41 active=1"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        if not self._candidate(environ):
            return self.downstream(environ, start_response)

        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        self._restore_body(environ, raw)

        try:
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        except Exception:
            return self.downstream(environ, start_response)

        marker = (parsed.get("awc_admin") or [""])[-1]
        operation = (parsed.get("operation") or parsed.get("awc_operation") or [""])[-1]
        if marker != MARKER or operation not in v19.HANDLERS:
            return self.downstream(environ, start_response)

        # Restore once more because Flask will parse request.form below.
        self._restore_body(environ, raw)
        with core.app.request_context(environ):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                result = v19._json(
                    "요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
                    False,
                    400,
                )
            else:
                if not current_user.is_authenticated:
                    result = v19._json("로그인이 필요합니다.", False, 401)
                elif not v19._is_admin():
                    result = v19._json("관리자 권한이 필요합니다.", False, 403)
                else:
                    handler = v19.HANDLERS.get(operation)
                    if handler is None:
                        result = v19._json("지원하지 않는 업무구분 작업입니다.", False, 400)
                    else:
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
            response.headers["X-MedPark-Admin-Work-Category"] = "body-v41"
            response.headers["Cache-Control"] = "no-store"
            return response(environ, start_response)


def wrap(downstream):
    return AdminWorkCategoryBodyV41(downstream)
