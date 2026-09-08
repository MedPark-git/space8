"""SPACE8 startup customization.

Legacy admin work-category auto-registration has been retired.

Previous versions imported ``admin_work_category_manager`` and
``admin_work_category_delete_manager`` automatically during interpreter startup.
That caused old routes / after_request script injection to coexist with the
current administrator work-category UI.  V17 intentionally performs no imports
here; the active runtime is registered explicitly by the Procfile entry module.
"""

# Intentionally empty.  Keep this module harmless because the project is
# installed editable and Python may import sitecustomize automatically.
