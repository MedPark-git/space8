import task_category_wsgi_guard as guard
import admin_work_category_header_v34 as awc_v34

app = awc_v34.wrap(guard.app)
