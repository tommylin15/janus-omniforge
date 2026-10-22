"""Risk prospective immutable prediction -> 20 *market-session* label reconciliation.

Offline pure evaluation invoked by the existing monthly workflow/operator. No
new scheduler, private owner fields, arbitrary external fetch or model refit.
Original shadow predictions are never rewritten. Explicit exchange calendars
and source bars are required; calendar dates/weekdays do not count as sessions.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def reconcile(shadow: dict, bars: list[dict], sessions: dict[str, list[str]],
              evaluation_as_of: str) -> dict:
    """Return a versioned reconciliation receipt; no GCS write or publication."""
    date.fromisoformat(evaluation_as_of)
    if (shadow.get("status") != "SHADOW_UNVALIDATED"
            or shadow.get("publication_allowed") is not False
            or not isinstance(shadow.get("rows"), list)
            or not shadow.get("model_sha256")
            or not shadow.get("source_manifest_hash")):
        raise ValueError("untrusted Risk prediction envelope")
    as_of = str(shadow["analysis_as_of"])
    date.fromisoformat(as_of)
    if evaluation_as_of < as_of:
        raise ValueError("evaluation before frozen prediction cutoff")
    grid = {}
    for market in ("twse", "tpex"):
        listed = sessions.get(market)
        if not listed or sorted(set(listed)) != listed:
            raise ValueError("market exchange sessions not ordered/unique")
        for day in listed:
            date.fromisoformat(day)
        grid[market] = listed
    index = {}
    for bar in bars:
        sym, market, day = str(bar["symbol"]), str(bar["market"]).lower(), str(bar["trade_date"])[:10]
        if market not in grid or day > evaluation_as_of or day not in grid[market]:
            raise ValueError("source bar beyond cutoff or outside evidenced sessions")
        key = (market, sym, day)
        if key in index:
            raise ValueError("ambiguous revised OHLCV; explicit revision gate required")
        index[key] = bar
    outcomes = []
    seen = set()
    for pred in shadow["rows"]:
        sym, market = str(pred["symbol"]), str(pred["market"]).lower()
        key = (market, sym)
        if key in seen:
            raise ValueError("duplicate immutable predicted symbol")
        seen.add(key)
        if pred.get("analysis_as_of") != as_of or market not in grid:
            raise ValueError("prediction identity or market mismatch")
        forecast = float(pred["future_20d_volatility_annualized"])
        rolling = float(pred["recent_20d_volatility_annualized"])
        if not all(math.isfinite(v) and v >= 0 for v in (forecast, rolling)):
            raise ValueError("invalid immutable forecast")
        days = grid[market]
        if as_of not in days:
            raise ValueError("signal date absent from verified market calendar")
        i = days.index(as_of)
        row = {"symbol": sym, "market": market, "signal_date": as_of,
               "model_sha256": shadow["model_sha256"], "status": "PENDING"}
        if i + 20 >= len(days) or days[i + 20] > evaluation_as_of:
            row["reason"] = "TWENTY_MARKET_SESSIONS_NOT_MATURE"
            outcomes.append(row)
            continue
        window = [index.get((market, sym, day)) for day in days[i:i + 21]]
        if any(item is None for item in window):
            row.update(status="PENDING", reason="MATURED_SESSIONS_MISSING_SOURCE_BARS")
            outcomes.append(row)
            continue
        if any(item.get("is_corporate_action") is True
               or str(item.get("source_authorization", "")).lower() in
                  {"blocked", "denied", "unauthorized"} for item in window):
            row.update(status="EXCLUDED", reason="COMPANY_ACTION_OR_DENIED_SOURCE")
            outcomes.append(row)
            continue
        bases = {str(item.get("adjustment_basis")) for item in window
                 if item.get("adjustment_basis") is not None}
        if len(bases) > 1:
            row.update(status="EXCLUDED", reason="INCONSISTENT_PRICE_ADJUSTMENT_BASIS")
            outcomes.append(row)
            continue
        prices = [float(item["close"]) for item in window]
        if any(not math.isfinite(p) or p <= 0 for p in prices):
            row.update(status="EXCLUDED", reason="INVALID_EVIDENCED_PRICE")
            outcomes.append(row)
            continue
        realized = math.sqrt(252 / 20 * sum(
            math.log(prices[j] / prices[j - 1]) ** 2 for j in range(1, 21)))
        row.update(status="MATURED", label_matures_on=days[i + 20],
                   realized_20d_volatility_annualized=realized,
                   xgboost_absolute_error=abs(forecast - realized),
                   rolling20_absolute_error=abs(rolling - realized),
                   xgboost_squared_error=(forecast - realized) ** 2,
                   rolling20_squared_error=(rolling - realized) ** 2)
        outcomes.append(row)
    complete = [x for x in outcomes if x["status"] == "MATURED"]

    def scores(group):
        if not group:
            return {"matured_symbols": 0, "unique_signal_dates": 0, "mae": None,
                    "rmse": None, "rolling20_mae": None, "rolling20_rmse": None}
        n = len(group)
        return {"matured_symbols": n,
                "unique_signal_dates": len({x["signal_date"] for x in group}),
                "mae": sum(x["xgboost_absolute_error"] for x in group) / n,
                "rmse": math.sqrt(sum(x["xgboost_squared_error"] for x in group) / n),
                "rolling20_mae": sum(x["rolling20_absolute_error"] for x in group) / n,
                "rolling20_rmse": math.sqrt(sum(x["rolling20_squared_error"] for x in group) / n)}
    result = {
        "schema_version": "risk_matured_outcome_v1",
        "source_shadow_sha256": sha256(_canonical(shadow)).hexdigest(),
        "analysis_as_of": as_of, "evaluation_as_of": evaluation_as_of,
        "model_sha256": shadow["model_sha256"], "source_manifest_hash": shadow["source_manifest_hash"],
        "status_counts": {state: sum(x["status"] == state for x in outcomes)
                          for state in ("MATURED", "PENDING", "EXCLUDED")},
        "overall": scores(complete),
        "by_market": {market: scores([x for x in complete if x["market"] == market])
                      for market in ("twse", "tpex")},
        "by_signal_month": {as_of[:7]: scores(complete)},
        "outcomes": outcomes, "publication_allowed": False,
    }
    result["receipt_sha256"] = sha256(_canonical(result)).hexdigest()
    return result


def write_once(receipt: dict, path: str | Path) -> None:
    """Creation-only local receipt; GCS upload must likewise use no-clobber."""
    data = _canonical(receipt) + b"\n"
    with open(path, "xb") as file:
        file.write(data)
