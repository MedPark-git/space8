import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - keeps administrator delete handler available
import admin_work_category_body_v41 as awc_v41

app = awc_v41.wrap(guard.app)
