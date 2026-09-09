import inspect
from flask import Response
import app as core


def _extract_admin_source():
    fn = core.app.view_functions.get('admin')
    if fn is None:
        return 'admin view not found'
    try:
        source = inspect.getsource(fn)
    except Exception as exc:
        return f'inspect failed: {type(exc).__name__}: {exc}'
    lines = source.splitlines()
    keywords = ('work-categories', 'work_category', 'action', 'toggle', 'abort(', 'section')
    picked = []
    for i, line in enumerate(lines):
        if any(keyword in line for keyword in keywords):
            start = max(0, i - 6)
            end = min(len(lines), i + 12)
            picked.extend(range(start, end))
    if not picked:
        return source[:12000]
    ordered = []
    seen = set()
    for i in sorted(set(picked)):
        if i in seen:
            continue
        seen.add(i)
        ordered.append(f'{i+1:04d}: {lines[i]}')
    return '\n'.join(ordered)[:18000]


@core.app.get('/__health/admin-route-source-v35')
def admin_route_source_v35():
    return Response(_extract_admin_source(), mimetype='text/plain')
