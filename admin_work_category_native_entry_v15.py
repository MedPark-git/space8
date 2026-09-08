import task_category_wsgi_guard as guard
import admin_work_category_admin_view_v15  # noqa: F401 - wraps existing Flask admin endpoint

app = guard.app
