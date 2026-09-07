from flask import request
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import task_category_runtime as runtime

flask_app = runtime.app
TARGET_PATHS = {"/task-categories", "/task-categories/"}


def _text_response(start_response, status, text, content_type="text/html; charset=utf-8"):
    body = text.encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
    return [body]


class TaskCategoryEntry:
    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/task-category-entry":
            return _text_response(start_response, "200 OK", "task_category_entry=active", "text/plain; charset=utf-8")
        if path not in TARGET_PATHS:
            return self.downstream(environ, start_response)

        try:
            with flask_app.request_context(environ):
                if request.method == "POST":
                    token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
                    try:
                        validate_csrf(token)
                    except ValidationError:
                        return _text_response(start_response, "400 Bad Request", "<h1>요청 보안 검증에 실패했습니다.</h1><p>페이지를 새로고침한 후 다시 시도해 주세요.</p>")

                result = runtime.employee_work_categories()
                response = flask_app.make_response(result)
                response.headers["X-MedPark-Task-Category-Entry"] = "1"
                response = flask_app.process_response(response)
                return response(environ, start_response)
        except Exception as exc:
            return _text_response(start_response, "500 Internal Server Error", f"<h1>업무구분 화면 처리 중 오류가 발생했습니다.</h1><p>진단코드: {type(exc).__name__}</p>")


app = TaskCategoryEntry(flask_app.wsgi_app)
