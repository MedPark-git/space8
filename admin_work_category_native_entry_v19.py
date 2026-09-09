import task_category_wsgi_guard as guard
import admin_work_category_task_new_v39  # noqa: F401 - handles administrator work-category writes inside the proven task_new POST view
import task_new_runtime_diag_v40  # noqa: F401 - temporary runtime routing diagnostic

app = guard.app
