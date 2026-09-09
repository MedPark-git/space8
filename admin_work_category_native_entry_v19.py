import task_category_wsgi_guard as guard
import admin_work_category_server_v22  # noqa: F401 - legacy fallback for existing administrator work-category requests
import admin_work_category_wsgi_v30 as awc_v30

app = awc_v30.wrap(guard.app)
