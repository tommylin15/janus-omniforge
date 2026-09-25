import os
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from packages.web_api import CoreQueryService, PublicMartService
from services.api.public_runtime import PipelineService, _catalog_settings, build_core_service, build_public_service


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


class _RunResponse:
    def __init__(self, payload=None):
        self.payload = payload or {"metadata": {"name": "operations/backfill-1"}}
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self.payload


class _Session:
    def __init__(self):
        self.posts = []
        self.patches = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return _RunResponse()

    def patch(self, url, **kwargs):
        self.patches.append((url, kwargs))
        raise AssertionError("backfill must not patch the Cloud Run Job definition")


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


def test_pipeline_backfill_uses_run_overrides_and_never_patches_job():
    service = PipelineService(
        project="project", region="us-central1",
        ingestion_job="janus-ingestion-core", mart_job="janus-intelligence-mart",
    )
    session = _Session()
    with patch.object(service, "_authorized_session", return_value=session):
        result = service.backfill("2026-09-01", "2026-09-24", trigger_mart=False)

    assert session.patches == []
    assert len(session.posts) == 1
    url, kwargs = session.posts[0]
    assert url.endswith("/jobs/janus-ingestion-core:run")
    assert kwargs["timeout"] == 10
    env = {item["name"]: item["value"] for item in kwargs["json"]["overrides"]["containerOverrides"][0]["env"]}
    assert env == {
        "INGESTION_DATE": "",
        "BACKFILL_START_DATE": "2026-09-01",
        "BACKFILL_END_DATE": "2026-09-24",
        "FORCE_REFRESH": "true",
        "QUEUE_CONSUMER": "false",
        "MART_JOB": "",
    }
    assert result["execution_name"] == "operations/backfill-1"


def test_pipeline_backfill_can_trigger_mart_without_mutating_job():
    service = PipelineService(
        project="project", region="us-central1",
        ingestion_job="janus-ingestion-core", mart_job="janus-intelligence-mart",
    )
    session = _Session()
    with patch.object(service, "_authorized_session", return_value=session):
        service.backfill("2026-09-01", "2026-09-02", trigger_mart=True)
    env = {item["name"]: item["value"] for item in session.posts[0][1]["json"]["overrides"]["containerOverrides"][0]["env"]}
    assert env["MART_JOB"] == "janus-intelligence-mart"


def test_pipeline_backfill_rejects_invalid_or_unbounded_dates_before_network():
    service = PipelineService(
        project="project", region="us-central1",
        ingestion_job="janus-ingestion-core", mart_job="janus-intelligence-mart",
    )
    session = _Session()
    with patch.object(service, "_authorized_session", return_value=session):
        with pytest.raises(ValueError, match="start_date"):
            service.backfill("2026-09-24", "2026-09-01")
        with pytest.raises(ValueError, match="367 calendar days"):
            service.backfill("2025-01-01", "2026-09-24")
    assert session.posts == []
    assert session.patches == []
