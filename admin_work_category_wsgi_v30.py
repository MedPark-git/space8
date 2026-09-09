from urllib.parse import parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core
PUBLIC_BASE = "https://medprk-management-task.mycafe24.ai"


class AdminWorkCategoryWSGIV30:
    """Handle administrator work-category writes before Flask's global POST/CSRF flow."""

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _is_target(environ):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        if path != "/admin" or method != "POST":
            return False
        query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
        return (
            query.get("section", [""])[-1] == "work-categories"
            and query.get("awc_transport", [""])[-1] == "v30"
        )

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

    def _self_test(self, start_response):
        url = PUBLIC_BASE + "/admin?section=work-categories&awc_transport=v30"
        payload = urlencode(
            {
                "operation": "rename_small",
                "work_category_id": "999999999",
                "new_small_name": "diagnostic-only",
                "awc_source": "v30-self-test",
                "awc_response": "json",
            }
        ).encode("utf-8")
        req = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "MedPark-AISpace-WSGI-V30-SelfTest/1.0",
            },
        )
        try:
            with urlopen(req, timeout=10) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                marker = response.headers.get("X-MedPark-Admin-Work-Category", "")
                preview = response.read(180).decode("utf-8", errors="replace")
        except HTTPError as exc:
            status = exc.code
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            marker = exc.headers.get("X-MedPark-Admin-Work-Category", "") if exc.headers else ""
            preview = exc.read(180).decode("utf-8", errors="replace")
        except Exception as exc:
            status = 0
            content_type = type(exc).__name__
            marker = ""
            preview = str(exc)

        text = (
            f"status={status} type={content_type} marker={marker} "
            f"preview={preview[:120]}"
        )
        return self._text(start_response, text)

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/admin-work-category-wsgi-v30":
            return self._text(start_response, "admin_work_category_wsgi=v30 active=1")
        if path == "/__health/admin-work-category-wsgi-v30-post":
            return self._self_test(start_response)

        if not self._is_target(environ):
            return self.downstream(environ, start_response)

        with core.app.request_context(environ):
            try:
                validate_csrf(
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
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
                    operation = str(request.form.get("operation") or "").strip()
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
            response.headers["X-MedPark-Admin-Work-Category"] = "wsgi-v30"
            response.headers["Cache-Control"] = "no-store"
            response = core.app.process_response(response)
            return response(environ, start_response)


def wrap(downstream):
    return AdminWorkCategoryWSGIV30(downstream)
