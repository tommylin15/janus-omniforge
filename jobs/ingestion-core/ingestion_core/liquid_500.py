"""Fail-closed weekly liquidity ranking over persisted Core market batches."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Any


def rank_week(
    rows: Iterable[Mapping[str, Any]], trading_days: Iterable[date],
    approved_stocks: set[str],
) -> tuple[dict[str, Any], ...]:
    """Return exactly 500 ranked stocks, or raise without publishing a new version."""
    days = tuple(sorted(set(trading_days)))
    if not days:
        raise ValueError("trading week has no days")
    expected = {("TWSE", day.isoformat()) for day in days}
    seen_batches: set[tuple[str, str]] = set()
    batch_sizes: Counter[tuple[str, str]] = Counter()
    seen_rows: set[tuple[str, str, str]] = set()
    totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"volume_shares": 0, "turnover_twd": Decimal(0)})
    for row in rows:
        market = str(row["market"])
        if market != "TWSE":
            continue
        day = str(row["trade_date"])[:10]
        if (market, day) not in expected:
            raise ValueError("Core market volume is outside requested week")
        seen_batches.add((market, day))
        batch_sizes[(market, day)] += 1
        symbol = str(row["symbol"])
        key = (market, day, symbol)
        if key in seen_rows:
            raise ValueError("Core market volume has duplicate stock day")
        seen_rows.add(key)
        if symbol not in approved_stocks:
            continue
        volume = int(row["volume_shares"])
        turnover = Decimal(str(row["turnover_twd"]))
        if volume < 0 or turnover < 0:
            raise ValueError("Core market volume has negative value")
        totals[symbol]["volume_shares"] += volume
        totals[symbol]["turnover_twd"] += turnover
    if seen_batches != expected:
        raise ValueError("Core TWSE market volume is missing a trading day")
    if any(batch_sizes[batch] < 500 for batch in expected):
        raise ValueError("Core market volume has an incomplete market batch")
    if len(totals) < 500:
        raise ValueError("fewer than 500 approved stocks have weekly volume")
    ordered = sorted(totals.items(), key=lambda item: (-item[1]["volume_shares"],
                                                        -item[1]["turnover_twd"], item[0]))[:500]
    return tuple({"rank": rank, "symbol": symbol, **values}
                 for rank, (symbol, values) in enumerate(ordered, 1))
