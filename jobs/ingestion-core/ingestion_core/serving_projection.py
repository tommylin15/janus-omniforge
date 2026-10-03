"""Bounded PostgreSQL read models for low-latency stock-detail serving.

Canonical/PIT history remains in Core Iceberg.  This module only materializes a
small recent window after a successful Core commit so normal page loads do not
need to open GCS/Iceberg files.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
import os
from typing import Any, Iterable


class StockServingProjection:
    DATASETS = frozenset({"ohlcv", "valuation", "events"})
    KEY_FIELDS = {
        "ohlcv": ("symbol", "market", "trade_date"),
        "valuation": ("symbol", "market", "observed_date"),
        "events": ("event_id", "published_at"),
    }
    SORT_FIELDS = {
        "ohlcv": "trade_date",
        "valuation": "observed_date",
        "events": "published_at",
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
        with self.connection_factory() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO control.stock_serving_recent(
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
                         updated_at=now()""",
                    prepared,
                )
                cursor.execute(
                    "DELETE FROM control.stock_serving_recent "
                    "WHERE dataset_id=%s AND sort_at < now() - (%s * interval '1 day')",
                    (dataset_id, self.retention_days),
                )
        return len(prepared)

    @classmethod
    def _row(cls, dataset_id: str, input_row: dict[str, Any], *, execution_id: str,
             provenance_id: str, source_id: str, core_snapshot_id: int | None) -> tuple[Any, ...] | None:
        symbol = str(input_row.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        sort_at = cls._timestamp(input_row.get(cls.SORT_FIELDS[dataset_id]))
        if sort_at is None:
            return None
        key_values = [input_row.get(field) for field in cls.KEY_FIELDS[dataset_id]]
        if any(value in (None, "") for value in key_values):
            return None
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
