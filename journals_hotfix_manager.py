from flask import url_for as flask_url_for

import journal_preview_safe_manager

app = journal_preview_safe_manager.app

# journals.html currently references the administrator preview endpoint by name.
# Resolve that one endpoint to its fixed URL directly so a route-name mismatch
# can never make the entire /journals board fail during Jinja rendering.
_original_jinja_url_for = app.jinja_env.globals.get("url_for", flask_url_for)


def safe_jinja_url_for(endpoint, **values):
    if endpoint == "journal_preview_direct":
        journal_id = values.get("journal_id")
        try:
            journal_id = int(journal_id)
        except (TypeError, ValueError):
            return "/journals"
        return f"/document-control/journals/{journal_id}/preview"
    return _original_jinja_url_for(endpoint, **values)


app.jinja_env.globals["url_for"] = safe_jinja_url_for
