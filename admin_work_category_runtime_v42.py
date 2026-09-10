from flask import request

import task_category_wsgi_guard as guard
import task_editor_runtime as runtime


ACTION_MAP = {
    "add_middle": "add",
    "add_small": "add",
    "rename_middle": "rename_middle",
    "rename_small": "rename_small",
    "delete": "delete",
}


def _payload():
    return request.form.to_dict(flat=True)


def _action_v42():
    explicit = str(
        request.form.get("category_action")
        or request.args.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or ""
    ).strip()
    if explicit in guard.HANDLERS:
        return explicit

    operation = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or request.args.get("awc_operation")
        or ""
    ).strip()
    return ACTION_MAP.get(operation, "")


def _wrap_guard_handler(action):
    def handler():
        return guard.HANDLERS[action](_payload())

    handler.__name__ = f"_admin_work_category_v42_{action}"
    return handler


# The existing runtime before_request is already the first Flask request hook.
# Make it understand administrator work-category operations and reuse the proven
# guard CRUD handlers without adding another WSGI body reader.
runtime._category_request_action = _action_v42
for _action in ("add", "rename_middle", "rename_small", "delete"):
    if _action in guard.HANDLERS:
        runtime.CATEGORY_HANDLERS[_action] = _wrap_guard_handler(_action)

# Deduplicate the category hook defensively and keep exactly one copy first.
_hooks = runtime.FLASK_APP.before_request_funcs.setdefault(None, [])
_category_hook = runtime._category_manager_v18_before_request
_hooks[:] = [fn for fn in _hooks if fn is not _category_hook]
_hooks.insert(0, _category_hook)


@runtime.FLASK_APP.get("/__health/admin-work-category-v42")
def admin_work_category_v42_health():
    before_names = [getattr(fn, "__name__", "") for fn in _hooks[:5]]
    return {
        "ok": True,
        "transport": "admin-work-category-v42",
        "first_before_request": before_names[0] if before_names else "",
        "handlers": sorted(runtime.CATEGORY_HANDLERS),
        "wsgi_body_wrapper": False,
    }
