from io import BytesIO
import http.client
from urllib.parse import parse_qs, urlencode

from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core
MARKER = "v41"
PUBLIC_HOST = "medprk-management-task.mycafe24.ai"


class AdminWorkCategoryBodyV41:
    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _restore_body(environ, raw):
        environ["wsgi.input"] = BytesIO(raw)
        environ["CONTENT_LENGTH"] = str(len(raw))
        # Werkzeug must not keep an old cached input object after restoration.
        environ.pop("werkzeug.request", None)

    @staticmethod
    def _candidate(environ):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        content_type = (environ.get("CONTENT_TYPE") or "").lower()
        return method == "POST" and content_type.startswith("application/x-www-form-urlencoded")

    @staticmethod
    def _text(start_response, text, status="200 OK"):
        body = text.encode("utf-8")
        start_response(
            status,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]

    @staticmethod
    def _read_body(environ):
        """Read the full request body even when Cafe24/Gunicorn omits CONTENT_LENGTH.

        Browser/proxy POSTs may arrive chunked. The previous implementation treated
        missing CONTENT_LENGTH as an empty body and then replaced wsgi.input with
        b"", which caused the request to fall through to normal task validation.
        Gunicorn's request body stream is request-bounded, so read() without a size
        safely consumes the current request body when Content-Length is absent.
        """
        stream = environ.get("wsgi.input")
        if stream is None:
            return b""
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0

        if length > 0:
            return stream.read(length)

        # Transfer-Encoding: chunked / input_terminated requests commonly have no
        # CONTENT_LENGTH. Gunicorn presents a bounded stream that reaches EOF at
        # the end of this request.
        try:
            return stream.read()
        except Exception:
            return None

    def _self_test_chunked(self, start_response):
        payload = urlencode(
            {
                "awc_admin": MARKER,
                "operation": "rename_small",
                "awc_operation": "rename_small",
                "work_category_id": "999999999",
                "new_small_name": "diagnostic-only",
            }
        ).encode("utf-8")
        status = 0
        content_type = ""
        marker = ""
        preview = ""
        try:
            connection = http.client.HTTPSConnection(PUBLIC_HOST, timeout=10)
            # Iterable body + encode_chunked=True intentionally sends no
            # Content-Length, reproducing the browser/proxy case that failed.
            connection.request(
                "POST",
                "/tasks/new",
                body=[payload],
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": "MedPark-V41-Chunked-SelfTest/1.0",
                },
                encode_chunked=True,
            )
            response = connection.getresponse()
            status = response.status
            content_type = response.getheader("Content-Type", "")
            marker = response.getheader("X-MedPark-Admin-Work-Category", "")
            preview = response.read(180).decode("utf-8", errors="replace")
            connection.close()
        except Exception as exc:
            preview = f"{type(exc).__name__}: {exc}"

        ok = (
            status == 400
            and "application/json" in content_type.lower()
            and marker == "body-v41"
        )
        text = (
            f"ok={int(ok)} status={status} type={content_type} "
            f"marker={marker} preview={preview[:100]}"
        )
        return self._text(start_response, text, "200 OK" if ok else "500 Internal Server Error")

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/admin-work-category-v41":
            return self._text(start_response, "admin_work_category_body=v41 active=1 body_read=chunked-safe")
        if path == "/__health/admin-work-category-v41-chunked-post":
            return self._self_test_chunked(start_response)

        if not self._candidate(environ):
            return self.downstream(environ, start_response)

        raw = self._read_body(environ)
        # If the body cannot be read, do not replace the original stream with an
        # empty one. Let the existing application handle the request untouched.
        if raw is None:
            return self.downstream(environ, start_response)

        self._restore_body(environ, raw)
        try:
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        except Exception:
            return self.downstream(environ, start_response)

        marker = (parsed.get("awc_admin") or [""])[-1]
        operation = (parsed.get("operation") or parsed.get("awc_operation") or [""])[-1]
        if marker != MARKER or operation not in v19.HANDLERS:
            # Restore the exact bytes before handing off to the normal app.
            self._restore_body(environ, raw)
            return self.downstream(environ, start_response)

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
