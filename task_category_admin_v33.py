from sqlalchemy import select

import task_category_wsgi_guard as guard

core = guard.core


def _handle_delete(payload):
    if not guard._is_admin():
        return guard._finish("관리자 권한이 필요합니다.", False, status=403)

    category_id = guard._int_value(payload.get("work_category_id"))
    if not category_id:
        return guard._finish("삭제할 업무구분을 확인해 주세요.", False, status=400)

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category:
        return guard._finish("삭제할 업무구분을 찾을 수 없습니다.", False, status=404)

    task_count = len(category.tasks)
    if task_count:
        return guard._finish(
            f"이 업무구분은 {task_count}개의 업무에서 사용 중이라 삭제할 수 없습니다. 미사용 전환을 이용해 주세요.",
            False,
            department_id=category.department_id,
            middle_name=category.middle_name,
            category_id=category.id,
            status=409,
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
            return guard._finish(
                "하위 소분류가 있어 중분류를 삭제할 수 없습니다. 소분류를 먼저 정리해 주세요.",
                False,
                department_id=category.department_id,
                middle_name=category.middle_name,
                category_id=category.id,
                status=409,
            )

    details = {
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
        "work_category_id": category.id,
        "source": "task-category-admin-v33",
    }
    core.audit("ADMIN_WORK_CATEGORY_DELETE", f"work-category:{category.id}", details)
    core.db.session.delete(category)
    core.db.session.commit()
    return guard._finish(
        "업무구분을 삭제했습니다.",
        True,
        department_id=details["department_id"],
        middle_name=details["middle_name"],
    )


guard.HANDLERS["delete"] = _handle_delete


@guard.flask_app.get("/__health/task-category-admin-v33")
def task_category_admin_v33_health():
    return (
        "task_category_admin=v33 active=1 handlers=" + ",".join(sorted(guard.HANDLERS)),
        200,
        {"Cache-Control": "no-store"},
    )
