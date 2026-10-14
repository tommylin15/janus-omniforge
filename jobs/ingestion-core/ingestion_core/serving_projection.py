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
        with self.connection_factory() as connection:
            with connection.transaction(), connection.cursor() as cursor:
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
                    prepared,
                )
                cursor.execute(
                    f"DELETE FROM control.{table} "
                    "WHERE dataset_id=%s AND sort_at < now() - (%s * interval '1 day')",
                    (dataset_id, self.retention_days),
                )
        return len(prepared)

    def materialize_home_market_snapshot(self, as_of_date: date | None = None) -> dict[str, Any]:
        """Write-time aggregation for /market-home; builds home_market_snapshot row in control."""
        today = as_of_date or datetime.now(timezone(timedelta(hours=8))).date()
        sections: dict[str, dict[str, Any]] = {}

        with self.connection_factory() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                # 1. Benchmark TAIEX
                cursor.execute(
                    """SELECT payload_json FROM control.market_serving_recent
                       WHERE dataset_id = 'benchmark' AND symbol = 'TAIEX'
                       ORDER BY sort_at DESC LIMIT 40"""
                )
                rows = cursor.fetchall()
                benchmarks = [r[0] if isinstance(r[0], dict) else json.loads(r[0]) for r in rows] if rows else []

                history_by_day: dict[str, dict[str, str]] = {}
                latest_readable = None
                for candidate in benchmarks:
                    day = str(candidate.get("trade_date") or "")[:10]
                    try:
                        trade_day = date.fromisoformat(day)
                        val = float(str(candidate.get("close")))
                    except (ValueError, TypeError):
                        continue
                    if trade_day > today or val <= 0:
                        continue
                    if latest_readable is None:
                        latest_readable = candidate
                    source = str(candidate.get("source_id") or "").strip()
                    provenance = str(candidate.get("provenance_id") or "").strip()
                    if not source or not provenance or day in history_by_day:
                        continue
                    history_by_day[day] = {
                        "date": day, "value": str(val),
                        "source_id": source, "provenance_id": provenance,
                    }
                history = sorted(history_by_day.values(), key=lambda item: item["date"])[-30:]

                as_of_taiex = str(latest_readable.get("trade_date")) if latest_readable and latest_readable.get("trade_date") else None
                age_taiex = (today - date.fromisoformat(as_of_taiex)).days if as_of_taiex else None
                taiex_section = {
                    "status": "available" if latest_readable and age_taiex is not None and age_taiex <= 7 else "missing",
                    "as_of": as_of_taiex,
                    "freshness_days": age_taiex,
                    "row_count": 1 if latest_readable else 0,
                    "coverage": {"requested_symbols": 1, "received_symbols": 1 if latest_readable else 0},
                    "provenance": {
                        "source_id": str(latest_readable.get("source_id") or "") if latest_readable else "",
                        "provenance_id": str(latest_readable.get("provenance_id") or "") if latest_readable else "",
                        "execution_id": str(latest_readable.get("execution_id") or "") if latest_readable else "",
                    },
                    "data": {
                        "benchmark_id": "TAIEX",
                        "close": latest_readable.get("close") if latest_readable else None,
                        "history_points": history,
                        "history_unit": "index_points",
                        "history_as_of": history[-1]["date"] if history else None,
                        "history_status": "available" if len(history) >= 2 else "missing",
                        "history_source_ids": sorted({p["source_id"] for p in history}),
                    }
                }
                sections["taiex"] = taiex_section

                # 2. Market Activity & Institutional Write-time Aggregations
                for dataset in ("market-activity", "institutional"):
                    fields = ({"day_trade_shares": "day_trade_shares", "day_trade_buy_twd": "day_trade_buy_twd",
                               "day_trade_sell_twd": "day_trade_sell_twd"} if dataset == "market-activity" else
                              {"foreign_net_shares": "foreign", "investment_trust_net_shares": "investment_trust",
                               "dealer_net_shares": "dealer"})
                    category, value = ("metric", "value") if dataset == "market-activity" else ("investor_type", "net_shares")
                    aggregates = ",".join(
                        f"sum((payload_json->>'{value}')::numeric) FILTER (WHERE payload_json->>'{category}'='{kind}') AS {alias}"
                        for alias, kind in fields.items())
                    cursor.execute(
                        f"""SELECT payload_json->>'trade_date' AS trade_date, count(*) AS row_count,
                                   count(DISTINCT symbol) AS covered_symbols, array_agg(DISTINCT source_id) AS source_ids,
                                   array_agg(DISTINCT provenance_id) AS provenance_ids, array_agg(DISTINCT execution_id::text) AS execution_ids,
                                   {aggregates}
                            FROM control.market_serving_recent
                            WHERE dataset_id=%s AND sort_at=(SELECT max(sort_at) FROM control.market_serving_recent WHERE dataset_id=%s)
                            GROUP BY payload_json->>'trade_date'""",
                        (dataset, dataset)
                    )
                    row = cursor.fetchone()
                    if row:
                        names = [col.name for col in cursor.description]
                        row_dict = dict(zip(names, row))
                        as_of_sec = str(row_dict.get("trade_date") or "")
                        age_sec = (today - date.fromisoformat(as_of_sec)).days if as_of_sec else None
                        data_fields = ("day_trade_shares", "day_trade_buy_twd", "day_trade_sell_twd") if dataset == "market-activity" else (
                            "foreign_net_shares", "investment_trust_net_shares", "dealer_net_shares")
                        data_vals = {k: float(row_dict[k]) if row_dict.get(k) is not None else None for k in data_fields}
                        sections[dataset] = {
                            "status": "available" if age_sec is not None and age_sec <= 7 else "missing",
                            "as_of": as_of_sec or None,
                            "freshness_days": age_sec,
                            "row_count": int(row_dict.get("row_count") or 0),
                            "coverage": {"received_symbols": int(row_dict.get("covered_symbols") or 0), "expected_symbols": None},
                            "provenance": {
                                "source_ids": [str(s) for s in (row_dict.get("source_ids") or [])],
                                "provenance_ids": [str(p) for p in (row_dict.get("provenance_ids") or [])],
                                "execution_ids": [str(e) for e in (row_dict.get("execution_ids") or [])],
                            },
                            "data": data_vals,
                        }
                    else:
                        sections[dataset] = {
                            "status": "missing", "as_of": None, "freshness_days": None,
                            "row_count": 0, "coverage": {}, "provenance": {}, "data": {},
                        }

                dates = [part["as_of"] for part in sections.values() if part.get("as_of")]
                available = [part for part in sections.values() if part["status"] in {"available", "partial", "stale"}]
                overall_status = ("available" if len(available) == len(sections) and all(part["status"] == "available" for part in sections.values())
                                  else "partial" if available else "missing")
                as_of_overall = dates[0] if dates and len(set(dates)) == 1 else (as_of_taiex or str(today))

                payload = {
                    "schema_version": "market-home.v1",
                    "as_of": as_of_overall,
                    "status": overall_status,
                    "sections": sections,
                }

                # 3. UPSERT 單列快照（id=1）
                cursor.execute(
                    """INSERT INTO control.home_market_snapshot(snapshot_id, schema_version, as_of_date, payload_json, updated_at)
                       VALUES (1, 'market-home.v1', %s, %s::jsonb, now())
                       ON CONFLICT (snapshot_id) DO UPDATE SET
                         schema_version = EXCLUDED.schema_version,
                         as_of_date = EXCLUDED.as_of_date,
                         payload_json = EXCLUDED.payload_json,
                         updated_at = now()""",
                    (as_of_overall if as_of_overall else today, json.dumps(payload, ensure_ascii=False))
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
