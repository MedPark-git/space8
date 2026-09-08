from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core

ALLOWED_OPERATIONS = {
    "add_middle",
    "add_small",
    "rename_middle",
    "rename_small",
    "delete",
}
TARGET_PATHS = {
    "/admin",
    "/admin/work-categories",
    "/admin/work-categories/manage",
    "/admin/work-categories/delete-v2",
}
LEGACY_JSON_PATHS = {
    "/admin/work-categories/manage",
    "/admin/work-categories/delete-v2",
}


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("admin")
            or current_user.role.allows("task_manage_all")
        )
    )


def _json(message, ok=True, status=200, **extra):
    payload = {
        "ok": bool(ok),
        "message": message,
        "transport": "admin-work-category-v19",
        **extra,
    }
    return jsonify(payload), status


def _department(department_id):
    if not department_id:
        return None
    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None
    return department


def _audit(action, target, details):
    core.audit(action, target, {**details, "source": "admin-work-category-v19"})


def _int_value(name):
    try:
        return int(request.form.get(name) or 0)
    except (TypeError, ValueError):
        return 0


def _detect_operation():
    if request.method != "POST":
        return ""

    path = request.path.rstrip("/") or "/"
    if path not in TARGET_PATHS:
        return ""

    if path == "/admin/work-categories/delete-v2":
        return "delete"

    explicit = str(
        request.form.get("operation")
        or request.form.get("awc_operation")
        or ""
    ).strip()
    if explicit in ALLOWED_OPERATIONS:
        return explicit

    # V19 field-signature fallback.  This deliberately does not depend on a
    # custom marker, header, query string or specific browser transport.
    keys = set(request.form.keys())
    if {"work_category_id", "new_small_name"}.issubset(keys):
        return "rename_small"
    if {"department_id", "old_middle_name", "new_middle_name"}.issubset(keys):
        return "rename_middle"
    if {"department_id", "middle_name", "small_name"}.issubset(keys):
        return "add_small"
    if path == "/admin/work-categories/manage" and {"department_id", "middle_name"}.issubset(keys):
        return "add_middle"
    return ""


