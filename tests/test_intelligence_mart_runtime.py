import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "intelligence-mart"))

from intelligence_mart.runtime import postgres_smoke


class _Cursor:
    def __init__(self, role):
        self.role = role
        self.result = None

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, query, params):
        self.result = (True,) if "has_table_privilege" in query else (self.role, "172.17.0.2/32", True)
    def fetchone(self): return self.result


class _Connection:
    def __init__(self, role): self.role = role
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def cursor(self): return _Cursor(self.role)


class MartRuntimeTests(unittest.TestCase):
    def test_smoke_uses_separate_credentials_and_private_postgres(self):
        settings = {
            "CATALOG_DB_HOST": "10.42.0.5", "CATALOG_DB_NAME": "janus_control",
            "CATALOG_DB_USER": "janus_mart_catalog", "CATALOG_DB_PASSWORD": "catalog-secret",
            "PUBLICATION_DB_HOST": "10.42.0.5", "PUBLICATION_DB_NAME": "janus_control",
            "PUBLICATION_DB_USER": "janus_mart_publication", "PUBLICATION_DB_PASSWORD": "publication-secret",
        }
        calls = []

        def connect(**kwargs):
            calls.append(kwargs)
            return _Connection(kwargs["user"])

        with patch.dict(os.environ, settings, clear=True):
            result = postgres_smoke(connect)

        self.assertEqual([call["user"] for call in calls], ["janus_mart_catalog", "janus_mart_publication"])
        self.assertTrue(all(call["connect_timeout"] == 5 for call in calls))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["databases"]["catalog"]["private"])

    def test_smoke_rejects_public_database_address(self):
        settings = {
            "CATALOG_DB_HOST": "203.0.113.10", "CATALOG_DB_NAME": "db",
            "CATALOG_DB_USER": "janus_mart_catalog", "CATALOG_DB_PASSWORD": "secret",
            "PUBLICATION_DB_HOST": "10.42.0.5", "PUBLICATION_DB_NAME": "db",
            "PUBLICATION_DB_USER": "janus_mart_publication", "PUBLICATION_DB_PASSWORD": "secret",
        }

        class PublicConnection(_Connection):
            def cursor(self):
                cursor = _Cursor(self.role)
                original = cursor.execute
                def execute(query, params):
                    original(query, params)
                    if "inet_server_addr" in query: cursor.result = (self.role, "8.8.8.8", True)
                cursor.execute = execute
                return cursor

        with patch.dict(os.environ, settings, clear=True), self.assertRaisesRegex(RuntimeError, "private"):
            postgres_smoke(lambda **kwargs: PublicConnection(kwargs["user"]))


if __name__ == "__main__":
    unittest.main()
