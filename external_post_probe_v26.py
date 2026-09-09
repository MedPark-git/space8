import json
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar

import app as core


def _post(url, headers=None, payload=None, opener=None):
    data = urllib.parse.urlencode(payload or {
        'operation': 'rename_small',
        'work_category_id': '999999999',
        'new_small_name': 'diagnostic-only',
    }).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'MedPark-AISpace-Diagnostic/1.0',
            **(headers or {}),
        },
    )
    client = opener or urllib.request
    try:
        with client.open(request, timeout=10) as response:
            return response.status, response.headers.get('Content-Type', ''), response.read(180).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.headers.get('Content-Type', '') if exc.headers else ''), exc.read(180).decode('utf-8', errors='replace')
    except Exception as exc:
        return 0, type(exc).__name__, str(exc)


def _csrf_roundtrip(base):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(base + '/csrf-probe-v28', timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
            token = str(payload.get('csrf_token') or '')
    except Exception as exc:
        return ('get_error', 0, type(exc).__name__, str(exc)), ('invalid_skip', 0, '', '')

    valid = _post(
        base + '/csrf-probe-v28',
        {'Accept': 'application/json'},
        {'csrf_token': token, 'probe': 'valid'},
        opener,
    )
    invalid = _post(
        base + '/csrf-probe-v28',
        {'Accept': 'application/json'},
        {'csrf_token': 'invalid-token', 'probe': 'invalid'},
        opener,
    )
    return ('valid', *valid), ('invalid', *invalid)


@core.app.get('/__health/external-post-v26')
def external_post_v26():
    base = 'https://medprk-management-task.mycafe24.ai'
    echo = _post(base + '/post-echo-v27', payload={'probe': 'v27'})
    api = _post(base + '/awc-api-v24', {'Accept': 'application/json'})
    admin_plain = _post(base + '/admin?section=work-categories')
    admin_xhr = _post(base + '/admin?section=work-categories', {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })
    csrf_valid, csrf_invalid = _csrf_roundtrip(base)
    text = (
        f'echo_status={echo[0]} echo_type={echo[1]} '
        f'api_status={api[0]} api_type={api[1]} '
        f'admin_plain_status={admin_plain[0]} admin_plain_type={admin_plain[1]} '
        f'admin_xhr_status={admin_xhr[0]} admin_xhr_type={admin_xhr[1]} '
        f'csrf_valid_status={csrf_valid[1]} csrf_valid_type={csrf_valid[2]} '
        f'csrf_invalid_status={csrf_invalid[1]} csrf_invalid_type={csrf_invalid[2]}'
    )
    print('[external-post-v28] ' + text, flush=True)
    return text, 200, {'Cache-Control': 'no-store'}
