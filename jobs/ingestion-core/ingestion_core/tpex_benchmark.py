"""SEQ-08 official TPEx monthly PRICE index, bounded one-time Core repair.

Never use TWSE/TAIEX as OTC benchmark; price index only (not total-return
or sector). No equity OHLCV requests, guessed sessions, PG/Owner writes, or
model training. Source response is staged before a versioned Core write.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
import re
from urllib.parse import urlencode
from uuid import uuid4

from packages.provenance import Provenance
from .control import ExecutionStatus
from .data_supplement import _fetch
from .first_batch import _iso_date
from .stage import GcsObjectStore, StageWriter

URL = "https://www.tpex.org.tw/www/zh-tw/indexInfo/inx"
SOURCE = "tpex"
BENCHMARK = "TPEx"
FIRST = date(2026, 9, 1)
LAST = date(2026, 10, 22)


def endpoint(month: str) -> str:
    if not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", month):
        raise ValueError("tpex_benchmark_invalid_month")
    return URL + "?" + urlencode({"date": month.replace("-", "/") + "/01", "response": "json"})


def _number(value: object) -> float:
    try:
        result = float(re.sub(r"<[^>]*>", "", str(value)).replace(",", "").strip())
    except ValueError as error:
        raise ValueError("tpex_benchmark_invalid_price") from error
    if not math.isfinite(result) or not 0 < result < 100000000:
        raise ValueError("tpex_benchmark_invalid_price")
    return result


def _table_rows(document: dict):
    items = document.get("tables")
    if not isinstance(items, list):
        items = [document]
    for table in items:
        if not isinstance(table, dict):
            continue
        fields = table.get("fields") or table.get("columns")
        raw = table.get("data") or table.get("aaData") or table.get("rows")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict):
                yield item
            elif isinstance(item, list) and isinstance(fields, list) and len(item) == len(fields):
                yield dict(zip(fields, item))


def parse_tpex_month(raw: bytes, month: str, *, through: date = LAST) -> list[dict]:
    """Pure approved price-index parser; closed-session values are never made up."""
    document = json.loads(raw)
    if not isinstance(document, dict) or str(document.get("stat", "OK")).upper() not in ("OK", "SUCCESS"):
        raise ValueError("tpex_benchmark_source_status_invalid")
    rows = {}
    for item in _table_rows(document):
        names = {re.sub(r"\s+", "", str(key)): value for key, value in item.items()}
        raw_day = next((names[key] for key in ("日期", "交易日期", "資料日期") if key in names), None)
        if raw_day is None:
            continue
        day = _iso_date(raw_day)
        if not day.startswith(month):
            raise ValueError("tpex_benchmark_month_mismatch")
        if day > through.isoformat():
            continue
        # Reject weekend responses; do not invent missed holidays.
        if date.fromisoformat(day).weekday() >= 5:
            raise ValueError("tpex_benchmark_weekend_source_row")
        close_raw = next((names[key] for key in ("收市", "收盤", "收盤指數") if key in names), None)
        if close_raw is None:
            raise ValueError("tpex_benchmark_price_index_missing")
        close = _number(close_raw)
        high = names.get("最高", names.get("最高價"))
        low = names.get("最低", names.get("最低價"))
        open_ = names.get("開市", names.get("開盤"))
        if all(value is not None for value in (open_, high, low)):
            o, h, l = (_number(value) for value in (open_, high, low))
            if not l <= o <= h or not l <= close <= h:
                raise ValueError("tpex_benchmark_ohlc_invalid")
        row = {"benchmark_id": BENCHMARK, "trade_date": day,
               "close": str(close), "return_percent": None, "index_kind": "price"}
        if day in rows and rows[day] != row:
            raise ValueError("tpex_benchmark_conflicting_date")
        rows[day] = row
    if not rows:
        raise ValueError("tpex_benchmark_official_month_empty")
    return [rows[day] for day in sorted(rows)]


def run_bounded_tpex_benchmark() -> dict:
    """One authorized existing Dev ingestion execution; never refetch whole stocks."""
    from .__main__ import (_control_plane, _iceberg_core, _current_core_fences,
                           _core_ready_event, TAIPEI)
    if (os.getenv("GCP_PROJECT_ID") != "gen-lang-client-0593591102"
            or os.getenv("CORE_BUCKET") != "gen-lang-client-0593591102-dev-core"
            or os.getenv("STAGE_BUCKET") != "gen-lang-client-0593591102-dev-stage"
            or os.getenv("SEQ08_TPEX_BENCHMARK_ONLY") != "true"
            or (os.getenv("BACKFILL_START_DATE"), os.getenv("BACKFILL_END_DATE"))
               != (FIRST.isoformat(), LAST.isoformat())):
        raise ValueError("seq08_tpex_benchmark_scope_denied")
    now = datetime.now(TAIPEI).date()
    if not LAST < now or (LAST - FIRST).days > 65:
        raise ValueError("seq08_tpex_benchmark_not_completed_or_unbounded")
    execution = None
    with _control_plane() as control:
        if not control.source_is_approved(SOURCE):
            raise ValueError("seq08_tpex_benchmark_source_not_approved")
        pool = control.full_market_snapshot()
        symbols = tuple(sorted(str(item["symbol"]) for item in pool["items"]))
        if pool.get("status") not in ("available", None) or not symbols or {
                str(row.get("market")).upper() for row in pool["items"]} != {"TWSE", "TPEX"}:
            raise ValueError("seq08_tpex_benchmark_current_roster_unavailable")
        execution = control.enqueue_collection("first-batch",
            request_options={"operation": "seq08-tpex-benchmark-only",
                             "first": FIRST.isoformat(), "last": LAST.isoformat()})
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        core = None
        try:
            writer = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
            core = _iceberg_core(os.environ["CORE_BUCKET"])
            months = ("2026-09", "2026-10")
            counts, staged = {}, []
            for month in months:
                url = endpoint(month)
                raw, _ = _fetch(url)
                rows = parse_tpex_month(raw, month)
                received = datetime.now(timezone.utc)
                proof = Provenance(str(uuid4()), SOURCE, url, "benchmark",
                    received, None, received, "sha256:" + sha256(raw).hexdigest(),
                    False, quality_details={"request_identity": {"month": month,
                        "scope": "official_tpex_price_index_only"}})
                stage = writer.write_raw(payload=raw, media_type="application/json",
                    extension="json", execution_id=execution.execution_id,
                    provenance=proof, execution_scoped=True)
                staged.append(stage)
                original = [{**row, "source_id": SOURCE,
                    "observed_at": row["trade_date"] + "T00:00:00Z",
                    "provenance_id": stage.idempotency_key} for row in rows]
                result = core.write(dataset_id="benchmark", rows=original,
                    execution_id=execution.execution_id,
                    provenance_id=stage.idempotency_key,
                    source_id=SOURCE, partition_date=date.fromisoformat(month + "-01"))
                counts[month] = {"official_sessions": len(rows),
                    "inserted": result.inserted, "updated": result.updated,
                    "reused": result.reused}
            # One successful, real Iceberg benchmark write makes a new
            # composite snapshot ID. Existing OHLCV/financial tables unchanged.
            fences = _current_core_fences(core)
            ready = _core_ready_event(core_bucket=os.environ["CORE_BUCKET"],
                execution_id=execution.execution_id, config_id="first-batch",
                analysis_as_of=now.isoformat(), iceberg_tables=fences,
                symbols=symbols, market="TWSE,TPEX")
            if not ready or "core.benchmark_v1" not in fences:
                raise ValueError("seq08_tpex_benchmark_core_fence_missing")
            writer.mark_core_committed(execution.execution_id, stage_results=staged)
            finished, _ = control.complete_collection(execution.execution_id, ready, partial=False)
            if getattr(finished.status, "value", "") != "succeeded":
                raise ValueError("seq08_tpex_benchmark_collection_not_terminal")
            return {"component": "seq08_tpex_benchmark", "status": "succeeded",
                "execution_id": execution.execution_id, "analysis_as_of": now.isoformat(),
                "core_snapshot_id": ready["coreSnapshotId"],
                "core_snapshot_uri": ready["coreSnapshotUri"],
                "official_price_index": BENCHMARK, "months": counts,
                "source_id": SOURCE, "source_url": URL,
                "market_stock_ohlcv_writes": 0, "owner_mutations": 0}
        except Exception:
            if execution is not None:
                control.transition_execution(execution.execution_id,
                    ExecutionStatus.FAILED, error_code="SEQ08_TPEX_BENCHMARK_FAILED")
            raise
        finally:
            if core is not None:
                core.close()


if __name__ == "__main__":
    print(json.dumps(run_bounded_tpex_benchmark(), ensure_ascii=False,
                     sort_keys=True), flush=True)
