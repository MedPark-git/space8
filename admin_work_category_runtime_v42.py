import re

from flask import request
from sqlalchemy import select

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


runtime._category_request_action = _action_v42
for _action in ("add", "rename_middle", "rename_small", "delete"):
    if _action in guard.HANDLERS:
        runtime.CATEGORY_HANDLERS[_action] = _wrap_guard_handler(_action)

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


@runtime.FLASK_APP.get("/__health/admin-work-category-v42-noop")
def admin_work_category_v42_noop_health():
    core = runtime.core
    admin = core.db.session.scalar(
        select(core.Employee).join(core.Role).where(
            core.Role.name == "관리자",
            core.Employee.status == "재직",
            core.Employee.approval_status == "승인완료",
        ).limit(1)
    )
    category = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.active.is_(True),
            core.WorkCategory.small_name != "",
        ).order_by(core.WorkCategory.id).limit(1)
    )
    if not admin or not category:
        return {"ok": False, "stage": "fixtures"}, 500

    client = runtime.FLASK_APP.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True

    page = client.get("/admin?section=work-categories")
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', page.get_data(as_text=True))
    if page.status_code != 200 or not match:
        return {"ok": False, "stage": "csrf", "status": page.status_code}, 500

    token = match.group(1)
    response = client.post(
        "/tasks/new?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=v42",
        data={
            "csrf_token": token,
            "operation": "rename_small",
            "awc_operation": "rename_small",
            "awc_admin": "v42",
            "category_action": "rename_small",
            "category_manager": "1",
            "work_category_id": str(category.id),
            "new_small_name": category.small_name,
        },
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-MedPark-Category-JSON": "1",
            "X-Task-Category-Action": "rename_small",
        },
        follow_redirects=False,
    )
    payload = response.get_json(silent=True)
    ok = (
        response.status_code == 200
        and isinstance(payload, dict)
        and payload.get("ok") is True
        and "변경된 내용이 없습니다" in str(payload.get("message") or "")
    )
    return {
        "ok": ok,
        "status": response.status_code,
        "content_type": response.content_type,
        "payload_ok": payload.get("ok") if isinstance(payload, dict) else None,
        "message": payload.get("message") if isinstance(payload, dict) else "",
        "transport": payload.get("transport") if isinstance(payload, dict) else "",
    }, (200 if ok else 500)
