import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - adds administrator delete handler
import admin_work_category_runtime_v42  # noqa: F401 - patches the first Flask category hook

# Export the Flask app directly.  Do not stack extra WSGI body readers around
# /tasks/new; the first Flask before_request owns all category-manager writes.
app = guard.flask_app
