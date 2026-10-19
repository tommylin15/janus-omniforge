"""Bounded PostgreSQL read models for low-latency stock-detail serving.

Canonical/PIT history remains in Core Iceberg.  This module only materializes a
small recent window after a successful Core commit so normal page loads do not
need to open GCS/Iceberg files.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import os
from typing import Any, Iterable


class StockServingProjection:
    MARKET_DATASETS = frozenset({"benchmark", "institutional", "market-activity", "financials"})
    DATASETS = frozenset({"ohlcv", "valuation", "events"}) | MARKET_DATASETS
    KEY_FIELDS = {
        "ohlcv": ("symbol", "market", "trade_date"),
        "valuation": ("symbol", "market", "observed_date"),
        "events": ("event_id", "published_at"),
        "benchmark": ("benchmark_id", "trade_date"),
        "institutional": ("symbol", "market", "trade_date", "investor_type"),
        "market-activity": ("symbol", "market", "trade_date", "metric"),
        "financials": ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "metric"),
    }
    SORT_FIELDS = {
        "ohlcv": "trade_date",
        "valuation": "observed_date",
        "events": "published_at",
        "benchmark": "trade_date",
        "institutional": "trade_date",
        "market-activity": "trade_date",
        "financials": "availability_at",
    }

    def __init__(self, connection_factory: Any, *, retention_days: int = 400) -> None:
        if not 30 <= int(retention_days) <= 1096:
            raise ValueError("stock serving retention must be between 30 and 1096 days")
        self.connection_factory = connection_factory
        self.retention_days = int(retention_days)

    @classmethod
    def from_env(cls) -> "StockServingProjection":
        required = {
            "host": os.environ.get("CONTROL_DB_HOST", "").strip(),
            "dbname": os.environ.get("CONTROL_DB_NAME", "").strip(),
            "user": os.environ.get("CONTROL_DB_USER", "").strip(),
            "password": os.environ.get("CONTROL_DB_PASSWORD", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing serving projection database settings:{','.join(missing)}")
        if required["user"] != "janus_control":
            raise ValueError("stock serving projection requires janus_control")
        import psycopg

        def connect():
            return psycopg.connect(
                host=required["host"], port=5432, dbname=required["dbname"],
                user=required["user"], password=required["password"],
                sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
            )

        return cls(connect, retention_days=int(os.environ.get("STOCK_SERVING_RETENTION_DAYS", "400")))

    def publish(self, dataset_id: str, rows: Iterable[dict[str, Any]], *, execution_id: str,
                provenance_id: str, source_id: str, core_snapshot_id: int | None) -> int:
        if dataset_id not in self.DATASETS:
            return 0
        prepared = [self._row(dataset_id, row, execution_id=execution_id,
                              provenance_id=provenance_id, source_id=source_id,
                              core_snapshot_id=core_snapshot_id) for row in rows]
        prepared = [row for row in prepared if row is not None]
        if not prepared:
            return 0
        table = "market_serving_recent" if dataset_id in self.MARKET_DATASETS else "stock_serving_recent"
        chunk_size = 500
        with self.connection_factory() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                for offset in range(0, len(prepared), chunk_size):
                    chunk = prepared[offset:offset + chunk_size]
                    cursor.executemany(
                        f"""INSERT INTO control.{table}(
                               dataset_id,symbol,natural_key,sort_at,payload_json,source_id,
                               provenance_id,execution_id,core_snapshot_id,updated_at)
                           VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,now())
                           ON CONFLICT(dataset_id,symbol,natural_key) DO UPDATE SET
                             sort_at=EXCLUDED.sort_at,
                             payload_json=EXCLUDED.payload_json,
                             source_id=EXCLUDED.source_id,
                             provenance_id=EXCLUDED.provenance_id,
                             execution_id=EXCLUDED.execution_id,
                             core_snapshot_id=EXCLUDED.core_snapshot_id,
                             updated_at=now()
                           WHERE EXCLUDED.sort_at >= control.{table}.sort_at""",
                        chunk,
                    )
                cursor.execute(
                    f"DELETE FROM control.{table} "
                    "WHERE dataset_id=%s AND sort_at < now() - (%s * interval '1 day')",
                    (dataset_id, max(self.retention_days,1096) if dataset_id=='financials' else self.retention_days),
                )
        return len(prepared)

    def materialize_home_market_snapshot(self, as_of_date: date | None = None) -> dict[str, Any]:
        """Use the API's canonical serializer and fixed SQL; no second financial calculation."""
        from packages.web_api import CoreQueryService
        from services.api.public_runtime import market_serving_query
        today = as_of_date or datetime.now(timezone(timedelta(hours=8))).date()
        with self.connection_factory() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                def query(identifier, _sql, parameters):
                    fixed = market_serving_query(identifier, parameters)
                    if fixed is None:
                        raise ValueError('unsupported home snapshot query')
                    statement, values, payload_only = fixed
                    cursor.execute(statement.replace('publication.market_serving_recent',
                                                     'control.market_serving_recent'), values)
                    records = cursor.fetchall()
                    if payload_only:
                        return [value if isinstance(value, dict) else json.loads(value) for (value,) in records]
                    names = [column.name for column in cursor.description]
                    return [dict(zip(names, record)) for record in records]
                payload = CoreQueryService(query).market_home(as_of_date=today)
                cursor.execute(
                    """INSERT INTO control.home_market_snapshot(snapshot_id, schema_version, as_of_date, payload_json, updated_at)
                       VALUES (1, 'market-home.v1', %s, %s::jsonb, now())
                       ON CONFLICT (snapshot_id) DO UPDATE SET
                         schema_version=EXCLUDED.schema_version, as_of_date=EXCLUDED.as_of_date,
                         payload_json=EXCLUDED.payload_json, updated_at=now()""",
                    (payload['as_of'] or today, json.dumps(payload, ensure_ascii=False, default=self._json_value, allow_nan=False)),
                )
                return payload

    @classmethod
    def eligible(cls, dataset_id: str, row: dict[str, Any]) -> bool:
        if dataset_id not in cls.DATASETS:
            return False
        if not str(row.get("symbol") or row.get("benchmark_id") or "").strip():
            return False
        if cls._timestamp(row.get(cls.SORT_FIELDS[dataset_id])) is None:
            return False
        return all(row.get(field) not in (None, "") for field in cls.KEY_FIELDS[dataset_id])

    @classmethod
    def _row(cls, dataset_id: str, input_row: dict[str, Any], *, execution_id: str,
             provenance_id: str, source_id: str, core_snapshot_id: int | None) -> tuple[Any, ...] | None:
        if (dataset_id == 'financials' and input_row.get('statement_type') == 'monthly_revenue'
                and str(input_row.get('metric','')).startswith('monthly_revenue_')
                and input_row.get('unit') == 'TWD_thousands'):
            input_row = {**input_row, 'canonical_metric':input_row['metric'], 'metric':'monthly_revenue'}
        symbol = str(input_row.get("symbol") or input_row.get("benchmark_id") or "").strip().upper()
        if not symbol:
            return None
        sort_at = cls._timestamp(input_row.get(cls.SORT_FIELDS[dataset_id]))
        if sort_at is None:
            return None
        key_values = [input_row.get(field) for field in cls.KEY_FIELDS[dataset_id]]
        if any(value in (None, "") for value in key_values):
            return None
        if dataset_id == 'financials':
            # Serving keeps the latest comparable period; canonical revisions stay in Core.
            key_values += [input_row.get('fiscal_period_end') or input_row.get('period_end'),
                           input_row.get('report_scope'), source_id]
        natural_key = "sha256:" + sha256(
            json.dumps([cls._json_value(value) for value in key_values], ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload = {key: cls._json_value(value) for key, value in input_row.items() if key != "raw_payload"}
        payload.update({
            "execution_id": execution_id,
            "provenance_id": provenance_id,
            "source_id": source_id,
            "core_snapshot_id": core_snapshot_id,
        })
        return (
            dataset_id, symbol, natural_key, sort_at,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            source_id, provenance_id, execution_id, core_snapshot_id,
        )

    @staticmethod
    def _timestamp(value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, time.min, timezone.utc)
        else:
            text = str(value).strip().replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                try:
                    parsed = datetime.combine(date.fromisoformat(text[:10]), time.min, timezone.utc)
                except ValueError:
                    return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if hasattr(value, "as_tuple"):
            return str(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return None
        return value


def backfill_recent(core: Any, projection: StockServingProjection, *,
                    as_of: datetime | None = None, max_rows: int | None = None,
                    max_bytes: int | None = None, chunk_rows: int = 1000) -> dict[str, Any]:
    """Materialize the recent Core window into PostgreSQL without inventing provenance.

    File bytes are planned before Parquet is read so the operation fails closed
    if a future Core grows beyond this bounded one-shot backfill contract.
    """
    max_rows = int(max_rows if max_rows is not None else os.environ.get("STOCK_SERVING_BACKFILL_MAX_ROWS", "250000"))
    max_bytes = int(max_bytes if max_bytes is not None else os.environ.get(
        "STOCK_SERVING_BACKFILL_MAX_BYTES", str(256 * 1024 * 1024)))
    if not 1 <= max_rows <= 1_000_000:
        raise ValueError("stock serving backfill row cap must be between 1 and 1000000")
    if not 16 * 1024 * 1024 <= max_bytes <= 1024 * 1024 * 1024:
        raise ValueError("stock serving backfill byte cap must be between 16 MiB and 1 GiB")
    if not 1 <= int(chunk_rows) <= 5000:
        raise ValueError("stock serving backfill chunk_rows must be between 1 and 5000")

    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(days=projection.retention_days)

    from pyiceberg.expressions import GreaterThanOrEqual

    report: dict[str, Any] = {
        "status": "succeeded",
        "retention_days": projection.retention_days,
        "cutoff": cutoff.isoformat(),
        "max_rows": max_rows,
        "max_bytes": max_bytes,
        "source_rows": 0,
        "eligible_rows": 0,
        "published_rows": 0,
        "source_bytes": 0,
        "datasets": {},
    }
    total_rows = 0
    total_bytes = 0

    for dataset_id in sorted(projection.DATASETS):
        if not core.table_exists(dataset_id):
            report["datasets"][dataset_id] = {"status": "missing", "source_rows": 0, "published_rows": 0}
            continue
        table = core.catalog.load_table(core.table_identifier(dataset_id))
        snapshot = table.current_snapshot()
        if snapshot is None:
            report["datasets"][dataset_id] = {"status": "empty", "source_rows": 0, "published_rows": 0}
            continue

        sort_field = projection.SORT_FIELDS[dataset_id]
        cutoff_value: Any = cutoff if sort_field == "published_at" else cutoff.date()
        scan = table.scan(row_filter=GreaterThanOrEqual(sort_field, cutoff_value))
        tasks = list(scan.plan_files())
        dataset_bytes = sum(int(getattr(task.file, "file_size_in_bytes", 0) or 0) for task in tasks)
        if total_bytes + dataset_bytes > max_bytes:
            raise RuntimeError(
                f"stock serving backfill byte cap exceeded before read: {total_bytes + dataset_bytes}>{max_bytes}"
            )
        rows = scan.to_arrow().to_pylist()
        if total_rows + len(rows) > max_rows:
            raise RuntimeError(
                f"stock serving backfill row cap exceeded: {total_rows + len(rows)}>{max_rows}"
            )

        eligible = [row for row in rows if projection.eligible(dataset_id, row)]
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            execution_id = str(row.get("execution_id") or "").strip()
            provenance_id = str(row.get("provenance_id") or "").strip()
            source_id = str(row.get("source_id") or "").strip()
            if not execution_id or not provenance_id or not source_id:
                raise RuntimeError(f"stock serving backfill missing canonical provenance in {dataset_id}")
            grouped[(execution_id, provenance_id, source_id)].append(row)

        published = 0
        for (execution_id, provenance_id, source_id), grouped_rows in grouped.items():
            for offset in range(0, len(grouped_rows), int(chunk_rows)):
                published += projection.publish(
                    dataset_id,
                    grouped_rows[offset:offset + int(chunk_rows)],
                    execution_id=execution_id,
                    provenance_id=provenance_id,
                    source_id=source_id,
                    core_snapshot_id=snapshot.snapshot_id,
                )
        if published != len(eligible):
            raise RuntimeError(f"stock serving backfill did not publish every eligible {dataset_id} row")

        total_rows += len(rows)
        total_bytes += dataset_bytes
        report["source_rows"] += len(rows)
        report["eligible_rows"] += len(eligible)
        report["published_rows"] += published
        report["source_bytes"] += dataset_bytes
        report["datasets"][dataset_id] = {
            "status": "succeeded",
            "snapshot_id": snapshot.snapshot_id,
            "source_files": len(tasks),
            "source_bytes": dataset_bytes,
            "source_rows": len(rows),
            "eligible_rows": len(eligible),
            "published_rows": published,
        }

    return report
