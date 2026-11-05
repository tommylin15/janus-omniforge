"""Read-only historical portfolio valuation from actual Owner Mart checkpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import json
from typing import Any

from packages.etf_catalog import looks_like_etf_code


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (TypeError, ValueError, InvalidOperation):
        return None


def build_portfolio_value_history(
    snapshots: list[dict[str, Any]], *, start: date, end: date,
    truncated: bool = False,
) -> dict[str, Any]:
    """Project one genuine saved valuation per day, never backfill from today's quote."""
    chosen: dict[str, tuple[int, str, dict[str, Any]]] = {}
    for snapshot in snapshots:
        day = str(snapshot.get("valuation_date") or "")[:10]
        try:
            valued = date.fromisoformat(day)
        except ValueError:
            continue
        if not start <= valued <= end:
            continue
        raw = snapshot.get("payload")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("positions"), list):
            continue
        try:
            version = int(snapshot.get("ledger_version") or payload.get("ledger_version") or 0)
        except (ValueError, TypeError):
            continue
        order = (version, str(snapshot.get("snapshot_id") or ""))
        previous = chosen.get(day)
        if previous is None or order > (previous[0], previous[1]):
            chosen[day] = (version, order[1], payload)

    points = []
    for day, (version, _, payload) in sorted(chosen.items()):
        positions: list[dict[str, Any]] = []
        market = Decimal("0")
        cost = Decimal("0")
        partial = False
        other_currency = False
        for original in payload["positions"]:
            if not isinstance(original, dict):
                partial = True
                continue
            if str(original.get("currency") or "") != "TWD":
                other_currency = True
                continue
            symbol = str(original.get("symbol") or "").strip().upper()
            shares = _decimal(original.get("shares"))
            average_cost = _decimal(original.get("average_cost"))
            raw_value = _decimal(original.get("market_value"))
            valid_cost = shares is not None and shares > 0 and average_cost is not None and average_cost >= 0
            valid_price = (original.get("price_status") == "available"
                           and str(original.get("price_date") or "")[:10] == day
                           and raw_value is not None and raw_value >= 0)
            if not symbol or not valid_cost:
                partial = True
                continue
            holding_cost = shares * average_cost
            cost += holding_cost
            if not valid_price:
                partial = True
            else:
                market += raw_value
            positions.append({
                "symbol": symbol,
                "name": str(original.get("stock_name") or symbol)[:80],
                "instrument_kind": "ETF" if looks_like_etf_code(symbol) else "EQUITY",
                "market_value": str(raw_value) if valid_price else None,
                "cost_basis": str(holding_cost),
                "status": "available" if valid_price else "missing_price",
            })
        points.append({
            "date": day, "ledger_version": version, "currency": "TWD",
            "market_value": None if partial else str(market),
            "cost_basis": str(cost),
            "status": "partial" if partial else "available",
            "other_currency_excluded": other_currency,
            "positions": positions,
        })
    valid_count = sum(point["status"] == "available" for point in points)
    return {
        "currency": "TWD", "points": points, "truncated": truncated,
        "status": "partial" if truncated or any(p["status"] == "partial" for p in points)
                  else "available" if valid_count >= 2 else "insufficient_history",
        "coverage": "TWD_only", "source": "private_workspace_snapshots",
        "from": start.isoformat(), "through": end.isoformat(),
    }
