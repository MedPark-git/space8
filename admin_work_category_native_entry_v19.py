import task_category_wsgi_guard as guard
import admin_work_category_route_v38  # noqa: F401 - dedicated administrator work-category API on normal /api path
import runtime_post_diag_v38  # noqa: F401 - temporary runtime POST diagnostic

app = guard.app
