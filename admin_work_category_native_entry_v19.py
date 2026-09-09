import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - extends proven WSGI category manager with administrator delete
import task_category_admin_probe_v40  # noqa: F401 - temporary public POST routing probe

app = guard.app
