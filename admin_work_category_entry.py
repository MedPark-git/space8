import task_category_wsgi_guard as guard
import admin_work_category_manager  # noqa: F401  # registers admin work-category routes/UI injection
import admin_work_category_delete_manager  # noqa: F401  # safe delete endpoint for unused categories

app = guard.app
