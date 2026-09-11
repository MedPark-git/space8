"""SPACE8 startup customization.

V49 intentionally registers administrator work-category routes directly on the
core Flask application during interpreter startup. Cafe24 can launch the core
app without honoring the Procfile WSGI wrapper, so route registration must not
depend on the external entry module.
"""

import admin_work_category_routes_v49  # noqa: F401
