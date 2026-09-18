"""Bounded read-only Core and public Mart runtimes for FastAPI."""

from __future__ import annotations

import os
from threading import Lock
from typing import Any, Sequence

from packages.web_api import CoreQueryService, IcebergArtifactReader, PostgreSQLPublicIndex, PublicMartService


def _required(*names: str) -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"missing public runtime settings:{','.join(missing)}")
    return values


def _catalog_settings() -> dict[str, str]:
    from packages.postgres_bundle import load_postgres_bundle

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("web_catalog_password", "catalog_password"),
    })
    warehouse = os.environ.get("CORE_ICEBERG_WAREHOUSE", "").strip()
    bucket = os.environ.get("CORE_BUCKET", "").strip()
    if not bucket and warehouse.startswith("gs://"):
        bucket = warehouse[5:].split("/", 1)[0]
    settings = {
        "GCP_PROJECT_ID": os.environ.get("GCP_PROJECT_ID", "").strip(),
        "CORE_BUCKET": bucket,
        "CATALOG_DB_HOST": (os.environ.get("CATALOG_DB_HOST", "").strip()
                             or os.environ.get("POSTGRES_HOST", "").strip()),
        "CATALOG_DB_NAME": (os.environ.get("CATALOG_DB_NAME", "").strip()
                             or os.environ.get("POSTGRES_DB", "").strip()),
        "CATALOG_DB_USER": (os.environ.get("CATALOG_DB_USER", "").strip()
                             or os.environ.get("CORE_CATALOG_USER", "").strip()),
        "CATALOG_DB_PASSWORD": os.environ.get("CATALOG_DB_PASSWORD", "").strip(),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise ValueError(f"missing public runtime settings:{','.join(missing)}")
    if settings["CATALOG_DB_USER"] != "janus_web_catalog":
        raise ValueError("public query runtime requires janus_web_catalog")
    return settings


def build_core_service() -> CoreQueryService:
    from packages.duckdb_query import DuckDBIcebergCore, IcebergQuery

    settings = _catalog_settings()
    iceberg = DuckDBIcebergCore.from_postgres(
        host=settings["CATALOG_DB_HOST"], dbname=settings["CATALOG_DB_NAME"],
        user=settings["CATALOG_DB_USER"], password=settings["CATALOG_DB_PASSWORD"],
        warehouse=os.environ.get("ICEBERG_WAREHOUSE", f"gs://{settings['CORE_BUCKET']}/warehouse"),
        project_id=settings["GCP_PROJECT_ID"], sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"),
        read_only=True,
    )
    reader = IcebergQuery(iceberg.catalog, engine=iceberg.engine)
    lock = Lock()

    # ponytail: one bounded DuckDB connection is serialized; use per-request engines if measured concurrency needs it.
    def query(identifier: str, sql: str, parameters: Sequence[Any] = ()):
        with lock:
            return reader.query(identifier, sql, parameters)

    return CoreQueryService(query, max_limit=int(os.environ.get("WEB_QUERY_MAX_ROWS", "200")))


def build_public_service() -> PublicMartService:
    from packages.postgres_bundle import load_postgres_bundle

    stage = "publication bundle"
    try:
        load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {"PUBLICATION_DB_PASSWORD": ("web_publication_password",)})
        stage = "catalog bundle/settings"
        settings = _catalog_settings() | _required("PUBLICATION_DB_PASSWORD")
        publication_user = os.environ.get("PUBLICATION_DB_USER", "janus_public_api").strip()
        if publication_user != "janus_public_api":
            raise ValueError("public query runtime requires janus_public_api")

        stage = "imports"
        import psycopg
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL
        from ingestion_core.stage import GcsObjectStore

        stage = "catalog"
        uri = URL.create(
            "postgresql+psycopg", username=settings["CATALOG_DB_USER"],
            password=settings["CATALOG_DB_PASSWORD"], host=settings["CATALOG_DB_HOST"],
            port=5432, database=settings["CATALOG_DB_NAME"],
            query={"sslmode": os.environ.get("CATALOG_DB_SSLMODE", "require"), "options": "-csearch_path=catalog"},
        )
        catalog = SqlCatalog(
            "janus", type="sql", uri=uri,
            warehouse=os.environ.get("ICEBERG_WAREHOUSE", f"gs://{settings['CORE_BUCKET']}/warehouse"),
            init_catalog_tables="false",
            **{"py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO", "gcs.project-id": settings["GCP_PROJECT_ID"],
               "pool_size": 1, "max_overflow": 0, "pool_timeout": 5, "pool_pre_ping": "true"},
        )
        stage = "publication connection"
        def connect_publication():
            return psycopg.connect(
                host=os.environ.get("PUBLICATION_DB_HOST", settings["CATALOG_DB_HOST"]),
                dbname=os.environ.get("PUBLICATION_DB_NAME", settings["CATALOG_DB_NAME"]),
                user=publication_user,
                password=settings["PUBLICATION_DB_PASSWORD"],
                sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
                options="-c statement_timeout=5000 -c default_transaction_read_only=on", autocommit=True,
            )
        connection = connect_publication()
        return PublicMartService(
            PostgreSQLPublicIndex(connection, connect_publication), IcebergArtifactReader(catalog, GcsObjectStore),
        )
    except Exception as error:
        raise RuntimeError(f"public runtime setup failed at {stage}:{type(error).__name__}") from error


