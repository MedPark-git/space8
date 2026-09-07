import inspect

from flask import jsonify

import task_category_runtime as runtime

app = runtime.app


@app.get('/__health/task-category-before-requests')
def task_category_before_requests_health():
    items = []
    for index, func in enumerate(app.before_request_funcs.get(None, [])):
        try:
            source = inspect.getsource(func)
        except Exception:
            source = ''
        items.append({
            'index': index,
            'name': getattr(func, '__name__', func.__class__.__name__),
            'module': getattr(func, '__module__', ''),
            'has_abort_404': 'abort(404)' in source,
            'has_request_path': 'request.path' in source,
            'has_menu': 'menu' in source.lower(),
            'source_head': source[:1200],
        })
    return jsonify({'ok': True, 'before_request': items})
