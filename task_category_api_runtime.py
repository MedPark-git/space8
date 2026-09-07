from flask import jsonify, request

import task_category_modal_runtime as modal_runtime
import task_category_runtime as base_runtime

app = modal_runtime.app


def _direct_task_category_api():
    path = request.path

    if path == "/tasks/work-categories/list" and request.method == "GET":
        return modal_runtime.task_work_category_list_inline()

    if path == "/tasks/work-categories/add" and request.method == "POST":
        return base_runtime.task_work_category_add_inline()

    if path == "/tasks/work-categories/rename-middle" and request.method == "POST":
        return modal_runtime.task_work_category_rename_middle_inline()

    if path == "/tasks/work-categories/rename-small" and request.method == "POST":
        return modal_runtime.task_work_category_rename_small_inline()

    return None


# Put the category API dispatcher before the legacy menu/path guards so these
# four authenticated API endpoints do not fall through to the app's 404 guard.
app.before_request_funcs.setdefault(None, []).insert(0, _direct_task_category_api)


@app.get("/__health/task-category-api-runtime")
def task_category_api_runtime_health():
    return jsonify({
        "ok": True,
        "runtime": "task_category_api_runtime",
        "paths": [
            "/tasks/work-categories/list",
            "/tasks/work-categories/add",
            "/tasks/work-categories/rename-middle",
            "/tasks/work-categories/rename-small",
        ],
    })
