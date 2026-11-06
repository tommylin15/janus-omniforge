"""Demand-driven Shioaji streaming cache; no snapshot polling and no order APIs.

One process owns subscriptions. The Cloud Run deployment must keep max-instances=1.
The callback cache is last-observation only, not canonical historical data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import RLock
from time import monotonic, sleep
from typing import Any

TAIPEI = timezone(timedelta(hours=8))


def _to_time(event: Any) -> datetime | None:
    value = getattr(event, "datetime", None)
    if isinstance(value, datetime):
        return value.replace(tzinfo=TAIPEI) if value.tzinfo is None else value.astimezone(TAIPEI)
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        try:
            return datetime(*value).replace(tzinfo=TAIPEI)
        except (TypeError, ValueError):
            return None
    if value:
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed.replace(tzinfo=TAIPEI) if parsed.tzinfo is None else parsed.astimezone(TAIPEI)
        except ValueError:
            pass
    return None


def _positive(value: Any) -> float | None:
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if isfinite(result) and result > 0 else None


class StreamCache:
    """Quote subscriptions shared by concurrent /quotes requests in one instance."""

    def __init__(self, client: Any):
        self.client = client
        self.lock = RLock()
        self.demand: dict[str, float] = {}
        self.subscribed: dict[str, Any] = {}
        self.latest: dict[str, dict] = {}
        # Separate on-demand five-level BidAsk stream, never snapshots() polling.
        self.book_demand: dict[str, float] = {}
        self.book_subscribed: dict[str, Any] = {}
        self.book_latest: dict[str, dict] = {}
        # The 150 subscription guard leaves room for non-stock subscriptions.
        self.max_subscriptions = 150
        self.client.set_on_quote_stk_v1_callback(self.on_stock)
        self.client.set_on_quote_idx_v1_callback(self.on_index)
        if hasattr(self.client, "set_on_bidask_stk_v1_callback"):
            self.client.set_on_bidask_stk_v1_callback(self.on_bidask)

    def _save(self, symbol: str, exchange: str, event: Any, *, index: bool = False) -> None:
        # Shioaji's simtrade flag describes an exchange-simulated tick; it must
        # not be published as an actual trade even in simulation login mode.
        if getattr(event, "simtrade", False):
            return
        at = _to_time(event)
        price = _positive(getattr(event, "close", None))
        now = datetime.now(TAIPEI)
        if not at or not price or at > now or at.date() != now.date():
            return
        # QuoteSTKv1 may publish the official reference without price_chg.
        # Keep that real reference for ETFs instead of dropping daily PnL.
        previous = _positive(getattr(event, "reference", None))
        if not index and getattr(event, "price_chg", None) is not None:
            try:
                previous = _positive(price - float(event.price_chg))
            except (ValueError, TypeError):
                pass
        observation = {
            "symbol": symbol,
            "exchange": exchange,
            "close": price,
            "previous_close": previous,
            "open": _positive(getattr(event, "open", None)),
            "high": _positive(getattr(event, "high", None)),
            "low": _positive(getattr(event, "low", None)),
            "volume": getattr(event, "vol_sum" if index else "total_volume", None),
            "trade_time": at.isoformat(),
            "received_at": now.isoformat(),
            "source": "shioaji",
            "is_final": False,
        }
        try:
            observation["volume"] = int(observation["volume"]) if observation["volume"] is not None else None
        except (ValueError, TypeError, OverflowError):
            observation["volume"] = None
        with self.lock:
            existing = self.latest.get(symbol)
            if existing is None or at.isoformat() >= existing["trade_time"]:
                self.latest[symbol] = observation

    def on_stock(self, exchange: Any, event: Any) -> None:
        symbol = str(getattr(event, "code", "")).upper()
        market = str(getattr(exchange, "value", exchange)).upper()
        if symbol:
            self._save(symbol, market, event)

    def on_bidask(self, exchange: Any, event: Any) -> None:
        """Only a real, dated regular-lot five-level callback may fill this cache."""
        symbol = str(getattr(event, "code", "")).strip().upper()
        at = _to_time(event)
        now = datetime.now(TAIPEI)
        if (not symbol or not at or at > now or at.date() != now.date()
                or getattr(event, "simtrade", False)
                or getattr(event, "intraday_odd", False)):
            return

        def levels(price_field: str, volume_field: str) -> list[dict]:
            prices = getattr(event, price_field, None)
            volumes = getattr(event, volume_field, None)
            if not isinstance(prices, (tuple, list)) or not isinstance(volumes, (tuple, list)):
                return []
            parsed = []
            for price_raw, volume_raw in list(zip(prices, volumes))[:5]:
                price = _positive(price_raw)
                try:
                    volume = int(volume_raw)
                except (ValueError, TypeError, OverflowError):
                    continue
                if price is not None and volume >= 0:
                    parsed.append({"price": str(price_raw), "volume": volume})
            return parsed

        bid = levels("bid_price", "bid_volume")
        ask = levels("ask_price", "ask_volume")
        if not bid and not ask:
            return
        observation = {
            "symbol": symbol,
            "exchange": str(getattr(exchange, "value", exchange)).upper(),
            "quote_time": at.isoformat(),
            "received_at": now.isoformat(),
            "source": "shioaji_bidask",
            "unit": "lots",
            "bid": bid,
            "ask": ask,
        }
        with self.lock:
            old = self.book_latest.get(symbol)
            if old is None or at.isoformat() >= old["quote_time"]:
                self.book_latest[symbol] = observation

    def on_index(self, event: Any) -> None:
        if str(getattr(event, "code", "")) == "IX0001":
            self._save("TAIEX", "TSE", event, index=True)

    def _contract(self, symbol: str) -> Any:
        return self.client.contracts.get("IX0001" if symbol == "TAIEX" else symbol)

    def _unsubscribe_expired(self, now: float) -> None:
        import shioaji as sj
        for symbol, end in tuple(self.book_demand.items()):
            if now < end:
                continue
            self.book_demand.pop(symbol, None)
            contract = self.book_subscribed.pop(symbol, None)
            self.book_latest.pop(symbol, None)
            if contract is not None:
                try:
                    self.client.unsubscribe(contract, quote_type=sj.QuoteType.BidAsk)
                except Exception:
                    pass
        for symbol, end in tuple(self.demand.items()):
            if now < end:
                continue
            self.demand.pop(symbol, None)
            contract = self.subscribed.pop(symbol, None)
            self.latest.pop(symbol, None)
            if contract is not None:
                try:
                    self.client.unsubscribe(contract, quote_type=sj.QuoteType.Quote)
                except Exception:
                    # No retry storm. A future request can subscribe again.
                    pass

    def read(self, symbols: list[str]) -> dict[str, dict]:
        # Caller only revalidates while the relevant page is active.
        now = monotonic()
        with self.lock:
            self._unsubscribe_expired(now)
            for symbol in symbols:
                self.demand[symbol] = now + 130
                if symbol in self.subscribed or len(self.subscribed) + len(self.book_subscribed) >= self.max_subscriptions:
                    continue
                contract = self._contract(symbol)
                if contract is None:
                    continue
                try:
                    import shioaji as sj
                    self.client.subscribe(contract, quote_type=sj.QuoteType.Quote)
                    self.subscribed[symbol] = contract
                except Exception:
                    pass
            cold = any(symbol not in self.latest for symbol in symbols)
        # A short synchronous wait permits first callbacks while Cloud Run CPU
        # is allocated to the incoming request; no perpetual background loop.
        if cold:
            sleep(1.0)
        at = datetime.now(TAIPEI)
        with self.lock:
            current: dict[str, dict] = {}
            for symbol in symbols:
                row = self.latest.get(symbol)
                if not row:
                    continue
                received = datetime.fromisoformat(row["received_at"])
                if received.date() == at.date() and 0 <= (at - received).total_seconds() <= 120:
                    current[symbol] = dict(row)
            return current

    def read_book(self, symbol: str) -> dict | None:
        """Demand once on stock selection/manual refresh; no periodic snapshot query."""
        now = monotonic()
        with self.lock:
            self._unsubscribe_expired(now)
            self.book_demand[symbol] = now + 130
            if (symbol not in self.book_subscribed
                    and len(self.subscribed) + len(self.book_subscribed) < self.max_subscriptions):
                contract = self._contract(symbol)
                if contract is not None:
                    try:
                        import shioaji as sj
                        self.client.subscribe(contract, quote_type=sj.QuoteType.BidAsk)
                        self.book_subscribed[symbol] = contract
                    except Exception:
                        pass
            cold = symbol not in self.book_latest
        if cold:
            sleep(1.0)
        now_local = datetime.now(TAIPEI)
        with self.lock:
            row = self.book_latest.get(symbol)
            if row:
                received = datetime.fromisoformat(row["received_at"])
                at = datetime.fromisoformat(row["quote_time"])
                if (received.date() == now_local.date()
                        and 0 <= (now_local - received).total_seconds() <= 120
                        and 0 <= (now_local - at).total_seconds() <= 120):
                    return dict(row)
        return None

    def subscribed_count(self) -> int:
        with self.lock:
            return len(self.subscribed) + len(self.book_subscribed)
