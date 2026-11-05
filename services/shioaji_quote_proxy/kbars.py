"""Bounded one-session Shioaji historical one-minute candles (simulation only).

These are actual provider-published one-minute OHLC bars, NOT the intraday
snapshot/quote observations and not a source for ongoing live polling.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
import logging
import re

TAIPEI = timezone(timedelta(hours=8))
LOGGER = logging.getLogger(__name__)
SESSION_FIRST = 9 * 60
SESSION_LAST = 13 * 60 + 30
MAX_RAW = 600


def kbar_timestamp(value: Any) -> datetime | None:
    """SDK ts may be epoch nanoseconds, an aware datetime, or ISO text."""
    if isinstance(value, datetime):
        return value.astimezone(TAIPEI) if value.tzinfo else value.replace(tzinfo=TAIPEI)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if numeric > 1e15:
            numeric /= 1e9  # nanoseconds
        elif numeric > 1e12:
            numeric /= 1e3  # milliseconds
        try:
            # SDK nanoseconds encode Taiwan wall-clock time, not UTC.
            # Convert the epoch components then attach Taipei without +8h.
            return datetime.fromtimestamp(numeric, timezone.utc).replace(tzinfo=TAIPEI)
        except (ValueError, OverflowError, OSError):
            return None
    try:
        decoded = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return decoded.astimezone(TAIPEI) if decoded.tzinfo else decoded.replace(tzinfo=TAIPEI)
    except (ValueError, TypeError):
        return None


def session_kbars(api: Any, symbol: str, trade_day: date, *, now: datetime | None = None) -> dict:
    """Exactly one SDK kbars call for today's one symbol. Never retries."""
    if not (re.fullmatch(r"[0-9A-Z]{4,10}", symbol) or symbol == "TAIEX"):
        raise ValueError("invalid kbar symbol")
    clock = (now or datetime.now(TAIPEI)).astimezone(TAIPEI)
    if trade_day != clock.date():
        raise ValueError("out-of-session kbar date")
    code = "IX0001" if symbol == "TAIEX" else symbol
    contract = api.contracts.get(code)
    if contract is None or str(getattr(contract, "code", code)) != code:
        return {"status": "unavailable", "symbol": symbol, "date": trade_day.isoformat(),
                "source": "shioaji_kbars", "points": []}
    try:
        raw = api.kbars(contract=contract, start=trade_day.isoformat(),
                        end=trade_day.isoformat(), timeout=6000)
    except Exception as error:
        LOGGER.warning("historical one-minute kbars unavailable: %s", type(error).__name__)
        return {"status": "unavailable", "symbol": symbol, "date": trade_day.isoformat(),
                "source": "shioaji_kbars", "points": []}
    timestamps = getattr(raw, "ts", None)
    closes = getattr(raw, "Close", None)
    if timestamps is None or closes is None or len(timestamps) != len(closes) or len(timestamps) > MAX_RAW:
        return {"status": "invalid", "symbol": symbol, "date": trade_day.isoformat(),
                "source": "shioaji_kbars", "points": []}
    by_minute: dict[str, str] = {}
    # Kbars are right-labelled: the timestamp represents the minute END.
    # Exclude the current unfinished bar, non-session, future and stale dates.
    latest_completed = clock.replace(second=0, microsecond=0)
    for stamp, price in zip(timestamps, closes):
        observed = kbar_timestamp(stamp)
        if observed is None or observed.date() != trade_day or observed > latest_completed:
            continue
        # Right-labelled [ts-1m, ts) candle is plotted in its START minute.
        bucket = observed - timedelta(minutes=1)
        minute = bucket.hour * 60 + bucket.minute
        if not SESSION_FIRST <= minute < SESSION_LAST:
            continue
        try:
            value = Decimal(str(price))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if not value.is_finite() or value <= 0 or value > Decimal("10000000"):
            continue
        minute_key = bucket.replace(second=0, microsecond=0).isoformat()
        by_minute[minute_key] = str(value)
    points = [{"date": stamp, "value": by_minute[stamp]}
              for stamp in sorted(by_minute)[:271]]
    return {"status": "available" if points else "missing",
            "symbol": symbol, "date": trade_day.isoformat(),
            "source": "shioaji_kbars",
            "bar_semantics": "one-minute-right-labelled-close",
            "points": points}
