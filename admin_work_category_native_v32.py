from flask import request

import admin_work_category_server_v19 as v19

core = v19.core
_original_detect_operation = v19._detect_operation


def _detect_operation_v32():
    """Recognize native work-category writes from the query before form parsing."""
    if request.method == "POST":
        path = request.path.rstrip("/") or "/"
        if path in v19.TARGET_PATHS:
            query_operation = str(request.args.get("wcop") or "").strip()
            if query_operation in v19.ALLOWED_OPERATIONS:
                return query_operation
    return _original_detect_operation()


def _return_url_v32():
    """Always return to the canonical work-category admin page after a write."""
    return "/admin?section=work-categories"


v19._detect_operation = _detect_operation_v32
v19._return_url = _return_url_v32


@core.app.get("/__health/admin-work-category-v32")
def admin_work_category_v32_health():
    first = ""
    funcs = core.app.before_request_funcs.get(None, [])
    if funcs:
        first = getattr(funcs[0], "__name__", "")
    return (
        "admin_work_category=v32 active=1 "
        f"first={first} "
        "operation=query+wform "
        "redirect=/admin?section=work-categories",
        200,
        {"Cache-Control": "no-store"},
    )
