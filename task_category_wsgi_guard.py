from urllib.parse import parse_qs

from flask import redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import task_editor_runtime as runtime

flask_app = runtime.FLASK_APP
TARGET_PATH = "/tasks/new"
TRANSPORT = "v9"


def _text_response(start_response, status, text):
    body = text.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-MedPark-Task-Category-WSGI", "v10"),
        ],
    )
    return [body]


class TaskCategoryWSGIGuard:
    """Handle category-manager POSTs before the legacy /tasks/new task validator."""

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _is_target(environ):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        if path != TARGET_PATH or (environ.get("REQUEST_METHOD") or "GET").upper() != "POST":
            return False
        query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
        return (
            query.get("category_manager", [""])[-1] == "1"
            and query.get("category_transport", [""])[-1] == TRANSPORT
        )

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/task-category-wsgi-v10":
            return _text_response(start_response, "200 OK", "task_category_wsgi_guard=v10 active")

        if not self._is_target(environ):
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                validate_csrf(
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
            except ValidationError:
                result = runtime._redirect_manager(
                    "요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                    "error",
                )
            else:
                if not current_user.is_authenticated:
                    result = redirect(url_for("login"))
                else:
                    action = str(request.args.get("category_action") or "").strip()
                    handler = runtime.CATEGORY_HANDLERS.get(action)
                    if handler is None:
                        result = runtime._redirect_manager(
                            "지원하지 않는 업무구분 작업입니다.",
                            "error",
                        )
                    else:
                        result = handler()

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Task-Category-WSGI"] = "v10"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = TaskCategoryWSGIGuard(flask_app.wsgi_app)
