import io

from flask import request
from flask_login import current_user

import admin_work_category_entry as previous

flask_app = previous.flask_app
core = previous.core


class AdminWorkCategoryBodyGatewayV7:
    """Proxy-proof admin work-category CRUD using POST body markers.

    The AI SPACE front proxy may normalize query strings and custom headers.
    V7 therefore identifies CRUD requests only by a hidden FormData field
    (awc_operation) on the already-working admin page path.  For ordinary admin
    POSTs, the buffered request body is restored untouched and passed through.
    """

    ADMIN_PATHS = {"/admin", "/admin/work-categories"}
    OPERATIONS = {"add_middle", "add_small", "rename_middle", "rename_small", "delete"}

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _buffer_body(environ):
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        stream = environ.get("wsgi.input")
        body = stream.read(length) if stream is not None and length > 0 else b""
        environ["wsgi.input"] = io.BytesIO(body)
        environ["CONTENT_LENGTH"] = str(len(body))
        return body

    @staticmethod
    def _restore_body(environ, body):
        environ["wsgi.input"] = io.BytesIO(body)
        environ["CONTENT_LENGTH"] = str(len(body))

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v7":
            body = b"admin_work_category_gateway=v7 body-marker direct-crud active"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        if method != "POST" or path not in self.ADMIN_PATHS:
            return self.downstream(environ, start_response)

        raw_body = self._buffer_body(environ)

        with flask_app.request_context(environ):
            operation = str(request.form.get("awc_operation") or "").strip()

        if operation not in self.OPERATIONS:
            self._restore_body(environ, raw_body)
            return self.downstream(environ, start_response)

        self._restore_body(environ, raw_body)
        with flask_app.request_context(environ):
            try:
                core.csrf.protect()
                if not current_user.is_authenticated:
                    result = previous._json("로그인이 필요합니다.", False, 401)
                elif not previous._is_admin():
                    result = previous._json("관리자 권한이 필요합니다.", False, 403)
                elif operation == "delete":
                    result = previous._handle_delete()
                else:
                    # Keep the existing direct CRUD implementation; mirror the
                    # marker to operation so the handler reads the intended task.
                    # FormData already includes operation, but V7 also accepts
                    # awc_operation as the authoritative value.
                    if str(request.form.get("operation") or "").strip() != operation:
                        result = previous._json("업무구분 요청 값이 일치하지 않습니다.", False, 400)
                    else:
                        result = previous._handle_manage()
            except Exception as exc:
                core.db.session.rollback()
                result = previous._json(
                    f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                    False,
                    500,
                )

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "v7-body-marker"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategoryBodyGatewayV7(previous.app)
