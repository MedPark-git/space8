import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - extends proven task-category WSGI for administrator delete

app = guard.app
