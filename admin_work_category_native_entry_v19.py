import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy task_new view fallback
import admin_work_category_v45  # noqa: F401 - MUST stay last: first-hook category guard

# Export the real Flask app. V45 is registered last and inserted as the absolute
# first before_request hook, so category-management POSTs cannot fall through to
# the ordinary task-registration validator.
app = guard.flask_app
