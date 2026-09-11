import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy /tasks/new fallback
import admin_work_category_server_v19  # noqa: F401 - dedicated /admin/work-categories/manage API

# Export the real Flask app. Administrator work-category CRUD uses the dedicated
# v19 API path. V44 stays loaded only as a legacy fallback for stale clients.
app = guard.flask_app
