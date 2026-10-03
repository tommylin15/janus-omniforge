"""Exact-snapshot Core reads and public Mart Iceberg v2 writes."""

from __future__ import annotations

from datetime import date
import json
import os
from typing import Any


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


def load_core_datasets(catalog: Any, manifest: dict[str, Any], requested_symbols: tuple[str, ...],
                       *, row_limit: int = 250_000) -> dict[str, list[dict[str, Any]]]:
    """Read only snapshot IDs carried by the immutable Core manifest."""
    embedded = manifest.get("datasets")
    if embedded is not None:
        if not isinstance(embedded, dict) or any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                                                 for rows in embedded.values()):
            raise ValueError("Core manifest datasets must be arrays")
        if sum(map(len, embedded.values())) > row_limit:
            raise ValueError("Core snapshot row limit exceeded")
        return {str(name): [dict(row) for row in rows] for name, rows in embedded.items()}
    tables = manifest.get("iceberg_tables", {})
    if not isinstance(tables, dict):
        raise ValueError("Core manifest iceberg_tables must be an object")
    from pyiceberg.expressions import In

    datasets: dict[str, list[dict[str, Any]]] = {}
    remaining = row_limit
    for identifier, fence in sorted(tables.items()):
        if remaining <= 0:
            raise ValueError("Core snapshot row limit exceeded")
        if not isinstance(fence, dict) or fence.get("snapshot_id") is None:
            raise ValueError("Core table is missing an immutable snapshot ID")
        if not str(identifier).startswith("core.") or not str(identifier).endswith("_v1"):
            raise ValueError("Core manifest contains a non-Core table")
        dataset_id = str(identifier).split(".", 1)[1][:-3].replace("_", "-")
        table = catalog.load_table(identifier)
        field_names = {field.name for field in table.schema().fields}
        filter_ = In("symbol", set(requested_symbols)) if requested_symbols and "symbol" in field_names else None
        # Read one extra row to detect overflow rather than silently truncate a fixed snapshot.
        scan_options: dict[str, Any] = {"snapshot_id": int(fence["snapshot_id"]), "limit": remaining + 1}
        if filter_ is not None:
            scan_options["row_filter"] = filter_
        scan = table.scan(**scan_options)
        rows = scan.to_arrow().to_pylist()
        remaining -= len(rows)
        if remaining < 0:
            raise ValueError("Core snapshot row limit exceeded")
        datasets[dataset_id] = [dict(row, __table_identifier=identifier, __snapshot_id=fence["snapshot_id"]) for row in rows]
    return datasets
