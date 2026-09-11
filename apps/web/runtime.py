"""Production runtime wiring for the Web Cloud Run service.

All credentials arrive through environment variables (normally Secret Manager
references).  The default application remains health-only when the settings
are absent, which keeps local static checks safe and deterministic.
"""

from __future__ import annotations

import os
from typing import Any

from packages.admin_api import AdminService
from packages.duckdb_query import DuckDBIcebergCore, IcebergQuery
from packages.web_api import CoreQueryService
from .scheduler import CloudSchedulerSync


def _required(*names: str) -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"missing web runtime settings: {','.join(missing)}")
    return values


class WebRuntime:
    """Owns one bounded catalog/ DuckDB reader and one control repository."""

    def __init__(self, *, core: Any, admin: AdminService, closeables: tuple[Any, ...] = ()) -> None:
        self.core = core
        self.admin = admin
        self._closeables = closeables

    def close(self) -> None:
        for item in reversed(self._closeables):
            close = getattr(item, "close", None)
            if close is not None:
                close()


def build_runtime() -> WebRuntime:
    """Create the read-only query and control-plane services for Cloud Run."""
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_WEB_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("web_control_password", "control_password"),
        "CATALOG_DB_PASSWORD": ("web_catalog_password", "catalog_password"),
    })
    settings = _required(
        "GCP_PROJECT_ID", "CORE_BUCKET", "CATALOG_DB_HOST", "CATALOG_DB_NAME",
        "CATALOG_DB_USER", "CATALOG_DB_PASSWORD", "CONTROL_DB_HOST",
        "CONTROL_DB_NAME", "CONTROL_DB_USER", "CONTROL_DB_PASSWORD",
    )

    import psycopg
    from ingestion_core.postgres_control import PostgreSQLControlPlane

    def control_connect():
        return psycopg.connect(
            host=settings["CONTROL_DB_HOST"], dbname=settings["CONTROL_DB_NAME"],
            user=settings["CONTROL_DB_USER"], password=settings["CONTROL_DB_PASSWORD"],
            sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
        )

    iceberg = DuckDBIcebergCore.from_postgres(
        host=settings["CATALOG_DB_HOST"], dbname=settings["CATALOG_DB_NAME"],
        user=settings["CATALOG_DB_USER"], password=settings["CATALOG_DB_PASSWORD"],
        warehouse=os.environ.get("ICEBERG_WAREHOUSE", f"gs://{settings['CORE_BUCKET']}/warehouse"),
        project_id=settings["GCP_PROJECT_ID"],
        sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"),
        read_only=True,
    )
    reader = IcebergQuery(iceberg.catalog, engine=iceberg.engine)
    core_service = CoreQueryService(reader.query, max_limit=int(os.environ.get("WEB_QUERY_MAX_ROWS", "200")))
    control = PostgreSQLControlPlane(control_connect)
    scheduler = None
    if os.environ.get("ADMIN_SCHEDULER_JOB", "").strip():
        scheduler = CloudSchedulerSync(
            settings["GCP_PROJECT_ID"], os.environ.get("ADMIN_SCHEDULER_LOCATION", "us-central1"),
            os.environ["ADMIN_SCHEDULER_JOB"], timezone=os.environ.get("ADMIN_SCHEDULER_TIMEZONE", "Asia/Taipei"),
        )
    return WebRuntime(
        core=core_service,
        admin=AdminService(control, core=core_service, schedule_sync=scheduler),
        closeables=(control, iceberg),
    )
