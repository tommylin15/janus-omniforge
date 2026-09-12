import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class MartRoleMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "infra" / "postgres" / "migrations" / "008_mart_runtime_roles.sql").read_text(encoding="utf-8")
        cls.queue_sql = (ROOT / "infra" / "postgres" / "migrations" / "017_mart_analysis_queue.sql").read_text(encoding="utf-8")
        cls.publication_sql = (ROOT / "infra" / "postgres" / "migrations" / "018_mart_publication.sql").read_text(encoding="utf-8")
        cls.integration_sql = (ROOT / "infra" / "postgres" / "migrations" / "019_core_mart_integration.sql").read_text(encoding="utf-8")
        cls.governance_sql = (ROOT / "infra" / "postgres" / "migrations" / "020_governance_audit.sql").read_text(encoding="utf-8")
        cls.hba = (ROOT / "infra" / "postgres" / "pg_hba.conf").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "infra" / "postgres" / "bootstrap-vm.sh").read_text(encoding="utf-8")

    def test_roles_are_non_privileged_and_private_network_scoped(self):
        for role in ("janus_mart_catalog", "janus_mart_publication"):
            self.assertIn(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", self.sql)
            self.assertIn(f"hostssl janus_control   {role}", self.hba)
        self.assertNotIn("0.0.0.0/0          scram-sha-256", self.hba)

    def test_grants_are_schema_bounded(self):
        self.assertIn("catalog.iceberg_tables", self.sql)
        self.assertIn("ALL TABLES IN SCHEMA publication", self.sql)
        self.assertNotIn("ALL PRIVILEGES", self.sql.upper())
        self.assertNotIn("GRANT USAGE ON SCHEMA control", self.sql)

    def test_analysis_queue_grants_are_column_bounded(self):
        self.assertIn("GRANT SELECT (", self.queue_sql)
        self.assertIn("GRANT UPDATE (", self.queue_sql)
        self.assertNotIn("ALL TABLES", self.queue_sql.upper())
        self.assertNotIn("ALL PRIVILEGES", self.queue_sql.upper())

    def test_fresh_bootstrap_applies_the_mart_migration(self):
        self.assertIn("008_mart_runtime_roles.sql", self.bootstrap)
        self.assertIn("017_mart_analysis_queue.sql", self.bootstrap)
        self.assertIn("018_mart_publication.sql", self.bootstrap)
        self.assertIn("019_core_mart_integration.sql", self.bootstrap)
        self.assertIn("020_governance_audit.sql", self.bootstrap)
        self.assertIn("MART_CATALOG_PASSWORD", self.bootstrap)
        self.assertIn("MART_PUBLICATION_PASSWORD", self.bootstrap)

    def test_publication_index_is_metadata_only_and_filters_blocked_results(self):
        table = self.publication_sql.split("CREATE TABLE IF NOT EXISTS publication.mart_report_index", 1)[1].split(");", 1)[0]
        self.assertNotIn("json", table.lower())
        self.assertNotIn("payload", table.lower())
        self.assertNotIn("evidence", table.lower())
        self.assertIn("analysis_outcome = 'complete'", self.publication_sql)
        self.assertIn("publication_status IN ('publishable','published')", self.publication_sql)
        self.assertIn("ready_at IS NOT NULL", self.publication_sql)
        self.assertIn("p_status = 'succeeded'", self.publication_sql)
        self.assertIn("REVOKE ALL ON publication.mart_report_index", self.publication_sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION publication.register_mart_report", self.publication_sql)

    def test_core_ready_event_and_analysis_queue_are_immutable_and_idempotent(self):
        self.assertIn("core_execution_id uuid PRIMARY KEY", self.integration_sql)
        self.assertIn("analysis_execution_id uuid UNIQUE", self.integration_sql)
        self.assertIn("payload->>'eventType' = 'core.dataset.ready.v1'", self.integration_sql)

    def test_governance_metadata_has_cas_retention_and_audit_role(self):
        self.assertIn("SET ROLE janus_audit", self.governance_sql)
        self.assertIn("current_version=p_expected_version", self.governance_sql)
        self.assertIn("ERRCODE='40001'", self.governance_sql)
        self.assertIn("prune_governance_revisions", self.governance_sql)
        self.assertIn("candidate.version <> head.current_version", self.governance_sql)
        table = self.governance_sql.split("CREATE TABLE IF NOT EXISTS audit.governance_revisions", 1)[1].split(");", 1)[0]
        self.assertNotIn("json", table.lower())
        self.assertIn("diff_artifact_uri", table)


if __name__ == "__main__":
    unittest.main()
