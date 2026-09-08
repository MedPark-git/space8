from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import task_category_wsgi_guard as guard

flask_app = guard.flask_app
core = guard.core


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (
            current_user.role.name == "관리자"
            or current_user.role.allows("admin")
            or current_user.role.allows("task_manage_all")
        )
    )


def _json(message, ok=True, status=200):
    return jsonify({"ok": bool(ok), "message": message, "transport": "admin-work-category-wsgi-v4"}), status


def _department(department_id):
    if not department_id:
        return None
    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None
    return department


def _audit(action, target, details):
    core.audit(action, target, {**details, "source": "admin-work-category-wsgi-v4"})


def _handle_manage():
    operation = str(request.form.get("operation") or "").strip()
    department_id = request.form.get("department_id", type=int)

    if operation in {"add_middle", "add_small", "rename_middle"}:
        department = _department(department_id)
        if not department:
            return _json("사용 가능한 대분류(부서·팀)를 확인해 주세요.", False, 400)
    else:
        department = None

    if operation == "add_middle":
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

    if operation == "add_small":
        middle_name = str(request.form.get("middle_name") or "").strip()
        small_name = str(request.form.get("small_name") or "").strip()
        if not middle_name:
            return _json("기존 중분류를 선택해 주세요.", False, 400)
        if not small_name:
            return _json("새 소분류명을 입력해 주세요.", False, 400)
        if len(small_name) > 150:
            return _json("소분류명은 150자 이하로 입력해 주세요.", False, 400)

        middle_exists = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == middle_name,
                core.WorkCategory.active.is_(True),
            ).limit(1)
        )
        if not middle_exists:
            return _json("선택한 중분류를 찾을 수 없습니다.", False, 404)

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

    if operation == "rename_middle":
        old_middle_name = str(request.form.get("old_middle_name") or "").strip()
        new_middle_name = str(request.form.get("new_middle_name") or "").strip()
        if not old_middle_name or not new_middle_name:
            return _json("기존 중분류와 새 중분류명을 확인해 주세요.", False, 400)
        if len(new_middle_name) > 100:
            return _json("중분류명은 100자 이하로 입력해 주세요.", False, 400)
        if old_middle_name == new_middle_name:
            return _json("변경된 내용이 없습니다.", False, 400)

        rows = core.db.session.scalars(
            select(core.WorkCategory).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == old_middle_name,
            )
        ).all()
        if not rows:
            return _json("수정할 중분류를 찾을 수 없습니다.", False, 404)

        row_ids = [row.id for row in rows]
        conflict = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == department_id,
                core.WorkCategory.middle_name == new_middle_name,
                ~core.WorkCategory.id.in_(row_ids),
            ).limit(1)
        )
        if conflict:
            return _json("변경하려는 이름의 중분류가 이미 존재합니다.", False, 409)

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
            return _json("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", False, 409)
        return _json("중분류명을 수정했습니다. 하위 소분류에도 함께 반영했습니다.")

    if operation == "rename_small":
        category_id = request.form.get("work_category_id", type=int)
        new_small_name = str(request.form.get("new_small_name") or "").strip()
        if not category_id:
            return _json("수정할 소분류를 확인해 주세요.", False, 400)
        if not new_small_name:
            return _json("새 소분류명을 입력해 주세요.", False, 400)
        if len(new_small_name) > 150:
            return _json("소분류명은 150자 이하로 입력해 주세요.", False, 400)

        category = core.db.session.get(core.WorkCategory, category_id)
        if not category:
            return _json("수정할 업무구분을 찾을 수 없습니다.", False, 404)
        if not category.small_name:
            return _json("소분류가 없는 중분류 전용 항목입니다.", False, 400)
        if category.small_name == new_small_name:
            return _json("변경된 내용이 없습니다.", False, 400)

        conflict = core.db.session.scalar(
            select(core.WorkCategory.id).where(
                core.WorkCategory.department_id == category.department_id,
                core.WorkCategory.middle_name == category.middle_name,
                core.WorkCategory.small_name == new_small_name,
                core.WorkCategory.id != category.id,
            )
        )
        if conflict:
            return _json("같은 중분류 아래에 동일한 소분류가 이미 존재합니다.", False, 409)

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
            return _json("중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.", False, 409)
        return _json("소분류명을 수정했습니다.")

    return _json("지원하지 않는 업무구분 작업입니다.", False, 400)


def _handle_delete():
    category_id = request.form.get("work_category_id", type=int)
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


@flask_app.after_request
def strip_legacy_admin_work_category_script(response):
    if response.status_code == 200 and response.mimetype.startswith("text/html"):
        html = response.get_data(as_text=True)
        legacy = '<script src="/static/admin_work_category_manager_v1.js?v=20260908-admin-work-category-v1" defer></script>'
        if legacy in html:
            html = html.replace(legacy, "")
            response.set_data(html)
            response.headers["Content-Length"] = str(len(response.get_data()))
    return response


class AdminWorkCategoryGateway:
    """Direct WSGI CRUD for admin work categories; no Flask route delegation."""

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()

        if path == "/__health/admin-work-category-v4":
            body = b"admin_work_category_gateway=v4 direct-crud active"
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]

        if method != "POST" or path not in {
            "/admin/work-categories/manage",
            "/admin/work-categories/delete-v2",
        }:
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                core.csrf.protect()
                if not current_user.is_authenticated:
                    result = _json("로그인이 필요합니다.", False, 401)
                elif not _is_admin():
                    result = _json("관리자 권한이 필요합니다.", False, 403)
                elif path == "/admin/work-categories/manage":
                    result = _handle_manage()
                else:
                    result = _handle_delete()
            except Exception as exc:
                core.db.session.rollback()
                result = _json(f"업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})", False, 500)

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Admin-Work-Category"] = "v4-direct"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = AdminWorkCategoryGateway(guard.app)
