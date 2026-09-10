import task_category_wsgi_guard as guard
import task_category_admin_v33  # noqa: F401 - administrator delete handler
import admin_work_category_wsgi_v43  # noqa: F401 - installs middleware inside Flask.app.wsgi_app

# Export the actual Flask app. V43 is installed on app.wsgi_app itself so the
# middleware is part of the Flask request chain regardless of Gunicorn loading.
app = guard.flask_app