class PipelineService:
    """Thin wrapper to trigger Cloud Run Jobs for backfill operations."""

    def __init__(self, *, project: str, region: str, ingestion_job: str, mart_job: str) -> None:
        self._project = project
        self._region = region
        self._ingestion_job = ingestion_job
        self._mart_job = mart_job

    @classmethod
    def from_env(cls) -> "PipelineService":
        project = os.environ.get("GCP_PROJECT_ID", "").strip()
        region = os.environ.get("GCP_REGION", "us-central1").strip()
        ingestion_job = os.environ.get("INGESTION_JOB", "janus-ingestion-core").strip()
        mart_job = os.environ.get("MART_JOB", "janus-intelligence-mart").strip()
        if not project:
            raise ValueError("GCP_PROJECT_ID is required for pipeline service")
        return cls(project=project, region=region, ingestion_job=ingestion_job, mart_job=mart_job)

    def _jobs_url(self, job: str) -> str:
        return f"https://run.googleapis.com/v2/projects/{self._project}/locations/{self._region}/jobs/{job}"

    def _authorized_session(self) -> Any:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
        return AuthorizedSession(credentials)

    def backfill(self, start_date: str, end_date: str, *, trigger_mart: bool = False) -> dict[str, Any]:
        """Update job env-vars and execute ingestion backfill."""
        from datetime import date as _date
        _date.fromisoformat(start_date)  # validate
        _date.fromisoformat(end_date)
        session = self._authorized_session()
        # Patch env-vars on the job definition
        patch_url = self._jobs_url(self._ingestion_job)
        patch_resp = session.patch(
            patch_url,
            json={"template": {"template": {"containers": [{"env": [
                {"name": "BACKFILL_START_DATE", "value": start_date},
                {"name": "BACKFILL_END_DATE", "value": end_date},
                {"name": "FORCE_REFRESH", "value": "true"},
                {"name": "MART_JOB", "value": self._mart_job if trigger_mart else ""},
            ]}]}}},
            params={"updateMask": "template.template.containers"},
            timeout=15,
        )
        patch_resp.raise_for_status()
        # Execute the job
        run_resp = session.post(self._jobs_url(self._ingestion_job) + ":run", json={}, timeout=10)
        run_resp.raise_for_status()
        run_data = run_resp.json()
        return {
            "status": "accepted",
            "start_date": start_date,
            "end_date": end_date,
            "trigger_mart": trigger_mart,
            "execution_name": run_data.get("metadata", {}).get("name", ""),
        }


def build_pipeline_service() -> PipelineService:
    return PipelineService.from_env()


def build_admin_service():
    from packages.admin_api import AdminService
    from packages.postgres_bundle import load_postgres_bundle

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("web_control_password", "control_password"),
    })
    settings = {
        "CONTROL_DB_HOST": os.environ.get("CONTROL_DB_HOST", "").strip() or os.environ.get("POSTGRES_HOST", "").strip(),
        "CONTROL_DB_NAME": os.environ.get("CONTROL_DB_NAME", "").strip() or os.environ.get("POSTGRES_DB", "").strip(),
        "CONTROL_DB_USER": os.environ.get("CONTROL_DB_USER", "").strip() or "janus_web_control",
        "CONTROL_DB_PASSWORD": os.environ.get("CONTROL_DB_PASSWORD", "").strip(),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise ValueError(f"missing admin runtime settings:{','.join(missing)}")

    import psycopg
    from ingestion_core.postgres_control import PostgreSQLControlPlane

    def connect():
        return psycopg.connect(
            host=settings["CONTROL_DB_HOST"], dbname=settings["CONTROL_DB_NAME"],
            user=settings["CONTROL_DB_USER"], password=settings["CONTROL_DB_PASSWORD"],
            sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
        )

    return AdminService(PostgreSQLControlPlane(connect), core=build_core_service())
