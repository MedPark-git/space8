import task_category_wsgi_guard as guard
import admin_work_category_manager  # noqa: F401  # registers admin work-category routes/UI injection

app = guard.app
