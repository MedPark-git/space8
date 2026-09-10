import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - patch the actual POST /tasks/new view

# Export the real Flask app. Administrator work-category writes are handled by
# the actual task_new view; do not stack additional WSGI wrappers around it.
app = guard.flask_app
