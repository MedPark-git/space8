from flask import Response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.routing import BuildError
from jinja2 import UndefinedError

import journal_emergency_gateway as emergency

app = emergency.app

LAST_JOURNAL_ERROR = {
    "stage": "none",
    "type": "",
    "message": "",
}


def _remember_error(stage, exc=None, message=""):
    LAST_JOURNAL_ERROR["stage"] = str(stage or "unknown")[:80]
    LAST_JOURNAL_ERROR["type"] = type(exc).__name__ if exc is not None else ""
    raw_message = str(exc) if exc is not None else str(message or "")
    # Keep only a short technical hint in memory; never expose document contents.
    LAST_JOURNAL_ERROR["message"] = raw_message.replace("\n", " ")[:240]


def _error_status_code():
    error_type = LAST_JOURNAL_ERROR.get("type") or ""
    if not error_type and LAST_JOURNAL_ERROR.get("stage") == "none":
        return 200
    mapping = {
        "BuildError": 521,
        "UndefinedError": 522,
        "AttributeError": 523,
        "TypeError": 524,
        "KeyError": 525,
        "RecursionError": 526,
        "RuntimeError": 527,
        "SQLAlchemyError": 528,
    }
    return mapping.get(error_type, 529)


@app.get('/__health/journal-gateway')
def journal_gateway_health():
    return Response('journal_gateway=active', status=200, mimetype='text/plain')


@app.get('/__health/journal-last-error-code')
def journal_last_error_code():
    code = _error_status_code()
    body = (
        f"stage={LAST_JOURNAL_ERROR.get('stage','none')};"
        f"type={LAST_JOURNAL_ERROR.get('type','')};"
        f"message={LAST_JOURNAL_ERROR.get('message','')}"
    )
    return Response(body, status=code, mimetype='text/plain')


def _safe_mode_body():
    stage = LAST_JOURNAL_ERROR.get("stage") or "unknown"
    error_type = LAST_JOURNAL_ERROR.get("type") or "ServerError"
    diagnostic = f"{stage}:{error_type}"
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>업무일지 안전 모드</title>"
        "<style>body{font-family:Arial,'Noto Sans KR',sans-serif;background:#f5f7fb;color:#17233c;margin:0}"
        ".shell{max-width:900px;margin:50px auto;padding:0 20px}.box{padding:28px;border:1px solid #dbe3ef;border-radius:16px;background:white}"
        "a{display:inline-block;margin-right:10px;color:#1764da;text-decoration:none;font-weight:700}.code{margin-top:16px;color:#7a8799;font-size:12px}</style>"
        "</head><body><main class='shell'><section class='box'>"
        "<h1>업무일지 안전 모드</h1>"
        "<p>업무일지 화면 처리 중 오류가 감지되어 기본 500 화면 대신 안전 모드로 전환했습니다.</p>"
        "<p><a href='/__safe-journal-board'>안전 업무일지 열기</a>"
        "<a href='/'>통합현황</a><a href='/tasks'>각 부서(팀) 업무 현황</a></p>"
        f"<div class='code'>진단코드: {diagnostic}</div>"
        "</section></main></body></html>"
    ).encode('utf-8')


def _send_safe(start_response):
    body = _safe_mode_body()
    start_response(
        '200 OK',
        [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-store, no-cache, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('X-MedPark-Journal-Rescue', '1'),
        ],
    )
    return [body]


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

        try:
            result = self.downstream(environ, capture_start_response)
        except Exception as exc:
            _remember_error('downstream_call', exc)
            return _send_safe(start_response)

        try:
            try:
                body = b''.join(result)
            except Exception as exc:
                _remember_error('response_iteration', exc)
                return _send_safe(start_response)
            finally:
                close = getattr(result, 'close', None)
                if close:
                    try:
                        close()
                    except Exception:
                        pass
        except Exception as exc:
            _remember_error('response_finalize', exc)
            return _send_safe(start_response)

        status = captured['status'] or '500 INTERNAL SERVER ERROR'
        if status.startswith('500'):
            _remember_error('downstream_500', message=status)
            return _send_safe(start_response)

        LAST_JOURNAL_ERROR.update({"stage": "none", "type": "", "message": ""})
        headers = list(captured['headers'] or [])
        headers = [(k, v) for k, v in headers if k.lower() != 'content-length']
        headers.append(('Content-Length', str(len(body))))
        headers.append(('Cache-Control', 'no-store'))
        headers.append(('X-MedPark-Journal-Gateway', '1'))
        try:
            start_response(status, headers, captured['exc_info'])
        except Exception as exc:
            _remember_error('start_response', exc)
            return _send_safe(start_response)
        return [body]


app.wsgi_app = Journal500Rescue(app.wsgi_app)
