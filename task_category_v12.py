from flask import jsonify, redirect, request, url_for
from flask_login import current_user

import task_category_wsgi_guard as guard

flask_app = guard.flask_app


@flask_app.post("/tasks/category-manager/v12")
def task_category_manager_v12():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    payload = guard._payload()
    action = str(
        request.form.get("category_action")
        or request.args.get("category_action")
        or request.headers.get("X-Task-Category-Action")
        or payload.get("category_action")
        or ""
    ).strip()

    handler = guard.HANDLERS.get(action)
    if handler is None:
        return guard._finish("지원하지 않는 업무구분 작업입니다.", False)
    return handler(payload)


@flask_app.get("/__health/task-category-v12")
def task_category_v12_health():
    return jsonify(
        {
            "ok": True,
            "runtime": "task_category_v12",
            "post_path": "/tasks/category-manager/v12",
            "actions": sorted(guard.HANDLERS),
        }
    )


app = guard.app
