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


def value_holdings(positions, quotes, now=None, *, previous_closes=None):
    now = now or datetime.now(TAIPEI)
    phase = market_phase(now)
    rows, totals = [], {}
    previous_closes = previous_closes or {}
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
        # One malformed / nonfinite source quote must not take down the whole
        # owner's DB-first holdings snapshot or contaminate published totals.
        try:
            price = Decimal(str(quote["price"])) if quote.get("price") is not None else None
            if price is not None and (not price.is_finite() or price <= 0):
                price = None
        except (InvalidOperation, TypeError, ValueError):
            price = None
        source = quote.get("source")
        price_date = quote.get("price_date") or (at.astimezone(TAIPEI).date().isoformat() if at and at.tzinfo else None)
        # 'Stale' is a freshness indicator, not evidence that a legitimate
        # historical observation has become numerically unusable. An indicative
        # owner estimate can use the most recent dated quote, while the formal
        # one-day publication remains separately fail-closed.
        from datetime import date
        try:
            observed_day = date.fromisoformat(str(price_date)[:10]) if price_date else None
        except ValueError:
            observed_day = None
        source_ok = source in {"twse_mis", "core_ohlcv", "tpex_openapi_eod"} or (
            # Local legacy quote fixtures may lack a source, but the runtime
            # QuoteRouter always stamps authorized provenance.
            source is None and state in {"intraday", "closing_pending_eod", "eod_final", "stale"}
            and (at is not None or state == "eod_final"))
        reference_eligible = (
            bool(quote) and price is not None and source_ok and
            observed_day is not None and observed_day <= now.astimezone(TAIPEI).date() and
            (at is None or (at.tzinfo is not None and at <= now + timedelta(seconds=30)))
        )
        usable = usable and reference_eligible
        shares, average = Decimal(str(row["shares"])), Decimal(str(row["average_cost"]))
        cost = shares * average
        value = price * shares if price is not None else None
        pnl = value - cost if value is not None else None
        prior = previous_closes.get(str(row["symbol"]), {}) if reference_eligible else {}
        reference = None
        try:
            if prior.get("previous_close_date") and price_date and (
                str(prior["previous_close_date"]) < str(price_date)
            ):
                reference = Decimal(str(prior["previous_close"]))
                if not reference.is_finite() or reference <= 0:
                    reference = None
        except (InvalidOperation, ValueError, TypeError):
            reference = None
        # During today's trading session, a prior-session official close is
        # a valid *dated valuation* but not today's change. Do not display its
        # older price movement under the current-day holdings column.
        if phase == "regular" and str(price_date or "")[:10] != now.astimezone(TAIPEI).date().isoformat():
            reference = None
        change = price - reference if reference is not None and price is not None else None
        row.update(
            market_price=str(price) if price is not None else None,
            reference_eligible=reference_eligible,
            market_value=str(value) if value is not None else None,
            unrealized_pnl=str(pnl) if pnl is not None else None,
            unrealized_return=str(pnl / cost) if pnl is not None and cost else None,
            price_status="available" if usable else "stale" if price is not None else "missing",
            quote_at=quote.get("quote_at"),
            received_at=quote.get("received_at"),
            quote_session=quote.get("session"),
            quote_state=state or "missing",
            freshness_seconds=(now - at).total_seconds() if at else None,
            quote_route_version=quote.get("route_version"),
            price_date=price_date,
            missing_reason=None if usable else "latest_price_stale" if price is not None else "latest_price_missing",
            price_source=source,
            is_final=bool(quote.get("is_final")),
            valuation_kind="eod" if source in {"core_ohlcv", "tpex_openapi_eod"} else "intraday",
            previous_close=str(reference) if reference is not None else None,
            previous_close_date=prior.get("previous_close_date") if reference is not None else None,
            change=str(change) if change is not None else None,
            change_percent=str(change / reference) if change is not None else None,
            day_change_amount=str(change * shares) if change is not None else None,
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
                "priced_market_value": Decimal(0),
                "priced_cost_basis": Decimal(0),
                "priced_symbol_count": 0,
                "price_dates": set(),
                "reference_priced_market_value": Decimal(0),
                "reference_priced_cost_basis": Decimal(0),
                "reference_priced_symbol_count": 0,
                "reference_price_dates": set(),
                "reference_unpriced_symbols": [],
            },
        )
        total["cost_basis"] += cost
        if reference_eligible:
            total["reference_priced_market_value"] += value
            total["reference_priced_cost_basis"] += cost
            total["reference_priced_symbol_count"] += 1
            total["reference_price_dates"].add(observed_day.isoformat())
        else:
            total["reference_unpriced_symbols"].append(row["symbol"])
        if not usable:
            total["affected_symbols"].append(row["symbol"])
            total["missing_price_count" if price is None else "stale_price_count"] += 1
        else:
            # This is a subtotal of only verifiably priced holdings. It must
            # never be silently relabelled as the whole portfolio's value.
            total["market_value"] += value
            total["priced_market_value"] += value
            total["priced_cost_basis"] += cost
            total["priced_symbol_count"] += 1
            if price_date:
                total["price_dates"].add(str(price_date)[:10])
    summaries = []
    for total in totals.values():
        cost, value, affected = total["cost_basis"], total["market_value"], total["affected_symbols"]
        price_dates = sorted(total["price_dates"])
        reference_dates = sorted(total["reference_price_dates"])
        reference_incomplete = bool(total["reference_unpriced_symbols"])
        mixed = len(price_dates) > 1
        incomplete = bool(affected) or mixed
        reason = ("mixed_price_dates" if mixed else
                  "some_prices_missing" if total["missing_price_count"] else
                  "some_prices_stale" if total["stale_price_count"] else None)
        summaries.append(
            {
                **{k: v for k, v in total.items() if k not in {
                    "price_dates", "priced_market_value", "priced_cost_basis",
                    "reference_priced_market_value", "reference_priced_cost_basis",
                    "reference_price_dates"}},
                "cost_basis": str(cost),
                "priced_market_value": str(total["priced_market_value"]),
                "priced_cost_basis": str(total["priced_cost_basis"]),
                "reference_priced_market_value": str(total["reference_priced_market_value"]),
                # Even with some unknown prices, the last-known, authorized
                # observations must remain useful as a CLEARLY partial subtotal.
                "reference_priced_unrealized_pnl": str(
                    total["reference_priced_market_value"] - total["reference_priced_cost_basis"])
                    if total["reference_priced_symbol_count"] else None,
                "reference_priced_unrealized_return": str(
                    (total["reference_priced_market_value"] - total["reference_priced_cost_basis"])
                    / total["reference_priced_cost_basis"])
                    if total["reference_priced_cost_basis"] else None,
                "reference_priced_symbol_count": total["reference_priced_symbol_count"],
                "reference_price_dates": reference_dates,
                "reference_status": "incomplete" if reference_incomplete else "available",
                "reference_market_value": None if reference_incomplete else str(total["reference_priced_market_value"]),
                "reference_unrealized_pnl": None if reference_incomplete else str(
                    total["reference_priced_market_value"] - cost),
                "reference_unrealized_return": None if reference_incomplete or not cost else str(
                    (total["reference_priced_market_value"] - cost) / cost),
                "price_dates": price_dates,
                "market_value": None if incomplete else str(value),
                "unrealized_pnl": None if incomplete else str(value - cost),
                "unrealized_return": None if incomplete or not cost else str((value - cost) / cost),
                "aggregate_status": "withheld" if incomplete else "available",
                "valuation_status": ("partial" if total["missing_price_count"] else
                                     "stale" if total["stale_price_count"] else
                                     "mixed" if mixed else "available"),
                "aggregate_missing_reason": reason,
                "affected_symbol_count": len(affected),
                "valuation_date": price_dates[0] if not incomplete and price_dates else None,
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
