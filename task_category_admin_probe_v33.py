from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import task_category_wsgi_guard as guard


@guard.flask_app.get('/__health/task-category-admin-v33-post')
def task_category_admin_v33_post_health():
    url = (
        'https://medprk-management-task.mycafe24.ai/tasks/new'
        '?category_manager=1&category_transport=v14&category_action=rename_small&awc_admin=1'
    )
    payload = urlencode({
        'work_category_id': '999999999',
        'new_small_name': 'diagnostic-only',
        'category_action': 'rename_small',
        'awc_source': 'v33-self-test',
    }).encode('utf-8')
    request = Request(
        url,
        data=payload,
        method='POST',
        headers={
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-MedPark-Category-JSON': '1',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'MedPark-AISpace-V33-SelfTest/1.0',
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '')
            marker = response.headers.get('X-MedPark-Task-Category-WSGI', '')
            preview = response.read(180).decode('utf-8', errors='replace')
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get('Content-Type', '') if exc.headers else ''
        marker = exc.headers.get('X-MedPark-Task-Category-WSGI', '') if exc.headers else ''
        preview = exc.read(180).decode('utf-8', errors='replace')
    except Exception as exc:
        status = 0
        content_type = type(exc).__name__
        marker = ''
        preview = str(exc)

    return (
        f'post_status={status} type={content_type} marker={marker} preview={preview[:120]}',
        200,
        {'Cache-Control': 'no-store'},
    )
