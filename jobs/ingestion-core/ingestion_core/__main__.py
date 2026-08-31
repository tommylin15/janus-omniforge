"""One-shot Cloud Run Job entrypoint for raw Stage collection."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
import json
import os
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import CollectionRequest, SourceResponse
from .control import DataState, ExecutionItem, ExecutionStatus, TriggerType
from .postgres_control import PostgreSQLControlPlane
from .first_batch import dataset_adapters, effective_trading_day, stage_raw_response
from .stage import GcsObjectStore, StageResult, StageWriter
from packages.duckdb_query import DuckDBIcebergCore


try:
    TAIPEI = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:  # Minimal containers may omit the optional tzdata package.
    TAIPEI = timezone(timedelta(hours=8))


SPARSE_DATASETS = frozenset({"finmind", "twse-events"})


def _holidays(value: str) -> set[date]:
    return {date.fromisoformat(item.strip()) for item in value.split(",") if item.strip()}


def _control_plane() -> PostgreSQLControlPlane:
    required = ("CONTROL_DB_HOST", "CONTROL_DB_NAME", "CONTROL_DB_USER", "CONTROL_DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError(f"missing control database settings: {','.join(missing)}")
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("PostgreSQL runtime dependency is unavailable") from error

    def connect():
        return psycopg.connect(
            host=os.environ["CONTROL_DB_HOST"], dbname=os.environ["CONTROL_DB_NAME"],
            user=os.environ["CONTROL_DB_USER"], password=os.environ["CONTROL_DB_PASSWORD"],
            sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
        )

    return PostgreSQLControlPlane(connect)


def _control_symbols() -> tuple[str, ...]:
    """Read the enabled first-batch symbols from the PostgreSQL control plane."""
    with _control_plane() as control:
        symbols = control.config_symbols(os.environ.get("CONTROL_COLLECTION_CONFIG", "first-batch"))
    if not symbols:
        raise ValueError("control database returned no enabled ingestion symbols")
    return symbols


def _iceberg_core(core_bucket: str) -> DuckDBIcebergCore:
    required = ("CATALOG_DB_HOST", "CATALOG_DB_NAME", "CATALOG_DB_USER", "CATALOG_DB_PASSWORD", "GCP_PROJECT_ID")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError(f"missing Iceberg catalog settings: {','.join(missing)}")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE", f"gs://{core_bucket}/warehouse").strip()
    if not warehouse.startswith(f"gs://{core_bucket}/"):
        raise ValueError("ICEBERG_WAREHOUSE must remain inside CORE_BUCKET")
    catalog_password = os.environ["CATALOG_DB_PASSWORD"].strip().lstrip("\ufeff")
    return DuckDBIcebergCore.from_postgres(
        host=os.environ["CATALOG_DB_HOST"],
        dbname=os.environ["CATALOG_DB_NAME"],
        user=os.environ["CATALOG_DB_USER"],
        password=catalog_password,
        warehouse=warehouse,
        project_id=os.environ["GCP_PROJECT_ID"],
        sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"),
    )


def _limit_response(response: SourceResponse, symbols: tuple[str, ...]) -> SourceResponse:
    """Keep only selected stock rows before Stage persistence; benchmarks stay market-wide."""
    if not response.rows or not any("symbol" in row for row in response.rows):
        return response
    selected = {symbol.upper() for symbol in symbols}
    rows = tuple(row for row in response.rows if str(row.get("symbol", "")).upper() in selected)
    payload = json.dumps([dict(row) for row in rows], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return replace(response, rows=rows, fields=frozenset(rows[0].keys()) if rows else response.fields, raw_payload=payload)


def _empty_is_nonfatal(adapter_key: str) -> bool:
    """Financial and event sources can legitimately have no rows in a window."""
    return adapter_key in SPARSE_DATASETS


def _cursor_key(source_id: str, dataset_id: str, symbols: tuple[str, ...]) -> str:
    scope = ",".join(symbols) if len(symbols) == 1 else "market"
    return f"{source_id}:{dataset_id}:{scope}"


def _cursor_is_fresh(control: object, cursor_key: str, target: date) -> bool:
    cursor = control.get_cursor(cursor_key)
    return cursor.last_success_at is not None and cursor.last_success_at.date() >= target


def _should_collect(adapter_key: str, source_id: str, dataset_id: str, symbols: tuple[str, ...],
                    target: date, control: object, *, force: bool = False) -> tuple[bool, str]:
    """Use committed cursors as the freshness fence; FinMind is fallback-only."""
    if force:
        return True, "forced"
    if _cursor_is_fresh(control, _cursor_key(source_id, dataset_id, symbols), target):
        return False, "already_fresh"
    if adapter_key == "finmind" and _cursor_is_fresh(control, _cursor_key("mops", dataset_id, ()), target):
        return False, "official_source_fresh"
    return True, "missing_target"


def _requested_dates(*, today: date, holidays: set[date], single: str = "", start: str = "", end: str = "") -> tuple[date, ...]:
    """Resolve bounded single-day or interval replay input for a job run."""
    if single.strip() and (start.strip() or end.strip()):
        raise ValueError("INGESTION_DATE cannot be combined with BACKFILL_START_DATE or BACKFILL_END_DATE")
    if bool(start.strip()) != bool(end.strip()):
        raise ValueError("BACKFILL_START_DATE and BACKFILL_END_DATE must be supplied together")
    if single.strip():
        requested = date.fromisoformat(single.strip())
        return (effective_trading_day(requested, holidays=holidays),)
    if start.strip():
        first, last = date.fromisoformat(start.strip()), date.fromisoformat(end.strip())
        if first > last:
            raise ValueError("BACKFILL_START_DATE must not be after BACKFILL_END_DATE")
        if (last - first).days > 366:
            raise ValueError("backfill range cannot exceed 367 calendar days")
        return tuple(effective_trading_day(day, holidays=holidays) for day in (first + timedelta(days=offset) for offset in range((last - first).days + 1)))
    return (effective_trading_day(today - timedelta(days=1), holidays=holidays),)


def collect_stage(*, execution_id: str | None = None, symbols: tuple[str, ...] | None = None,
                  control: object | None = None) -> dict[str, object]:
    bucket = os.environ.get("STAGE_BUCKET", "").strip()
    core_bucket = os.environ.get("CORE_BUCKET", "").strip()
    if not bucket:
        raise ValueError("STAGE_BUCKET is required")
    if not core_bucket:
        raise ValueError("CORE_BUCKET is required")
    configured = dataset_adapters()
    selected = tuple(item.strip() for item in os.environ.get("INGESTION_DATASETS", ",".join(configured)).split(",") if item.strip())
    unknown = sorted(set(selected) - set(configured))
    if unknown:
        raise ValueError(f"unsupported INGESTION_DATASETS: {','.join(unknown)}")

    # This job runs before market open, so the current calendar date cannot be
    # a completed observation day. Exchange holidays can be injected without
    # rebuilding the image.
    owned_control = control is None
    control = control or _control_plane()
    symbols = symbols or control.config_symbols(os.environ.get("CONTROL_COLLECTION_CONFIG", "first-batch"))
    if not symbols:
        if owned_control:
            control.close()
        raise ValueError("control database returned no enabled ingestion symbols")
    local_now = datetime.now(TAIPEI)
    holidays = _holidays(os.environ.get("MARKET_HOLIDAYS", ""))
    dates = tuple(dict.fromkeys(_requested_dates(
        today=local_now.date(), holidays=holidays,
        single=os.environ.get("INGESTION_DATE", ""),
        start=os.environ.get("BACKFILL_START_DATE", ""), end=os.environ.get("BACKFILL_END_DATE", ""))))
    persisted_execution = execution_id is not None
    execution_id = execution_id or str(uuid4())
    store = GcsObjectStore(bucket)
    stage_writer = StageWriter(store)
    core = _iceberg_core(core_bucket)
    staged: list[str] = []
    core_created = core_updated = core_reused = 0
    iceberg_tables: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    empty_items: list[dict[str, object]] = []
    skipped_items: list[dict[str, object]] = []
    stage_results: list[StageResult] = []
    execution_scoped = os.environ.get("STAGE_EXECUTION_SCOPED", "true").lower() in {"1", "true", "yes"}
    force_refresh = os.environ.get("FORCE_REFRESH", "false").lower() in {"1", "true", "yes"}

    for as_of in dates:
        for key in selected:
            adapter = configured[key]
            request_symbols = tuple((symbol,) for symbol in symbols) if key == "finmind" else (symbols,)
            for requested_symbols in request_symbols:
                item_key = f"{key}:{as_of.isoformat()}:{','.join(requested_symbols)}"
                should_collect, reason = _should_collect(
                    key, adapter.source_id, adapter.dataset_id, requested_symbols, as_of, control,
                    force=force_refresh,
                )
                if not should_collect:
                    skipped_items.append({"dataset": key, "date": as_of.isoformat(), "reason": reason})
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=DataState.SUCCESS, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), latest_observation_at=datetime.combine(as_of, datetime.min.time(), timezone.utc),
                        expected_symbols=len(requested_symbols), received_symbols=len(requested_symbols), cache_hit=True,
                    )
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       DataState.SUCCESS, 0, 0, True, False, None, reason))
                    continue
                request = CollectionRequest(
                    execution_id=execution_id,
                    trace_id=str(uuid4()),
                    source_id=adapter.source_id,
                    dataset_id=adapter.dataset_id,
                    market="TPEX" if adapter.source_id in {"tpex", "tpex-benchmark"} else "TWSE",
                    symbols=requested_symbols,
                    window_start=as_of - timedelta(days=400) if adapter.dataset_id == "financials" else as_of,
                    window_end=as_of,
                    timeout_seconds=30,
                )
                try:
                    response = _limit_response(adapter.fetch(request), symbols)
                    if not response.rows:
                        if _empty_is_nonfatal(key):
                            empty_items.append({
                                "dataset": key,
                                "date": as_of.isoformat(),
                                "symbols": list(requested_symbols),
                            })
                            control.record_health(
                                adapter.source_id, adapter.dataset_id, state=DataState.EMPTY, latency_ms=0,
                                fetched_at=datetime.now(timezone.utc), expected_symbols=len(requested_symbols), received_symbols=0,
                            )
                            if persisted_execution:
                                control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                               DataState.EMPTY, 0, 0, False, key == "finmind", None, "source returned no rows"))
                            continue
                        raise ValueError("source returned no rows for configured symbols")
                    result, _ = stage_raw_response(response, request, bucket=bucket, store=store, execution_scoped=execution_scoped)
                    staged.append(result.object_name)
                    stage_results.append(result)
                    committed = core.write(dataset_id=adapter.dataset_id, rows=[dict(row) for row in response.rows],
                                           execution_id=execution_id, provenance_id=result.idempotency_key,
                                           source_id=adapter.source_id, partition_date=as_of)
                    core_created += committed.inserted
                    core_updated += committed.updated
                    core_reused += committed.reused
                    iceberg_tables[committed.table_identifier] = {
                        "rows": committed.row_count,
                        "snapshot_id": committed.snapshot_id,
                        "metadata_location": committed.metadata_location,
                    }
                    observed_at = datetime.combine(as_of, datetime.min.time(), timezone.utc)
                    control.advance_cursor(_cursor_key(adapter.source_id, adapter.dataset_id, requested_symbols), observed_at, successful=True)
                    state = DataState.FALLBACK if key == "finmind" else DataState.SUCCESS
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=state, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), latest_observation_at=observed_at,
                        expected_symbols=len(requested_symbols), received_symbols=len({str(row.get("symbol", "")) for row in response.rows if row.get("symbol")}),
                    )
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       state, len(response.rows), 0, False, key == "finmind", None, None))
                except Exception as error:
                    failures.append({"dataset": key, "date": as_of.isoformat(), "error": type(error).__name__, "message": str(error)[:120]})
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=DataState.FAILED, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), expected_symbols=len(requested_symbols), received_symbols=0,
                    )
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       DataState.FAILED, 0, 0, False, key == "finmind",
                                                       type(error).__name__.upper(), "source collection failed"))

    summary: dict[str, object] = {
        "component": "ingestion-core",
        "execution_id": execution_id,
        "as_of": dates[-1].isoformat(),
        "dates": [item.isoformat() for item in dates],
        "symbols": list(symbols),
        "requested": len(selected),
        "staged": len(staged),
        "failed": len(failures),
        "empty": len(empty_items),
        "empty_items": empty_items,
        "skipped": len(skipped_items),
        "skipped_items": skipped_items,
        "core_created": core_created,
        "core_updated": core_updated,
        "core_reused": core_reused,
        "iceberg_tables": iceberg_tables,
        "objects": staged,
        "failures": failures,
    }
    try:
        if failures:
            raise RuntimeError(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        if execution_scoped:
            stage_writer.mark_core_committed(execution_id, stage_results=stage_results)
            previous = os.environ.get("PREVIOUS_STAGE_EXECUTION_ID", "").strip()
            if previous:
                summary["cleanup"] = stage_writer.cleanup_committed_execution(previous)
        return summary
    finally:
        core.close()
        if owned_control:
            control.close()


def consume_queued_collection() -> dict[str, object]:
    worker_id = os.environ.get("QUEUE_WORKER_ID", os.environ.get("K_REVISION", "ingestion-core")).strip()
    max_retries = int(os.environ.get("QUEUE_MAX_RETRIES", "1"))
    with _control_plane() as control:
        execution = control.claim_execution(worker_id, trigger_type=TriggerType.COLLECTION)
        if execution is None:
            return {"component": "ingestion-core", "status": "idle", "claimed": False}
        try:
            summary = collect_stage(execution_id=execution.execution_id, symbols=execution.requested_symbols, control=control)
            control.transition_execution(execution.execution_id, ExecutionStatus.SUCCEEDED)
            return {**summary, "status": "succeeded", "claimed": True}
        except Exception:
            retry_count = execution.retry_count + 1
            status = ExecutionStatus.RETRYING if retry_count <= max_retries else ExecutionStatus.FAILED
            control.transition_execution(execution.execution_id, status, error_code="COLLECTION_FAILED", retry_count=retry_count)
            raise


def main() -> None:
    try:
        operation = consume_queued_collection if os.environ.get("QUEUE_CONSUMER", "false").lower() in {"1", "true", "yes"} else collect_stage
        print(json.dumps(operation(), ensure_ascii=False, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "ingestion-core", "status": "failed", "error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
