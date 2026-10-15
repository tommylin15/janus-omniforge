"""Owner-demand TPEx official EOD snapshot; never substitutes a live execution.

Open government data TPEx OpenAPI latest daily close. This adapter does not
write canonical Core/Iceberg or infer trade executions. Strict published price,
trade-date, and source checks before persisting a read-only latest quote cache.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from threading import Lock
from time import monotonic
from urllib.request import Request, urlopen

from .intraday_quotes import TAIPEI

TPEX_OFFICIAL_EOD_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
SOURCE = "tpex_openapi_eod"
CLOSE_TIME = time(13, 30)
_CACHE_TTL = 600
_FAILURE_RETRY_TTL = 60  # Bound requests after transient 200/HTML, timeout or JSON failure.
_MAX_PAYLOAD = 12_000_000


def _official_day(value: object) -> date | None:
    raw = str(value or "").strip().replace("/", "").replace("-", "")
    try:
        if len(raw) == 7 and raw.isdigit():
            year, month, day = int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7])
        elif len(raw) == 8 and raw.isdigit():
            year, month, day = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
        else:
            return None
        return date(year, month, day)
    except ValueError:
        return None


def parse_tpex_daily_quotes(rows: object, symbols: set[str], now: datetime) -> dict[str, dict]:
    """Fail closed on a mismatched date/price/symbol; never use an old dataset as live."""
    if not isinstance(rows, list) or len(rows) > 25000:
        return {}
    wanted = set(symbols)
    result = {}
    local = now.astimezone(TAIPEI)
    today = local.date()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("SecuritiesCompanyCode") or
                     raw.get("SecuritiesCode") or raw.get("Code") or "").strip()
        if symbol not in wanted:
            continue
        day = _official_day(raw.get("Date") or raw.get("TradeDate"))
        if day is None or day > today or (today - day).days > 7:
            continue
        if day == today and local.time() < time(14, 30):
            continue
        try:
            value = Decimal(str(raw.get("Close") or "").replace(",", "").strip())
        except (InvalidOperation, ValueError):
            continue
        if not value.is_finite() or value <= 0:
            continue
        # OpenAPI includes multiple sessions (over 12k rows). Input order
        # is not a contract: publish the newest eligible dated close, never
        # whichever record happens to be returned first.
        if symbol in result and result[symbol]["price_date"] >= day.isoformat():
            continue
        # quote_at is the *session close anchor*, never a purported timestamp
        # of an individual trade. The originating trade date is checked above.
        at = datetime.combine(day, CLOSE_TIME, TAIPEI)
        result[symbol] = {
            "price": str(value),
            "price_date": day.isoformat(),
            "quote_at": at.isoformat(),
            "received_at": now.isoformat(),
            "session": "official_close",
            "source": SOURCE,
            "route_version": "latest-price.v2",
        }
    return result


class TpexDailyQuotes:
    """Bounded process-level source cache, single public fetch for a holdings batch."""

    def __init__(self, fetch=None):
        self._fetch = fetch
        self._lock = Lock()
        self._stamp = -float("inf")
        self._rows = None
        self._window = None

    def _download(self) -> object:
        if self._fetch is not None:
            return self._fetch()
        req = Request(TPEX_OFFICIAL_EOD_URL,
                      headers={"User-Agent": "JanusPersonalResearch/1.0",
                               "Accept": "application/json"})
        with urlopen(req, timeout=6) as response:
            content = response.read(_MAX_PAYLOAD + 1)
        if len(content) > _MAX_PAYLOAD:
            raise ValueError("TPEx payload exceeded bound")
        rows = json.loads(content.decode("utf-8-sig"))
        if not isinstance(rows, list) or len(rows) > 25000:
            raise ValueError("TPEx source schema unavailable")
        return rows

    def quotes(self, symbols: set[str], now: datetime) -> dict[str, dict]:
        if not symbols:
            return {}
        # Earlier closes remain usable before handoff; today's close does not.
        local = now.astimezone(TAIPEI)
        window = (local.date(), local.time() >= time(14, 30))
        with self._lock:
            tick = monotonic()
            # A failed fetch previously retried on every caller because
            # _rows is None. Repeated owner requests must not hammer TPEx
            # when it returns HTML/invalid JSON or temporarily blocks traffic.
            if (self._rows is None and self._window == window
                    and tick - self._stamp < _FAILURE_RETRY_TTL):
                raise RuntimeError("TPEx official source retry cooldown")
            if self._rows is None or tick - self._stamp >= _CACHE_TTL or self._window != window:
                self._stamp = tick
                self._window = window
                try:
                    self._rows = self._download()
                except Exception:
                    self._rows = None
                    raise
            return parse_tpex_daily_quotes(self._rows, set(symbols), now)
