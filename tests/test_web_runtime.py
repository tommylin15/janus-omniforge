import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from apps.web import runtime


class _Control:
    def __init__(self, connect): self.connect = connect


class _Iceberg:
    catalog = object()
    engine = object()

    @classmethod
    def from_postgres(cls, **kwargs):
        cls.kwargs = kwargs
        return cls()


class _Reader:
    def __init__(self, catalog, engine): self.query = lambda *args: ()


class WebRuntimeTests(unittest.TestCase):
    def test_catalog_runtime_is_opened_read_only(self):
        settings = {
            "GCP_PROJECT_ID": "project", "CORE_BUCKET": "core", "CATALOG_DB_HOST": "catalog",
            "CATALOG_DB_NAME": "db", "CATALOG_DB_USER": "reader", "CATALOG_DB_PASSWORD": "secret",
            "CONTROL_DB_HOST": "control", "CONTROL_DB_NAME": "db", "CONTROL_DB_USER": "admin",
            "CONTROL_DB_PASSWORD": "secret", "PUBLICATION_DB_PASSWORD": "public-secret",
        }
        with patch.object(runtime, "_required", return_value=settings), \
             patch.object(runtime, "DuckDBIcebergCore", _Iceberg), \
             patch.object(runtime, "IcebergQuery", _Reader), \
             patch.dict("sys.modules", {"psycopg": type("P", (), {"connect": staticmethod(lambda **kwargs: None)}),
                                        "ingestion_core.postgres_control": type("M", (), {"PostgreSQLControlPlane": _Control}),
                                        "ingestion_core.stage": type("S", (), {"GcsObjectStore": object})}):
            result = runtime.build_runtime()
        self.assertTrue(_Iceberg.kwargs["read_only"])
        result.close()


if __name__ == "__main__":
    unittest.main()
