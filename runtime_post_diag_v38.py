from flask import jsonify

import app as core


@core.app.get('/__health/runtime-post-diag-v38')
def runtime_post_diag_v38():
    hooks = []
    for fn in core.app.before_request_funcs.get(None, []):
        hooks.append({
            'name': getattr(fn, '__name__', ''),
            'module': getattr(fn, '__module__', ''),
        })
    rules = []
    for rule in core.app.url_map.iter_rules():
        if rule.rule in {
            '/api/admin/work-category-v38',
            '/__internal/admin-work-category-v37',
            '/admin',
            '/admin/work-categories',
        }:
            rules.append({
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': sorted(rule.methods),
            })
    exempt = sorted(getattr(core.csrf, '_exempt_views', set()))
    return jsonify({
        'ok': True,
        'hooks': hooks,
        'rules': rules,
        'csrf_exempt': exempt,
    })
