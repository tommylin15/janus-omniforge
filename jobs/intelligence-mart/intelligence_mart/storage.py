"""Iceberg catalog construction, compatibility reads, and Mart maintenance handles."""

from __future__ import annotations

import os
from typing import Any

from .analytics_reader import IcebergSnapshotReader


MART_TABLES = (
    "mart_screening_signals", "mart_core_alpha", "mart_risk_portfolio",
    "mart_alternative_sentiment", "mart_scoped_analysis", "mart_market_regime_daily",
    "mart_sector_rotation_daily", "mart_topic_trends_daily", "mart_candidate_health",
    "mart_daily_brief", "mart_llm_narratives",
)


class MartMaintenanceStore:
    """Read/maintenance handle for historical tables; no legacy analysis writer."""
    IDENTIFIERS = MART_TABLES

    def __init__(self, catalog, warehouse):
        self.catalog = catalog

    def table_identifier(self, name):
        if name not in self.IDENTIFIERS:
            raise ValueError("unsupported Mart table")
        return f"mart.{name}_v1"

    def close(self):
        engine = getattr(self.catalog, "engine", None)
        if engine is not None:
            engine.dispose()


def sql_catalog_from_environment() -> Any:
    from pyiceberg.catalog.sql import SqlCatalog
    from sqlalchemy import URL

    required = {name: os.environ.get(name, "").strip() for name in (
        "CATALOG_DB_HOST", "CATALOG_DB_NAME", "CATALOG_DB_USER", "CATALOG_DB_PASSWORD", "GCP_PROJECT_ID", "MART_BUCKET",
    )}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"missing Iceberg catalog settings: {','.join(missing)}")
    uri = URL.create(
        "postgresql+psycopg", username=required["CATALOG_DB_USER"], password=required["CATALOG_DB_PASSWORD"],
        host=required["CATALOG_DB_HOST"], port=5432, database=required["CATALOG_DB_NAME"],
        query={"sslmode": os.environ.get("CATALOG_DB_SSLMODE", "require"), "options": "-csearch_path=catalog"},
    )
    warehouse = os.environ.get("MART_ICEBERG_WAREHOUSE", f"gs://{required['MART_BUCKET']}/warehouse").strip()
    if not warehouse.startswith(f"gs://{required['MART_BUCKET']}/"):
        raise ValueError("MART_ICEBERG_WAREHOUSE must remain inside MART_BUCKET")
    catalog = SqlCatalog(
        "janus", type="sql", uri=uri, warehouse=warehouse, init_catalog_tables="false",
        **{"py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO", "gcs.project-id": required["GCP_PROJECT_ID"],
           "pool_size": 1, "max_overflow": 0, "pool_timeout": 5, "pool_pre_ping": "true"},
    )
    catalog._janus_lock_settings = dict(host=required["CATALOG_DB_HOST"], dbname=required["CATALOG_DB_NAME"],
                                       user=required["CATALOG_DB_USER"], password=required["CATALOG_DB_PASSWORD"],
                                       sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"), connect_timeout=5)
    return catalog


def iceberg_snapshot_reader_from_environment() -> IcebergSnapshotReader:
    """Build the default exact-snapshot reference/fallback reader."""
    return IcebergSnapshotReader(sql_catalog_from_environment())


def load_core_datasets(catalog: Any, manifest: dict[str, Any], requested_symbols: tuple[str, ...],
                       *, row_limit: int = 250_000, telemetry: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Compatibility wrapper; specialist runtime uses AnalyticsSnapshotReader directly."""
    snapshot_id = str(manifest.get("snapshot_id", "")).strip()
    if not snapshot_id:
        raise ValueError("Core manifest is missing immutable snapshot identity")
    result = IcebergSnapshotReader(catalog).read(
        manifest, requested_symbols, core_snapshot_id=snapshot_id, row_limit=row_limit,
    )
    if telemetry is not None:
        telemetry.update(result.telemetry)
    return result.datasets
