"""Bounded official daily archives, monthly Core commits on existing dev resources."""
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from urllib.parse import urlencode
from uuid import uuid4

from packages.provenance import Provenance
from .adapters import CollectionRequest
from .control import ExecutionStatus
from .data_supplement import _fetch
from .dq import ALLOWED_COLUMNS, validate_ohlcv
from .first_batch import normalise_benchmark
from .sources import twse_market_volume_adapter
from .stage import GcsObjectStore, StageWriter


def archive_months(first, last):
    if first > last or (last-first).days > 240:
        raise ValueError("market screening history is bounded to 241 calendar days")
    return [divmod(i, 12) for i in range(first.year*12+first.month-1, last.year*12+last.month)]


def run_market_history():
    from .__main__ import _control_plane, _iceberg_core, _current_core_fences, _core_ready_event, TAIPEI
    first, last = (date.fromisoformat(os.environ[k]) for k in ("BACKFILL_START_DATE", "BACKFILL_END_DATE"))
    today = datetime.now(TAIPEI).date()
    if last >= today:
        raise ValueError("only completed historical dates may be filled")
    months = archive_months(first, last)
    core = None
    execution = None
    summary = {"operation": "market-history", "core_created": 0, "core_updated": 0, "core_reused": 0,
               "failures": [], "months": [], "tolerance": .1, "auto_fail": False}
    with _control_plane() as control:
        try:
            if not all(control.source_is_approved(s) for s in ("twse", "taiex")):
                raise ValueError("official market history sources are not approved")
            pool = control.liquid_500_snapshot()
            symbols = tuple(sorted(r["symbol"] for r in pool["items"]))
            if len(symbols) != 500 or any(r["market"] != "TWSE" for r in pool["items"]):
                raise ValueError("verified TWSE liquid-500 membership is required")
            targets = set(symbols) | set(control.portfolio_coverage_symbols())
            execution = control.enqueue_collection("first-batch", request_options={"operation": "market-history"})
            control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
            summary["execution_id"] = execution.execution_id
            core = _iceberg_core(os.environ["CORE_BUCKET"])
            writer = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
            def stage(raw, url, source, dataset, identity):
                received = datetime.now(timezone.utc)
                p = Provenance(str(uuid4()), source, url, dataset, received, None, received,
                    "sha256:"+sha256(raw).hexdigest(), False, quality_details={"request_identity": identity})
                r = writer.write_raw(payload=raw, media_type="application/json", extension="json",
                    execution_id=execution.execution_id, provenance=p, execution_scoped=True)
                return r
            all_staged = []
            for year, zero_month in reversed(months):
                month = zero_month+1
                period = f"{year}-{month:02d}"
                staged, prices = [], []
                try:
                    url = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?"+urlencode(
                        {"date": f"{year}{month:02d}01", "response": "json"})
                    raw, _ = _fetch(url)
                    entry = stage(raw, url, "taiex", "benchmark", {"month": period})
                    staged.append(entry)
                    document = json.loads(raw)
                    benchmark = [dict(r, source_id="taiex", observed_at=r["trade_date"]+"T00:00:00Z",
                        provenance_id=entry.idempotency_key) for r in normalise_benchmark(
                        dict(zip(document["fields"], cells)) for cells in document.get("data", []))
                        if first.isoformat() <= r["trade_date"] <= last.isoformat()]
                    if not benchmark:
                        raise ValueError("official trading calendar is empty")
                    counts = {}
                    for index in benchmark:
                        day = date.fromisoformat(index["trade_date"])
                        adapter = twse_market_volume_adapter()
                        request = CollectionRequest(execution.execution_id, execution.trace_id, "twse", "market-volume",
                            "TWSE", (), day, day, 30)
                        url = adapter.url_builder(request)
                        try:
                            raw, _ = _fetch(url)
                            entry = stage(raw, url, "twse", "ohlcv", {"date": day.isoformat()})
                            staged.append(entry)
                            adapter.transport = lambda _: raw
                            response = adapter.fetch(request)
                            checked = validate_ohlcv([dict({k:v for k,v in r.items() if k in ALLOWED_COLUMNS}, change_percent=None)
                                for r in response.rows if r["symbol"] in targets], analysis_as_of=day)
                            accepted = [r for r in checked.accepted if r.get("close") is not None]
                            prices.extend(dict(r, provenance_id=entry.idempotency_key) for r in accepted)
                            counts[day.isoformat()] = len({r["symbol"] for r in accepted} & set(symbols))
                        except Exception as error:
                            counts[day.isoformat()] = 0
                            summary["failures"].append({"date": day.isoformat(), "error": type(error).__name__})
                    for dataset, rows, source in (("ohlcv", prices, "twse"), ("benchmark", benchmark, "taiex")):
                        if rows:
                            result = core.write(dataset_id=dataset, rows=rows, execution_id=execution.execution_id,
                                provenance_id=rows[0]["provenance_id"], source_id=source, partition_date=first)
                            for field, value in (("created", result.inserted), ("updated", result.updated), ("reused", result.reused)):
                                summary["core_"+field] += value
                    all_staged.extend(staged)
                    missing = 1-sum(counts.values())/(500*len(benchmark))
                    checkpoint = {"month": period, "trading_days": len(benchmark), "received_rows": len(prices),
                        "missing_ratio": missing, "status": "accepted" if missing <= .1 else "discussion_required"}
                    summary["months"].append(checkpoint)
                    print(json.dumps({"operation": "market-history-progress", "execution_id": execution.execution_id, **checkpoint}), flush=True)
                    if missing > .1:
                        break  # Preserve valid data, discuss quality before filling further months.
                except Exception as error:
                    summary["failures"].append({"month": period, "error": type(error).__name__})
                    break
            if not summary["failures"]:
                writer.mark_core_committed(execution.execution_id, stage_results=all_staged)
            ready = _core_ready_event(core_bucket=os.environ["CORE_BUCKET"], execution_id=execution.execution_id,
                config_id="first-batch", analysis_as_of=today.isoformat(), iceberg_tables=_current_core_fences(core),
                symbols=symbols, market="TWSE")
            completed, analysis = control.complete_collection(execution.execution_id, ready, partial=bool(summary["failures"])
                or len(summary["months"]) != len(months) or any(r["status"] != "accepted" for r in summary["months"]))
            summary.update(status=completed.status.value, ready_event=ready,
                analysis_execution_id=analysis.execution_id if analysis else None)
            return summary
        except Exception:
            if execution:
                control.transition_execution(execution.execution_id, ExecutionStatus.FAILED, error_code="MARKET_HISTORY_FAILED")
            raise
        finally:
            if core is not None:
                core.close()
