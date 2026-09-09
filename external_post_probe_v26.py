import urllib.parse
import urllib.request
import urllib.error

import app as core


@core.app.get('/__health/external-post-v26')
def external_post_v26():
    url = 'https://medprk-management-task.mycafe24.ai/awc-api-v24'
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
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'MedPark-AISpace-Diagnostic/1.0',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '')
            body = response.read(240).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get('Content-Type', '') if exc.headers else ''
        body = exc.read(240).decode('utf-8', errors='replace')
    except Exception as exc:
        status = 0
        content_type = type(exc).__name__
        body = str(exc)

    print(f'[external-post-v26] status={status} content_type={content_type} body={body[:160]}', flush=True)
    return (
        f'external_post_v26 status={status} content_type={content_type} body={body[:160]}',
        200,
        {'Cache-Control': 'no-store'},
    )
