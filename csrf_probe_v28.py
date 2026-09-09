from flask import jsonify, request
from flask_wtf.csrf import generate_csrf

import app as core


@core.app.route('/csrf-probe-v28', methods=['GET', 'POST'])
def csrf_probe_v28():
    if request.method == 'GET':
        return jsonify({'ok': True, 'csrf_token': generate_csrf()})
    return jsonify({'ok': True, 'method': 'POST', 'form': request.form.to_dict(flat=True)})
