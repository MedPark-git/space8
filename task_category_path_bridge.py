from urllib.parse import parse_qsl, urlencode

from flask import abort, request
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import task_category_runtime as runtime

flask_app = runtime.app

BRIDGED_PATHS = {"/task-categories", "/task-categories/"}
INTERNAL_FLAG = "__employee_task_categories"


def _serve_employee_task_categories_before_guards():
    if request.path != "/tasks/new" or request.args.get(INTERNAL_FLAG) != "1":
        return None

    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        try:
            validate_csrf(token)
        except ValidationError:
            abort(400)

    return runtime.employee_work_categories()


# Run this handler before the legacy menu/path access guards.  It only handles
# internally bridged /task-categories requests and leaves every other request untouched.
flask_app.before_request_funcs.setdefault(None, []).insert(
    0,
    _serve_employee_task_categories_before_guards,
)


class TaskCategoryPathBridge:
    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _append_internal_flag(environ):
        pairs = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        pairs = [(key, value) for key, value in pairs if key != INTERNAL_FLAG]
        pairs.append((INTERNAL_FLAG, "1"))
        environ["QUERY_STRING"] = urlencode(pairs)

    @staticmethod
    def _health(start_response):
        body = b"task_category_path_bridge=active"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-MedPark-Task-Category-Bridge", "1"),
            ],
        )
        return [body]

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""

        if path == "/__health/task-category-path-bridge":
            return self._health(start_response)

        if path in BRIDGED_PATHS:
            rewritten = environ.copy()
            rewritten["ORIGINAL_PATH_INFO"] = path
            rewritten["PATH_INFO"] = "/tasks/new"
            self._append_internal_flag(rewritten)
            return self.downstream(rewritten, start_response)

        return self.downstream(environ, start_response)


app = TaskCategoryPathBridge(flask_app.wsgi_app)
