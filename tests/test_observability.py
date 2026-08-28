import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.observability import PostgresHealthCollector, redact


class ObservabilityTests(unittest.TestCase):
    def test_redaction_removes_secrets_and_url_credentials(self):
        value = redact("password=hunter2 https://example.test/x?token=abc&x=1")
        self.assertNotIn("hunter2", value)
        self.assertNotIn("abc", value)
        self.assertIn("<redacted>", value)

    def test_postgres_snapshot_is_bounded_and_aggregate_only(self):
        def query(sql, params):
            if "pg_stat_activity" in sql: return {"connection_count": 2}
            if "pg_stat_database" in sql: return {"deadlocks": 1, "temp_bytes": 3}
            if "pg_database_size" in sql: return {"disk_bytes": 4}
            if "pg_stat_statements" in sql: return {"slow_query_count": 5}
            return {"row_count": 6}

        snapshot = PostgresHealthCollector(query).snapshot()
        self.assertEqual(snapshot["connection_count"], 2)
        self.assertEqual(snapshot["retention"]["executions"], 6)
        self.assertNotIn("payload", snapshot)


if __name__ == "__main__":
    unittest.main()
