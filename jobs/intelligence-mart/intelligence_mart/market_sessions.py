"""Verified TWSE/TPEx non-trading sessions used for Quant/Risk market windows.

The 2026 scheduled closures are the same dates already approved in
infra/postgres/migrations/029_twse_2026_holiday_overrides.sql.
2026-10-23 is an additional verified typhoon shutdown for BOTH exchanges.
This is a feature-calendar filter only: never rewrite canonical OHLCV or
benchmark source rows. Unverified closures in later years must not be guessed.
"""
from __future__ import annotations

from datetime import date

CLOSED_2026 = frozenset({
    "2026-01-01", "2026-02-12", "2026-02-13",
    "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-19", "2026-02-20", "2026-02-27", "2026-02-28",
    "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06",
    "2026-05-01", "2026-06-19", "2026-09-25", "2026-09-28",
    "2026-10-09", "2026-10-10", "2026-10-23", "2026-10-25",
    "2026-10-26", "2026-12-25",
})


def verified_stock_market_day(value: str) -> bool:
    """Reject only the verified 2026 closures and ordinary weekends.

    A benchmark on a closed market date is not a trading-day observation.
    This must not create stock prices, shift the PIT cutoff, or relax the
    >=100 symbol same-market denominator. Source rows remain unmodified.
    """
    try:
        day = date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return False
    return day.weekday() < 5 and day.isoformat() not in CLOSED_2026
