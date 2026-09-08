import task_category_wsgi_guard as guard

flask_app = guard.flask_app


@flask_app.after_request
def strip_legacy_admin_work_category_script(response):
    """Keep only the directly loaded V2 admin category UI.

    The legacy manager injects V1 dynamically. V2 is loaded from base.html, so
    remove the legacy injected tag after it has been added to avoid duplicate
    dialogs/events and stale REDACTED option markup.
    """
    if response.status_code == 200 and response.mimetype.startswith("text/html"):
        html = response.get_data(as_text=True)
        legacy = '<script src="/static/admin_work_category_manager_v1.js?v=20260908-admin-work-category-v1" defer></script>'
        if legacy in html:
            html = html.replace(legacy, "")
            response.set_data(html)
            response.headers["Content-Length"] = str(len(response.get_data()))
    return response


import admin_work_category_manager  # noqa: E402,F401
import admin_work_category_delete_manager  # noqa: E402,F401


class AdminWorkCategoryGateway:
    """Serve admin work-category CRUD before Flask routing."""

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
