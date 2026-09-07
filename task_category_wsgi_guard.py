from urllib.parse import parse_qs

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError

import task_editor_runtime as runtime

flask_app = runtime.FLASK_APP
core = runtime.core
TARGET_PATH = "/tasks/new"
SOURCE = "task-category-wsgi-v11"


def _text_response(start_response, status, text):
    body = text.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-MedPark-Task-Category-WSGI", "v11"),
        ],
    )
    return [body]


def _is_admin():
    return runtime._is_admin()


def _payload():
    if request.is_json:
        value = request.get_json(silent=True)
        return value if isinstance(value, dict) else {}
    return request.form.to_dict(flat=True)


def _int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _wants_json():
    return (
        "application/json" in (request.headers.get("Accept") or "").lower()
        and (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest"
    )


def _catalog(department_id):
    if not department_id:
        return []
    categories = core.active_work_categories([department_id])
    return core.build_work_category_catalog(categories)


def _category_payload(category):
    if not category:
        return None
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
    }


def _finish(message, ok=True, department_id=None, middle_name="", category_id=None, status=None):
    if _wants_json():
        category = core.db.session.get(core.WorkCategory, category_id) if category_id else None
        payload = {
            "ok": bool(ok),
            "message": message,
            "categories": _catalog(department_id),
        }
        if category:
            payload["category"] = _category_payload(category)
        return jsonify(payload), (status or (200 if ok else 400))

    tone = "success" if ok else "error"
    flash(message, tone)
    return redirect(
        url_for(
            "task_new",
            category_manager="1",
            category_result=tone,
            category_middle=middle_name or None,
            category_id=category_id or None,
        )
    )


def _resolve_department(payload, fallback_category=None):
    if _is_admin():
        department_id = _int_value(payload.get("department_id"))
        if not department_id and fallback_category is not None:
            department_id = fallback_category.department_id
    else:
        department_id = current_user.department_id

    if not department_id:
        return None, _finish("대분류(부서·팀)를 확인해 주세요.", False)

    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None, _finish("사용 가능한 부서(팀)를 찾을 수 없습니다.", False)

    if not _is_admin() and department.id != current_user.department_id:
        return None, _finish(
            "본인 소속 부서(팀)의 중분류·소분류만 관리할 수 있습니다.",
            False,
            department_id=current_user.department_id,
        )
    return department, None


