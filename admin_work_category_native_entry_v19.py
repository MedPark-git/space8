import task_category_wsgi_guard as guard
import admin_work_category_header_v34 as awc_v34
import admin_route_source_probe_v35  # noqa: F401 - temporary runtime source inspection

app = awc_v34.wrap(guard.app)
