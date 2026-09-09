from flask import request

import admin_work_category_server_v19 as v19


def _wants_json_v21():
    """Force JSON for administrator work-category UI requests.

    Cafe24/edge proxies may normalize or strip Accept/X-Requested-With headers.
    The browser transport therefore sends stable POST-body markers that survive
    proxying.  If either marker is present, never redirect to HTML.
    """
    path = request.path.rstrip("/") or "/"
    source = str(request.form.get("awc_source") or "").strip()
    response_mode = str(request.form.get("awc_response") or "").strip().lower()

    return bool(
        path in v19.LEGACY_JSON_PATHS
        or response_mode == "json"
        or source.startswith("v20-")
        or source.startswith("v21-")
        or "application/json" in (request.headers.get("Accept") or "").lower()
        or (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest"
    )


# V19's before_request and CRUD functions look up _wants_json dynamically from
# their module globals, so replacing it here upgrades the active handler without
# duplicating or re-registering any DB logic/routes.
v19._wants_json = _wants_json_v21


@v19.core.app.get("/__health/admin-work-category-v21")
def admin_work_category_v21_health():
    funcs = v19.core.app.before_request_funcs.get(None, [])
    first = getattr(funcs[0], "__name__", "") if funcs else ""
    return (
        "admin_work_category=v21 active=1 "
        f"first={first} "
        "json=body-marker "
        "markers=awc_source,awc_response "
        "crud=v19",
        200,
        {"Cache-Control": "no-store"},
    )
