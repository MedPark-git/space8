import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - extends proven task-category WSGI for administrator delete
import task_category_admin_probe_v33  # noqa: F401 - temporary public POST self-test

app = guard.app
