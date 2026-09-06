from flask import Response

import journal_emergency_gateway as gateway

app = gateway.app
LAST_WORK_JOURNAL_ERROR = {"code": "none"}


@app.get("/work-journals")
def work_journals_safe():
    """Canonical stable work-journal board.

    The underlying safe board already enforces login and document visibility.
    Keeping a different public path prevents legacy /journals hooks from running.
    """
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

    It runs outside all older journal wrappers. GET /journals is rewritten before
    the legacy gateway sees it, and any 500/uncaught exception on the canonical
    /work-journals path is converted to a safe 200 page while recording only a
    non-sensitive error code for diagnosis.
    """

    def __init__(self, downstream):
        self.downstream = downstream

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD")
        original_path = environ.get("PATH_INFO") or ""
        monitored = method == "GET" and original_path in {"/journals", "/work-journals"}

        if method == "GET" and original_path == "/journals":
            environ = environ.copy()
            environ["ORIGINAL_PATH_INFO"] = "/journals"
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
