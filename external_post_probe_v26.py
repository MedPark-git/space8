import urllib.parse
import urllib.request
import urllib.error

import app as core


def _post(url, headers=None):
    payload = urllib.parse.urlencode({
        'operation': 'rename_small',
        'work_category_id': '999999999',
        'new_small_name': 'diagnostic-only',
    }).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=payload,
        method='POST',
        headers={
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'MedPark-AISpace-Diagnostic/1.0',
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers.get('Content-Type', ''), response.read(160).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.headers.get('Content-Type', '') if exc.headers else ''), exc.read(160).decode('utf-8', errors='replace')
    except Exception as exc:
        return 0, type(exc).__name__, str(exc)


@core.app.get('/__health/external-post-v26')
def external_post_v26():
    base = 'https://medprk-management-task.mycafe24.ai'
    api = _post(base + '/awc-api-v24', {'Accept': 'application/json'})
    admin_plain = _post(base + '/admin?section=work-categories')
    admin_xhr = _post(base + '/admin?section=work-categories', {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })
    text = (
        f'api_status={api[0]} api_type={api[1]} '
        f'admin_plain_status={admin_plain[0]} admin_plain_type={admin_plain[1]} '
        f'admin_xhr_status={admin_xhr[0]} admin_xhr_type={admin_xhr[1]}'
    )
    print('[external-post-v26] ' + text, flush=True)
    return text, 200, {'Cache-Control': 'no-store'}
