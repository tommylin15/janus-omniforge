"""Private OIDC transport for simulation-only, demand-driven Shioaji proxy.

Never exposes broker credentials, broker account information, or direct proxy URL
to Flutter. Returned observations are non-final operational quotes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

DEFAULT_URL = "https://shioaji-quote-proxy-131494961796.asia-east1.run.app"
MAX_BYTES = 512 * 1024
TAIPEI = timezone(timedelta(hours=8))


def _time(raw):
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return value if value.tzinfo else None


def _positive(raw):
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def _identity_token(audience: str) -> str:
    endpoint = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity?" + urlencode(
            {"audience": audience, "format": "full"}
        )
    )
    with urlopen(Request(endpoint, headers={"Metadata-Flavor": "Google"}), timeout=2) as resp:
        token = resp.read(8192).decode("utf-8").strip()
    if not token or len(token) >= 8192:
        raise RuntimeError("proxy identity token unavailable")
    return token


class ShioajiQuotes:
    """QuoteRouter-compatible source, bounded and private by construction."""

    def __init__(self, proxy_url: str | None = None):
        self.base_url = (proxy_url or os.getenv("JANUS_SHIOAJI_PROXY_URL", DEFAULT_URL)).rstrip("/")
        parsed = urlsplit(self.base_url)
        expected = urlsplit(DEFAULT_URL)
        if parsed.scheme != "https" or parsed.hostname != expected.hostname or parsed.path not in ("", "/"):
            raise ValueError("unapproved Shioaji proxy endpoint")

    def prices(self, identities: dict) -> dict:
        """Single shared batch request per up to 30 symbols (no scheduled polling)."""
        result = {}
        candidates = {
            str(symbol).upper(): row for symbol, row in identities.items()
            if re.fullmatch(r"[0-9A-Z]{4,10}|TAIEX", str(symbol).upper())
            and str(row.get("market", "")).upper() in
            {"TWSE", "TWSE_INDEX", "TPEX", "OTC", "TPEX_UNVERIFIED"}
            and row.get("enabled", True) is not False
        }
        if not candidates:
            return result
        token = _identity_token(self.base_url)
        symbols = sorted(candidates)
        for start in range(0, len(symbols), 30):
            batch = symbols[start:start + 30]
            uri = self.base_url + "/quotes?" + urlencode({"symbols": ",".join(batch)})
            request = Request(uri, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
            # Cold simulation login + first quote callback + bounded MIS fallback
            # can exceed 8 seconds. Keep a finite response deadline.
            with urlopen(request, timeout=18) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("oversized quote response")
            payload = json.loads(data)
            if not isinstance(payload, dict) or payload.get("status") != "success":
                raise ValueError("invalid Shioaji proxy response")
            now = datetime.now(TAIPEI)
            rows = payload.get("quotes")
            if not isinstance(rows, dict):
                raise ValueError("invalid quote collection")
            for symbol, raw in rows.items():
                if symbol not in batch or not isinstance(raw, dict) or str(raw.get("symbol")) != symbol:
                    continue
                market = str(candidates[symbol].get("market", "")).upper()
                exchange = str(raw.get("exchange", "")).upper()
                # Never accept an OTC row as a TSE equity or vice versa.
                if market == "TWSE_INDEX":
                    if symbol != "TAIEX" or exchange not in {"TSE", "TSE_INDEX"}:
                        continue
                elif market == "TWSE":
                    if exchange != "TSE":
                        continue
                elif market in {"TPEX", "OTC", "TPEX_UNVERIFIED"}:
                    if exchange != "OTC":
                        continue
                price = _positive(raw.get("close"))
                at, received = _time(raw.get("trade_time")), _time(raw.get("received_at"))
                if (price is None or at is None or received is None or at > received or
                    received > now + timedelta(seconds=5) or at > now + timedelta(seconds=5)):
                    continue
                prior = _positive(raw.get("previous_close"))
                source = str(raw.get("source", ""))
                if source not in {"shioaji", "twse_mis"}:
                    continue
                result[symbol] = {
                    "price": str(price),
                    "previous_close": str(prior) if prior is not None else None,
                    "quote_at": at.isoformat(),
                    "received_at": received.isoformat(),
                    "source": source,
                }
        return result


    def historical_minutes(self, symbol: str, trade_day: str) -> dict:
        """One IAM-authenticated call after a durable PG backfill claim.

        This is NOT called by the shared 60-second quote refresh path.
        Caller authorizes user scope and applies all cross-instance quotas.
        """
        if not re.fullmatch(r"[0-9A-Z]{4,10}|TAIEX", symbol):
            raise ValueError("invalid broker historical symbol")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_day):
            raise ValueError("invalid broker historical date")
        if datetime.fromisoformat(trade_day).date() != datetime.now(TAIPEI).date():
            raise ValueError("broker history is restricted to today's bounded session")
        token = _identity_token(self.base_url)
        url = self.base_url + "/kbars?" + urlencode({"symbol": symbol, "day": trade_day})
        request = Request(url, headers={"Authorization": "Bearer " + token,
                                        "Accept": "application/json"})
        with urlopen(request, timeout=16) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("broker kbars response exceeds boundary")
        payload = json.loads(data)
        if (not isinstance(payload, dict) or payload.get("symbol") != symbol
                or payload.get("date") != trade_day
                or payload.get("source") != "shioaji_kbars"
                or payload.get("status") not in
                {"available", "missing", "unavailable", "invalid"}):
            raise ValueError("invalid broker kbars source or day")
        rows = payload.get("points")
        if not isinstance(rows, list) or len(rows) > 271:
            raise ValueError("invalid broker kbar count")
        accepted = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            at, value = _time(row.get("date")), _positive(row.get("value"))
            if at is None or at.astimezone(TAIPEI).date().isoformat() != trade_day:
                continue
            local = at.astimezone(TAIPEI)
            minute = local.hour * 60 + local.minute
            if 540 <= minute < 810 and value is not None:
                accepted.append({"date": local.isoformat(), "value": str(value)})
        return {"status": payload["status"], "source": "shioaji_kbars",
                "symbol": symbol, "date": trade_day, "points": accepted}

    def order_book(self, symbol: str, market: str = "") -> dict:
        """Read private, dated regular-lot five-level depth; never expose Proxy URL."""
        empty = {"symbol": symbol, "status": "missing", "source": "shioaji_bidask",
                 "unit": "lots", "bid": [], "ask": []}
        if not re.fullmatch(r"[0-9A-Z]{4,10}", symbol):
            raise ValueError("invalid order-book symbol")
        token = _identity_token(self.base_url)
        request = Request(self.base_url + "/order-book/" + symbol,
                          headers={"Authorization": "Bearer " + token,
                                   "Accept": "application/json"})
        with urlopen(request, timeout=18) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("oversized order-book response")
        payload = json.loads(raw)
        if (not isinstance(payload, dict) or payload.get("symbol") != symbol
                or payload.get("source") != "shioaji_bidask"
                or payload.get("status") not in {"available", "missing"}):
            raise ValueError("invalid order-book response")
        if payload["status"] != "available":
            return empty
        book = payload.get("data")
        if not isinstance(book, dict) or book.get("symbol") != symbol:
            raise ValueError("invalid order-book book")
        market = str(market).upper()
        exchange = str(book.get("exchange") or "").upper()
        if (market == "TWSE" and exchange != "TSE") or (
                market in {"TPEX", "OTC", "TPEX_UNVERIFIED"} and exchange != "OTC"):
            raise ValueError("order-book market mismatch")
        if exchange not in {"TSE", "OTC"} or book.get("unit") != "lots" or (
                book.get("source") != "shioaji_bidask"):
            raise ValueError("invalid order-book provenance")
        observed = _time(book.get("quote_time"))
        received = _time(book.get("received_at"))
        now = datetime.now(TAIPEI)
        if (observed is None or received is None or observed > received
                or received > now + timedelta(seconds=5)
                or observed.astimezone(TAIPEI).date() != now.date()
                or (now - received).total_seconds() > 120
                or (now - observed).total_seconds() > 120):
            return {**empty, "status": "stale"}

        def valid_levels(value):
            if not isinstance(value, list) or len(value) > 5:
                raise ValueError("invalid order-book depth count")
            parsed = []
            for row in value:
                if not isinstance(row, dict):
                    raise ValueError("invalid order-book depth row")
                price = _positive(row.get("price"))
                volume = row.get("volume")
                if (price is None or type(volume) is not int or
                        volume < 0 or volume > 10**9):
                    raise ValueError("invalid order-book depth value")
                parsed.append({"price": str(price), "volume": volume})
            return parsed

        bid = valid_levels(book.get("bid"))
        ask = valid_levels(book.get("ask"))
        if not bid and not ask:
            return empty
        return {"symbol": symbol, "status": "available" if len(bid) == 5 and len(ask) == 5 else "partial",
                "source": "shioaji_bidask", "quote_at": observed.isoformat(),
                "received_at": received.isoformat(), "unit": "lots",
                "bid": bid, "ask": ask}
