"""Fail-closed weekly liquidity ranking over persisted Core market batches."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
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


def rotate_from_core(catalog: Any, control: Any, *, week_start: date,
                     trading_days: tuple[date, ...], effective_from: datetime) -> int:
    """Publish one future-effective version from the exact persisted source week."""
    if not trading_days or min(trading_days) < week_start or max(trading_days) >= week_start + timedelta(days=7):
        raise ValueError("trading days are outside requested week")
    volume_table = catalog.load_table("core.market_volume_v1")
    profile_table = catalog.load_table("core.stock_profile_v1")
    from pyiceberg.expressions import And, GreaterThanOrEqual, LessThanOrEqual
    end = week_start + timedelta(days=6)
    market_rows = volume_table.scan(
        row_filter=And(GreaterThanOrEqual("trade_date", week_start), LessThanOrEqual("trade_date", end)),
        selected_fields=("symbol", "market", "trade_date", "volume_shares", "turnover_twd"),
        limit=20000,
    ).to_arrow().to_pylist()
    if len(market_rows) >= 20000:
        raise ValueError("Core market volume scan reached its row limit")
    profile_rows = profile_table.scan(
        row_filter=And(GreaterThanOrEqual("observed_date", week_start),
                       LessThanOrEqual("observed_date", effective_from.date())),
        selected_fields=("symbol", "market", "observed_date"), limit=20000,
    ).to_arrow().to_pylist()
    if len(profile_rows) >= 20000:
        raise ValueError("Core stock profile scan reached its row limit")
    latest_profile: dict[str, date] = {}
    for row in profile_rows:
        value = row["observed_date"]
        day = value.date() if isinstance(value, datetime) else value
        if row["market"] == "TWSE":
            latest_profile["TWSE"] = max(latest_profile.get("TWSE", date.min), day)
    if "TWSE" not in latest_profile:
        raise ValueError("official TWSE company profile is required")
    official: dict[str, str] = {}
    for row in profile_rows:
        if row["market"] != "TWSE":
            continue
        observed = row["observed_date"]
        day = observed.date() if isinstance(observed, datetime) else observed
        if day != latest_profile[row["market"]]:
            continue
        symbol, market = str(row["symbol"]), str(row["market"])
        if symbol in official and official[symbol] != market:
            raise ValueError("official company profiles disagree on stock market")
        official[symbol] = market
    if any(row["market"] == "TWSE" and row["symbol"] in official
           and official[row["symbol"]] != row["market"] for row in market_rows):
        raise ValueError("Core market volume disagrees with official stock market")
    with control.connection.cursor() as cur:
        cur.execute("""SELECT symbol,market,enabled,listing_status FROM control.stock_master
                       WHERE symbol=ANY(%s)""", (list(official),))
        master = {row[0]: row[1:] for row in cur.fetchall()}
    if set(master) != set(official) or any(master[symbol][0] != market
                                          for symbol, market in official.items()):
        raise ValueError("stock master cannot classify official company profiles")
    approved = {symbol for symbol, (_, enabled, status) in master.items()
                if enabled and status == "listed"}
    ranked = rank_week(market_rows, trading_days, approved)
    snapshots = {"market": "TWSE", "trading_days": [day.isoformat() for day in trading_days],
                 "market_volume_snapshot": volume_table.current_snapshot().snapshot_id,
                 "stock_profile_snapshot": profile_table.current_snapshot().snapshot_id}
    return control.publish_liquid_500(ranked, week_start=week_start,
                                      effective_from=effective_from, reason="weekly_volume_rank_twse",
                                      actor="scheduled_ingestion", source_snapshot=snapshots)
