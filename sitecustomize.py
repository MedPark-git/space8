"""SPACE8 startup customization.

Register the administrator work-category API directly on the core Flask app.
The API uses one stable endpoint only: /admin/work-categories/manage.
"""

import admin_work_category_api as work_category_api

_rules = {rule.rule for rule in work_category_api.app.url_map.iter_rules()}
if work_category_api.API_PATH not in _rules:
    raise RuntimeError(
        f"work-category API route registration failed: {work_category_api.API_PATH}"
    )
