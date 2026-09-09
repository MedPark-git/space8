import task_category_wsgi_guard as guard
import admin_view_work_category_v36  # noqa: F401 - V36 classifies work-category writes from query before form parsing

app = guard.app
