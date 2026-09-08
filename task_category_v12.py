from flask import redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import task_category_wsgi_guard as guard

flask_app = guard.flask_app
DEDICATED_PATH = "/tasks/category-manager/v12"


def _plain(start_response, status, text):
    body = text.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-MedPark-Task-Category-V12", "direct"),
        ],
    )
    return [body]


def _dispatch_category_action():
    payload = guard._payload()
    action = str(
        request.form.get("category_action")
        or request.args.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or payload.get("category_action")
        or ""
    ).strip()
    handler = guard.HANDLERS.get(action)
    if handler is None:
        return guard._finish("지원하지 않는 업무구분 작업입니다.", False)
    return handler(payload)


class TaskCategoryV12Entry:
    """Serve the dedicated category endpoint before Flask URL routing.

    This deliberately avoids sharing /tasks/new with the legacy task form and
    also avoids depending on Flask route registration order in the runtime.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/task-category-v12-direct":
            return _plain(
                start_response,
                "200 OK",
                "task_category_v12=direct active; endpoint=/tasks/category-manager/v12",
            )

        if path != DEDICATED_PATH or method != "POST":
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                validate_csrf(
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
            except ValidationError:
                result = guard._finish(
                    "요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                    False,
                )
            else:
                if not current_user.is_authenticated:
                    result = redirect(url_for("login"))
                else:
                    result = _dispatch_category_action()

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Task-Category-V12"] = "direct"
            response.headers["X-Task-Category-Dispatch"] = "v12-direct"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = TaskCategoryV12Entry(guard.app)
