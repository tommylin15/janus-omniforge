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
        "mart_user_positions": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_realized_pnl": ("user_id", "event_id", "ledger_version", "valuation_date"),
        "mart_user_unrealized_pnl": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_annual_pnl": ("user_id", "year", "currency", "ledger_version", "valuation_date"),
        "context_snapshots": ("user_id", "context_id"),
        "assistant_events": ("user_id", "thread_id", "event_id"),
        "assistant_skill_revisions": ("user_id", "skill_id", "revision"),
    }

    def __init__(self, catalog: Any, warehouse: str, namespace: str = "private") -> None:
        self.catalog, self.warehouse, self.namespace = catalog, warehouse.rstrip("/"), namespace
        catalog.create_namespace_if_not_exists(namespace)

    @classmethod
    def from_env(cls) -> "PrivateIcebergStore":
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
        latest=max((row.get("ledger_version",0),str(row.get("valuation_date",""))) for row in rows)
        return [row for row in rows if (row.get("ledger_version",0),str(row.get("valuation_date","")))==latest]

    def write_context_snapshot(self, *, user_id: Any, context_id: str, thread_id: str, source_id: str,
                               resource: str, as_of: str | None, expires_at: datetime,
                               records: list[dict[str, Any]], provenance: list[dict[str, Any]]) -> str:
        ref = f"private.context_snapshots/{context_id}"
        self.upsert("context_snapshots", [{"user_id":str(user_id), "context_id":context_id,
            "thread_id":thread_id, "source_id":source_id, "resource":resource, "as_of":as_of,
            "expires_at":expires_at, "records_json":json.dumps(records,default=str,separators=(",",":")),
            "provenance_json":json.dumps(provenance,default=str,separators=(",",":")), "artifact_ref":ref}])
        return ref

    def read_context_snapshot(self, user_id: Any, context_id: str) -> dict[str, Any] | None:
        identifier = f"{self.namespace}.context_snapshots"
        if not self.catalog.table_exists(identifier): return None
        from pyiceberg.expressions import And, EqualTo
        rows=self.catalog.load_table(identifier).scan(
            row_filter=And(EqualTo("user_id",str(user_id)),EqualTo("context_id",context_id)),limit=1).to_arrow().to_pylist()
        row=rows[0] if rows else None
        if row is None: return None
        return {key:value for key,value in row.items() if key not in {"records_json","provenance_json"}} | {
            "records":json.loads(row["records_json"]), "provenance":json.loads(row["provenance_json"])}

    def write_assistant_event(self, *, user_id: Any, record: dict[str, Any]) -> str:
        from .assistant_storage import _json
        ref=f"private.assistant_events/{record['thread_id']}/{record['event_id']}"
        self.upsert("assistant_events", [{"user_id":str(user_id), "thread_id":record["thread_id"],
            "turn_id":record["turn_id"], "event_id":record["event_id"], "seq":record["seq"],
            "event_type":record["event_type"], "record_json":_json(record),
            "created_at":datetime.now(timezone.utc), "artifact_ref":ref}])
        return ref

    def read_assistant_event(self, user_id: Any, thread_id: str, event_id: str) -> dict[str, Any] | None:
        identifier=f"{self.namespace}.assistant_events"
        if not self.catalog.table_exists(identifier): return None
        from pyiceberg.expressions import And, EqualTo
        rows=self.catalog.load_table(identifier).scan(row_filter=And(
            And(EqualTo("user_id",str(user_id)),EqualTo("thread_id",thread_id)),EqualTo("event_id",event_id)
        ),limit=1).to_arrow().to_pylist()
        return json.loads(rows[0]["record_json"]) if rows else None

    def write_skill_revision(self, *, user_id: Any, skill_id: str, revision: int,
                             definition: Any, content_digest: str) -> str:
        from .assistant_storage import _json
        ref=f"private.assistant_skill_revisions/{skill_id}/{revision}"
        self.upsert("assistant_skill_revisions", [{"user_id":str(user_id), "skill_id":skill_id,
            "revision":revision, "content_digest":content_digest, "definition_json":_json(definition),
            "created_at":datetime.now(timezone.utc), "artifact_ref":ref}])
        return ref

    def read_skill_revision(self, user_id: Any, skill_id: str, revision: int) -> dict[str, Any] | None:
        identifier = f"{self.namespace}.assistant_skill_revisions"
        if not self.catalog.table_exists(identifier): return None
        from pyiceberg.expressions import And, EqualTo
        rows = self.catalog.load_table(identifier).scan(row_filter=And(
            And(EqualTo("user_id", str(user_id)), EqualTo("skill_id", skill_id)),
            EqualTo("revision", revision),
        ), limit=1).to_arrow().to_pylist()
        if not rows: return None
        return json.loads(rows[0]["definition_json"])

    def export_assistant(self, user_id: Any) -> dict[str, list[dict[str, Any]]]:
        names=("assistant_events","assistant_skill_revisions")
        return {name:self.rows(name,user_id,limit=None) for name in names}

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
        for table_name in self.TABLE_KEYS:
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
