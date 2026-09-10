import html as html_lib
import re

from sqlalchemy import select

import admin_work_category_v45 as v45

core = v45.core


def _is_admin_candidate(employee):
    role = getattr(employee, "role", None)
    if role is None:
        return False
    return bool(
        role.name == "관리자"
        or role.allows("admin")
        or role.allows("task_manage_all")
    )


def _run_v45_noop_selftest():
    """Run one authenticated no-op category rename through the real Flask stack.

    The selected category is renamed to its existing name, so the handler exits
    with '변경된 내용이 없습니다.' before any DB write/commit occurs.
    """
    with core.app.app_context():
        employees = core.db.session.scalars(
            select(core.Employee)
            .where(
                core.Employee.status == "재직",
                core.Employee.approval_status == "승인완료",
            )
            .order_by(core.Employee.id)
        ).all()
        admin = next((employee for employee in employees if _is_admin_candidate(employee)), None)
        category = core.db.session.scalar(
            select(core.WorkCategory)
            .where(
                core.WorkCategory.active.is_(True),
                core.WorkCategory.small_name != "",
            )
            .order_by(core.WorkCategory.id)
            .limit(1)
        )

        if admin is None or category is None:
            raise RuntimeError("V45 selftest requires one active administrator and one active small category")

        client = core.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(admin.id)
            session["_fresh"] = True

        page = client.get("/admin?section=work-categories", follow_redirects=False)
        if page.status_code != 200:
            raise RuntimeError(f"V45 selftest admin page failed: HTTP {page.status_code}")

        html_text = page.get_data(as_text=True)
        token_match = re.search(
            r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
            html_text,
        )
        if not token_match:
            raise RuntimeError("V45 selftest CSRF token not found")
        csrf_token = html_lib.unescape(token_match.group(1))

        url = "/tasks/new?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=v42"
        response = client.post(
            url,
            data={
                "csrf_token": csrf_token,
                "operation": "rename_small",
                "awc_operation": "rename_small",
                "awc_admin": "v42",
                "category_action": "rename_small",
                "category_manager": "1",
                "awc_response": "json",
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
        marker = response.headers.get("X-MedPark-Admin-Work-Category", "")
        message = payload.get("message", "") if isinstance(payload, dict) else ""
        ok = bool(
            response.status_code == 200
            and response.is_json
            and isinstance(payload, dict)
            and payload.get("ok") is True
            and marker == "v45"
            and message == "변경된 내용이 없습니다."
        )
        if not ok:
            raise RuntimeError(
                "V45 selftest failed: "
                f"HTTP={response.status_code}, json={response.is_json}, marker={marker or '-'}, message={message or '-'}"
            )

        print(
            "[V45_SELFTEST] PASS "
            f"HTTP={response.status_code} json=1 marker={marker} message={message}",
            flush=True,
        )


_run_v45_noop_selftest()
