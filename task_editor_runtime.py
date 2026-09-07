import io
from urllib.parse import parse_qs

from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app as core

FLASK_APP = core.app
TRANSPORT_VERSION = "task-category-transport-v6"
ALLOWED_ACTIONS = {"list", "add", "rename_middle", "rename_small"}


def _json_response(payload, status=200):
    return jsonify({"transport": TRANSPORT_VERSION, **payload}), status


def _json_error(message, status=400, code=None):
    payload = {"ok": False, "message": message}
    if code:
        payload["code"] = code
    return _json_response(payload, status)


def _json_ok(message="", **extra):
    payload = {"ok": True, **extra}
    if message:
        payload["message"] = message
    return _json_response(payload)


def _is_admin():
    return bool(
        current_user.is_authenticated
        and (current_user.role.name == "관리자" or current_user.role.allows("task_manage_all"))
    )


def _allowed_department(department_id):
    try:
        department_id = int(department_id or 0)
    except (TypeError, ValueError):
        department_id = 0
    if not department_id:
        return None, _json_error("대분류(부서·팀)를 선택해 주세요.", 400, "DEPARTMENT_REQUIRED")
    department = core.db.session.get(core.Department, department_id)
    if not department or not department.active:
        return None, _json_error("사용 가능한 부서(팀)를 찾을 수 없습니다.", 404, "DEPARTMENT_NOT_FOUND")
    if not _is_admin() and current_user.department_id != department.id:
        return None, _json_error(
            "본인 소속 부서(팀)의 중분류·소분류만 관리할 수 있습니다.",
            403,
            "CATEGORY_FORBIDDEN",
        )
    return department, None


def _visible_categories():
    rows = (
        core.active_work_categories()
        if _is_admin()
        else core.active_work_categories([current_user.department_id])
    )
    return core.build_work_category_catalog(rows)


def _category_payload(category):
    return {
        "id": category.id,
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
    }


def _handle_add():
    department, error = _allowed_department(request.form.get("department_id"))
    if error:
        return error
    middle_name = str(request.form.get("middle_name") or "").strip()
    small_name = str(request.form.get("small_name") or "").strip()
    if not middle_name:
        return _json_error("중분류명을 확인해 주세요.", 400, "MIDDLE_REQUIRED")
    if len(middle_name) > 100:
        return _json_error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_TOO_LONG")
    if len(small_name) > 150:
        return _json_error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_TOO_LONG")

    category = core.db.session.scalar(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == middle_name,
            core.WorkCategory.small_name == small_name,
        )
    )
    if category and category.active:
        return _json_ok(
            "이미 등록된 업무구분입니다. 저장된 기초자료를 다시 불러왔습니다.",
            category=_category_payload(category),
            categories=_visible_categories(),
            duplicate=True,
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
        )
        core.db.session.add(category)

    try:
        core.db.session.flush()
        core.audit(
            "TASK_WORK_CATEGORY_CREATE" if created else "TASK_WORK_CATEGORY_REACTIVATE",
            f"work-category:{category.id}",
            {
                "department_id": department.id,
                "middle_name": middle_name,
                "small_name": small_name,
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error("동일한 업무구분이 이미 존재합니다.", 409, "CATEGORY_CONFLICT")
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"업무구분 등록 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "CATEGORY_ADD_ERROR",
        )
    return _json_ok(
        "업무구분을 등록했습니다.",
        category=_category_payload(category),
        categories=_visible_categories(),
    )


def _handle_rename_middle():
    department, error = _allowed_department(request.form.get("department_id"))
    if error:
        return error
    old_name = str(request.form.get("old_middle_name") or "").strip()
    new_name = str(request.form.get("new_middle_name") or "").strip()
    if not old_name or not new_name:
        return _json_error("수정할 중분류와 새 중분류명을 확인해 주세요.", 400, "MIDDLE_REQUIRED")
    if len(new_name) > 100:
        return _json_error("중분류명은 100자 이하로 입력해 주세요.", 400, "MIDDLE_TOO_LONG")
    if old_name == new_name:
        return _json_ok("변경된 내용이 없습니다.", categories=_visible_categories())

    rows = core.db.session.scalars(
        select(core.WorkCategory).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == old_name,
            core.WorkCategory.active.is_(True),
        )
    ).all()
    if not rows:
        return _json_error("수정할 중분류를 찾을 수 없습니다.", 404, "MIDDLE_NOT_FOUND")

    row_ids = {row.id for row in rows}
    small_names = {row.small_name for row in rows}
    conflict = core.db.session.scalar(
        select(core.WorkCategory.id)
        .where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == new_name,
            core.WorkCategory.small_name.in_(small_names),
            core.WorkCategory.id.not_in(row_ids),
        )
        .limit(1)
    )
    if conflict:
        return _json_error(
            "변경하려는 중분류명에 동일한 소분류가 이미 존재합니다.",
            409,
            "MIDDLE_CONFLICT",
        )

    try:
        for row in rows:
            row.middle_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_MIDDLE_RENAME",
            f"department:{department.id}",
            {
                "previous_middle_name": old_name,
                "new_middle_name": new_name,
                "category_ids": sorted(row_ids),
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error(
            "중복된 업무구분이 있어 중분류명을 수정할 수 없습니다.",
            409,
            "MIDDLE_CONFLICT",
        )
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"중분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "MIDDLE_RENAME_ERROR",
        )
    return _json_ok("중분류명을 수정했습니다.", categories=_visible_categories())


