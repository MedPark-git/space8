from flask import Response, redirect
from sqlalchemy import text

import journal_emergency_gateway as gateway
import app as core_app

app = gateway.app
LAST_WORK_JOURNAL_ERROR = {"code": "none"}


@app.get("/work-journals")
@app.get("/work-journal")
@app.get("/journal")
@app.get("/journal-board")
def work_journals_safe():
    """Canonical stable work-journal board with legacy URL aliases."""
    return gateway.safe_journal_board()


@app.get("/__health/work-journals-entry")
def work_journals_entry_health():
    return Response("work_journals_entry=active", status=200, mimetype="text/plain")


@app.get("/__health/work-journals-last-error")
def work_journals_last_error():
    return Response(
        f"work_journals_last_error={LAST_WORK_JOURNAL_ERROR['code']}",
        status=200,
        mimetype="text/plain",
    )


@app.get("/__health/work-journal-menu-url")
def work_journal_menu_url():
    try:
        row = core_app.db.session.execute(
            text("SELECT url FROM menus WHERE name = '업무일지' AND active = true ORDER BY id LIMIT 1")
        ).mappings().first()
        value = row["url"] if row else "missing"
        return Response(f"work_journal_menu_url={value}", status=200, mimetype="text/plain")
    except Exception as exc:
        core_app.db.session.rollback()
        return Response(
            f"work_journal_menu_url_error={type(exc).__name__}",
            status=200,
            mimetype="text/plain",
        )


def _rescue_html():
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>업무일지 안전 모드</title>"
        "<style>body{font-family:Arial,'Noto Sans KR',sans-serif;background:#f5f7fb;"
        "color:#17233c;margin:0}.box{max-width:760px;margin:60px auto;padding:28px;"
        "background:#fff;border:1px solid #dbe3ef;border-radius:16px}"
        "a{color:#1764da;text-decoration:none;font-weight:700}</style></head><body>"
        "<div class='box'><h1>업무일지 안전 모드</h1>"
        "<p>업무일지 화면을 불러오는 과정에서 오류가 감지되어 안전 화면으로 전환했습니다.</p>"
        "<p><a href='/'>통합현황</a> · <a href='/tasks'>각 부서(팀) 업무 현황</a></p>"
        "</div></body></html>"
    ).encode("utf-8")


class WorkJournalEntryGateway:
    """Outer-most journal gateway.

    All known work-journal GET paths are normalized to /work-journals before
    older wrappers or legacy Flask routes can handle them. Any uncaught 500 is
    converted to a safe 200 response and a non-sensitive error code is retained.
    """

    JOURNAL_PATHS = {
        "/journals",
        "/work-journals",
        "/work-journal",
        "/journal",
        "/journal-board",
    }

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD")
        original_path = environ.get("PATH_INFO") or ""
        monitored = method == "GET" and original_path in self.JOURNAL_PATHS

        if method == "GET" and original_path in self.JOURNAL_PATHS and original_path != "/work-journals":
            environ = environ.copy()
            environ["ORIGINAL_PATH_INFO"] = original_path
            environ["PATH_INFO"] = "/work-journals"

        if not monitored:
            return self.downstream(environ, start_response)

        captured = {"status": None, "headers": None}

        def capture_start_response(status, headers, exc_info=None):
            captured["status"] = status
            captured["headers"] = list(headers)
            return lambda _data: None

        try:
            result = self.downstream(environ, capture_start_response)
            try:
                body = b"".join(result)
            finally:
                close = getattr(result, "close", None)
                if close:
                    close()
        except Exception as exc:
            LAST_WORK_JOURNAL_ERROR["code"] = f"exception:{type(exc).__name__}"
            body = _rescue_html()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                    ("X-MedPark-Work-Journal-Rescue", "exception"),
                ],
            )
            return [body]

        status = captured["status"] or "500 INTERNAL SERVER ERROR"
        if status.startswith("404") and monitored:
            LAST_WORK_JOURNAL_ERROR["code"] = f"response:{status.split()[0]}"
            location = "/work-journals"
            response_body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<meta http-equiv='refresh' content='0;url=/work-journals'></head>"
                "<body><a href='/work-journals'>업무일지로 이동</a></body></html>"
            ).encode("utf-8")
            start_response(
                "302 FOUND",
                [
                    ("Location", location),
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(response_body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [response_body]

        if status.startswith("500"):
            LAST_WORK_JOURNAL_ERROR["code"] = "response:500"
            body = _rescue_html()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                    ("X-MedPark-Work-Journal-Rescue", "response-500"),
                ],
            )
            return [body]

        headers = [
            (key, value)
            for key, value in (captured["headers"] or [])
            if key.lower() != "content-length"
        ]
        headers.append(("Content-Length", str(len(body))))
        headers.append(("X-MedPark-Work-Journal-Entry", "1"))
        start_response(status, headers)
        return [body]


app.wsgi_app = WorkJournalEntryGateway(app.wsgi_app)
