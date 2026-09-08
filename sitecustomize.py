"""SPACE8 startup bootstrap.

Installed through the local editable package so Python discovers this module
at interpreter startup. It preloads the Flask app, then registers the admin
work-category CRUD modules against that same app instance.
"""

import sys

try:
    import app  # noqa: F401
    import admin_work_category_manager  # noqa: F401
    import admin_work_category_delete_manager  # noqa: F401
except Exception as exc:  # do not prevent the service from starting
    print(f"[space8 bootstrap] admin work-category registration failed: {exc!r}", file=sys.stderr)
