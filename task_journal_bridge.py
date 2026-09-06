import re
from urllib.parse import parse_qs, quote, urlencode

import app as core_app
import direct_work_journal_entry as journal

flask_app = journal.flask_app
TASK_JOURNAL_PATH = "/tasks"
OLD_JOURNAL_PREFIXES = (
    "/journals",
    "/work-journals",
    "/work-journal",
    "/journal-board",
    "/journal",
    "/wj-260906-r1",
)


def _is_task_journal_get(environ):
    if (environ.get("REQUEST_METHOD") or "GET").upper() != "GET":
        return False
    if (environ.get("PATH_INFO") or "") != TASK_JOURNAL_PATH:
        return False
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    return (query.get("journal_board") or [""])[0] == "1"


def _journal_action(environ):
    if (environ.get("REQUEST_METHOD") or "GET").upper() != "POST":
        return ""
    if (environ.get("PATH_INFO") or "") != TASK_JOURNAL_PATH:
        return ""
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    return str((query.get("journal_action") or [""])[0])


def _journal_id(environ):
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    try:
        return int((query.get("id") or [""])[0])
    except (TypeError, ValueError):
        return None


def _bridge_url(url):
    value = str(url or "")
    if not value.startswith("/work-journals"):
        return value
    if value == "/work-journals":
        return "/tasks?journal_board=1"
    if value.startswith("/work-journals?"):
        return "/tasks?journal_board=1&" + value.split("?", 1)[1]
    return "/tasks?journal_board=1"


def _bridge_html(value):
    text = value.decode("utf-8", errors="replace") if isinstance(value, (bytes, bytearray)) else str(value)
    text = re.sub(
        r"/work-journals/delete/(\d+)",
        r"/tasks?journal_action=delete&id=\1",
        text,
    )
    text = text.replace("/work-journals/delete-bulk", "/tasks?journal_action=delete-bulk")
    text = text.replace("/work-journals/create", "/tasks?journal_action=create")
    text = text.replace("/work-journals?", "/tasks?journal_board=1&")
    text = text.replace("/work-journals'", "/tasks?journal_board=1'")
    text = text.replace('/work-journals"', '/tasks?journal_board=1"')
    return text.encode("utf-8")


def _plain_response(start_response, body, status="200 OK", headers=None):
    if isinstance(body, str):
        body = body.encode("utf-8")
    response_headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-MedPark-Task-Journal-Bridge", "1"),
    ]
    if headers:
        response_headers.extend(headers)
    start_response(status, response_headers)
    return [body]


def _redirect(start_response, location):
    body = (
        "<!doctype html><meta charset='utf-8'>"
        f"<meta http-equiv='refresh' content='0;url={location}'>"
        f"<a href='{location}'>이동</a>"
    )
    return _plain_response(
        start_response,
        body,
        status="302 FOUND",
        headers=[("Location", location)],
    )


def _bridge_call(callback, start_response):
    captured = {"status": "200 OK", "headers": []}

    def capture(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = list(headers)
        return lambda _data: None

    result = callback(capture)
    try:
        body = b"".join(result)
    finally:
        close = getattr(result, "close", None)
        if close:
            close()

    body = _bridge_html(body)
    headers = []
    for key, value in captured["headers"]:
        lower = key.lower()
        if lower == "content-length":
            continue
        if lower == "location":
            value = _bridge_url(value)
        headers.append((key, value))
    headers.append(("Content-Length", str(len(body))))
    headers.append(("Cache-Control", "no-store"))
    headers.append(("X-MedPark-Task-Journal-Bridge", "1"))
    start_response(captured["status"], headers)
    return [body]


def _old_journal_redirect(environ, start_response):
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or ""
    if method != "GET":
        return None
    matched = None
    for prefix in OLD_JOURNAL_PREFIXES:
        if path == prefix or path == prefix + "/" or path.startswith(prefix + "/"):
            matched = prefix
            break
    if matched is None:
        return None

    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    pairs = [("journal_board", "1")]
    for key in ("document_type", "open", "compose"):
        for value in query.get(key, []):
            if value != "":
                pairs.append((key, value))

    suffix = path[len(matched):].strip("/")
    if suffix.isdigit() and not any(key == "open" for key, _ in pairs):
        pairs.append(("open", suffix))
    return _redirect(start_response, "/tasks?" + urlencode(pairs))


class TaskJournalBridge:
    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/__health/task-journal-bridge":
            return _plain_response(
                start_response,
                "task_journal_bridge=active",
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )

        old_redirect = _old_journal_redirect(environ, start_response)
        if old_redirect is not None:
            return old_redirect

        action = _journal_action(environ)
        if not (_is_task_journal_get(environ) or action):
            return self.downstream(environ, start_response)

        try:
            with flask_app.app_context():
                viewer, cookie_value = journal._viewer(environ)
                if not viewer:
                    return _redirect(
                        start_response,
                        "/login?next=" + quote("/tasks?journal_board=1"),
                    )

                if action == "create":
                    return _bridge_call(
                        lambda sr: journal._create(environ, sr, viewer, cookie_value),
                        start_response,
                    )
                if action == "delete-bulk":
                    return _bridge_call(
                        lambda sr: journal._delete_bulk(environ, sr, viewer, cookie_value),
                        start_response,
                    )
                if action == "delete":
                    journal_id = _journal_id(environ)
                    if journal_id is None:
                        return _redirect(start_response, "/tasks?journal_board=1")
                    return _bridge_call(
                        lambda sr: journal._delete_one(
                            environ, sr, viewer, cookie_value, journal_id
                        ),
                        start_response,
                    )

                html = journal._render_board(viewer, cookie_value, environ)
                return _plain_response(start_response, _bridge_html(html))
        except Exception as exc:
            try:
                with flask_app.app_context():
                    core_app.db.session.rollback()
            except Exception:
                pass
            return _plain_response(
                start_response,
                (
                    "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
                    "<title>업무일지</title></head><body>"
                    "<h1>업무일지 안전 화면</h1>"
                    f"<p>진단코드: {type(exc).__name__}</p>"
                    "<p><a href='/tasks'>업무현황으로 이동</a></p>"
                    "</body></html>"
                ),
            )


app = TaskJournalBridge(journal.app)
