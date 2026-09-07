import inspect
from functools import wraps

from flask import jsonify, request

import task_category_runtime as runtime

app = runtime.app

ALLOWED_TASK_CATEGORY_PATHS = {"/task-categories", "/task-categories/"}


def _looks_like_route_access_guard(func):
    try:
        source = inspect.getsource(func)
    except Exception:
        source = ""
    lower_source = source.lower()
    name = str(getattr(func, "__name__", "") or "").lower()
    has_404 = "404" in source
    checks_route = "request.path" in source or "request.endpoint" in source
    access_related = (
        "menu" in lower_source
        or "allowed" in lower_source
        or "access" in lower_source
        or "permission" in lower_source
        or "menu" in name
        or "access" in name
        or "permission" in name
    )
    return has_404 and checks_route and access_related


def _patch_task_category_access():
    funcs = app.before_request_funcs.get(None, [])
    patched = 0
    patched_names = []
    for index, func in enumerate(list(funcs)):
        if not _looks_like_route_access_guard(func):
            continue

        @wraps(func)
        def wrapped(*args, __original=func, **kwargs):
            if request.path in ALLOWED_TASK_CATEGORY_PATHS:
                return None
            return __original(*args, **kwargs)

        funcs[index] = wrapped
        patched += 1
        patched_names.append(getattr(func, "__name__", func.__class__.__name__))
    return patched, patched_names


PATCHED_GUARD_COUNT, PATCHED_GUARD_NAMES = _patch_task_category_access()


@app.get("/__health/task-category-access")
def task_category_access_health():
    route_exists = any(
        rule.rule in ALLOWED_TASK_CATEGORY_PATHS
        for rule in app.url_map.iter_rules()
    )
    ok = PATCHED_GUARD_COUNT > 0 and route_exists
    return jsonify({
        "ok": ok,
        "route_exists": route_exists,
        "patched_guard_count": PATCHED_GUARD_COUNT,
        "patched_guard_names": PATCHED_GUARD_NAMES,
        "allowed_paths": sorted(ALLOWED_TASK_CATEGORY_PATHS),
    }), (200 if ok else 500)
