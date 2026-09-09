from flask import jsonify, request

import app as core


@core.app.route('/post-echo-v27', methods=['GET', 'POST'])
def post_echo_v27():
    if request.method == 'GET':
        return jsonify({'ok': True, 'method': 'GET', 'route': '/post-echo-v27'})
    return jsonify({
        'ok': True,
        'method': 'POST',
        'route': '/post-echo-v27',
        'content_type': request.content_type or '',
        'form': request.form.to_dict(flat=True),
    })


core.csrf.exempt(post_echo_v27)
