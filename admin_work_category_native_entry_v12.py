import task_category_wsgi_guard as guard
import admin_work_category_native_hook_v12  # noqa: F401 - registers native Flask before_request handler

app = guard.app
