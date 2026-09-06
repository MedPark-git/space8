import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class RuntimeDocumentIntegrityTests(unittest.TestCase):
    def test_runtime_entrypoint_uses_journal_preview_manager(self):
        procfile = read_text("Procfile")
        self.assertIn("journal_preview_safe_manager:app", procfile)

    def test_admin_journal_board_renders_details_without_ajax_preview(self):
        template = read_text("templates/journals.html")
        self.assertIn('data-dialog="journal-inline-{{ item.id }}"', template)
        self.assertIn('data-admin-delete-ready="true"', template)
        self.assertIn('data-journal-admin-check', template)
        self.assertIn('/document-control/journals/{{ item.id }}/delete', template)
        self.assertIn("safe_document_task_content('journal', item.id, task)", template)
        self.assertNotIn("url_for('journal_preview_direct'", template)

    def test_admin_direct_preview_route_keeps_minimal_200_fallback(self):
        manager = read_text("journal_preview_safe_manager.py")
        self.assertIn(
            '@app.get("/document-control/journals/<int:journal_id>/preview")',
            manager,
        )
        self.assertIn("def journal_preview_direct(journal_id):", manager)
        self.assertIn("return _minimal_fallback_html(row), 200", manager)
        self.assertIn('app.jinja_env.globals["safe_document_task_content"]', manager)

    def test_admin_preview_frontend_cannot_break_server_rendered_admin_board(self):
        template = read_text("templates/journals.html")
        script = read_text("static/admin_journal_preview.js")
        self.assertIn('{% else %}\n<dialog id="journal-preview-dialog"', template)
        self.assertNotIn('id="journal-preview-dialog"', template.split("{% else %}")[0])
        self.assertIn('if (!dialog || !content) return;', script)

    def test_admin_delete_controls_are_server_rendered_and_js_will_not_duplicate(self):
        template = read_text("templates/journals.html")
        script = read_text("static/admin_bulk_document_delete.js")
        self.assertIn('data-admin-delete-ready="true"', template)
        self.assertIn('if (!table || table.dataset.adminDeleteReady === "true") return;', script)
        self.assertIn('/document-control/journals/bulk-delete', template)
        self.assertIn('name="document_ids"', template)

    def test_document_edit_and_delete_permission_contracts_are_present(self):
        access = read_text("document_access_manager.py")
        self.assertIn('DELETE_ROLES = {"팀장", "부서장", "관리자"}', access)
        self.assertIn(
            "core_app.can_edit_work_journal = _can_edit_journal_for_all_visible",
            access,
        )
        admin_ui = read_text("admin_document_ui_fix.py")
        self.assertIn("bulk_delete._admin_only = _admin_only", admin_ui)
        self.assertIn('ADMIN_ROLE_NAMES = {"관리자", "시스템관리자"}', admin_ui)

    def test_document_snapshot_migration_chain_is_linear(self):
        migration_17 = read_text(
            "migrations/versions/20260905_0017_document_task_contents.py"
        )
        migration_18 = read_text(
            "migrations/versions/20260905_0018_backfill_document_task_contents.py"
        )
        self.assertIn('revision = "20260905_0017"', migration_17)
        self.assertIn('down_revision = "20260904_0016"', migration_17)
        self.assertIn('revision = "20260905_0018"', migration_18)
        self.assertIn('down_revision = "20260905_0017"', migration_18)


if __name__ == "__main__":
    unittest.main()
