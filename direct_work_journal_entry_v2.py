from urllib.parse import parse_qsl, urlencode

from direct_work_journal_entry import app as downstream_app


class WorkJournalPathNormalizer:
    """Normalize all work-journal GET URL variants before legacy Flask routing.

    This wrapper intentionally sits outside the existing direct work-journal WSGI app.
    It catches trailing slashes and stale/deep journal URLs that would otherwise fall
    through to the Flask 404 handler for authenticated browser sessions.
    """

    JOURNAL_PREFIXES = (
        "/work-journals",
        "/work-journal",
        "/journals",
        "/journal-board",
        "/journal",
    )

    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    def _append_open_query(environ, open_id):
        pairs = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        if not any(key == "open" for key, _ in pairs):
            pairs.append(("open", str(open_id)))
        environ["QUERY_STRING"] = urlencode(pairs)

    def __call__(self, environ, start_response):
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        path = environ.get("PATH_INFO") or ""

        if method != "GET":
            return self.downstream(environ, start_response)

        matched_prefix = None
        for prefix in self.JOURNAL_PREFIXES:
            if path == prefix or path == prefix + "/" or path.startswith(prefix + "/"):
                matched_prefix = prefix
                break

        if matched_prefix is None:
            return self.downstream(environ, start_response)

        rewritten = environ.copy()
        rewritten["ORIGINAL_PATH_INFO"] = path
        rewritten["PATH_INFO"] = "/work-journals"

        suffix = path[len(matched_prefix):].strip("/")
        if suffix.isdigit():
            self._append_open_query(rewritten, int(suffix))

        return self.downstream(rewritten, start_response)


app = WorkJournalPathNormalizer(downstream_app)
