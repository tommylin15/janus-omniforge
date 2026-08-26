"""One-shot Cloud Run Job entrypoint for raw Stage collection."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import os
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

from .adapters import CollectionRequest
from .first_batch import dataset_adapters, effective_trading_day, stage_raw_response
from .core import IncrementalCoreWriter
from .stage import GcsObjectStore


TAIPEI = ZoneInfo("Asia/Taipei")


def _holidays(value: str) -> set[date]:
    return {date.fromisoformat(item.strip()) for item in value.split(",") if item.strip()}


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
    as_of = effective_trading_day(local_now.date() - timedelta(days=1), holidays=_holidays(os.environ.get("MARKET_HOLIDAYS", "")))
    execution_id = str(uuid4())
    store = GcsObjectStore(bucket)
    core = IncrementalCoreWriter(GcsObjectStore(core_bucket))
    staged: list[str] = []
    core_created = core_reused = 0
    failures: list[dict[str, str]] = []

    for key in selected:
        adapter = configured[key]
        request = CollectionRequest(
            execution_id=execution_id,
            trace_id=str(uuid4()),
            source_id=adapter.source_id,
            dataset_id=adapter.dataset_id,
            market="TPEX" if adapter.source_id in {"tpex", "tpex-benchmark"} else "TWSE",
            symbols=(),
            window_start=as_of,
            window_end=as_of,
            timeout_seconds=30,
        )
        try:
            response = adapter.fetch(request)
            if not response.rows:
                raise ValueError("source returned no normalized rows")
            result, _ = stage_raw_response(response, request, bucket=bucket, store=store)
            staged.append(result.object_name)
            committed = core.write(dataset_id=adapter.dataset_id, rows=[dict(row) for row in response.rows],
                                   execution_id=execution_id, provenance_id=result.idempotency_key,
                                   source_id=adapter.source_id, partition_date=as_of)
            core_created += committed.created
            core_reused += committed.reused
        except Exception as error:
            failures.append({"dataset": key, "error": type(error).__name__})

    summary: dict[str, object] = {
        "component": "ingestion-core",
        "execution_id": execution_id,
        "as_of": as_of.isoformat(),
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
    return summary


def main() -> None:
    try:
        print(json.dumps(collect_stage(), ensure_ascii=False, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "ingestion-core", "status": "failed", "error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
