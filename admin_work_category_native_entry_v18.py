import task_category_wsgi_guard as guard
import admin_work_category_before_request_v18  # noqa: F401 - registers first Flask before_request handler

app = guard.app
