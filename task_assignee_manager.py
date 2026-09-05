from flask import abort, g, has_request_context, jsonify, request
from flask_login import login_required
from sqlalchemy import select

import app as core_app
import space8_extension  # noqa: F401
from app import AuditLog, Employee, Task, audit, db

app = space8_extension.app

ASSIGNEE_OVERRIDE_ACTION = "TASK_ASSIGNEE_UPDATE"
_ORIGINAL_DISPLAY_ASSIGNEES = Task.display_assignees.fget


def _task_override_ids():
    if not has_request_context():
        return set()
    cached = getattr(g, "_task_assignee_override_ids", None)
    if cached is not None:
        return cached
    targets = db.session.scalars(
        select(AuditLog.target)
        .where(AuditLog.action == ASSIGNEE_OVERRIDE_ACTION)
        .distinct()
    ).all()
    override_ids = set()
    for target in targets:
        if not target or not target.startswith("task:"):
            continue
        try:
            override_ids.add(int(target.split(":", 1)[1]))
        except (TypeError, ValueError):
            continue
    g._task_assignee_override_ids = override_ids
    return override_ids


def _has_manual_assignee_override(task_id):
    return bool(task_id and task_id in _task_override_ids())


def _display_assignees(task):
    if _has_manual_assignee_override(task.id):
        return task.assignee.name if task.assignee else "-"
    return _ORIGINAL_DISPLAY_ASSIGNEES(task)


Task.display_assignees = property(_display_assignees)


def _parse_task_ids():
    values = []
    for raw in request.args.getlist("task_ids"):
        values.extend(str(raw or "").split(","))
    ids = []
    seen = set()
    for value in values:
        try:
            task_id = int(value)
        except (TypeError, ValueError):
            continue
        if task_id <= 0 or task_id in seen:
            continue
        seen.add(task_id)
        ids.append(task_id)
        if len(ids) >= 200:
            break
    return ids


def _can_view_task(task):
    return bool(task and task.deleted_at is None and core_app.can_view_task_detail(task))


def _active_department_employees(department_ids):
    if not department_ids:
        return []
    return db.session.scalars(
        select(Employee)
        .where(
            Employee.department_id.in_(department_ids),
            Employee.status == "재직",
            Employee.approval_status == "승인완료",
        )
        .order_by(Employee.department_id, Employee.name, Employee.id)
    ).all()


@app.get("/tasks/assignee-metadata")
@login_required
def task_assignee_metadata():
    task_ids = _parse_task_ids()
    if not task_ids:
        return jsonify({"ok": True, "tasks": {}, "departments": {}})

    tasks = db.session.scalars(
        select(Task)
        .where(Task.id.in_(task_ids), Task.deleted_at.is_(None))
        .order_by(Task.id)
    ).all()
    visible_tasks = [task for task in tasks if _can_view_task(task)]
    department_ids = {
        task.department_id
        for task in visible_tasks
        if core_app.can_edit_task(task)
    }

    departments = {}
    for employee in _active_department_employees(department_ids):
        departments.setdefault(str(employee.department_id), []).append(
            {
                "id": employee.id,
                "name": employee.name,
                "position": employee.position or "",
                "label": " · ".join(
                    value
                    for value in (employee.name, employee.position or "")
                    if value
                ),
            }
        )

    payload = {}
    for task in visible_tasks:
        payload[str(task.id)] = {
            "id": task.id,
            "department_id": task.department_id,
            "department_name": task.department.name,
            "current_assignee_id": task.assignee_id,
            "current_label": task.display_assignees,
            "editable": bool(core_app.can_edit_task(task)),
            "original_assignees": task.source_assignees or "",
        }

    return jsonify({"ok": True, "tasks": payload, "departments": departments})


@app.post("/tasks/<int:task_id>/assignee")
@login_required
def task_assignee_update(task_id):
    task = core_app.get_active_task_or_404(task_id)
    if not core_app.can_edit_task(task):
        abort(403)

    assignee_id = request.form.get("assignee_id", type=int)
    if not assignee_id:
        return jsonify({"ok": False, "message": "변경할 담당자를 선택해 주세요."}), 400

    assignee = db.session.get(Employee, assignee_id)
    if (
        not assignee
        or assignee.status != "재직"
        or assignee.approval_status != "승인완료"
    ):
        return jsonify({"ok": False, "message": "재직 중이며 승인 완료된 임직원만 담당자로 지정할 수 있습니다."}), 400

    if assignee.department_id != task.department_id:
        return jsonify({"ok": False, "message": "해당 업무와 같은 부서(팀)의 임직원만 담당자로 지정할 수 있습니다."}), 400

    previous_assignee_id = task.assignee_id
    previous_display = task.display_assignees
    had_override = _has_manual_assignee_override(task.id)

    if previous_assignee_id == assignee.id and had_override:
        return jsonify(
            {
                "ok": True,
                "message": "이미 선택된 담당자입니다.",
                "task_id": task.id,
                "assignee_id": assignee.id,
                "assignee_name": assignee.name,
            }
        )

    task.assignee_id = assignee.id
    audit(
        ASSIGNEE_OVERRIDE_ACTION,
        f"task:{task.id}",
        {
            "previous_assignee_id": previous_assignee_id,
            "previous_display": previous_display,
            "new_assignee_id": assignee.id,
            "new_assignee_name": assignee.name,
            "department_id": task.department_id,
            "department_name": task.department.name,
            "original_source_assignees": task.source_assignees,
        },
    )
    db.session.commit()

    if has_request_context() and hasattr(g, "_task_assignee_override_ids"):
        delattr(g, "_task_assignee_override_ids")

    return jsonify(
        {
            "ok": True,
            "message": f"담당자를 {assignee.name}(으)로 변경했습니다.",
            "task_id": task.id,
            "assignee_id": assignee.id,
            "assignee_name": assignee.name,
        }
    )


@app.after_request
def inject_task_assignee_manager(response):
    if (
        request.path.startswith("/tasks")
        and response.mimetype == "text/html"
        and response.status_code < 400
    ):
        html = response.get_data(as_text=True)
        asset = "/static/task_assignee_manager.js?v=20260905-assignee-manager"
        if asset not in html and "</body>" in html:
            html = html.replace(
                "</body>",
                f'<script src="{asset}" defer></script></body>',
            )
            response.set_data(html)
            response.headers.pop("Content-Length", None)
    return response
