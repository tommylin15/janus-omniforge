import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class WebRoleMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "infra" / "postgres" / "migrations" / "007_web_runtime_roles.sql").read_text(encoding="utf-8")
        cls.hba = (ROOT / "infra" / "postgres" / "pg_hba.conf").read_text(encoding="utf-8")
        cls.public_sql = (ROOT / "infra" / "postgres" / "migrations" / "021_public_api_role.sql").read_text(encoding="utf-8")
        cls.stock_sql = (ROOT / "infra" / "postgres" / "migrations" / "023_public_stock_index.sql").read_text(encoding="utf-8")

    def test_web_roles_are_non_privileged_and_network_scoped(self):
        for role in ("janus_web_control", "janus_web_catalog"):
            self.assertIn(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", self.sql)
            self.assertIn(f"hostssl janus_control   {role}", self.hba)
        self.assertNotIn("0.0.0.0/0          scram-sha-256", self.hba)

    def test_catalog_role_is_read_only_and_control_access_is_schema_bounded(self):
        self.assertIn("default_transaction_read_only = on", self.sql)
        self.assertIn("statement_timeout = '60s'", self.sql)
        self.assertIn("idle_in_transaction_session_timeout = '15s'", self.sql)
        self.assertNotIn("ALL PRIVILEGES", self.sql.upper())
        self.assertIn("control.execution_items", self.sql)
        self.assertIn("control.source_health", self.sql)
        self.assertNotIn("GRANT USAGE ON SCHEMA catalog TO janus_web_control", self.sql)

    def test_public_api_role_can_only_read_publishable_view(self):
        self.assertIn("CREATE ROLE janus_public_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", self.public_sql)
        self.assertIn("GRANT SELECT ON publication.publishable_mart_reports TO janus_public_api", self.public_sql)
        self.assertIn("default_transaction_read_only = on", self.public_sql)
        self.assertIn("statement_timeout = '5s'", self.public_sql)
        self.assertIn("idle_in_transaction_session_timeout = '5s'", self.public_sql)
        self.assertIn("REVOKE ALL ON publication.mart_report_index", self.public_sql)
        self.assertIn("hostssl janus_control   janus_public_api", self.hba)

    def test_public_stock_index_exposes_only_enabled_symbols(self):
        self.assertIn("BEGIN;", self.stock_sql)
        self.assertIn("COMMIT;", self.stock_sql)
        self.assertIn("SELECT upper(symbol) AS symbol", self.stock_sql)
        self.assertIn("WHERE enabled = true", self.stock_sql)
        self.assertIn("GRANT SELECT ON publication.enabled_stock_symbols TO janus_public_api", self.stock_sql)
        self.assertNotIn("TO janus_public_api", self.stock_sql.split("control.stock_master", 1)[0])


if __name__ == "__main__":
    unittest.main()
