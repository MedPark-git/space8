"""Startup bootstrap for SPACE8 admin work-category routes.

Python imports sitecustomize automatically during interpreter startup when the
project root is on sys.path. Importing these modules here guarantees that the
admin work-category CRUD routes are registered even when the runtime entrypoint
changes or bypasses Procfile wrappers.
"""

try:
    import admin_work_category_manager  # noqa: F401
    import admin_work_category_delete_manager  # noqa: F401
except Exception:
    pass