def _handle_add_middle():
    department_id = _int_value("department_id")
    department = _department(department_id)
    if not department:
        return _json("사용 가능한 대분류(부서·팀)를 선택해 주세요.", False, 400)

    middle_name = str(request.form.get("middle_name") or "").strip()
    if not middle_name:
        return _json("새 중분류명을 입력해 주세요.", False, 400)
    if len(middle_name) > 100:
        return _json("중분류명은 100자 이하로 입력해 주세요.", False, 400)

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department_id,
            core.WorkCategory.middle_name == middle_name,
        )
    ).all()
    if rows:
        changed = False
        for row in rows:
            if not row.active:
                row.active = True
                changed = True
        if not changed:
            return _json("이미 등록된 중분류입니다.", False, 409)
        _audit(
            "ADMIN_WORK_CATEGORY_MIDDLE_REACTIVATE",
            f"department:{department_id}",
            {
                "department_name": department.name,
                "middle_name": middle_name,
                "category_ids": [row.id for row in rows],
            },
        )
        core.db.session.commit()
        return _json("기존 중분류를 다시 사용 상태로 전환했습니다.")

    try:
        category = core.WorkCategory(
            department_id=department_id,
            middle_name=middle_name,
            small_name="",
            active=True,
            sort_order=0,
        )
        core.db.session.add(category)
        core.db.session.flush()
        _audit(
            "ADMIN_WORK_CATEGORY_MIDDLE_CREATE",
            f"work-category:{category.id}",
            {
                "department_id": department_id,
                "department_name": department.name,
                "middle_name": middle_name,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json("같은 중분류가 이미 등록되어 있습니다.", False, 409)
    return _json("중분류를 추가했습니다.")


def _handle_add_small():
    department_id = _int_value("department_id")
    department = _department(department_id)
    if not department:
        return _json("사용 가능한 대분류(부서·팀)를 선택해 주세요.", False, 400)

    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()
    if not middle_name:
        return _json("기존 중분류를 선택해 주세요.", False, 400)
    if not small_name:
        return _json("새 소분류명을 입력해 주세요.", False, 400)
    if len(small_name) > 150:
        return _json("소분류명은 150자 이하로 입력해 주세요.", False, 400)

    middle_exists = core.db.session.scalar(
        select(core.WorkCategory.id)
        .where(
            core.WorkCategory.department_id == department_id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.active.is_(True),
        )
        .limit(1)
    )
    if not middle_exists:
        return _json("선택한 중분류를 찾을 수 없습니다. 중분류를 먼저 등록해 주세요.", False, 400)

    existing = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department_id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.small_name == small_name,
        )
    )
    if existing:
        if existing.active:
            return _json("이미 등록된 소분류입니다.", False, 409)
        existing.active = True
        _audit(
            "ADMIN_WORK_CATEGORY_SMALL_REACTIVATE",
            f"work-category:{existing.id}",
            {
                "department_id": department_id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
            },
        )
        core.db.session.commit()
        return _json("기존 소분류를 다시 사용 상태로 전환했습니다.")

    try:
        category = core.WorkCategory(
            department_id=department_id,
            middle_name=middle_name,
            small_name=small_name,
            active=True,
            sort_order=0,
        )
        core.db.session.add(category)
        core.db.session.flush()
        _audit(
            "ADMIN_WORK_CATEGORY_SMALL_CREATE",
            f"work-category:{category.id}",
            {
                "department_id": department_id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json("같은 소분류가 이미 등록되어 있습니다.", False, 409)
    return _json("소분류를 추가했습니다.")


def _handle_rename_middle():
    department_id = _int_value("department_id")
    department = _department(department_id)
    if not department:
        return _json("사용 가능한 대분류(부서·팀)를 선택해 주세요.", False, 400)

    old_name = str(request.form.get("old_middle_name") or "").strip()
    new_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _json("기존 중분류와 새 중분류명을 확인해 주세요.", False, 400)
    if len(new_name) > 100:
        return _json("중분류명은 100자 이하로 입력해 주세요.", False, 400)
    if old_name == new_name:
        return _json("변경된 내용이 없습니다.")

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department_id,
            core.WorkCategory.middle_name == old_name,
        )
    ).all()
    if not rows:
        return _json("수정할 중분류를 찾을 수 없습니다.", False, 404)

    row_ids = [row.id for row in rows]
    conflict = core.db.session.scalar(
        select(core.WorkCategory.id)
        .where(
            core.WorkCategory.department_id == department_id,
            core.WorkCategory.middle_name == new_name,
            ~core.WorkCategory.id.in_(row_ids),
        )
        .limit(1)
    )
    if conflict:
        return _json("변경하려는 이름의 중분류가 이미 존재합니다.", False, 409)

    try:
        for row in rows:
            row.middle_name = new_name
        _audit(
            "ADMIN_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department_id}",
            {
                "department_name": department.name,
                "previous_middle_name": old_name,
                "new_middle_name": new_name,
                "category_ids": row_ids,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", False, 409)
    return _json("중분류명을 수정했습니다. 하위 소분류에도 함께 반영했습니다.")


def _handle_rename_small():
    category_id = _int_value("work_category_id")
    new_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id:
        return _json("수정할 소분류를 확인해 주세요.", False, 400)
    if not new_name:
        return _json("새 소분류명을 입력해 주세요.", False, 400)
    if len(new_name) > 150:
        return _json("소분류명은 150자 이하로 입력해 주세요.", False, 400)

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category:
        return _json("수정할 업무구분을 찾을 수 없습니다.", False, 404)
    if not category.small_name:
        return _json("소분류가 없는 중분류 전용 항목입니다.", False, 400)
    if category.small_name == new_name:
        return _json("변경된 내용이 없습니다.")

    conflict = core.db.session.scalar(
        select(core.WorkCategory.id).where(
            core.WorkCategory.department_id == category.department_id,
            core.WorkCategory.middle_name == category.middle_name,
            core.WorkCategory.small_name == new_name,
            core.WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _json("같은 중분류 아래에 동일한 소분류가 이미 존재합니다.", False, 409)

    previous = category.small_name
    try:
        category.small_name = new_name
        _audit(
            "ADMIN_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "department_id": category.department_id,
                "department_name": category.department.name,
                "middle_name": category.middle_name,
                "previous_small_name": previous,
                "new_small_name": new_name,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", False, 409)
    return _json("소분류명을 수정했습니다.")


def _handle_delete():
    category_id = _int_value("work_category_id")
    if not category_id:
        return _json("삭제할 업무구분을 확인해 주세요.", False, 400)

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category:
        return _json("삭제할 업무구분을 찾을 수 없습니다.", False, 404)

    task_count = len(category.tasks)
    if task_count:
        return _json(
            f"이 업무구분은 {task_count}개의 업무에서 사용 중이라 삭제할 수 없습니다. 미사용 전환을 이용해 주세요.",
            False,
            409,
        )

    if not category.small_name:
        child_count = core.db.session.scalar(
            select(core.db.func.count(core.WorkCategory.id)).where(
                core.WorkCategory.department_id == category.department_id,
                core.WorkCategory.middle_name == category.middle_name,
                core.WorkCategory.id != category.id,
            )
        ) or 0
        if child_count:
            return _json("하위 소분류가 있어 중분류를 삭제할 수 없습니다. 소분류를 먼저 정리해 주세요.", False, 409)

    details = {
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
        "work_category_id": category.id,
    }
    _audit("ADMIN_WORK_CATEGORY_DELETE", f"work-category:{category.id}", details)
    core.db.session.delete(category)
    core.db.session.commit()
    return _json("업무구분을 삭제했습니다.")


HANDLERS = {
    "add_middle": _handle_add_middle,
    "add_small": _handle_add_small,
    "rename_middle": _handle_rename_middle,
    "rename_small": _handle_rename_small,
    "delete": _handle_delete,
}


def _return_url():
    query = request.query_string.decode("utf-8", errors="ignore")
    path = request.path if request.path in {"/admin", "/admin/work-categories"} else "/admin"
    if path == "/admin" and "section=work-categories" not in query:
        query = "section=work-categories"
    return path + (f"?{query}" if query else "")


def _wants_json():
    path = request.path.rstrip("/") or "/"
    return (
        path in LEGACY_JSON_PATHS
        or "application/json" in (request.headers.get("Accept") or "").lower()
        or (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest"
    )


def _dispatch_result(result):
    if _wants_json():
        return result

    response = core.app.make_response(result)
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict):
        flash(
            str(payload.get("message") or "업무구분 처리가 완료되었습니다."),
            "success" if payload.get("ok") else "error",
        )
    else:
        flash("업무구분 처리가 완료되었습니다.", "success")
    return redirect(_return_url())


def _admin_work_category_before_request_v19():
    operation = _detect_operation()
    if not operation:
        return None

    # This hook is first and returns before any legacy admin validator or route.
    try:
        core.csrf.protect()
    except Exception:
        return _dispatch_result(_json("요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", False, 400))

    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if not _is_admin():
        return _dispatch_result(_json("관리자 권한이 필요합니다.", False, 403))

    try:
        result = HANDLERS[operation]()
    except Exception as exc:
        core.db.session.rollback()
        result = _json(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", False, 500)
    return _dispatch_result(result)


_before = core.app.before_request_funcs.setdefault(None, [])
_before[:] = [fn for fn in _before if getattr(fn, "__name__", "") != "_admin_work_category_before_request_v19"]
_before.insert(0, _admin_work_category_before_request_v19)


# Explicit routes make legacy V2 AJAX URLs routable even if no older manager
# module is imported.  The first before_request above normally handles them.
@core.app.post("/admin/work-categories/manage")
def admin_work_category_manage_v19_fallback():
    return _json("업무구분 요청을 처리하지 못했습니다. 화면을 새로고침해 주세요.", False, 400)


@core.app.post("/admin/work-categories/delete-v2")
def admin_work_category_delete_v19_fallback():
    return _json("업무구분 삭제 요청을 처리하지 못했습니다. 화면을 새로고침해 주세요.", False, 400)


@core.app.get("/__health/admin-work-category-v19")
def admin_work_category_v19_health():
    funcs = core.app.before_request_funcs.get(None, [])
    first = getattr(funcs[0], "__name__", "") if funcs else ""
    rules = sorted(
        rule.rule
        for rule in core.app.url_map.iter_rules()
        if rule.rule in {"/admin/work-categories/manage", "/admin/work-categories/delete-v2"}
    )
    return (
        "admin_work_category=v19 active=1 "
        f"first={first} "
        "dispatch=form-signature-or-operation "
        "legacy_bootstrap=off "
        "routes=" + ",".join(rules),
        200,
        {"Cache-Control": "no-store"},
    )
