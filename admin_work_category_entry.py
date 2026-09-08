from flask import request

import task_category_wsgi_guard as guard
import admin_work_category_manager  # noqa: F401
import admin_work_category_delete_manager  # noqa: F401

flask_app = guard.flask_app


class AdminWorkCategoryGateway:
    """Serve admin work-category CRUD before Flask routing.

    This protects the admin category manager from runtime route-registration
    drift and guarantees the two JSON endpoints used by the admin UI.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v3":
            body = b"admin_work_category_gateway=v3 active"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        target = None
        if method == "POST" and path == "/admin/work-categories/manage":
            target = admin_work_category_manager.admin_work_category_manage
        elif method == "POST" and path == "/admin/work-categories/delete-v2":
            target = admin_work_category_delete_manager.admin_work_category_delete_v2

        if target is None:
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                import app as core
                core.csrf.protect()
                result = target()
            except Exception as exc:
                response = flask_app.handle_exception(exc)
            else:
                response = flask_app.make_response(result)

            response.headers["X-MedPark-Admin-Work-Category"] = "v3"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategoryGateway(guard.app)
