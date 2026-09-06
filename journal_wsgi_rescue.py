from flask import Response

import journal_emergency_gateway as emergency

app = emergency.app


@app.get('/__health/journal-gateway')
def journal_gateway_health():
    return Response('journal_gateway=active', status=200, mimetype='text/plain')


class Journal500Rescue:
    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        is_journal_get = (
            environ.get('REQUEST_METHOD') == 'GET'
            and environ.get('PATH_INFO') == '/journals'
        )
        if not is_journal_get:
            return self.downstream(environ, start_response)

        captured = {'status': None, 'headers': None, 'exc_info': None}

        def capture_start_response(status, headers, exc_info=None):
            captured['status'] = status
            captured['headers'] = headers
            captured['exc_info'] = exc_info
            return lambda _data: None

        result = self.downstream(environ, capture_start_response)
        try:
            body = b''.join(result)
        finally:
            close = getattr(result, 'close', None)
            if close:
                close()

        status = captured['status'] or '500 INTERNAL SERVER ERROR'
        if status.startswith('500'):
            safe_body = (
                "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>업무일지 안전 모드</title>"
                "<style>body{font-family:Arial,sans-serif;margin:40px;color:#17233c}"
                ".box{max-width:760px;padding:24px;border:1px solid #dbe3ef;border-radius:14px;background:#f8fafc}"
                "a{color:#1764da}</style></head><body><div class='box'>"
                "<h1>업무일지 안전 모드</h1>"
                "<p>기존 업무일지 화면에서 오류가 발생해 안전 모드로 전환했습니다.</p>"
                "<p><a href='/'>통합현황으로 이동</a> · <a href='/tasks'>각 부서(팀) 업무 현황</a></p>"
                "</div></body></html>"
            ).encode('utf-8')
            start_response(
                '200 OK',
                [
                    ('Content-Type', 'text/html; charset=utf-8'),
                    ('Content-Length', str(len(safe_body))),
                    ('Cache-Control', 'no-store'),
                    ('X-MedPark-Journal-Rescue', '1'),
                ],
            )
            return [safe_body]

        headers = list(captured['headers'] or [])
        headers = [(k, v) for k, v in headers if k.lower() != 'content-length']
        headers.append(('Content-Length', str(len(body))))
        headers.append(('X-MedPark-Journal-Gateway', '1'))
        start_response(status, headers, captured['exc_info'])
        return [body]


app.wsgi_app = Journal500Rescue(app.wsgi_app)
