from flask import Response
from sqlalchemy import select

import app as core_app
import journal_board_stable_manager as stable

app = stable.app


@app.get('/__health/journals-all-users')
def journals_all_users_health():
    users = core_app.db.session.scalars(
        select(core_app.Employee)
        .where(
            core_app.Employee.status == '재직',
            core_app.Employee.approval_status == '승인완료',
        )
        .order_by(core_app.Employee.id)
    ).all()

    failures = 0
    status_counts = {}
    for user in users:
        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        response = client.get('/journals')
        status = int(response.status_code)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status >= 400:
            failures += 1

    summary = ','.join(f'{code}:{count}' for code, count in sorted(status_counts.items()))
    return Response(
        f'tested={len(users)} failures={failures} statuses={summary}',
        status=200 if failures == 0 else 503,
        mimetype='text/plain',
    )
