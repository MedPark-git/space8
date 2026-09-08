from flask import abort, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core

app = core.app


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("admin")
            or current_user.role.allows("task_manage_all")
        )
    )


def _error(message, status=400):
    return jsonify({"ok": False, "message": message}), status


def _department(department_id):
    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None
    return department


def _audit(action, target, details):
    core.audit(action, target, {**details, "source": "admin_work_category_manager_v1"})


@app.post("/admin/work-categories/manage")
@login_required
def admin_work_category_manage():
    if not _is_admin():
        abort(403)

    operation = str(request.form.get("operation") or "").strip()
    department_id = request.form.get("department_id", type=int)

    if operation in {"add_middle", "add_small", "rename_middle"}:
        if not department_id:
            return _error("대분류(부서·팀)를 선택해 주세요.")
        department = _department(department_id)
        if not department:
            return _error("사용 가능한 대분류(부서·팀)를 찾을 수 없습니다.", 404)
    else:
        department = None

    if operation == "add_middle":
        middle_name = str(request.form.get("middle_name") or "").strip()
        if not middle_name:
            return _error("새 중분류명을 입력해 주세요.")
        if len(middle_name) > 100:
            return _error("중분류명은 100자 이하로 입력해 주세요.")

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
            if changed:
                _audit(
                    "ADMIN_WORK_CATEGORY_MIDDLE_REACTIVATE",
                    f"department:{department_id}",
                    {"department_name": department.name, "middle_name": middle_name, "category_ids": [row.id for row in rows]},
                )
                core.db.session.commit()
                return jsonify({"ok": True, "message": "기존 중분류를 다시 사용 상태로 전환했습니다."})
            return _error("이미 등록된 중분류입니다.", 409)

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
                {"department_id": department_id, "department_name": department.name, "middle_name": middle_name},
            )
            core.db.session.commit()
        except IntegrityError:
            core.db.session.rollback()
            return _error("같은 중분류가 이미 등록되어 있습니다.", 409)
        return jsonify({"ok": True, "message": "중분류를 추가했습니다."})

    if operation == "add_small":
        middle_name = str(request.form.get("middle_name") or "").strip()
        small_name = str(request.form.get("small_name") or "").strip()
        if not middle_name:
            return _error("기존 중분류를 선택해 주세요.")
        if not small_name:
            return _error("새 소분류명을 입력해 주세요.")
        if len(small_name) > 150:
            return _error("소분류명은 150자 이하로 입력해 주세요.")

        middle_exists = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == middle_name,
                core.WorkCategory.active.is_(True),
            ).limit(1)
        )
        if not middle_exists:
            return _error("선택한 중분류를 찾을 수 없습니다. 중분류를 먼저 등록해 주세요.")

        existing = core.db.session.scalar(
            select(core.WorkCategory).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == middle_name,
                core.WorkCategory.small_name == small_name,
            )
        )
        if existing:
            if existing.active:
                return _error("이미 등록된 소분류입니다.", 409)
            existing.active = True
            _audit(
                "ADMIN_WORK_CATEGORY_SMALL_REACTIVATE",
                f"work-category:{existing.id}",
                {"department_id": department_id, "department_name": department.name, "middle_name": middle_name, "small_name": small_name},
            )
            core.db.session.commit()
            return jsonify({"ok": True, "message": "기존 소분류를 다시 사용 상태로 전환했습니다."})

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
                {"department_id": department_id, "department_name": department.name, "middle_name": middle_name, "small_name": small_name},
            )
            core.db.session.commit()
        except IntegrityError:
            core.db.session.rollback()
            return _error("같은 소분류가 이미 등록되어 있습니다.", 409)
        return jsonify({"ok": True, "message": "소분류를 추가했습니다."})

    if operation == "rename_middle":
        old_middle_name = str(request.form.get("old_middle_name") or "").strip()
        new_middle_name = str(request.form.get("new_middle_name") or "").strip()
        if not old_middle_name or not new_middle_name:
            return _error("기존 중분류와 새 중분류명을 확인해 주세요.")
        if len(new_middle_name) > 100:
            return _error("중분류명은 100자 이하로 입력해 주세요.")
        if old_middle_name == new_middle_name:
            return _error("변경된 내용이 없습니다.")

        rows = core.db.session.scalars(
            select(core.WorkCategory).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == old_middle_name,
            )
        ).all()
        if not rows:
            return _error("수정할 중분류를 찾을 수 없습니다.", 404)

        row_ids = [row.id for row in rows]
        conflict = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == new_middle_name,
                ~core.WorkCategory.id.in_(row_ids),
            ).limit(1)
        )
        if conflict:
            return _error("변경하려는 이름의 중분류가 이미 존재합니다.", 409)

        try:
            for row in rows:
                row.middle_name = new_middle_name
            _audit(
                "ADMIN_WORK_CATEGORY_MIDDLE_RENAME",
                f"department:{department_id}",
                {
                    "department_name": department.name,
                    "previous_middle_name": old_middle_name,
                    "new_middle_name": new_middle_name,
                    "category_ids": row_ids,
                },
            )
            core.db.session.commit()
        except IntegrityError:
            core.db.session.rollback()
            return _error("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", 409)
        return jsonify({"ok": True, "message": "중분류명을 수정했습니다. 하위 소분류에도 함께 반영했습니다."})

    if operation == "rename_small":
        category_id = request.form.get("work_category_id", type=int)
        new_small_name = str(request.form.get("new_small_name") or "").strip()
        if not category_id:
            return _error("수정할 소분류를 확인해 주세요.")
        if not new_small_name:
            return _error("새 소분류명을 입력해 주세요.")
        if len(new_small_name) > 150:
            return _error("소분류명은 150자 이하로 입력해 주세요.")

        category = core.db.session.get(core.WorkCategory, category_id)
        if not category:
            return _error("수정할 업무구분을 찾을 수 없습니다.", 404)
        if not category.small_name:
            return _error("소분류가 없는 중분류 전용 항목입니다.")
        if category.small_name == new_small_name:
            return _error("변경된 내용이 없습니다.")

        conflict = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == category.department_id,
                core.WorkCategory.middle_name == category.middle_name,
                core.WorkCategory.small_name == new_small_name,
                core.WorkCategory.id != category.id,
            )
        )
        if conflict:
            return _error("같은 중분류 아래에 동일한 소분류가 이미 존재합니다.", 409)

        previous_small_name = category.small_name
        try:
            category.small_name = new_small_name
            _audit(
                "ADMIN_WORK_CATEGORY_SMALL_RENAME",
                f"work-category:{category.id}",
                {
                    "department_id": category.department_id,
                    "department_name": category.department.name,
                    "middle_name": category.middle_name,
                    "previous_small_name": previous_small_name,
                    "new_small_name": new_small_name,
                },
            )
            core.db.session.commit()
        except IntegrityError:
            core.db.session.rollback()
            return _error("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", 409)
        return jsonify({"ok": True, "message": "소분류명을 수정했습니다."})

    return _error("지원하지 않는 업무구분 작업입니다.")


@app.after_request
def inject_admin_work_category_manager(response):
    if response.status_code != 200 or not response.mimetype.startswith("text/html"):
        return response
    path = request.path.rstrip("/")
    is_work_category_admin = (
        path == "/admin" and request.args.get("section") == "work-categories"
    ) or path.endswith("/admin/work-categories")
    if not is_work_category_admin:
        return response

    html = response.get_data(as_text=True)
    script_tag = '<script src="/static/admin_work_category_manager_v1.js?v=20260908-admin-work-category-v1" defer></script>'
    if script_tag not in html:
        html = html.replace("</body>", f"{script_tag}</body>")
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
    return response
