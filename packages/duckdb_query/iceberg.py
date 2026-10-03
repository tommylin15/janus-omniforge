"""PostgreSQL-catalogued Iceberg Core commits queried through embedded DuckDB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from contextlib import contextmanager
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
        "stock-profile": ("symbol", "market", "observed_date"),
        "market-volume": ("symbol", "market", "trade_date"),
        "ohlcv": ("symbol", "market", "trade_date"),
        "valuation": ("symbol", "market", "observed_date"),
        "institutional": ("symbol", "market", "trade_date", "investor_type"),
        "financials": ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "version_at", "metric", "source_id"),
        "events": ("event_id", "published_at"),
        "market-activity": ("symbol", "market", "trade_date", "metric"),
        "benchmark": ("benchmark_id", "trade_date"),
    }
    TABLE_NAMES = {dataset: f"{dataset.replace('-', '_')}_v1" for dataset in IDENTIFIERS}
    PARTITIONS = {
        "stock-profile": (("observed_date", "month"), ("symbol", "bucket[32]")),
        "market-volume": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "ohlcv": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "valuation": (("observed_date", "month"), ("symbol", "bucket[32]")),
        "institutional": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "financials": (("published_at", "year"), ("symbol", "bucket[32]")),
        "events": (("published_at", "month"), ("symbol", "bucket[32]")),
        "market-activity": (("trade_date", "month"), ("symbol", "bucket[32]")),
        "benchmark": (("trade_date", "month"), ("benchmark_id", "bucket[16]")),
    }
    DATE_FIELDS = frozenset({"observed_date", "trade_date", "effective_date"})
    TIMESTAMP_FIELDS = frozenset({"published_at", "observed_at", "version_at"})
    UPSERT_KEY_LIMIT = 512

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
        core = cls(catalog, warehouse, create_namespace=not read_only)
        core._lock_settings = dict(host=host, dbname=dbname, user=user, password=password, sslmode=sslmode, connect_timeout=5)
        return core

    @contextmanager
    def mutation_lock(self):
        from packages.postgres_lock import public_data_lock
        with public_data_lock(getattr(self, "_lock_settings", None)):
            yield

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
        with self.mutation_lock():
            return self._write(dataset_id=dataset_id, rows=rows, execution_id=execution_id,
                               provenance_id=provenance_id, source_id=source_id, partition_date=partition_date)

    def _write(self, *, dataset_id: str, rows: list[dict[str, Any]], execution_id: str,
               provenance_id: str, source_id: str, partition_date: date) -> IcebergCommitResult:
        del partition_date  # Partition values come from each row, not the execution date.
        identifiers = self.IDENTIFIERS.get(dataset_id)
        if identifiers is None:
            raise ValueError(f"unsupported Iceberg Core dataset: {dataset_id}")
        incoming = [self._normalise(row, execution_id, provenance_id, source_id) for row in rows]
        if dataset_id == "financials":
            incoming = [self._financial_version(row) for row in incoming]
        if not incoming:
            raise ValueError("Iceberg Core write requires at least one row")

        import pyarrow as pa

        identifier = self.table_identifier(dataset_id)
        created = not self.catalog.table_exists(identifier)
        observation_reused = 0
        if dataset_id == "financials" and not created:
            table = self.catalog.load_table(identifier)
            from pyiceberg.expressions import And, In
            scope = And(In("symbol", {row["symbol"] for row in incoming}),
                        In("fiscal_year", {row["fiscal_year"] for row in incoming}))
            fields = {field.name for field in table.schema().fields}
            columns = [name for name in ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "metric",
                       "source_id", "value", "unit", "currency", "period_basis", "report_scope", "availability_at", "observed_at", "published_at") if name in fields]
            prior = table.scan(row_filter=scope, selected_fields=tuple(columns)).to_arrow().to_pylist()
            incoming, observation_reused = self._financial_observations(prior, incoming)
            if not incoming:
                snapshot = table.current_snapshot()
                return IcebergCommitResult(dataset_id, 0, 0, observation_reused,
                    int(snapshot.summary["total-records"]), identifier, table.metadata_location, snapshot.snapshot_id)
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
            existing = []
        else:
            table = self.catalog.load_table(identifier)
            incoming_arrow = self._arrow_table(incoming, existing_schema=table.schema().as_arrow())
            with table.update_schema() as update:
                update.union_by_name(incoming_arrow.schema)
            del incoming_arrow
            table = self.catalog.load_table(identifier)
            from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, In, IsNull, LessThanOrEqual, Or

            partition_field = self.PARTITIONS[dataset_id][0][0]
            selection_field = self.PARTITIONS[dataset_id][1][0]
            dates = [row[partition_field] for row in incoming if row.get(partition_field) is not None]
            if dates:
                first, last = min(dates), max(dates)
                row_filter = EqualTo(partition_field, first) if first == last else And(
                    GreaterThanOrEqual(partition_field, first), LessThanOrEqual(partition_field, last))
                if len(dates) != len(incoming):
                    row_filter = Or(row_filter, IsNull(partition_field))
            else:
                row_filter = IsNull(partition_field)
            if all(row.get(selection_field) is not None for row in incoming):
                row_filter = And(row_filter, In(selection_field, {row[selection_field] for row in incoming}))
            existing = table.scan(row_filter=row_filter).to_arrow().to_pylist()
            if dataset_id == "financials":
                existing = [self._financial_version(row) for row in existing]
        if dataset_id == "financials":
            versions = {}
            for row in existing + incoming:
                key = tuple(row.get(field) for field in identifiers)
                values = tuple(row.get(field) for field in ("value", "unit", "currency"))
                if key in versions and versions[key] != values:
                    raise ValueError("conflicting financial values at the same version time")
                versions[key] = values
        merged = self.engine.merge(existing, incoming, identifiers)
        if merged.changed_rows:
            properties = {"janus.execution-id": execution_id, "janus.dataset-id": dataset_id}
            schema = table.schema().as_arrow()
            if merged.updated and len(merged.changed_rows) > self.UPSERT_KEY_LIMIT:
                # PyIceberg upsert builds one predicate branch per changed natural key.
                replacement = pa.Table.from_pylist(list(merged.rows), schema=schema)
                table.overwrite(replacement, overwrite_filter=row_filter, snapshot_properties=properties)
            else:
                changed = pa.Table.from_pylist(list(merged.changed_rows), schema=schema)
                if merged.updated:
                    table.upsert(changed, join_cols=list(identifiers), snapshot_properties=properties)
                else:
                    table.append(changed, snapshot_properties=properties)
            table = self.catalog.load_table(identifier)
        snapshot = table.current_snapshot()
        row_count = int(snapshot.summary["total-records"]) if snapshot else len(merged.rows)
        return IcebergCommitResult(
            dataset_id=dataset_id,
            inserted=merged.inserted,
            updated=merged.updated,
            reused=merged.reused + observation_reused,
            row_count=row_count,
            table_identifier=identifier,
            metadata_location=table.metadata_location,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
        )

    @staticmethod
    def _financial_version(input_row: dict[str, Any]) -> dict[str, Any]:
        """A version clock identifies an observation, never invents publication."""
        row = dict(input_row)
        value = row.get("version_at") or row.get("published_at") or row.get("availability_at")
        if not value:
            raise ValueError("financial version requires publication or proven availability")
        if not row.get("published_at") and row.get("publication_time_authoritative") is not False:
            raise ValueError("unknown financial publication must be explicitly non-authoritative")
        if not row.get("published_at") and not row.get("availability_at"):
            raise ValueError("unknown publication requires proven receipt availability")
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if not row.get("published_at") and parsed.tzinfo is None:
            raise ValueError("receipt version time must include timezone")
        row["version_at"] = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return row

    @staticmethod
    def _financial_observations(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        """Reuse unchanged non-authoritative observations; retain actual value revisions."""
        keys = ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "metric", "source_id")
        identity = lambda row: tuple(str(row.get(key)) for key in keys)
        def observed(row):
            value = row.get("availability_at") or row.get("observed_at") or row.get("published_at")
            if not value: return datetime.min.replace(tzinfo=timezone.utc)
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        latest = {}
        for row in sorted(existing, key=observed):
            latest[identity(row)] = row
        retained, reused = [], 0
        for row in sorted(incoming, key=observed):
            prior = latest.get(identity(row))
            same = prior is not None and all(row.get(field) is None or str(row.get(field)) == str(prior.get(field))
                                            for field in ("value", "unit", "currency", "period_basis", "report_scope"))
            if (row.get("publication_time_authoritative") is False and same and observed(prior) <= observed(row)
                    and (prior.get("availability_at") or not row.get("availability_at"))):
                reused += 1
                continue
            retained.append(row)
            latest[identity(row)] = row
        return retained, reused

    @staticmethod
    def _arrow_table(rows: list[dict[str, Any]], existing_schema: Any | None = None) -> Any:
        """Infer additive fields while giving all-null columns a stable concrete type."""
        import pyarrow as pa

        names = dict.fromkeys(name for row in rows for name in row)
        inferred = pa.Table.from_pylist([{name: row.get(name) for name in names} for row in rows]).schema
        def concrete(field):
            if not pa.types.is_null(field.type):
                return field
            kind = pa.timestamp("us", tz="UTC") if field.name in DuckDBIcebergCore.TIMESTAMP_FIELDS else pa.string()
            return pa.field(field.name, kind, nullable=True)
        existing = {field.name: field for field in existing_schema or ()}
        incoming = {field.name: field for field in inferred}
        fields = list(existing.values())
        for name, field in incoming.items():
            if name in existing:
                continue
            fields.append(concrete(field))
        schema = pa.schema(fields or [
            concrete(field)
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
