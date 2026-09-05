from flask import request
from flask_login import current_user

import document_task_content_manager  # noqa: F401

app = document_task_content_manager.app


@app.after_request
def inject_document_task_content_guard(response):
    if (
        response.mimetype == "text/html"
        and response.status_code < 400
        and current_user.is_authenticated
        and request.path.startswith(("/tasks", "/meetings", "/journals"))
    ):
        page = response.get_data(as_text=True)
        asset = '<script src="/static/document_task_content_guard.js?v=20260905-document-snapshot-guard" defer></script>'
        if asset not in page and "</body>" in page:
            page = page.replace("</body>", asset + "</body>")
            response.set_data(page)
            response.headers.pop("Content-Length", None)
    return response
