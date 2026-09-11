import re

from sqlalchemy import select
from werkzeug.test import Client
from werkzeug.wrappers import Response

import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_view_v44  # noqa: F401 - legacy task_new view fallback
import admin_work_category_server_v19 as admin_api
import admin_work_category_v45  # noqa: F401 - stale-client /tasks/new category guard
import admin_work_category_wsgi_v48 as transport_v48

# Production entrypoint. V48 wraps the actual Flask WSGI application, so the
# dedicated administrator work-category endpoint is handled before Flask route
# matching and cannot fall through to a 404 URL-map response.
flask_app = guard.flask_app
app = transport_v48.wrap(flask_app)

# Read-only transport health invariant.
_probe = Client(app, Response).get(transport_v48.HEALTH_PATH)
if _probe.status_code != 200 or _probe.headers.get("X-MedPark-Admin-Work-Category") != "wsgi-v48":
    raise RuntimeError(
        "admin work category v48 transport is not active: "
        f"status={_probe.status_code} marker={_probe.headers.get('X-MedPark-Admin-Work-Category')}"
    )


def _run_authenticated_v48_noop_selftest():
    """Exercise the exact exported WSGI endpoint without changing DB data."""
    core = admin_api.core
    admin = core.db.session.scalar(
        select(core.Employee)
        .join(core.Role, core.Employee.role_id == core.Role.id)
        .where(
            core.Role.name == "관리자",
            core.Employee.status == "재직",
            core.Employee.approval_status == "승인완료",
        )
        .order_by(core.Employee.id)
        .limit(1)
    )
    category = core.db.session.scalar(
        select(core.WorkCategory)
        .where(core.WorkCategory.active.is_(True), core.WorkCategory.small_name != "")
        .order_by(core.WorkCategory.id)
        .limit(1)
    )
    if not admin or not category:
        raise RuntimeError("v48 selftest: active administrator or category not found")

    flask_client = flask_app.test_client()
    with flask_client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True

    page = flask_client.get("/admin?section=work-categories")
    html = page.get_data(as_text=True)
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if not match:
        raise RuntimeError("v48 selftest: csrf token not found")

    cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
    cookie = flask_client.get_cookie(cookie_name)
    if cookie is None:
        raise RuntimeError("v48 selftest: session cookie not found")

    wsgi_client = Client(app, Response, use_cookies=False)
    response = wsgi_client.post(
        transport_v48.TARGET_PATH,
        data={
            "csrf_token": match.group(1),
            "operation": "rename_small",
            "work_category_id": str(category.id),
            "new_small_name": category.small_name,
        },
        headers={
            "Cookie": f"{cookie_name}={cookie.value}",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Admin-Category-Transport": "v48-startup-selftest",
        },
    )
    payload = response.get_json(silent=True) or {}
    marker = response.headers.get("X-MedPark-Admin-Work-Category") or ""
    content_type = (response.headers.get("Content-Type") or "").lower()
    ok = (
        response.status_code == 200
        and "application/json" in content_type
        and marker == "wsgi-v48"
        and payload.get("ok") is True
        and "변경된 내용이 없습니다." in str(payload.get("message") or "")
    )
    if not ok:
        body = response.get_data(as_text=True)[:500]
        raise RuntimeError(
            "v48 authenticated selftest failed: "
            f"status={response.status_code} type={content_type} marker={marker} "
            f"payload={payload} body={body}"
        )
    return True


V48_SELFTEST_OK = _run_authenticated_v48_noop_selftest()
