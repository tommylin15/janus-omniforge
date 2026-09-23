"""Private Iceberg storage for note bodies, normalized events and marts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import os
from typing import Any, Iterable
from uuid import UUID


class PrivateIcebergStore:
    TABLE_KEYS = {
        "note_revisions": ("user_id", "note_id", "revision"),
        "ledger_events": ("user_id", "ledger_version"),
        "watchlist_events": ("user_id", "symbol", "change_version"),
        "investment_profile_revisions": ("user_id", "version"),
        "mart_user_positions": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_realized_pnl": ("user_id", "event_id", "ledger_version", "valuation_date"),
        "mart_user_unrealized_pnl": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_annual_pnl": ("user_id", "year", "currency", "ledger_version", "valuation_date"),
        "mart_user_exposure": ("user_id", "industry", "currency", "ledger_version", "valuation_date"),
        "mart_user_annual_performance": ("user_id", "year", "currency", "ledger_version", "valuation_date"),
        "mart_user_stress_tests": ("user_id", "scenario_id", "currency", "ledger_version", "valuation_date"),
        "mart_user_portfolio_summary": ("user_id", "currency", "ledger_version", "valuation_date"),
    }

    def __init__(self, catalog: Any, warehouse: str, namespace: str = "private") -> None:
        self.catalog, self.warehouse, self.namespace = catalog, warehouse.rstrip("/"), namespace
        catalog.create_namespace_if_not_exists(namespace)

    @classmethod
    def from_env(cls) -> "PrivateIcebergStore":
        from packages.postgres_bundle import load_postgres_bundle
        load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
            "PRIVATE_DATABASE_URL": "database_url",
            "PRIVATE_CATALOG_PASSWORD": "catalog_password",
            "CORE_CATALOG_PASSWORD": "core_catalog_password",
        })
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL

        required = {name: os.getenv(name, "") for name in (
            "POSTGRES_HOST", "POSTGRES_DB", "PRIVATE_CATALOG_USER", "PRIVATE_CATALOG_PASSWORD",
            "PRIVATE_ICEBERG_WAREHOUSE", "GCP_PROJECT_ID",
        )}
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing Private Iceberg settings: {','.join(missing)}")
        uri = URL.create("postgresql+psycopg", username=required["PRIVATE_CATALOG_USER"],
                         password=required["PRIVATE_CATALOG_PASSWORD"], host=required["POSTGRES_HOST"], port=5432,
                         database=required["POSTGRES_DB"], query={"sslmode": os.getenv("POSTGRES_SSLMODE", "require"), "options": "-csearch_path=catalog"})
        catalog = SqlCatalog("janus-private", type="sql", uri=uri, warehouse=required["PRIVATE_ICEBERG_WAREHOUSE"],
                             init_catalog_tables="false", **{"py-io-impl":"pyiceberg.io.pyarrow.PyArrowFileIO",
                             "gcs.project-id":required["GCP_PROJECT_ID"], "pool_size":1, "max_overflow":0, "pool_timeout":5})
        return cls(catalog, required["PRIVATE_ICEBERG_WAREHOUSE"])

    def write_note(self, *, user_id: Any, note_id: Any, revision: int, body: str, symbol: str | None,
                   trade_event_id: str | None, needs_follow_up: bool) -> str:
        ref = f"private.note_revisions/{note_id}/{revision}"
        self.upsert("note_revisions", [{"user_id":str(user_id),"note_id":str(note_id),"revision":revision,"body":body,
                    "symbol":symbol,"trade_event_id":trade_event_id,"needs_follow_up":needs_follow_up,
                    "created_at":datetime.now(timezone.utc),"artifact_ref":ref}])
        return ref

    def read_notes(self, user_id: Any, indexes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        wanted = {row["artifact_ref"]: row for row in indexes}
        if not wanted: return []
        rows = self.rows("note_revisions", user_id)
        return [{**wanted[row["artifact_ref"]], **row} for row in rows if row.get("artifact_ref") in wanted]

    def mart(self, table: str, user_id: Any, **filters: Any) -> list[dict[str, Any]]:
        rows = self.rows(table, user_id)
        rows=[row for row in rows if all(row.get(key) == value for key, value in filters.items())]
        if not rows: return []
        latest=max((str(row.get("valuation_date","")),row.get("ledger_version",0)) for row in rows)
        return [row for row in rows if (str(row.get("valuation_date","")),row.get("ledger_version",0))==latest]

    def rows(self, table: str, user_id: Any, limit: int | None = 200) -> list[dict[str, Any]]:
        identifier = f"{self.namespace}.{table}"
        if not self.catalog.table_exists(identifier): return []
        from pyiceberg.expressions import EqualTo
        scan_kwargs={"row_filter":EqualTo("user_id",str(user_id))}
        if limit is not None: scan_kwargs["limit"]=min(limit,200)
        scan=self.catalog.load_table(identifier).scan(**scan_kwargs)
        return scan.to_arrow().to_pylist()

    def upsert(self, table_name: str, rows: list[dict[str, Any]]) -> int | None:
        if not rows: return None
        import pyarrow as pa

        identifier = f"{self.namespace}.{table_name}"
        normalized = [{key:self._value(value) for key,value in row.items()} for row in rows]
        inferred=pa.Table.from_pylist(normalized)
        incoming=pa.Table.from_pylist(normalized,schema=pa.schema([
            pa.field(field.name,pa.string() if pa.types.is_null(field.type) else field.type,nullable=True) for field in inferred.schema]))
        if not self.catalog.table_exists(identifier):
            table = self.catalog.create_table(identifier, incoming.schema,
                location=f"{self.warehouse}/{table_name}", properties={"format-version":"2"})
            with table.update_spec() as spec:
                spec.add_field("user_id", "bucket[32]")
        table = self.catalog.load_table(identifier)
        incoming = pa.Table.from_pylist(normalized, schema=table.schema().as_arrow())
        table.upsert(incoming, join_cols=list(self.TABLE_KEYS[table_name]))
        snapshot = self.catalog.load_table(identifier).current_snapshot()
        return snapshot.snapshot_id if snapshot else None

    def delete_user(self, user_id: Any) -> None:
        from pyiceberg.expressions import EqualTo
        for table_name in (*self.TABLE_KEYS, "context_snapshots", "assistant_events", "assistant_skill_revisions"):
            identifier=f"{self.namespace}.{table_name}"
            if self.catalog.table_exists(identifier):
                self.catalog.load_table(identifier).delete(EqualTo("user_id",str(user_id)))

    @staticmethod
    def _value(value: Any) -> Any:
        if isinstance(value, (UUID, Enum)): return str(value)
        if isinstance(value, Decimal): return str(value)
        if isinstance(value, datetime) and value.tzinfo is not None: return value.astimezone(timezone.utc)
        if isinstance(value, date) and not isinstance(value, datetime): return value.isoformat()
        return value
