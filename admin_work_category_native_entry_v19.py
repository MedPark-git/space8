import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - replaces the actual POST /tasks/new view

# Export the Flask app directly. V44 handles administrator work-category writes
# in the actual /tasks/new view after normal CSRF processing.
app = guard.flask_app
