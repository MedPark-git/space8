import sys

import task_editor_runtime as runtime

FLASK_APP = runtime.FLASK_APP


@FLASK_APP.get('/__diag/runtime')
def runtime_diagnostic():
    rules = []
    for rule in FLASK_APP.url_map.iter_rules():
        if (
            rule.rule.startswith('/tasks')
            or 'work-categor' in rule.rule
            or rule.rule.startswith('/admin/work-categories')
        ):
            rules.append({
                'rule': rule.rule,
                'methods': sorted(method for method in rule.methods if method not in {'HEAD', 'OPTIONS'}),
                'endpoint': rule.endpoint,
                'view': getattr(FLASK_APP.view_functions.get(rule.endpoint), '__name__', str(FLASK_APP.view_functions.get(rule.endpoint))),
            })
    before = []
    for scope, funcs in FLASK_APP.before_request_funcs.items():
        before.append({
            'scope': scope,
            'functions': [getattr(func, '__name__', repr(func)) for func in funcs],
        })
    return FLASK_APP.json.response({
        'ok': True,
        'runtime_module': runtime.__name__,
        'outer_app_type': type(runtime.app).__name__,
        'flask_app_type': type(FLASK_APP).__name__,
        'flask_wsgi_app_type': type(FLASK_APP.wsgi_app).__name__,
        'space8_extension_loaded': 'space8_extension' in sys.modules,
        'before_request': before,
        'routes': rules,
    })


app = runtime.app
