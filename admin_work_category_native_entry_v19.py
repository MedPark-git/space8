import task_category_wsgi_guard as guard
import admin_work_category_server_v19  # noqa: F401 - native administrator work-category handler
import admin_work_category_native_v32  # noqa: F401 - query operation detection + canonical redirect

app = guard.app
