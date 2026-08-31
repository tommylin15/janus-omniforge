import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PostgreSQLAdminCursorTests(unittest.TestCase):
    def test_migration_and_queries_use_composite_keyset_indexes(self):
        migration = (ROOT / "infra" / "postgres" / "migrations" / "009_admin_cursor_indexes.sql").read_text(encoding="utf-8")
        repository = (ROOT / "jobs" / "ingestion-core" / "ingestion_core" / "postgres_control.py").read_text(encoding="utf-8")
        self.assertIn("requested_at DESC, execution_id DESC", migration)
        self.assertIn("(requested_at, execution_id) <", repository)
        self.assertIn("symbol>%s", repository)
        self.assertNotIn("OFFSET %s", repository)

    def test_runtime_migration_paths_include_cursor_index(self):
        bootstrap = (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8")
        apply_web = (ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh").read_text(encoding="utf-8")
        self.assertIn("009_admin_cursor_indexes.sql", bootstrap)
        self.assertIn("009_admin_cursor_indexes.sql", apply_web)


if __name__ == "__main__":
    unittest.main()
