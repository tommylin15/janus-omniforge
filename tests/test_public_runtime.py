import os
import sys
from types import ModuleType
from unittest.mock import patch

from packages.web_api import CoreQueryService, PublicMartService
from services.api.public_runtime import _catalog_settings, build_core_service, build_public_service


class _Catalog:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class _URL:
    @staticmethod
    def create(*args, **kwargs):
        return (args, kwargs)


class _Psycopg:
    kwargs = None

    @staticmethod
    def connect(**kwargs):
        _Psycopg.kwargs = kwargs
        return object()


def test_build_public_service_uses_bounded_read_only_runtime():
    pyiceberg_sql = ModuleType("pyiceberg.catalog.sql")
    pyiceberg_sql.SqlCatalog = _Catalog
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.URL = _URL
    stage = ModuleType("ingestion_core.stage")
    stage.GcsObjectStore = object
    modules = {
        "psycopg": _Psycopg,
        "pyiceberg.catalog.sql": pyiceberg_sql,
        "sqlalchemy": sqlalchemy,
        "ingestion_core.stage": stage,
    }
    env = {
        "GCP_PROJECT_ID": "project", "CORE_BUCKET": "core",
        "CATALOG_DB_HOST": "catalog", "CATALOG_DB_NAME": "db",
        "CATALOG_DB_USER": "janus_web_catalog", "CATALOG_DB_PASSWORD": "secret",
        "PUBLICATION_DB_USER": "janus_public_api",
        "PUBLICATION_DB_PASSWORD": "public-secret",
    }
    with patch.dict(os.environ, env, clear=False), patch.dict(sys.modules, modules), \
            patch("packages.postgres_bundle.load_postgres_bundle"):
        result = build_public_service()

    assert isinstance(result, PublicMartService)
    assert result.index.connection is not None
    assert result.read_artifact.catalog.kwargs["pool_size"] == 1
    assert result.read_artifact.catalog.kwargs["max_overflow"] == 0
    assert result.read_artifact.catalog.kwargs["pool_timeout"] == 5
    assert _Psycopg.kwargs["options"] == "-c statement_timeout=5000 -c default_transaction_read_only=on"
    assert _Psycopg.kwargs["autocommit"] is True


def test_catalog_runtime_rejects_owner_role():
    env = {
        "GCP_PROJECT_ID": "project", "CORE_BUCKET": "core",
        "CATALOG_DB_HOST": "catalog", "CATALOG_DB_NAME": "db",
        "CATALOG_DB_USER": "catalog_owner", "CATALOG_DB_PASSWORD": "secret",
    }
    with patch.dict(os.environ, env, clear=False), patch("packages.postgres_bundle.load_postgres_bundle"):
        try:
            _catalog_settings()
        except ValueError as error:
            assert "janus_web_catalog" in str(error)
        else:
            raise AssertionError("catalog owner role was accepted")


def test_catalog_runtime_accepts_existing_core_aliases():
    env = {
        "GCP_PROJECT_ID": "project", "POSTGRES_HOST": "catalog", "POSTGRES_DB": "db",
        "CORE_CATALOG_USER": "janus_web_catalog", "CORE_ICEBERG_WAREHOUSE": "gs://core/warehouse",
        "CATALOG_DB_HOST": "", "CATALOG_DB_NAME": "", "CATALOG_DB_USER": "",
        "CORE_BUCKET": "", "CATALOG_DB_PASSWORD": "secret",
    }
    with patch.dict(os.environ, env, clear=False), patch("packages.postgres_bundle.load_postgres_bundle"):
        settings = _catalog_settings()
    assert settings["CATALOG_DB_HOST"] == "catalog"
    assert settings["CATALOG_DB_NAME"] == "db"
    assert settings["CORE_BUCKET"] == "core"


def test_build_core_service_uses_read_only_catalog_and_bounded_rows():
    calls = {}

    class Iceberg:
        catalog, engine = object(), object()

        @classmethod
        def from_postgres(cls, **kwargs):
            calls.update(kwargs)
            return cls()

    class Reader:
        def __init__(self, catalog, *, engine):
            calls["reader"] = (catalog, engine)

        def query(self, *_args):
            return []

    modules = ModuleType("packages.duckdb_query")
    modules.DuckDBIcebergCore = Iceberg
    modules.IcebergQuery = Reader
    settings = {
        "GCP_PROJECT_ID": "project", "CORE_BUCKET": "core", "CATALOG_DB_HOST": "catalog",
        "CATALOG_DB_NAME": "db", "CATALOG_DB_USER": "janus_web_catalog", "CATALOG_DB_PASSWORD": "secret",
    }
    with patch.dict(sys.modules, {"packages.duckdb_query": modules}), patch(
            "services.api.public_runtime._catalog_settings", return_value=settings), patch.dict(
            os.environ, {"WEB_QUERY_MAX_ROWS": "120"}, clear=False):
        result = build_core_service()

    assert isinstance(result, CoreQueryService)
    assert result.max_limit == 120
    assert calls["read_only"] is True
