from direct_work_journal_entry_v2 import app as downstream_app


CACHE_BUST_PATH = "/wj-260906-r1"


class WorkJournalCacheBustGateway:
    """Serve a never-before-used work-journal URL outside legacy routing/cache paths."""

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _health(start_response):
        body = b"work_journal_cache_bust=active"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-MedPark-Work-Journal-Cache-Bust", "1"),
            ],
        )
        return [body]

    def __call__(self, environ, start_response):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        path = environ.get("PATH_INFO") or ""

        if path == "/__health/work-journal-cache-bust":
            return self._health(start_response)

        if method == "GET" and (path == CACHE_BUST_PATH or path == CACHE_BUST_PATH + "/" or path.startswith(CACHE_BUST_PATH + "/")):
            rewritten = environ.copy()
            rewritten["ORIGINAL_PATH_INFO"] = path
            rewritten["PATH_INFO"] = "/work-journals"
            return self.downstream(rewritten, start_response)

        return self.downstream(environ, start_response)


app = WorkJournalCacheBustGateway(downstream_app)
