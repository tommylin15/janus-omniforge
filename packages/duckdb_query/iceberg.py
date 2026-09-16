"""PostgreSQL-catalogued Iceberg Core commits queried through embedded DuckDB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import os
from typing import Any, Sequence

from .engine import DuckDBEngine


@dataclass(frozen=True)
class IcebergCommitResult:
    dataset_id: str
    inserted: int
    updated: int
    reused: int
    row_count: int
    table_identifier: str
    metadata_location: str
    snapshot_id: int | None


class DuckDBIcebergCore:
    """Natural-key merge in DuckDB followed by an atomic Iceberg v2 upsert."""

    IDENTIFIERS = {
        "ohlcv": ("symbol", "market", "trade_date"),
        "valuation": ("symbol", "market", "observed_date"),
        "institutional": ("symbol", "market", "trade_date", "investor_type"),
        "financials": ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "published_at", "metric"),
        "events": ("event_id", "published_at"),
        "market-activity": ("symbol", "market", "trade_date", "metric"),
        "benchmark": ("benchmark_id", "trade_date"),
    }
    TABLE_NAMES = {dataset: f"{dataset.replace('-', '_')}_v1" for dataset in IDENTIFIERS}
    PARTITIONS = {
        "ohlcv": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "valuation": (("observed_date", "month"), ("symbol", "bucket[32]")),
        "institutional": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "financials": (("published_at", "year"), ("symbol", "bucket[32]")),
        "events": (("published_at", "month"), ("symbol", "bucket[32]")),
        "market-activity": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "benchmark": (("trade_date", "month"), ("benchmark_id", "bucket[16]")),
    }
    DATE_FIELDS = frozenset({"observed_date", "trade_date", "effective_date"})
    TIMESTAMP_FIELDS = frozenset({"published_at", "observed_at"})

    def __init__(self, catalog: Any, warehouse: str, *, namespace: str = "core",
                 engine: DuckDBEngine | None = None, create_namespace: bool = True) -> None:
        self.catalog = catalog
        self.warehouse = warehouse.rstrip("/")
        self.namespace = namespace
        self.engine = engine or DuckDBEngine(
            memory_limit=os.environ.get("DUCKDB_MEMORY_LIMIT", "384MB"),
            threads=int(os.environ.get("DUCKDB_THREADS", "1")),
            query_timeout_seconds=int(os.environ.get("DUCKDB_QUERY_TIMEOUT_SECONDS", "60")),
        )
        if create_namespace:
            self.catalog.create_namespace_if_not_exists(namespace)

    @classmethod
    def from_postgres(cls, *, host: str, dbname: str, user: str, password: str,
                      warehouse: str, project_id: str, sslmode: str = "require",
                      read_only: bool = False) -> "DuckDBIcebergCore":
        import psycopg
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL

        # Fail fast at the credential/network boundary before SQLAlchemy adds
        # catalog-specific behaviour. No password or SQL is logged here.
        with psycopg.connect(
            host=host, port=5432, dbname=dbname, user=user, password=password,
            sslmode=sslmode, connect_timeout=5,
        ) as connection:
            connection.execute("SELECT 1")

        # The existing JDBC tables live in the isolated catalog schema.
        uri = URL.create(
            "postgresql+psycopg",
            username=user,
            password=password,
            host=host,
            port=5432,
            database=dbname,
            query={"sslmode": sslmode, "options": "-csearch_path=catalog"},
        )
        catalog = SqlCatalog(
            "janus",
            type="sql",
            uri=uri,
            warehouse=warehouse,
            init_catalog_tables="false",
            pool_pre_ping="true",
            **{
                "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
                "gcs.project-id": project_id,
                "pool_size": 1,
                "max_overflow": 0,
                "pool_timeout": 5,
            },
        )
        return cls(catalog, warehouse, create_namespace=not read_only)

    def close(self) -> None:
        self.engine.close()
        catalog_engine = getattr(self.catalog, "engine", None)
        if catalog_engine is not None:
            catalog_engine.dispose()

    def table_identifier(self, dataset_id: str) -> str:
        try:
            return f"{self.namespace}.{self.TABLE_NAMES[dataset_id]}"
        except KeyError as error:
            raise ValueError(f"unsupported Iceberg Core dataset: {dataset_id}") from error

    def table_exists(self, dataset_id: str) -> bool:
        return bool(self.catalog.table_exists(self.table_identifier(dataset_id)))

    def write(self, *, dataset_id: str, rows: list[dict[str, Any]], execution_id: str,
              provenance_id: str, source_id: str, partition_date: date) -> IcebergCommitResult:
        del partition_date  # Partition values come from each row, not the execution date.
        identifiers = self.IDENTIFIERS.get(dataset_id)
        if identifiers is None:
            raise ValueError(f"unsupported Iceberg Core dataset: {dataset_id}")
        incoming = [self._normalise(row, execution_id, provenance_id, source_id) for row in rows]
        if not incoming:
            raise ValueError("Iceberg Core write requires at least one row")

        import pyarrow as pa

        identifier = self.table_identifier(dataset_id)
        created = not self.catalog.table_exists(identifier)
        if created:
            incoming_arrow = self._arrow_table(incoming)
            table = self.catalog.create_table(
                identifier,
                incoming_arrow.schema,
                location=f"{self.warehouse}/{self.TABLE_NAMES[dataset_id]}",
                properties={
                    "format-version": "2",
                    "write.delete.mode": "copy-on-write",
                    "write.update.mode": "copy-on-write",
                },
            )
            update = table.update_spec()
            for field, transform in self.PARTITIONS[dataset_id]:
                update.add_field(field, transform)
            update.commit()
            table = self.catalog.load_table(identifier)
        else:
            table = self.catalog.load_table(identifier)
            incoming_arrow = self._arrow_table(incoming, existing_schema=table.schema().as_arrow())
            with table.update_schema() as update:
                update.union_by_name(incoming_arrow.schema)
            table = self.catalog.load_table(identifier)

        existing = table.scan().to_arrow().to_pylist()
        merged = self.engine.merge(existing, incoming, identifiers)
        if merged.changed_rows:
            changed = pa.Table.from_pylist(list(merged.changed_rows), schema=table.schema().as_arrow())
            table.upsert(
                changed,
                join_cols=list(identifiers),
                snapshot_properties={"janus.execution-id": execution_id, "janus.dataset-id": dataset_id},
            )
            table = self.catalog.load_table(identifier)
        snapshot = table.current_snapshot()
        return IcebergCommitResult(
            dataset_id=dataset_id,
            inserted=merged.inserted,
            updated=merged.updated,
            reused=merged.reused,
            row_count=len(merged.rows),
            table_identifier=identifier,
            metadata_location=table.metadata_location,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
        )

    @staticmethod
    def _arrow_table(rows: list[dict[str, Any]], existing_schema: Any | None = None) -> Any:
        """Infer additive fields while giving all-null columns a stable concrete type."""
        import pyarrow as pa

        inferred = pa.Table.from_pylist(rows).schema
        existing = {field.name: field for field in existing_schema or ()}
        incoming = {field.name: field for field in inferred}
        fields = list(existing.values())
        for name, field in incoming.items():
            if name in existing:
                continue
            fields.append(pa.field(name, pa.string() if pa.types.is_null(field.type) else field.type, nullable=True))
        schema = pa.schema(fields or [
            pa.field(field.name, pa.string() if pa.types.is_null(field.type) else field.type, nullable=True)
            for field in inferred
        ])
        # No existing schema means the inferred fields have not yet been added above.
        if not existing:
            schema = pa.schema([
                pa.field(field.name, pa.string() if pa.types.is_null(field.type) else field.type, nullable=True)
                for field in inferred
            ])
        return pa.Table.from_pylist(rows, schema=schema)

    @classmethod
    def _normalise(cls, input_row: dict[str, Any], execution_id: str,
                   provenance_id: str, source_id: str) -> dict[str, Any]:
        row: dict[str, Any] = {}
        for field, value in input_row.items():
            if value in {"", None}:
                row[field] = None
            elif field in cls.DATE_FIELDS and not isinstance(value, date):
                row[field] = date.fromisoformat(str(value)[:10])
            elif field in cls.TIMESTAMP_FIELDS:
                parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                row[field] = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            elif isinstance(value, Decimal):
                row[field] = str(value)
            elif isinstance(value, (dict, list, tuple)):
                import json
                row[field] = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            else:
                row[field] = value
        row.setdefault("execution_id", execution_id)
        row.setdefault("provenance_id", provenance_id)
        row.setdefault("source_id", source_id)
        row["content_hash"] = DuckDBEngine.content_hash(row)
        return row


class IcebergQuery:
    """Read-only, row-bounded DuckDB queries over a PyIceberg scan."""

    def __init__(self, catalog: Any, engine: DuckDBEngine | None = None) -> None:
        self.catalog = catalog
        self.engine = engine or DuckDBEngine()

    def query(self, identifier: str, sql: str, parameters: Sequence[Any] = ()) -> tuple[dict[str, Any], ...]:
        # A dataset may have no committed partition yet. Treat that as a
        # legitimate empty Core dataset; transport/catalog failures still
        # propagate to the bounded API error boundary.
        if hasattr(self.catalog, "table_exists") and not self.catalog.table_exists(identifier):
            return ()
        table = self.catalog.load_table(identifier)
        table.scan().to_duckdb("core_table", connection=self.engine.connection)
        # CoreQueryService supplies an allow-listed logical identifier.  The
        # physical scan is registered under a private temporary name so the
        # query runtime cannot address arbitrary catalog tables.
        safe_sql = sql.replace(identifier, "core_table")
        return self.engine.query(safe_sql, parameters)
