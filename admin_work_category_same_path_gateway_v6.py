from urllib.parse import parse_qs

from flask import request
from flask_login import current_user

import admin_work_category_entry as previous

flask_app = previous.flask_app
core = previous.core


class AdminWorkCategorySamePathGatewayV6:
    """Proxy-safe admin work-category CRUD on the current admin page path.

    V6 deliberately does not depend on custom HTTP headers because the AI SPACE
    front proxy may drop them.  The request is identified only by ordinary query
    parameters (awc=1 + operation=...), which are preserved by the proxy.
    Both known admin page paths are accepted.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v6":
            body = b"admin_work_category_gateway=v6 query-marker direct-crud active"
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
        operation = str(query.get("operation", [""])[0] or "").strip()
        is_admin_path = path in {"/admin", "/admin/work-categories"}
        is_target = (
            method == "POST"
            and is_admin_path
            and query.get("awc", [""])[0] == "1"
            and operation in {
                "add_middle",
                "add_small",
                "rename_middle",
                "rename_small",
                "delete",
            }
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
                elif operation == "delete":
                    result = previous._handle_delete()
                else:
                    # The direct CRUD handler reads the concrete values from
                    # request.form; operation is mirrored into the form by the
                    # browser bridge, so no Flask route lookup is involved.
                    result = previous._handle_manage()
            except Exception as exc:
                core.db.session.rollback()
                result = previous._json(
                    f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})",
                    False,
                    500,
                )

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "v6-query-marker"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategorySamePathGatewayV6(previous.app)
