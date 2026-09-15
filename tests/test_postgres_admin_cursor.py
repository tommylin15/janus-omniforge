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
        self.assertIn("(source_id, dataset_id) >", repository)
        self.assertIn("config_id>%s", repository)
        self.assertNotIn("OFFSET %s", repository)

    def test_runtime_migration_paths_include_cursor_index(self):
        bootstrap = (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8")
        apply_web = (ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh").read_text(encoding="utf-8")
        self.assertIn("009_admin_cursor_indexes.sql", bootstrap)
        self.assertIn("009_admin_cursor_indexes.sql", apply_web)

    def test_control_role_owns_settings_for_runtime_development(self):
        migration = (ROOT / "infra" / "postgres" / "migrations" / "011_control_settings_ownership.sql").read_text(encoding="utf-8")
        bootstrap = (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8")
        apply_web = (ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh").read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE admin_settings OWNER TO janus_control", migration)
        self.assertIn("ALTER TABLE admin_audit OWNER TO janus_control", migration)
        self.assertIn("ALTER SEQUENCE admin_audit_audit_id_seq OWNER TO janus_control", migration)
        self.assertNotIn("SUPERUSER", migration)
        for path in (bootstrap, apply_web):
            self.assertIn("010_execution_runtime_options.sql", path)
            self.assertIn("011_control_settings_ownership.sql", path)

    def test_first_batch_uses_authorized_provenance_source_ids(self):
        migration = (ROOT / "infra" / "postgres" / "migrations" / "012_first_batch_source_ids.sql").read_text(encoding="utf-8")
        self.assertIn('["taiex","tpex-benchmark","twse","mops","finmind"]', migration)
        self.assertNotIn('"twse-valuation"', migration)
        for path in (
            (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh").read_text(encoding="utf-8"),
        ):
            self.assertIn("012_first_batch_source_ids.sql", path)

    def test_membership_version_migration_is_in_runtime_paths(self):
        migration = (ROOT / "infra" / "postgres" / "migrations" / "013_membership_versions.sql").read_text(encoding="utf-8")
        self.assertIn("coverage_membership_versions", migration)
        self.assertIn("GRANT SELECT, INSERT", migration)
        for path in (
            (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh").read_text(encoding="utf-8"),
        ):
            self.assertIn("013_membership_versions.sql", path)

    def test_pilot_readiness_migration_is_in_bootstrap_and_runtime_paths(self):
        for path in (
            ROOT / "infra" / "postgres" / "bootstrap-vm.sh",
            ROOT / "scripts" / "gcp" / "apply-web-postgres-migration.sh",
            ROOT / "scripts" / "gcp" / "apply-mart-postgres-migration.sh",
        ):
            self.assertIn("025_pilot_readiness.sql", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
