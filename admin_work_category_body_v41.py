from io import BytesIO
from urllib.parse import parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from werkzeug.wsgi import get_input_stream

import admin_work_category_server_v19 as v19

core = v19.core
MARKER = "v41"
TARGET_PATH = "/tasks/new"
PUBLIC_BASE = "https://medprk-management-task.mycafe24.ai"


class AdminWorkCategoryBodyV41:
    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _restore_body(environ, raw):
        environ["wsgi.input"] = BytesIO(raw)
        environ["CONTENT_LENGTH"] = str(len(raw))

    @staticmethod
    def _candidate(environ):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        return method == "POST" and path == TARGET_PATH

    @staticmethod
    def _text(start_response, text, status="200 OK"):
        body = text.encode("utf-8")
        start_response(status,[
            ("Content-Type","text/plain; charset=utf-8"),
            ("Content-Length",str(len(body))),
            ("Cache-Control","no-store"),
        ])
        return [body]

    @staticmethod
    def _read_body(environ):
        try:
            stream = get_input_stream(environ, safe_fallback=True)
            raw = stream.read()
            return raw if isinstance(raw, (bytes, bytearray)) else bytes(raw or b"")
        except Exception:
            return None

    def _self_test(self, start_response):
        raw = b"awc_admin=v41&operation=rename_small&awc_operation=rename_small&work_category_id=999999999&new_small_name=diagnostic"
        req = Request(
            PUBLIC_BASE + TARGET_PATH,
            data=raw,
            method="POST",
            headers={
                "Accept":"application/json",
                "Content-Type":"text/plain; charset=UTF-8",
                "User-Agent":"MedPark-V41-ContentType-Probe/1.0",
            },
        )
        try:
            with urlopen(req, timeout=10) as response:
                status = response.status
                content_type = response.headers.get("Content-Type","")
                marker = response.headers.get("X-MedPark-Admin-Work-Category","")
                preview = response.read(120).decode("utf-8",errors="replace")
        except HTTPError as exc:
            status = exc.code
            content_type = exc.headers.get("Content-Type","") if exc.headers else ""
            marker = exc.headers.get("X-MedPark-Admin-Work-Category","") if exc.headers else ""
            preview = exc.read(120).decode("utf-8",errors="replace")
        except Exception as exc:
            status = 0
            content_type = type(exc).__name__
            marker = ""
            preview = str(exc)

        ok = status == 400 and "application/json" in content_type.lower() and marker == "body-v41"
        return self._text(
            start_response,
            f"ok={int(ok)} status={status} type={content_type} marker={marker} preview={preview[:80]}",
            "200 OK" if ok else "500 Internal Server Error",
        )

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/admin-work-category-v41":
            return self._text(start_response,"admin_work_category_body=v41 active=1 candidate=all-post-tasks-new reader=werkzeug")
        if path == "/__health/admin-work-category-v41-contenttype-post":
            return self._self_test(start_response)

        if not self._candidate(environ):
            return self.downstream(environ, start_response)

        raw = self._read_body(environ)
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
            self._restore_body(environ, raw)
            return self.downstream(environ, start_response)

        self._restore_body(environ, raw)
        with core.app.request_context(environ):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                result = v19._json("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",False,400)
            else:
                if not current_user.is_authenticated:
                    result = v19._json("로그인이 필요합니다.",False,401)
                elif not v19._is_admin():
                    result = v19._json("관리자 권한이 필요합니다.",False,403)
                else:
                    handler = v19.HANDLERS.get(operation)
                    if handler is None:
                        result = v19._json("지원하지 않는 업무구분 작업입니다.",False,400)
                    else:
                        try:
                            result = handler()
                        except Exception as exc:
                            core.db.session.rollback()
                            result = v19._json(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",False,500)

            response = core.app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "body-v41"
            response.headers["Cache-Control"] = "no-store"
            return response(environ, start_response)


def wrap(downstream):
    return AdminWorkCategoryBodyV41(downstream)
