"""SPACE8 runtime bootstrap.

The project is installed editable (``-e .``), so Python imports this module at
interpreter startup.  Do not import ``app`` here directly: doing so during the
site initialization phase can create a circular/partial import and silently
prevent the admin work-category routes from being registered.

Instead, wrap Python's import function very briefly.  When the *real* ``app``
module has finished importing, attach the admin work-category modules to that
fully initialized Flask app, then restore the original import function.
"""

import builtins
import sys

_ORIGINAL_IMPORT = builtins.__import__
_BOOTSTRAP_RUNNING = False
_BOOTSTRAP_DONE = False


def _register_admin_work_category_modules():
    global _BOOTSTRAP_RUNNING, _BOOTSTRAP_DONE

    if _BOOTSTRAP_DONE or _BOOTSTRAP_RUNNING:
        return

    app_module = sys.modules.get("app")
    if app_module is None or not hasattr(app_module, "app"):
        return

    _BOOTSTRAP_RUNNING = True
    try:
        _ORIGINAL_IMPORT("admin_work_category_manager")
        _ORIGINAL_IMPORT("admin_work_category_delete_manager")
    except Exception as exc:  # visible in runtime logs instead of failing silently
        print(
            f"[space8-bootstrap] admin work-category registration failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
    else:
        _BOOTSTRAP_DONE = True
        builtins.__import__ = _ORIGINAL_IMPORT
        print(
            "[space8-bootstrap] admin work-category routes registered",
            file=sys.stderr,
        )
    finally:
        _BOOTSTRAP_RUNNING = False


def _bootstrap_import(name, globals=None, locals=None, fromlist=(), level=0):
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)

    # Only register after the outer app import has completed.  This avoids
    # importing admin modules against a partially initialized app.py.
    if not _BOOTSTRAP_DONE and level == 0 and name == "app":
        _register_admin_work_category_modules()

    return module


builtins.__import__ = _bootstrap_import

# Covers unusual runtimes that imported app before sitecustomize was reached.
_register_admin_work_category_modules()
