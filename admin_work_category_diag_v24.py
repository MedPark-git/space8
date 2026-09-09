from flask import jsonify

import app as core


@core.app.get('/__health/admin-work-category-post-diagnostic-v24')
def admin_work_category_post_diagnostic_v24():
    rules = []
    for rule in core.app.url_map.iter_rules():
        if rule.rule.startswith('/admin') or rule.rule == '/awc-api-v24':
            rules.append({
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': sorted(rule.methods),
            })

    with core.app.test_client() as client:
        admin_response = client.post(
            '/admin?section=work-categories',
            data={
                'operation': 'rename_small',
                'awc_operation': 'rename_small',
                'awc_source': 'v24-diagnostic',
                'awc_response': 'json',
                'work_category_id': '999999999',
                'new_small_name': 'diagnostic-only',
            },
            headers={
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            follow_redirects=False,
        )
        api_response = client.post(
            '/awc-api-v24',
            data={
                'operation': 'rename_small',
                'awc_source': 'v25-diagnostic',
                'awc_response': 'json',
                'work_category_id': '999999999',
                'new_small_name': 'diagnostic-only',
            },
            headers={
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            follow_redirects=False,
        )

    return jsonify({
        'ok': True,
        'admin_post': {
            'status': admin_response.status_code,
            'content_type': admin_response.content_type,
            'location': admin_response.headers.get('Location', ''),
            'preview': admin_response.get_data(as_text=True)[:180],
        },
        'api_post': {
            'status': api_response.status_code,
            'content_type': api_response.content_type,
            'location': api_response.headers.get('Location', ''),
            'preview': api_response.get_data(as_text=True)[:180],
        },
        'rules': rules,
    })