def _handle_add(payload):
    department, error = _resolve_department(payload)
    if error:
        return error

    middle_name = str(payload.get("middle_name") or "").strip()
    small_name = str(payload.get("small_name") or "").strip()
    if not middle_name:
        return _finish("중분류명을 확인해 주세요.", False, department.id)
    if len(middle_name) > 100:
        return _finish("중분류명은 100자 이하로 입력해 주세요.", False, department.id)
    if len(small_name) > 150:
        return _finish("소분류명은 150자 이하로 입력해 주세요.", False, department.id)

    category = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.small_name == small_name,
        )
    )
    if category and category.active:
        return _finish(
            "이미 등록된 업무구분입니다. 저장된 항목을 선택했습니다.",
            True,
            department.id,
            middle_name,
            category.id,
        )

    created = category is None
    if category:
        category.active = True
    else:
        category = core.WorkCategory(
            department_id=department.id,
            middle_name=middle_name,
            small_name=small_name,
            active=True,
            sort_order=0,
        )
        core.db.session.add(category)

    try:
        core.db.session.flush()
        core.audit(
            "TASK_WORK_CATEGORY_CREATE" if created else "TASK_WORK_CATEGORY_REACTIVATE",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": middle_name,
                "small_name": small_name,
                "source": SOURCE,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        existing = core.db.session.scalar(
            select(core.WorkCategory).where(
                core.WorkCategory.department_id == department.id,
                core.WorkCategory.middle_name == middle_name,
                core.WorkCategory.small_name == small_name,
            )
        )
        if existing:
            return _finish(
                "이미 등록된 업무구분입니다. 저장된 항목을 선택했습니다.",
                True,
                department.id,
                middle_name,
                existing.id,
            )
        return _finish("업무구분 저장 중 충돌이 발생했습니다. 다시 시도해 주세요.", False, department.id)
    except Exception as exc:
        core.db.session.rollback()
        return _finish(
            f"업무구분 등록 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            department.id,
        )

    return _finish("업무구분을 등록했습니다.", True, department.id, middle_name, category.id)


def _handle_rename_middle(payload):
    department, error = _resolve_department(payload)
    if error:
        return error

    old_name = str(payload.get("old_middle_name") or "").strip()
    new_name = str(payload.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _finish("수정할 중분류와 새 중분류명을 확인해 주세요.", False, department.id)
    if len(new_name) > 100:
        return _finish("중분류명은 100자 이하로 입력해 주세요.", False, department.id)
    if old_name == new_name:
        return _finish("변경된 내용이 없습니다.", True, department.id, new_name)

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == old_name,
            core.WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        return _finish("수정할 중분류를 찾을 수 없습니다.", False, department.id)

    row_ids = [row.id for row in rows]
    small_names = [row.small_name for row in rows]
    conflict = core.db.session.scalar(
        select(core.WorkCategory.id)
        .where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == new_name,
            core.WorkCategory.small_name.in_(small_names),
            ~core.WorkCategory.id.in_(row_ids),
        )
        .limit(1)
    )
    if conflict:
        return _finish(
            "변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.",
            False,
            department.id,
            old_name,
        )

    try:
        for row in rows:
            row.middle_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "previous_middle_name": old_name,
                "new_middle_name": new_name,
                "category_ids": row_ids,
                "source": SOURCE,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _finish("중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.", False, department.id, old_name)
    except Exception as exc:
        core.db.session.rollback()
        return _finish(f"중분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})", False, department.id, old_name)

    return _finish("중분류명을 수정했습니다.", True, department.id, new_name)


def _handle_rename_small(payload):
    category_id = _int_value(payload.get("work_category_id"))
    new_name = str(payload.get("new_small_name") or "").strip()
    if not category_id or not new_name:
        return _finish("수정할 소분류와 새 소분류명을 확인해 주세요.", False)
    if len(new_name) > 150:
        return _finish("소분류명은 150자 이하로 입력해 주세요.", False)

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category or not category.active:
        return _finish("수정할 소분류를 찾을 수 없습니다.", False)

    department, error = _resolve_department(payload, fallback_category=category)
    if error:
        return error
    if category.department_id != department.id:
        return _finish("본인 소속 부서(팀)의 소분류만 수정할 수 있습니다.", False, department.id)
    if not category.small_name:
        return _finish("소분류 미지정 항목은 수정할 수 없습니다.", False, department.id, category.middle_name)
    if category.small_name == new_name:
        return _finish("변경된 내용이 없습니다.", True, department.id, category.middle_name, category.id)

    conflict = core.db.session.scalar(
        select(core.WorkCategory.id).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == category.middle_name,
            core.WorkCategory.small_name == new_name,
            core.WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _finish(
            "같은 중분류 아래에 동일한 소분류가 이미 존재합니다.",
            False,
            department.id,
            category.middle_name,
            category.id,
        )

    previous = category.small_name
    try:
        category.small_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "department_name": department.name,
                "middle_name": category.middle_name,
                "previous_small_name": previous,
                "new_small_name": new_name,
                "source": SOURCE,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _finish(
            "중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.",
            False,
            department.id,
            category.middle_name,
        )
    except Exception as exc:
        core.db.session.rollback()
        return _finish(
            f"소분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            False,
            department.id,
            category.middle_name,
        )

    return _finish("소분류명을 수정했습니다.", True, department.id, category.middle_name, category.id)


HANDLERS = {
    "add": _handle_add,
    "rename_middle": _handle_rename_middle,
    "rename_small": _handle_rename_small,
}


class TaskCategoryWSGIGuard:
    """Handle all category-manager transports before the legacy task validator."""

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _classify(environ):
        path = (environ.get("PATH_INFO") or "").rstrip("/") or "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        if path != TARGET_PATH or method != "POST":
            return None

        query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
        if (
            query.get("category_manager", [""])[-1] == "1"
            and query.get("category_transport", [""])[-1] == "v9"
        ):
            return "v9"

        accept = (environ.get("HTTP_ACCEPT") or "").lower()
        requested_with = (environ.get("HTTP_X_REQUESTED_WITH") or "").lower()
        if "application/json" in accept and requested_with == "xmlhttprequest":
            return "ajax"
        return None

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/task-category-wsgi-v11":
            return _text_response(start_response, "200 OK", "task_category_wsgi_guard=v11 active")

        mode = self._classify(environ)
        if mode is None:
            return self.downstream(environ, start_response)

        with flask_app.request_context(environ):
            try:
                validate_csrf(
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
            except ValidationError:
                result = _finish(
                    "요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.",
                    False,
                )
            else:
                if not current_user.is_authenticated:
                    result = redirect(url_for("login"))
                else:
                    payload = _payload()
                    action = str(
                        request.args.get("category_action")
                        or request.headers.get("X-Task-Category-Action")
                        or payload.get("category_action")
                        or ""
                    ).strip()
                    handler = HANDLERS.get(action)
                    if handler is None:
                        result = _finish("지원하지 않는 업무구분 작업입니다.", False)
                    else:
                        result = handler(payload)

            response = flask_app.make_response(result)
            response.headers["X-MedPark-Task-Category-WSGI"] = "v11"
            response.headers["X-Task-Category-Dispatch"] = "wsgi-v11"
            response.headers["Cache-Control"] = "no-store"
            response = flask_app.process_response(response)
            return response(environ, start_response)


app = TaskCategoryWSGIGuard(flask_app.wsgi_app)
