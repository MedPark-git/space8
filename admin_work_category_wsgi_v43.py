from flask import request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - ensure administrator delete handler exists

core = guard.core
MARKER = "v43"
TARGET_PATH = "/tasks/new"


class AdminWorkCategoryWSGIV43:
    """Intercept administrator work-category writes inside Flask.app.wsgi_app.

    Identification uses only PATH_INFO + query parameters, before Flask route
    dispatch. Request body parsing is left to Flask/Werkzeug inside a normal
    request context, so this middleware never consumes or rewrites wsgi.input.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _is_target(environ):
        if (environ.get("REQUEST_METHOD") or "GET").upper() != "POST":
            return False
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        if path != TARGET_PATH:
            return False
        from urllib.parse import parse_qs
        query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
        return (query.get("awc_admin") or [""])[-1] == MARKER

    def __call__(self, environ, start_response):
        if not self._is_target(environ):
            return self.downstream(environ, start_response)

        with core.app.request_context(environ):
            action = str(
                request.args.get("category_action")
                or request.form.get("category_action")
                or request.headers.get("X-Task-Category-Action")
                or ""
            ).strip()
            if action not in guard.HANDLERS:
                operation = str(
                    request.form.get("operation")
                    or request.form.get("awc_operation")
                    or ""
                ).strip()
                action = {
                    "add_middle": "add",
                    "add_small": "add",
                    "rename_middle": "rename_middle",
                    "rename_small": "rename_small",
                    "delete": "delete",
                }.get(operation, "")

            try:
                validate_csrf(
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
            except ValidationError:
                result = guard._finish(
                    "요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
                    False,
                    status=400,
                )
            else:
                if not current_user.is_authenticated:
                    result = guard._finish("로그인이 필요합니다.", False, status=401)
                elif not guard._is_admin():
                    result = guard._finish("관리자 권한이 필요합니다.", False, status=403)
                elif action not in guard.HANDLERS:
                    result = guard._finish("지원하지 않는 업무구분 작업입니다.", False, status=400)
                else:
                    payload = guard._payload()
                    try:
                        result = guard.HANDLERS[action](payload)
                    except Exception as exc:
                        core.db.session.rollback()
                        result = guard._finish(
                            f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                            False,
                            status=500,
                        )

            response = core.app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "wsgi-v43"
            response.headers["Cache-Control"] = "no-store"
            response = core.app.process_response(response)
            return response(environ, start_response)


def install():
    current = core.app.wsgi_app
    if isinstance(current, AdminWorkCategoryWSGIV43):
        return current
    wrapped = AdminWorkCategoryWSGIV43(current)
    core.app.wsgi_app = wrapped
    return wrapped


installed = install()


@core.app.get("/__health/admin-work-category-v43")
def admin_work_category_v43_health():
    return {
        "ok": True,
        "transport": "admin-work-category-v43",
        "installed_on_flask_wsgi_app": isinstance(core.app.wsgi_app, AdminWorkCategoryWSGIV43),
        "handlers": sorted(guard.HANDLERS),
    }
