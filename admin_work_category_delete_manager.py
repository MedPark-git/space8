from flask import abort, jsonify, request
from flask_login import current_user, login_required

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


@app.post("/admin/work-categories/delete-v2")
@login_required
def admin_work_category_delete_v2():
    if not _is_admin():
        abort(403)

    category_id = request.form.get("work_category_id", type=int)
    if not category_id:
        return jsonify({"ok": False, "message": "삭제할 업무구분을 확인해 주세요."}), 400

    category = core.db.session.get(core.WorkCategory, category_id)
    if not category:
        return jsonify({"ok": False, "message": "삭제할 업무구분을 찾을 수 없습니다."}), 404

    task_count = len(category.tasks)
    if task_count:
        return jsonify(
            {
                "ok": False,
                "message": f"이 업무구분은 {task_count}개의 업무에서 사용 중이라 삭제할 수 없습니다. 미사용 전환을 이용해 주세요.",
            }
        ), 409

    details = {
        "department_id": category.department_id,
        "department_name": category.department.name,
        "middle_name": category.middle_name,
        "small_name": category.small_name or "",
        "work_category_id": category.id,
        "source": "admin_work_category_delete_v2",
    }
    core.audit("ADMIN_WORK_CATEGORY_DELETE", f"work-category:{category.id}", details)
    core.db.session.delete(category)
    core.db.session.commit()
    return jsonify({"ok": True, "message": "업무구분을 삭제했습니다."})
