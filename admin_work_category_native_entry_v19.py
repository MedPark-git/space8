import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - wraps the actual POST /tasks/new route

# Export the real Flask app. V44 owns administrator work-category writes at the
# actual route view; no additional WSGI body readers or category middleware.
app = guard.flask_app
