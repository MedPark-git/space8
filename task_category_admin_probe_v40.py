from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import app as core


@core.app.get('/__health/task-category-admin-v40-post')
def task_category_admin_v40_post_probe():
    payload = urlencode({
        'operation': 'rename_small',
        'awc_operation': 'rename_small',
        'category_action': 'rename_small',
        'work_category_id': '999999999',
        'new_small_name': 'diagnostic-only',
        'awc_source': 'v40-probe',
    }).encode('utf-8')
    req = Request(
        'https://medprk-management-task.mycafe24.ai/tasks/new?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=v40',
        data=payload,
        method='POST',
        headers={
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-MedPark-Category-JSON': '1',
            'X-Task-Category-Action': 'rename_small',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'MedPark-V40-Probe/1.0',
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '')
            marker = response.headers.get('X-MedPark-Task-Category-WSGI', '')
            body = response.read(200).decode('utf-8', errors='replace')
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get('Content-Type', '') if exc.headers else ''
        marker = exc.headers.get('X-MedPark-Task-Category-WSGI', '') if exc.headers else ''
        body = exc.read(200).decode('utf-8', errors='replace')
    except Exception as exc:
        status = 0
        content_type = type(exc).__name__
        marker = ''
        body = str(exc)

    ok = status == 400 and 'application/json' in content_type.lower() and marker == 'v14'
    return (
        f'ok={int(ok)} status={status} type={content_type} marker={marker} body={body[:120]}',
        200 if ok else 500,
        {'Cache-Control': 'no-store'},
    )
