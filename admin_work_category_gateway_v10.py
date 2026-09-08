import io
import sys
from urllib.parse import parse_qs

from flask import request
from flask_login import current_user

import admin_work_category_entry as previous

flask_app = previous.flask_app
core = previous.core


class AdminWorkCategoryGatewayV10:
    """Direct CRUD gateway that tolerates missing CONTENT_LENGTH.

    Some reverse proxies forward browser POST requests as a terminated/chunked
    WSGI stream without a useful CONTENT_LENGTH. Older gateways treated that as
    an empty body, missed ``awc_operation``, and fell through to the normal admin
    HTML handler (HTTP 200). V10 reads the request stream even when the length is
    missing, restores the exact body with a concrete length, then executes CRUD.
    """

    OPERATIONS = {"add_middle", "add_small", "rename_middle", "rename_small", "delete"}

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _read_and_restore_body(environ):
        stream = environ.get("wsgi.input")
        if stream is None:
            body = b""
        else:
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except (TypeError, ValueError):
                length = 0

            # Normal WSGI request with a valid length.
            if length > 0:
                body = stream.read(length)
            else:
                # Gunicorn exposes a request-bounded stream for chunked / proxy
                # requests. Reading to EOF is safe here and is required when the
                # proxy omits CONTENT_LENGTH.
                body = stream.read()

        # Make the request body reusable by Flask-WTF and request.form. Setting
        # both a concrete length and input_terminated avoids a second empty read.
        environ["wsgi.input"] = io.BytesIO(body)
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input_terminated"] = True
        return body

    @staticmethod
    def _restore_body(environ, body):
        environ["wsgi.input"] = io.BytesIO(body)
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input_terminated"] = True

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v10":
            body = b"admin_work_category_gateway=v10 full-body direct-crud active"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        if method != "POST" or not path.startswith("/admin"):
            return self.downstream(environ, start_response)

        original_content_length = environ.get("CONTENT_LENGTH")
        original_terminated = environ.get("wsgi.input_terminated")
        raw_body = self._read_and_restore_body(environ)

        operation = ""
        try:
            payload = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
            operation = str(payload.get("awc_operation", [""])[0] or "").strip()
        except Exception:
            operation = ""

        if operation not in self.OPERATIONS:
            # This is an ordinary admin POST (employee, role, toggle, etc.). Pass
            # through with the exact buffered body so legacy behavior is unchanged.
            self._restore_body(environ, raw_body)
            return self.downstream(environ, start_response)

        # Runtime diagnostic is intentionally metadata-only: no form values.
        print(
            f"[awc-v10] intercepted path={path} operation={operation} "
            f"body_len={len(raw_body)} content_length={original_content_length!r} "
            f"input_terminated={original_terminated!r}",
            file=sys.stderr,
        )

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
                    form_operation = str(request.form.get("operation") or "").strip()
                    if form_operation != operation:
                        result = previous._json("업무구분 요청 값이 일치하지 않습니다.", False, 400)
                    else:
                        result = previous._handle_manage()
            except Exception as exc:
                core.db.session.rollback()
                print(
                    f"[awc-v10] CRUD failed: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                result = previous._json(
                    f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                    False,
                    500,
                )

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "v10-full-body"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategoryGatewayV10(previous.app)
