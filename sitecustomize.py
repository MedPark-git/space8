"""SPACE8 startup customization.

Register the administrator work-category API directly on the core Flask app.
The API uses one stable endpoint only: /admin/work-categories/manage.
"""

import admin_work_category_api  # noqa: F401
