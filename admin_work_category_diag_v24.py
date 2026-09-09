from flask import jsonify

import app as core


@core.app.get('/__health/admin-work-category-post-diagnostic-v24')
def admin_work_category_post_diagnostic_v24():
    rules = []
    for rule in core.app.url_map.iter_rules():
        if rule.rule.startswith('/admin'):
            rules.append({
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': sorted(rule.methods),
            })

    with core.app.test_client() as client:
        response = client.post(
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
        preview = response.get_data(as_text=True)[:240]
        result = {
            'ok': True,
            'post_status': response.status_code,
            'post_content_type': response.content_type,
            'post_location': response.headers.get('Location', ''),
            'post_preview': preview,
            'admin_rules': rules,
        }
    return jsonify(result)
