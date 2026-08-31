import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class MartRoleMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "infra" / "postgres" / "migrations" / "008_mart_runtime_roles.sql").read_text(encoding="utf-8")
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

    def test_fresh_bootstrap_applies_the_mart_migration(self):
        self.assertIn("008_mart_runtime_roles.sql", self.bootstrap)
        self.assertIn("MART_CATALOG_PASSWORD", self.bootstrap)
        self.assertIn("MART_PUBLICATION_PASSWORD", self.bootstrap)


if __name__ == "__main__":
    unittest.main()
