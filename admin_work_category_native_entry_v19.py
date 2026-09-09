import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - extends proven WSGI category manager with administrator delete

app = guard.app
