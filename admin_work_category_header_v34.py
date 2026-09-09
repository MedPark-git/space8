from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core
MARKER = "v34"
PUBLIC_BASE = "https://medprk-management-task.mycafe24.ai"


class AdminWorkCategoryHeaderV34:
    """Intercept admin work-category writes by an explicit request header."""

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _is_target(environ):
        return (
            (environ.get("REQUEST_METHOD") or "GET").upper() == "POST"
            and (environ.get("HTTP_X_MEDPARK_ADMIN_CATEGORY") or "").strip().lower() == MARKER
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
        payload = urlencode(
            {
                "operation": "rename_small",
                "work_category_id": "999999999",
                "new_small_name": "diagnostic-only",
                "awc_source": "v34-self-test",
                "awc_response": "json",
            }
        ).encode("utf-8")
        req = Request(
            PUBLIC_BASE + "/admin?section=work-categories&awc_admin=v34",
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "X-MedPark-Admin-Category": MARKER,
                "X-MedPark-Admin-Operation": "rename_small",
                "User-Agent": "MedPark-AISpace-V34-SelfTest/1.0",
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

        return self._text(
            start_response,
            f"status={status} type={content_type} marker={marker} preview={preview[:100]}",
        )

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/admin-work-category-v34":
            return self._text(start_response, "admin_work_category_header=v34 active=1")
        if path == "/__health/admin-work-category-v34-post":
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
                    operation = str(
                        request.headers.get("X-MedPark-Admin-Operation")
                        or request.form.get("operation")
                        or request.form.get("awc_operation")
                        or ""
                    ).strip()
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
            response.headers["X-MedPark-Admin-Category"] = MARKER
            response.headers["Cache-Control"] = "no-store"
            return response(environ, start_response)


def wrap(downstream):
    return AdminWorkCategoryHeaderV34(downstream)
