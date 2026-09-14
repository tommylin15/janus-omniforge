"""Bounded 5/20/60 trading-day Pilot outcome calculation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any


def _date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _number(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise InvalidOperation
    return result


def _provenance(candidate: dict[str, Any], horizon: int, rows: list[dict[str, Any]], status: str) -> str:
    value = {
        "analysis_execution_id": str(candidate["analysis_execution_id"]),
        "horizon_days": horizon,
        "membership_snapshot_hash": candidate["membership_snapshot_hash"],
        "rows": sorted({str(row.get("provenance_id") or row.get("__snapshot_id") or "missing") for row in rows}),
        "status": status,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def evaluate_outcome(candidate: dict[str, Any], ohlcv: list[dict[str, Any]],
                     benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate one horizon without calendar-day substitution or future leakage."""
    as_of, symbol = _date(candidate["analysis_as_of"]), candidate["scope_id"]
    prices = sorted((row for row in ohlcv if row.get("symbol") == symbol), key=lambda row: _date(row["trade_date"]))
    before = [row for row in prices if _date(row["trade_date"]) <= as_of]
    after = [row for row in prices if _date(row["trade_date"]) > as_of]
    horizon = int(candidate["horizon_days"])
    common = {**candidate, "status": "pending", "exclusion_reason": None,
              "benchmark_id": "TAIEX", "entry_date": None, "outcome_date": None,
              "return_ratio": None, "benchmark_return_ratio": None,
              "relative_return_ratio": None, "mfe_ratio": None, "mae_ratio": None,
              "price_snapshot_id": None, "benchmark_snapshot_id": None}
    if not before or len(after) < horizon:
        common["provenance_id"] = _provenance(candidate, horizon, before[-1:] + after, "pending")
        return common
    entry, window, target = before[-1], after[:horizon], after[horizon - 1]
    target_date = _date(target["trade_date"])
    benchmark_rows = [row for row in benchmarks if row.get("benchmark_id") == "TAIEX"]
    benchmark_entry = [row for row in benchmark_rows if _date(row["trade_date"]) <= as_of]
    benchmark_target = [row for row in benchmark_rows if _date(row["trade_date"]) == target_date]
    evidence = [entry, *window, *benchmark_entry[-1:], *benchmark_target[-1:]]
    try:
        if not benchmark_entry or not benchmark_target:
            raise LookupError("missing_benchmark")
        entry_close, target_close = _number(entry["close"]), _number(target["close"])
        benchmark_start, benchmark_end = _number(benchmark_entry[-1]["close"]), _number(benchmark_target[-1]["close"])
        highs = [_number(row.get("high") or row["close"]) for row in window]
        lows = [_number(row.get("low") or row["close"]) for row in window]
    except (KeyError, InvalidOperation, ValueError):
        reason = "invalid_price"
    except LookupError as error:
        reason = str(error)
    else:
        result = target_close / entry_close - 1
        benchmark_result = benchmark_end / benchmark_start - 1
        return {**common, "status": "valid", "entry_date": _date(entry["trade_date"]),
                "outcome_date": target_date, "return_ratio": result,
                "benchmark_return_ratio": benchmark_result,
                "relative_return_ratio": result - benchmark_result,
                "mfe_ratio": max(highs) / entry_close - 1,
                "mae_ratio": min(lows) / entry_close - 1,
                "price_snapshot_id": entry.get("__snapshot_id"),
                "benchmark_snapshot_id": benchmark_entry[-1].get("__snapshot_id"),
                "provenance_id": _provenance(candidate, horizon, evidence, "valid")}
    return {**common, "status": "excluded", "exclusion_reason": reason,
            "provenance_id": _provenance(candidate, horizon, evidence, reason)}


def collect_pilot_outcomes(publication: Any, datasets: dict[str, list[dict[str, Any]]]) -> int:
    symbols = sorted({str(row.get("symbol")) for row in datasets.get("ohlcv", []) if row.get("symbol")})
    if not symbols:
        return 0
    rows = [evaluate_outcome(candidate, datasets.get("ohlcv", []), datasets.get("benchmark", []))
            for candidate in publication.pending_outcomes(symbols)]
    publication.save_outcomes(rows)
    return len(rows)
