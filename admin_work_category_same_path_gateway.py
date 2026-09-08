from urllib.parse import parse_qs

from flask import request
from flask_login import current_user

import admin_work_category_entry as previous

flask_app = previous.flask_app
core = previous.core


class AdminWorkCategorySamePathGateway:
    """Handle admin work-category CRUD on the already-working /admin page path.

    Browser requests are identified by X-MedPark-Admin-Work-Category: v5 so
    ordinary admin POSTs such as toggle/reactivate continue through the legacy
    Flask admin handler unchanged.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v5":
            body = b"admin_work_category_gateway=v5 same-admin-path active"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
        is_target = (
            method == "POST"
            and path == "/admin"
            and query.get("section", [""])[0] == "work-categories"
            and environ.get("HTTP_X_MEDPARK_ADMIN_WORK_CATEGORY") == "v5"
        )
        if not is_target:
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                core.csrf.protect()
                if not current_user.is_authenticated:
                    result = previous._json("로그인이 필요합니다.", False, 401)
                elif not previous._is_admin():
                    result = previous._json("관리자 권한이 필요합니다.", False, 403)
                else:
                    operation = str(request.form.get("operation") or "").strip()
                    if operation == "delete":
                        result = previous._handle_delete()
                    elif operation in {
                        "add_middle",
                        "add_small",
                        "rename_middle",
                        "rename_small",
                    }:
                        result = previous._handle_manage()
                    else:
                        result = previous._json("지원하지 않는 업무구분 작업입니다.", False, 400)
            except Exception as exc:
                core.db.session.rollback()
                result = previous._json(
                    f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                    False,
                    500,
                )

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "v5-same-path"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategorySamePathGateway(previous.app)
