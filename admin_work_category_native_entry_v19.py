import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy task_new view fallback
import admin_work_category_server_v19  # noqa: F401 - dedicated /admin/work-categories/manage API
import admin_work_category_v45  # noqa: F401 - stale-client /tasks/new category guard; keep last

# Primary path: administrator work-category CRUD uses the dedicated v19 API.
# Compatibility path: V45 stays last so already-open/stale V42 pages posting to
# /tasks/new are intercepted before ordinary task-registration validation.
app = guard.flask_app
