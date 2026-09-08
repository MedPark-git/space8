import task_category_wsgi_guard as guard
import admin_work_category_flask_hook_v11  # noqa: F401 - registers Flask before_request hook

app = guard.app
