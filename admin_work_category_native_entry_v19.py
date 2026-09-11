import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy /tasks/new fallback
import admin_work_category_server_v19  # noqa: F401 - dedicated /admin/work-categories/manage API
import admin_work_category_v46_selftest  # noqa: F401 - temporary startup no-op validation

# Export the real Flask app. Administrator work-category CRUD uses the dedicated
# v19 API path. The v46 selftest is temporary and performs a no-op rename using
# the same name, so it validates routing/JSON/CSRF without changing DB data.
app = guard.flask_app
