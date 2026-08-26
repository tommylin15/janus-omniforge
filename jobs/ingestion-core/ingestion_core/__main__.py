"""One-shot Cloud Run Job entrypoint for raw Stage collection."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import CollectionRequest
from .first_batch import dataset_adapters, effective_trading_day, stage_raw_response
from .core import IncrementalCoreWriter
from .stage import GcsObjectStore, StageResult, StageWriter


try:
    TAIPEI = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:  # Minimal containers may omit the optional tzdata package.
    TAIPEI = timezone(timedelta(hours=8))


def _holidays(value: str) -> set[date]:
    return {date.fromisoformat(item.strip()) for item in value.split(",") if item.strip()}


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


def collect_stage() -> dict[str, object]:
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
    local_now = datetime.now(TAIPEI)
    holidays = _holidays(os.environ.get("MARKET_HOLIDAYS", ""))
    dates = tuple(dict.fromkeys(_requested_dates(
        today=local_now.date(), holidays=holidays,
        single=os.environ.get("INGESTION_DATE", ""),
        start=os.environ.get("BACKFILL_START_DATE", ""), end=os.environ.get("BACKFILL_END_DATE", ""))))
    execution_id = str(uuid4())
    store = GcsObjectStore(bucket)
    stage_writer = StageWriter(store)
    core = IncrementalCoreWriter(GcsObjectStore(core_bucket))
    staged: list[str] = []
    core_created = core_reused = 0
    failures: list[dict[str, str]] = []
    stage_results: list[StageResult] = []
    execution_scoped = os.environ.get("STAGE_EXECUTION_SCOPED", "true").lower() in {"1", "true", "yes"}

    for as_of in dates:
        for key in selected:
            adapter = configured[key]
            request = CollectionRequest(
                execution_id=execution_id,
                trace_id=str(uuid4()),
                source_id=adapter.source_id,
                dataset_id=adapter.dataset_id,
                market="TPEX" if adapter.source_id in {"tpex", "tpex-benchmark"} else "TWSE",
                symbols=(),
                window_start=as_of - timedelta(days=400) if adapter.dataset_id == "financials" else as_of,
                window_end=as_of,
                timeout_seconds=30,
            )
            try:
                response = adapter.fetch(request)
                if not response.rows:
                    raise ValueError("source returned no normalized rows")
                result, _ = stage_raw_response(response, request, bucket=bucket, store=store, execution_scoped=execution_scoped)
                staged.append(result.object_name)
                stage_results.append(result)
                committed = core.write(dataset_id=adapter.dataset_id, rows=[dict(row) for row in response.rows],
                                       execution_id=execution_id, provenance_id=result.idempotency_key,
                                       source_id=adapter.source_id, partition_date=as_of)
                core_created += committed.created
                core_reused += committed.reused
            except Exception as error:
                failures.append({"dataset": key, "date": as_of.isoformat(), "error": type(error).__name__, "message": str(error)[:120]})

    summary: dict[str, object] = {
        "component": "ingestion-core",
        "execution_id": execution_id,
        "as_of": dates[-1].isoformat(),
        "dates": [item.isoformat() for item in dates],
        "requested": len(selected),
        "staged": len(staged),
        "failed": len(failures),
        "core_created": core_created,
        "core_reused": core_reused,
        "objects": staged,
        "failures": failures,
    }
    if failures:
        raise RuntimeError(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if execution_scoped:
        stage_writer.mark_core_committed(execution_id, stage_results=stage_results)
        previous = os.environ.get("PREVIOUS_STAGE_EXECUTION_ID", "").strip()
        if previous:
            summary["cleanup"] = stage_writer.cleanup_committed_execution(previous)
    return summary


def main() -> None:
    try:
        print(json.dumps(collect_stage(), ensure_ascii=False, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "ingestion-core", "status": "failed", "error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
