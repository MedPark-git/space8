import task_category_wsgi_guard as guard
import admin_work_category_api_v24  # noqa: F401 - dedicated admin work-category JSON API
import admin_work_category_diag_v24  # noqa: F401 - safe runtime diagnostic route

app = guard.app
