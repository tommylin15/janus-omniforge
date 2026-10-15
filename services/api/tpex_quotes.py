"""Owner-demand TPEx official EOD snapshot; never substitutes a live execution.

Open government data TPEx OpenAPI latest daily close. This adapter does not
write canonical Core/Iceberg or infer trade executions. Strict published price,
trade-date, and source checks before persisting a read-only latest quote cache.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlencode
import json
from threading import Lock
from time import monotonic
from urllib.request import Request, urlopen

from .intraday_quotes import TAIPEI

TPEX_OFFICIAL_EOD_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TPEX_OFFICIAL_DATED_URL = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
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


def parse_tpex_daily_quote_history(rows: object, symbols: set[str],
                                   now: datetime) -> dict[str, list[dict]]:
    """Only official, published EOD sessions; keep every eligible trade day.

    The API must not silently promote today's unpublished or future price.
    Source provenance is per official record, independent of owner ledger.
    """
    if not isinstance(rows, list) or len(rows) > 25000:
        return {}
    local = now.astimezone(TAIPEI)
    latest = local.date()
    selected: dict[str, dict[str, dict]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("SecuritiesCompanyCode") or
                     raw.get("SecuritiesCode") or raw.get("Code") or "").strip()
        if symbol not in symbols:
            continue
        day = _official_day(raw.get("Date") or raw.get("TradeDate"))
        if day is None or day > latest or (latest - day).days > 7:
            continue
        if day == latest and local.time() < time(14, 30):
            continue
        try:
            price = Decimal(str(raw.get("Close") or "").replace(",", "").strip())
        except (InvalidOperation, ValueError):
            continue
        if price <= 0 or not price.is_finite():
            continue
        uri = raw.get("_official_source_uri") or TPEX_OFFICIAL_EOD_URL
        if uri != TPEX_OFFICIAL_EOD_URL and not (
            isinstance(uri, str) and
            uri.startswith(TPEX_OFFICIAL_DATED_URL + "?") and
            "o=json" in uri
        ):
            continue
        trade_day = day.isoformat()
        source_record = {k: v for k, v in raw.items() if not k.startswith("_")}
        digest = sha256(json.dumps(source_record, sort_keys=True,
                                   ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        at = datetime.combine(day, CLOSE_TIME, TAIPEI)
        result = {
            "price": str(price), "price_date": trade_day,
            "quote_at": at.isoformat(), "received_at": now.isoformat(),
            "session": "official_close", "source": SOURCE,
            "source_uri": uri, "record_sha256": digest,
            "route_version": "latest-price.v2",
        }
        by_day = selected.setdefault(symbol, {})
        if trade_day in by_day and by_day[trade_day] is not None and by_day[trade_day]["price"] != result["price"]:
            # Source contains conflicting official closes for one session:
            # refuse that session rather than depend on row ordering.
            by_day[trade_day] = None
        elif trade_day not in by_day:
            by_day[trade_day] = result
    return {
        symbol: [value for _, value in sorted(days.items()) if value is not None]
        for symbol, days in selected.items()
        if any(value is not None for value in days.values())
    }


def parse_tpex_daily_quotes(rows: object, symbols: set[str], now: datetime) -> dict[str, dict]:
    return {symbol: values[-1] for symbol, values in
            parse_tpex_daily_quote_history(rows, symbols, now).items() if values}


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
        headers = {"User-Agent": "Mozilla/5.0 (compatible; JanusResearch/1.0)",
                   "Accept": "application/json,text/html;q=0.5",
                   "Accept-Encoding": "identity"}
        def read(url):
            with urlopen(Request(url, headers=headers), timeout=12) as response:
                body = response.read(_MAX_PAYLOAD + 1)
            if len(body) > _MAX_PAYLOAD:
                raise ValueError("official TPEx payload exceeded bound")
            return json.loads(body.decode("utf-8-sig"))
        try:
            rows = read(TPEX_OFFICIAL_EOD_URL)
            if not isinstance(rows, list) or len(rows) > 25000:
                raise ValueError("official TPEx OpenAPI schema unavailable")
            return rows
        except (ValueError, UnicodeError, OSError):
            # Cloud Run egress has returned HTTP 200 non-JSON (WAF/HTML)
            # while GitHub runners receive JSON. The legacy JSON endpoint
            # is *also* official TPEx. It must advertise the requested day.
            local = datetime.now(TAIPEI)
            target = local.date()
            if local.time() < time(14, 30) or local.weekday() >= 5:
                target -= timedelta(days=1)
                while target.weekday() >= 5:
                    target -= timedelta(days=1)
            day = f"{target.year-1911:03d}/{target.month:02d}/{target.day:02d}"
            uri = TPEX_OFFICIAL_DATED_URL + "?" + urlencode(
                {"l": "zh-tw", "o": "json", "d": day, "s": "0"})
            document = read(uri)
            if not isinstance(document, dict) or _official_day(document.get("date")) != target:
                raise ValueError("official TPEx dated response day unavailable")
            tables = document.get("tables")
            if not isinstance(tables, list) or len(tables) > 20:
                raise ValueError("official TPEx dated response table unavailable")
            rows = []
            for table in tables:
                fields, data = table.get("fields"), table.get("data")
                if not isinstance(fields, list) or not isinstance(data, list):
                    continue
                if len(fields) > 100 or len(data) > 25000:
                    raise ValueError("official TPEx dated response exceeds bound")
                for values in data:
                    if not isinstance(values, list) or len(values) != len(fields):
                        continue
                    item = dict(zip(fields, values))
                    symbol = str(item.get("代號") or "").strip()
                    if not symbol:
                        continue
                    rows.append({"Date": day, "SecuritiesCompanyCode": symbol,
                                 "Close": item.get("收盤"),
                                 "_official_source_uri": uri})
            if len(rows) > 25000:
                raise ValueError("official TPEx dated response exceeds bound")
            return rows

    def history(self, symbols: set[str], now: datetime) -> dict[str, list[dict]]:
        if not symbols:
            return {}
        local = now.astimezone(TAIPEI)
        window = (local.date(), local.time() >= time(14, 30))
        with self._lock:
            tick = monotonic()
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
            return parse_tpex_daily_quote_history(self._rows, set(symbols), now)

    def quotes(self, symbols: set[str], now: datetime) -> dict[str, dict]:
        return {symbol: rows[-1] for symbol, rows in self.history(symbols, now).items() if rows}

