"""TWSE-only bounded MIS read-through source; never writes canonical EOD data."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from threading import Lock
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TAIPEI = timezone(timedelta(hours=8))


def market_phase(now=None):
    now = now or datetime.now(TAIPEI)
    local = now.astimezone(TAIPEI)
    if local.weekday() >= 5:
        return "closed"
    minute = local.hour * 60 + local.minute
    if 540 <= minute < 810:
        return "regular"
    if 810 <= minute < 870:
        return "closing_pending_eod"
    return "closed"


class MisQuotes:
    """Authorized TWSE MIS source with a tiny per-process anti-burst cache.

    Persistent TTL/last-success semantics live in PostgreSQL through QuoteRouter.
    This cache only prevents same-instance duplicate network calls inside 10s.
    """

    def __init__(self):
        self.lock = Lock()
        self.cache = {}
        self.fetched_at = {}
        self.market_date = None

    @staticmethod
    def _channel(symbol, row):
        market = str(row.get("market", "")).upper()
        if symbol == "TAIEX" or market == "TWSE_INDEX":
            return "tse_t00.tw"
        if market == "TWSE":
            return f"tse_{symbol}.tw"
        return None

    def prices(self, identities):
        if os.getenv("JANUS_MIS_QUOTES_ENABLED", "false").lower() != "true":
            raise ValueError("MIS source authorization is pending")
        channels = {
            symbol: channel
            for symbol, row in identities.items()
            if (channel := self._channel(symbol, row)) is not None
        }
        if not channels:
            return {}
        if len(channels) > 200:
            raise ValueError("TWSE MIS quote limit exceeded")

        with self.lock:
            now = monotonic()
            due = {
                symbol: channel
                for symbol, channel in channels.items()
                if symbol not in self.cache or now - self.fetched_at.get(symbol, 0.0) >= 10
            }
            if due:
                query = urlencode({"ex_ch": "|".join(due.values()), "json": "1", "delay": "0"})
                request = Request(
                    "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?" + query,
                    headers={
                        "User-Agent": "JanusPersonalResearch/1.0",
                        "Referer": "https://mis.twse.com.tw/stock/index.jsp",
                    },
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.load(response)
                if payload.get("rtcode") != "0000" or not isinstance(payload.get("msgArray"), list):
                    raise ValueError("MIS quote response unavailable")
                self.market_date = max((str(row.get("d", "")) for row in payload["msgArray"]), default="")
                by_channel = {channel: symbol for symbol, channel in due.items()}
                received_at = datetime.now(TAIPEI).isoformat()
                for row in payload["msgArray"]:
                    channel = f"{row.get('ex', '')}_{row.get('c', '')}.tw"
                    symbol = by_channel.get(channel)
                    if symbol is None:
                        continue
                    trade = row.get("trade") or {}
                    trade_price = trade.get("z")
                    raw_price = trade_price if trade_price not in {None, "-"} else row.get("z")
                    raw_time = trade.get("t") if trade_price not in {None, "-"} else row.get("t")
                    try:
                        price = Decimal(str(raw_price))
                        at = datetime.strptime(
                            str(row.get("d")) + " " + str(raw_time), "%Y%m%d %H:%M:%S"
                        ).replace(tzinfo=TAIPEI)
                        if not price.is_finite() or price <= 0:
                            continue
                    except (InvalidOperation, ValueError, TypeError):
                        continue
                    self.cache[symbol] = {
                        "price": str(price),
                        "quote_at": at.isoformat(),
                        "received_at": received_at,
                    }
                    self.fetched_at[symbol] = now
            return {symbol: dict(self.cache[symbol]) for symbol in channels if symbol in self.cache}


def value_holdings(positions, quotes, now=None):
    now = now or datetime.now(TAIPEI)
    phase = market_phase(now)
    rows, totals = [], {}
    for position in positions:
        row = dict(position)
        quote = quotes.get(str(row["symbol"]), {}) if row.get("currency") == "TWD" else {}
        at = datetime.fromisoformat(quote["quote_at"]) if quote.get("quote_at") else None
        state = str(quote.get("state") or "")
        if not state and quote:
            fresh = (
                at is not None
                and at.date() == now.astimezone(TAIPEI).date()
                and 0 <= (now - at).total_seconds() <= 120
            )
            state = "intraday" if fresh else "stale"
        usable = bool(quote) and state in {"intraday", "closing_pending_eod", "eod_final"}
        price = Decimal(str(quote["price"])) if quote.get("price") is not None else None
        shares, average = Decimal(str(row["shares"])), Decimal(str(row["average_cost"]))
        cost = shares * average
        value = price * shares if price is not None else None
        pnl = value - cost if value is not None else None
        source = quote.get("source")
        price_date = quote.get("price_date") or (at.date().isoformat() if at else None)
        row.update(
            market_price=str(price) if price is not None else None,
            market_value=str(value) if value is not None else None,
            unrealized_pnl=str(pnl) if pnl is not None else None,
            unrealized_return=str(pnl / cost) if pnl is not None and cost else None,
            price_status="available" if usable else "stale" if quote else "missing",
            quote_at=quote.get("quote_at"),
            received_at=quote.get("received_at"),
            quote_session=quote.get("session"),
            quote_state=state or "missing",
            freshness_seconds=(now - at).total_seconds() if at else None,
            quote_route_version=quote.get("route_version"),
            price_date=price_date,
            missing_reason=None if usable else "latest_price_stale" if quote else "latest_price_missing",
            price_source=source,
            is_final=bool(quote.get("is_final")),
            valuation_kind="eod" if source == "core_ohlcv" else "intraday",
        )
        rows.append(row)
        total = totals.setdefault(
            row["currency"],
            {
                "currency": row["currency"],
                "market_value": Decimal(0),
                "cost_basis": Decimal(0),
                "affected_symbols": [],
                "missing_price_count": 0,
                "stale_price_count": 0,
            },
        )
        total["cost_basis"] += cost
        if not usable:
            total["affected_symbols"].append(row["symbol"])
            total["missing_price_count" if not quote else "stale_price_count"] += 1
        if value is not None:
            total["market_value"] += value
    summaries = []
    for total in totals.values():
        cost, value, affected = total["cost_basis"], total["market_value"], total["affected_symbols"]
        missing = total["missing_price_count"] > 0
        summaries.append(
            {
                **total,
                "cost_basis": str(cost),
                "market_value": None if missing else str(value),
                "unrealized_pnl": None if missing else str(value - cost),
                "unrealized_return": None if missing or not cost else str((value - cost) / cost),
                "aggregate_status": "withheld" if missing else "stale" if affected else "available",
                "affected_symbol_count": len(affected),
                "valuation_date": now.astimezone(TAIPEI).date().isoformat(),
                "valuation_kind": "latest_price",
            }
        )
    return {
        "positions": rows,
        "items": summaries,
        "source": "latest-price-resolver",
        "checked_at": now.isoformat(),
        "market_open": phase == "regular",
        "session": phase,
    }
