"""Direct Flask route registration for administrator work-category CRUD.

This module is imported from sitecustomize so routes are attached to the core
Flask app even when Cafe24 launches app.py directly instead of the Procfile WSGI
wrapper.
"""

import re

from sqlalchemy import select

import admin_work_category_server_v19 as api

core = api.core

MANAGE_PATH = "/admin/work-categories/manage"
V48_PATH = "/admin/work-categories/manage-v48"
HEALTH_PATH = "/__health/admin-work-category-v49"

# Make the existing v19 before_request dispatcher recognize the V48 alias too.
api.TARGET_PATHS.add(V48_PATH)
api.LEGACY_JSON_PATHS.add(V48_PATH)


def _rules():
    return {rule.rule for rule in core.app.url_map.iter_rules()}


# v19 already registers MANAGE_PATH when imported. Register the V48 alias on
# the same Flask app so both current and stale browser transports are valid.
if V48_PATH not in _rules():
    core.app.add_url_rule(
        V48_PATH,
        endpoint="admin_work_category_manage_v49_alias",
        view_func=lambda: api._json(
            "업무구분 요청을 처리하지 못했습니다. 화면을 새로고침해 주세요.",
            False,
            400,
        ),
        methods=["POST"],
    )


if HEALTH_PATH not in _rules():
    def _health():
        rules = sorted(
            rule.rule
            for rule in core.app.url_map.iter_rules()
            if rule.rule in {MANAGE_PATH, V48_PATH, HEALTH_PATH}
        )
        hooks = [
            getattr(fn, "__name__", "")
            for fn in core.app.before_request_funcs.get(None, [])[:8]
        ]
        return {
            "ok": MANAGE_PATH in rules and V48_PATH in rules,
            "transport": "direct-flask-v49",
            "rules": rules,
            "first_hooks": hooks,
        }

    core.app.add_url_rule(
        HEALTH_PATH,
        endpoint="admin_work_category_v49_health",
        view_func=_health,
        methods=["GET"],
    )


def _authenticated_noop_selftest():
    """Verify the exact core Flask app routes used by the public service."""
    rules = _rules()
    missing = {MANAGE_PATH, V48_PATH, HEALTH_PATH} - rules
    if missing:
        raise RuntimeError(f"v49 route registration failed: missing={sorted(missing)}")

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
        raise RuntimeError("v49 selftest: active administrator or category not found")

    client = core.app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True

    page = client.get("/admin?section=work-categories")
    html = page.get_data(as_text=True)
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if not match:
        raise RuntimeError("v49 selftest: csrf token not found")

    for path in (MANAGE_PATH, V48_PATH):
        response = client.post(
            path,
            data={
                "csrf_token": match.group(1),
                "operation": "rename_small",
                "work_category_id": str(category.id),
                "new_small_name": category.small_name,
            },
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-MedPark-Admin-Category-Transport": "v49-core-selftest",
            },
            follow_redirects=False,
        )
        payload = response.get_json(silent=True) or {}
        content_type = (response.headers.get("Content-Type") or "").lower()
        ok = (
            response.status_code == 200
            and "application/json" in content_type
            and payload.get("ok") is True
            and "변경된 내용이 없습니다." in str(payload.get("message") or "")
        )
        if not ok:
            body = response.get_data(as_text=True)[:500]
            raise RuntimeError(
                "v49 core selftest failed: "
                f"path={path} status={response.status_code} type={content_type} "
                f"payload={payload} body={body}"
            )
    return True


V49_SELFTEST_OK = _authenticated_noop_selftest()
app = core.app
