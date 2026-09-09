from flask import jsonify, request
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

import admin_work_category_server_v19 as v19

core = v19.core


def _api_json(message, ok=True, status=200):
    return jsonify({
        'ok': bool(ok),
        'message': message,
        'transport': 'admin-work-category-api-v24',
    }), status


@core.app.route('/awc-api-v24', methods=['GET', 'POST'])
def admin_work_category_api_v24():
    if request.method == 'GET':
        return jsonify({
            'ok': True,
            'transport': 'admin-work-category-api-v24',
            'method': 'POST',
        })

    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        return _api_json('요청 보안 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.', False, 400)

    if not current_user.is_authenticated:
        return _api_json('로그인이 필요합니다.', False, 401)
    if not v19._is_admin():
        return _api_json('관리자 권한이 필요합니다.', False, 403)

    operation = str(request.form.get('operation') or '').strip()
    if operation not in v19.HANDLERS:
        return _api_json('지원하지 않는 업무구분 작업입니다.', False, 400)

    try:
        result = v19.HANDLERS[operation]()
        response = core.app.make_response(result)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-MedPark-Admin-Work-Category'] = 'api-v24'
        return response
    except Exception as exc:
        core.db.session.rollback()
        return _api_json(f'업무구분 처리 중 오류가 발생했습니다. ({type(exc).__name__})', False, 500)


core.csrf.exempt(admin_work_category_api_v24)
