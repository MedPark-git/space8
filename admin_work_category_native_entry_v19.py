from werkzeug.test import Client
from werkzeug.wrappers import Response

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy task_new view fallback
import admin_work_category_server_v19  # noqa: F401 - legacy dedicated Flask API
import admin_work_category_v45  # noqa: F401 - stale-client /tasks/new category guard
import admin_work_category_wsgi_v48 as transport_v48

# Production entrypoint. V48 wraps the actual Flask WSGI application, so the
# dedicated administrator work-category endpoint is handled before Flask route
# matching and cannot fall through to a 404 URL-map response.
flask_app = guard.flask_app
app = transport_v48.wrap(flask_app)

# Startup invariant: fail deployment if Gunicorn's exported WSGI object is not
# actually serving the V48 transport. This probe is read-only and has no DB write.
_probe = Client(app, Response).get(transport_v48.HEALTH_PATH)
if _probe.status_code != 200 or _probe.headers.get("X-MedPark-Admin-Work-Category") != "wsgi-v48":
    raise RuntimeError(
        "admin work category v48 transport is not active: "
        f"status={_probe.status_code} marker={_probe.headers.get('X-MedPark-Admin-Work-Category')}"
    )
