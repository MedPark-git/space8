import re

from sqlalchemy import select

import admin_work_category_server_v19 as api

core = api.core


def run_selftest():
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
        raise RuntimeError("v46 selftest: active admin or category not found")

    client = core.app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True

    page = client.get("/admin?section=work-categories")
    html = page.get_data(as_text=True)
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if not match:
        raise RuntimeError("v46 selftest: csrf token not found")

    response = client.post(
        "/admin/work-categories/manage",
        data={
            "csrf_token": match.group(1),
            "operation": "rename_small",
            "work_category_id": str(category.id),
            "new_small_name": category.small_name,
        },
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Admin-Category-Transport": "v46-selftest",
        },
        follow_redirects=False,
    )
    payload = response.get_json(silent=True) or {}
    content_type = (response.headers.get("Content-Type") or "").lower()
    ok = (
        response.status_code == 200
        and "application/json" in content_type
        and payload.get("ok") is True
        and payload.get("transport") == "admin-work-category-v19"
        and "변경된 내용이 없습니다." in str(payload.get("message") or "")
    )
    if not ok:
        body = response.get_data(as_text=True)[:500]
        raise RuntimeError(
            "v46 selftest failed: "
            f"status={response.status_code} type={content_type} payload={payload} body={body}"
        )
    return True


SELFTEST_OK = run_selftest()
