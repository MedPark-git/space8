import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class RuntimeDocumentIntegrityTests(unittest.TestCase):
    def test_runtime_entrypoint_uses_journal_preview_manager(self):
        procfile = read_text("Procfile")
        self.assertIn("journal_preview_safe_manager:app", procfile)

    def test_admin_journal_board_uses_exact_document_id_preview_contract(self):
        template = read_text("templates/journals.html")
        self.assertIn("url_for('journal_preview_direct', journal_id=item.id)", template)
        self.assertIn('data-journal-id="{{ item.id }}"', template)
        self.assertIn("url_for('journal_preview', journal_id=item.id)", template)

    def test_admin_direct_preview_route_has_minimal_200_fallback(self):
        manager = read_text("journal_preview_safe_manager.py")
        self.assertIn(
            '@app.get("/document-control/journals/<int:journal_id>/preview")',
            manager,
        )
        self.assertIn("def journal_preview_direct(journal_id):", manager)
        self.assertIn("if not _is_admin(current_user):", manager)
        self.assertIn("return _minimal_fallback_html(row), 200", manager)

    def test_admin_preview_frontend_does_not_rewrite_to_removed_safe_path(self):
        script = read_text("static/admin_journal_preview.js")
        self.assertNotIn("admin-safe/journals", script)
        self.assertIn("button.dataset.journalPreview", script)
        self.assertIn('cache: "no-store"', script)

    def test_admin_delete_uses_explicit_journal_id_and_supports_direct_preview_url(self):
        script = read_text("static/admin_bulk_document_delete.js")
        self.assertIn('idDatasetKey: "journalId"', script)
        self.assertIn("preview.dataset[config.idDatasetKey]", script)
        self.assertIn("document-control\\/", script)
        self.assertNotIn("rewriteAdminJournalPreviewUrls", script)

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

    def test_asset_versions_force_refresh_after_integrity_fix(self):
        base = read_text("templates/base.html")
        self.assertIn("20260906-admin-bulk-delete-v5", base)
        self.assertIn("20260906-admin-journal-preview-v4", base)


if __name__ == "__main__":
    unittest.main()
