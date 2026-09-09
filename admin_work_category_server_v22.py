from flask import request
from flask_login import current_user

import admin_work_category_server_v21 as v21

v19 = v21.v19
core = v19.core


def _operation():
    if request.method != "POST" or not request.path.startswith("/admin"):
        return ""
    value = str(request.form.get("operation") or "").strip()
    if value in v19.ALLOWED_OPERATIONS:
        return value
    if not str(request.form.get("awc_source") or "").startswith("v22-"):
        return ""
    keys = set(request.form.keys())
    if {"work_category_id", "new_small_name"}.issubset(keys):
        return "rename_small"
    if {"department_id", "old_middle_name", "new_middle_name"}.issubset(keys):
        return "rename_middle"
    if {"department_id", "middle_name", "small_name"}.issubset(keys):
        return "add_small"
    if {"department_id", "middle_name"}.issubset(keys):
        return "add_middle"
    if "work_category_id" in keys:
        return "delete"
    return ""


def _handle_v22():
    operation = _operation()
    if not operation:
        return None
    try:
        core.csrf.protect()
    except Exception:
        return v19._json("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", False, 400)
    if not current_user.is_authenticated:
        return v19._json("로그인이 필요합니다.", False, 401)
    if not v19._is_admin():
        return v19._json("관리자 권한이 필요합니다.", False, 403)
    try:
        return v19.HANDLERS[operation]()
    except Exception as exc:
        core.db.session.rollback()
        return v19._json(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", False, 500)


hooks = core.app.before_request_funcs.setdefault(None, [])
hooks.insert(0, _handle_v22)


@core.app.get("/__health/admin-work-category-v22")
def health_v22():
    hooks = core.app.before_request_funcs.get(None, [])
    first = getattr(hooks[0], "__name__", "") if hooks else ""
    return f"admin_work_category=v22 active=1 first={first} response=json-only", 200, {"Cache-Control": "no-store"}
