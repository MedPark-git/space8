import task_category_wsgi_guard as guard
import admin_work_category_server_v22  # noqa: F401 - stable administrator work-category dispatch
import admin_work_category_api_v24  # noqa: F401 - dedicated JSON API outside /admin
import admin_work_category_diag_v24  # noqa: F401 - safe runtime diagnostic route
import external_post_probe_v26  # noqa: F401 - safe public POST routing diagnostic

app = guard.app