def _handle_rename_small():
    try:
        category_id = int(request.form.get("work_category_id") or 0)
    except (TypeError, ValueError):
        category_id = 0
    new_name = str(request.form.get("new_small_name") or "").strip()
    if not category_id or not new_name:
        return _json_error("수정할 소분류와 새 소분류명을 확인해 주세요.", 400, "SMALL_REQUIRED")
    if len(new_name) > 150:
        return _json_error("소분류명은 150자 이하로 입력해 주세요.", 400, "SMALL_TOO_LONG")

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category or not category.active:
        return _json_error("수정할 소분류를 찾을 수 없습니다.", 404, "SMALL_NOT_FOUND")
    department, error = _allowed_department(category.department_id)
    if error:
        return error
    if not category.small_name:
        return _json_error("소분류 미지정 항목은 수정할 수 없습니다.", 400, "SMALL_PLACEHOLDER")
    if category.small_name == new_name:
        return _json_ok("변경된 내용이 없습니다.", categories=_visible_categories())

    conflict = core.db.session.scalar(
        select(core.WorkCategory.id).where(
            core.WorkCategory.department_id == department.id,
            core.WorkCategory.middle_name == category.middle_name,
            core.WorkCategory.small_name == new_name,
            core.WorkCategory.id != category.id,
        )
    )
    if conflict:
        return _json_error(
            "같은 중분류 아래에 동일한 소분류가 이미 존재합니다.",
            409,
            "SMALL_CONFLICT",
        )

    previous = category.small_name
    try:
        category.small_name = new_name
        core.audit(
            "TASK_WORK_CATEGORY_SMALL_RENAME",
            f"work-category:{category.id}",
            {
                "previous_small_name": previous,
                "new_small_name": new_name,
                "source": TRANSPORT_VERSION,
            },
        )
        core.db.session.commit()
    except IntegrityError:
        core.db.session.rollback()
        return _json_error(
            "중복된 업무구분이 있어 소분류명을 수정할 수 없습니다.",
            409,
            "SMALL_CONFLICT",
        )
    except Exception as exc:
        core.db.session.rollback()
        return _json_error(
            f"소분류 수정 중 오류가 발생했습니다. ({type(exc).__name__})",
            500,
            "SMALL_RENAME_ERROR",
        )
    return _json_ok("소분류명을 수정했습니다.", categories=_visible_categories())


HANDLERS = {
    "list": lambda: _json_ok(categories=_visible_categories()),
    "add": _handle_add,
    "rename_middle": _handle_rename_middle,
    "rename_small": _handle_rename_small,
}


@FLASK_APP.get("/__health/task-category-transport-v6")
def task_category_transport_health():
    return jsonify(
        {
            "ok": True,
            "transport": TRANSPORT_VERSION,
            "path": "/tasks/new",
            "detection": "query_header_or_form_body",
            "actions": sorted(HANDLERS),
        }
    )


class TaskCategoryTransportMiddleware:
    def __init__(self, flask_app):
        self.flask_app = flask_app

    def __call__(self, environ, start_response):
        path = str(environ.get("PATH_INFO") or "").rstrip("/")
        method = str(environ.get("REQUEST_METHOD") or "").upper()
        if path == "/__health/task-category-transport-v6-wsgi" and method == "GET":
            body = b'{"ok":true,"transport":"task-category-transport-v6","layer":"outer-wsgi-middleware"}'
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]
        if path != "/tasks/new" or method != "POST":
            return self.flask_app(environ, start_response)

        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            content_length = 0
        raw_body = environ.get("wsgi.input").read(content_length) if content_length > 0 else b""
        environ["wsgi.input"] = io.BytesIO(raw_body)

        query = parse_qs(str(environ.get("QUERY_STRING") or ""), keep_blank_values=True)
        form = parse_qs(raw_body.decode("utf-8", errors="replace"), keep_blank_values=True)
        query_action = str((query.get("category_action") or [""])[0]).strip()
        body_action = str((form.get("category_action") or [""])[0]).strip()
        header_action = str(environ.get("HTTP_X_TASK_CATEGORY_ACTION") or "").strip()
        action = next((value for value in (header_action, query_action, body_action) if value), "")

        query_transport = str((query.get("_category_transport") or [""])[0]).strip()
        body_transport = str((form.get("_category_transport") or [""])[0]).strip()
        header_transport = str(environ.get("HTTP_X_TASK_CATEGORY_TRANSPORT") or "").strip()
        transport = next(
            (value for value in (header_transport, query_transport, body_transport) if value),
            "",
        )

        if action not in ALLOWED_ACTIONS or transport != "v6":
            return self.flask_app(environ, start_response)

        environ["wsgi.input"] = io.BytesIO(raw_body)
        with self.flask_app.request_context(environ):
            if not current_user.is_authenticated:
                response = self.flask_app.make_response(
                    _json_error("로그인이 필요합니다.", 401, "LOGIN_REQUIRED")
                )
            else:
                core.csrf.protect()
                response = self.flask_app.make_response(HANDLERS[action]())
            return response(environ, start_response)


app = TaskCategoryTransportMiddleware(FLASK_APP)
