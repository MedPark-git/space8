import app as core_app
import journal_preview_safe_manager as preview_manager

app = preview_manager.app
_original_render_template = core_app.render_template


def stable_render_template(template_name, *args, **context):
    """Use a stable server-rendered board for administrator journal lists.

    The original /journals route still prepares all business data and handles POSTs.
    Only the administrator list template is swapped to remove AJAX preview dependencies
    and inline deep relationship rendering that previously caused 404/500 failures.
    """
    if (
        template_name == "journals.html"
        and context.get("mode") == "list"
        and preview_manager._is_admin(core_app.current_user)
    ):
        return _original_render_template("journals_admin_stable.html", *args, **context)
    return _original_render_template(template_name, *args, **context)


core_app.render_template = stable_render_template
