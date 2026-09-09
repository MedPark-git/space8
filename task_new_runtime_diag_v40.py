import app as core


def _task_new_rule():
    for rule in core.app.url_map.iter_rules():
        if rule.rule == '/tasks/new':
            return rule
    return None


@core.app.get('/__health/task-new-runtime-v40')
def task_new_runtime_v40():
    rule = _task_new_rule()
    endpoint = rule.endpoint if rule else ''
    view = core.app.view_functions.get(endpoint) if endpoint else None
    hooks = core.app.before_request_funcs.get(None, [])
    first = hooks[0] if hooks else None
    return (
        'task_new_runtime=v40 '
        f'rule={getattr(rule, "rule", "")} '
        f'endpoint={endpoint} '
        f'methods={",".join(sorted(rule.methods)) if rule else ""} '
        f'view_name={getattr(view, "__name__", "")} '
        f'view_module={getattr(view, "__module__", "")} '
        f'before_first={getattr(first, "__name__", "")} '
        f'before_first_module={getattr(first, "__module__", "")} ',
        200,
        {'Cache-Control': 'no-store'},
    )
