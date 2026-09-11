"""Direct Flask route registration for administrator work-category CRUD.

This module is imported from sitecustomize so routes are attached to the core
Flask app even when Cafe24 launches app.py directly instead of the Procfile WSGI
wrapper.
"""

import admin_work_category_server_v19 as api

core = api.core

MANAGE_PATH = "/admin/work-categories/manage"
V48_PATH = "/admin/work-categories/manage-v48"
HEALTH_PATH = "/__health/admin-work-category-v49"

# Make the existing v19 before_request dispatcher recognize the V48 alias too.
api.TARGET_PATHS.add(V48_PATH)
api.LEGACY_JSON_PATHS.add(V48_PATH)


def _rules():
    return {rule.rule for rule in core.app.url_map.iter_rules()}


# v19 already registers MANAGE_PATH when imported. Register the V48 alias on
# the same Flask app so both current and stale browser transports are valid.
if V48_PATH not in _rules():
    core.app.add_url_rule(
        V48_PATH,
        endpoint="admin_work_category_manage_v49_alias",
        view_func=lambda: api._json(
            "업무구분 요청을 처리하지 못했습니다. 화면을 새로고침해 주세요.",
            False,
            400,
        ),
        methods=["POST"],
    )


if HEALTH_PATH not in _rules():
    def _health():
        rules = sorted(
            rule.rule
            for rule in core.app.url_map.iter_rules()
            if rule.rule in {MANAGE_PATH, V48_PATH, HEALTH_PATH}
        )
        hooks = [
            getattr(fn, "__name__", "")
            for fn in core.app.before_request_funcs.get(None, [])[:8]
        ]
        return {
            "ok": MANAGE_PATH in rules and V48_PATH in rules,
            "transport": "direct-flask-v49",
            "rules": rules,
            "first_hooks": hooks,
        }

    core.app.add_url_rule(
        HEALTH_PATH,
        endpoint="admin_work_category_v49_health",
        view_func=_health,
        methods=["GET"],
    )


app = core.app
