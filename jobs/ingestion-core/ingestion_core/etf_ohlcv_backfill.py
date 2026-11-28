"""Bounded official EOD OHLCV backfill for already-registered ETFs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from http.client import IncompleteRead
import json
import os
from time import sleep
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from uuid import uuid4

from packages.provenance import Provenance
from .adapters import CollectionRequest
from .control import ExecutionStatus
from .dq import validate_ohlcv
from .sources import (
    ExchangeOhlcvAdapter,
    _date as _official_date,
    parse_registered_etf_ohlcv,
    tpex_market_volume_adapter,
    twse_market_volume_adapter,
)
from .stage import GcsObjectStore, StageResult, StageWriter


_MARKET_SOURCE_IDS: dict[str, str] = {"TWSE": "twse", "TPEX": "tpex"}


def _default_fetch(url: str) -> bytes:
    """Fetch an official exchange endpoint with a single transient retry."""
    try:
        return ExchangeOhlcvAdapter._https(url)
    except (HTTPError, IncompleteRead, TimeoutError, URLError, OSError):
        sleep(1)
        return ExchangeOhlcvAdapter._https(url)


def _is_non_trading_payload(raw: bytes, expected_day: date) -> tuple[bool, str | None]:
    """Identify official exchange holiday or empty-session payloads cleanly."""
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, None
    if isinstance(document, list):
        return (len(document) == 0, "empty_list" if not document else None)
    if not isinstance(document, dict):
        return True, "unexpected_payload_type"
    stat = str(document.get("stat") or "").strip()
    tables = document.get("tables")
    if stat and ("沒有" in stat or "no data" in stat.lower()):
        return True, "non_trading_stat"
    if not tables and stat.upper() != "OK":
        return True, "missing_tables_non_ok"
    if not tables or all(not (isinstance(tab, dict) and (tab.get("data") or [])) for tab in tables):
        return True, "empty_tables"
    doc_date = document.get("date")
    if doc_date:
        try:
            if _official_date(doc_date) != expected_day.isoformat():
                return True, "date_mismatch"
        except ValueError:
            return True, "invalid_response_date"
    return False, None


def backfill_registered_etf_ohlcv(
    start_date: date,
    end_date: date,
    *,
    markets: tuple[str, ...] = ("TWSE", "TPEX"),
    symbols: tuple[str, ...] | None = None,
    control: Any | None = None,
    core: Any | None = None,
    writer: StageWriter | None = None,
    projection: Any | None = None,
    fetch: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Backfill official EOD OHLCV for registered ETFs without mutating equity universe."""
    from .__main__ import TAIPEI, _control_plane, _iceberg_core
    from .serving_projection import StockServingProjection

    today = datetime.now(TAIPEI).date()
    if start_date > end_date:
        raise ValueError("BACKFILL_START_DATE must not be after BACKFILL_END_DATE")
    if (end_date - start_date).days > 31:
        raise ValueError("ETF OHLCV backfill range cannot exceed 31 days")
    if end_date > today:
        raise ValueError("BACKFILL_END_DATE cannot be in the future")

    normalized_markets = tuple(dict.fromkeys(str(m).strip().upper() for m in markets if str(m).strip()))
    if not normalized_markets or not set(normalized_markets).issubset({"TWSE", "TPEX"}):
        raise ValueError("markets must be a non-empty subset of TWSE, TPEX")

    symbol_filter = (
        {str(sym).strip().upper() for sym in symbols if str(sym).strip()}
        if symbols is not None
        else None
    )

    owns_control = control is None
    owns_core = core is None
    execution = None
    if control is None:
        control = _control_plane()

    try:
        market_etfs: dict[str, list[str]] = {}
        for market in normalized_markets:
            registered = set(control.registered_etf_symbols(market))
            if symbol_filter is not None:
                registered &= symbol_filter
            market_etfs[market] = sorted(registered)

        active_markets = [market for market in normalized_markets if market_etfs[market]]
        for market in active_markets:
            source_id = _MARKET_SOURCE_IDS[market]
            if not control.source_is_approved(source_id):
                raise ValueError(f"official market source is not approved: {source_id}")

        if core is None:
            core_bucket = os.environ.get("CORE_BUCKET", "").strip()
            if not core_bucket:
                raise ValueError("CORE_BUCKET is required")
            core = _iceberg_core(core_bucket)
        if writer is None:
            stage_bucket = os.environ.get("STAGE_BUCKET", "").strip()
            if not stage_bucket:
                raise ValueError("STAGE_BUCKET is required")
            writer = StageWriter(GcsObjectStore(stage_bucket))
        if projection is None:
            projection = StockServingProjection.from_env()

        execution = control.enqueue_collection(
            "first-batch",
            request_options={
                "operation": "etf-ohlcv-backfill",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "markets": list(normalized_markets),
            },
        )
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)

        fetcher = fetch or _default_fetch
        adapters = {
            "TWSE": twse_market_volume_adapter(),
            "TPEX": tpex_market_volume_adapter(),
        }
        days_processed = 0
        core_inserted = 0
        core_updated = 0
        core_reused = 0
        serving_published = 0
        skipped_days: list[dict[str, str]] = []
        per_day_counts: dict[str, int] = {}
        errors: list[dict[str, str]] = []
        staged: list[StageResult] = []

        total_days = (end_date - start_date).days + 1
        for offset in range(total_days):
            day = start_date + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            days_processed += 1
            for market in active_markets:
                source_id = _MARKET_SOURCE_IDS[market]
                adapter = adapters[market]
                request = CollectionRequest(
                    execution.execution_id,
                    execution.trace_id,
                    source_id,
                    "market-volume",
                    market,
                    tuple(market_etfs[market]),
                    day,
                    day,
                    30,
                )
                url = adapter.url_builder(request) if adapter.url_builder else adapter.endpoint
                try:
                    raw = fetcher(url)
                    non_trading, reason = _is_non_trading_payload(raw, day)
                    if non_trading:
                        skipped_days.append(
                            {
                                "date": day.isoformat(),
                                "market": market,
                                "reason": reason or "non_trading",
                            }
                        )
                        continue
                    observed_at = datetime.combine(day, datetime.min.time(), timezone.utc)
                    parsed = parse_registered_etf_ohlcv(
                        raw,
                        market=market,
                        source_id=source_id,
                        expected_date=day,
                        allowed_symbols=set(market_etfs[market]),
                        observed_at=observed_at,
                    )
                    if not parsed:
                        per_day_counts[f"{day.isoformat()}:{market}"] = 0
                        continue
                    dq = validate_ohlcv(parsed, analysis_as_of=day)
                    if not dq.accepted:
                        per_day_counts[f"{day.isoformat()}:{market}"] = 0
                        continue

                    received_at = datetime.now(timezone.utc)
                    provenance = Provenance(
                        provenance_id=str(uuid4()),
                        source_id=source_id,
                        source_url=url,
                        dataset_id="ohlcv",
                        observed_at=observed_at,
                        published_at=None,
                        fetched_at=received_at,
                        content_hash="sha256:" + sha256(raw).hexdigest(),
                        is_fallback=False,
                        quality_details={
                            "request_identity": {
                                "kind": "etf_ohlcv_backfill",
                                "market": market,
                                "date": day.isoformat(),
                            }
                        },
                    )
                    entry = writer.write_raw(
                        payload=raw,
                        media_type="application/json",
                        extension="json",
                        execution_id=execution.execution_id,
                        provenance=provenance,
                        execution_scoped=True,
                    )
                    staged.append(entry)
                    accepted_rows = [
                        {**dict(row), "provenance_id": entry.idempotency_key}
                        for row in dq.accepted
                    ]
                    commit = core.write(
                        dataset_id="ohlcv",
                        rows=accepted_rows,
                        execution_id=execution.execution_id,
                        provenance_id=entry.idempotency_key,
                        source_id=source_id,
                        partition_date=day,
                    )
                    published = projection.publish(
                        "ohlcv",
                        accepted_rows,
                        execution_id=execution.execution_id,
                        provenance_id=entry.idempotency_key,
                        source_id=source_id,
                        core_snapshot_id=commit.snapshot_id,
                    )
                    core_inserted += commit.inserted
                    core_updated += commit.updated
                    core_reused += commit.reused
                    serving_published += published
                    per_day_counts[f"{day.isoformat()}:{market}"] = len(accepted_rows)
                except Exception as error:
                    errors.append(
                        {
                            "date": day.isoformat(),
                            "market": market,
                            "error_code": type(error).__name__[:64],
                        }
                    )

        if staged:
            writer.mark_core_committed(execution.execution_id, stage_results=staged)

        status = "succeeded" if not errors and serving_published > 0 else "partial"
        control.complete_collection(execution.execution_id, None, partial=(status != "succeeded"))
        return {
            "component": "ingestion-core",
            "operation": "etf-ohlcv-backfill",
            "status": status,
            "execution_id": execution.execution_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "markets": list(normalized_markets),
            "etf_counts": {market: len(market_etfs[market]) for market in normalized_markets},
            "days_processed": days_processed,
            "skipped_days": skipped_days,
            "core_inserted": core_inserted,
            "core_updated": core_updated,
            "core_reused": core_reused,
            "serving_published": serving_published,
            "per_day_counts": per_day_counts,
            "errors": errors,
        }
    except Exception:
        if execution is not None:
            control.transition_execution(
                execution.execution_id,
                ExecutionStatus.FAILED,
                error_code="ETF_OHLCV_BACKFILL_FAILED",
            )
        raise
    finally:
        if owns_core and core is not None:
            core.close()
        if owns_control:
            control.close()


def run_from_env() -> dict[str, Any]:
    """Execute bounded ETF OHLCV backfill from Cloud Run Job environment variables."""
    start_raw = os.environ.get("BACKFILL_START_DATE", "").strip()
    end_raw = os.environ.get("BACKFILL_END_DATE", "").strip()
    if not start_raw or not end_raw:
        raise ValueError("BACKFILL_START_DATE and BACKFILL_END_DATE are required")
    markets_raw = os.environ.get("ETF_BACKFILL_MARKETS", "TWSE,TPEX")
    markets = tuple(m.strip().upper() for m in markets_raw.split(",") if m.strip())
    symbols_raw = os.environ.get("ETF_BACKFILL_SYMBOLS", "").strip()
    symbols = tuple(s.strip().upper() for s in symbols_raw.split(",") if s.strip()) if symbols_raw else None
    return backfill_registered_etf_ohlcv(
        date.fromisoformat(start_raw),
        date.fromisoformat(end_raw),
        markets=markets,
        symbols=symbols,
    )
