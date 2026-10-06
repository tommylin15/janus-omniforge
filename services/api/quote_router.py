"""Persistent DB-first latest-price resolver for TWSE stocks and TAIEX."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import logging

from .intraday_quotes import TAIPEI, market_phase

LOGGER = logging.getLogger(__name__)
ROUTE_VERSION = "latest-price.v2"
TTL_SECONDS = 60
MANUAL_THROTTLE_SECONDS = 10


def _timestamp(value):
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=TAIPEI)
    except ValueError:
        return None


def _strict_timestamp(value):
    if value in {None, ""}:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _day(row):
    raw = row.get("price_date")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    at = _timestamp(row.get("quote_at"))
    return at.astimezone(TAIPEI).date() if at else None


class QuoteRouter:
    def __init__(self, repository, source):
        self.repository, self.source = repository, source

    def _live(self, identities):
        reader = getattr(self.repository, "last_quotes", None)
        return reader(identities) if reader is not None else {}

    def _eod(self, identities):
        reader = getattr(self.repository, "eod_quotes", None)
        return reader(identities) if reader is not None else {}

    def read(self, identities, *, now=None):
        now = now or datetime.now(TAIPEI)
        live = self._live(identities)
        eod = self._eod(identities)
        result = {}
        for symbol in identities:
            live_row = dict(live.get(symbol) or {})
            eod_row = dict(eod.get(symbol) or {})
            live_day, eod_day = _day(live_row), _day(eod_row)
            if eod_row and (not live_row or (eod_day is not None and (live_day is None or eod_day >= live_day))):
                result[symbol] = {
                    **eod_row,
                    "source": "core_ohlcv",
                    "route_version": ROUTE_VERSION,
                    "state": "eod_final",
                    "is_final": True,
                    "price_date": eod_day.isoformat() if eod_day else eod_row.get("price_date"),
                }
                continue
            if not live_row:
                continue
            at = _timestamp(live_row.get("quote_at"))
            received = _timestamp(live_row.get("received_at"))
            phase = market_phase(now)
            same_day = at is not None and at.astimezone(TAIPEI).date() == now.astimezone(TAIPEI).date()
            age = (now - received).total_seconds() if received is not None else None
            if same_day and phase == "regular" and age is not None and 0 <= age <= TTL_SECONDS * 2:
                state = "intraday"
            elif same_day and phase != "regular":
                state = "closing_pending_eod"
            else:
                state = "stale"
            result[symbol] = {
                **live_row,
                "source": "twse_mis",
                "route_version": ROUTE_VERSION,
                "state": state,
                "is_final": False,
                "price_date": live_day.isoformat() if live_day else None,
            }
        return result

    def _due(self, identities, *, force=False, now=None):
        now = now or datetime.now(TAIPEI)
        current = self._live(identities)
        threshold = MANUAL_THROTTLE_SECONDS if force else TTL_SECONDS
        due = {}
        for symbol, identity in identities.items():
            market = str(identity.get("market", "")).upper()
            if identity.get("enabled") is False or market not in {"TWSE", "TWSE_INDEX"}:
                continue
            row = current.get(symbol)
            received = _timestamp(row.get("received_at")) if row else None
            if received is None or (now - received).total_seconds() >= threshold:
                due[symbol] = identity
        return due

    def refresh(self, identities, *, force=False, now=None):
        now = now or datetime.now(TAIPEI)
        due = self._due(identities, force=force, now=now)
        if not due:
            return {"status": "fresh", "requested": 0, "updated": 0}
        try:
            rows = self.source.prices(due)
            received = datetime.now(TAIPEI)
            successful = {}
            for symbol, row in rows.items():
                if symbol not in due:
                    continue
                try:
                    price = Decimal(str(row["price"]))
                    at = _strict_timestamp(row["quote_at"])
                    raw_received = row.get("received_at")
                    source_received = _strict_timestamp(raw_received) if raw_received not in {None, ""} else received
                    if (
                        not price.is_finite()
                        or price <= 0
                        or at is None
                        or source_received is None
                        or at > source_received
                        or source_received > received
                    ):
                        continue
                except (KeyError, ValueError, TypeError, InvalidOperation):
                    continue
                successful[symbol] = {
                    **row,
                    "received_at": source_received.isoformat(),
                    "session": "regular" if market_phase(at) == "regular" else "off_session",
                    "source": "twse_mis",
                    "route_version": ROUTE_VERSION,
                }
            if successful:
                writer = getattr(self.repository, "save_last_quotes", None)
                if writer is None:
                    raise RuntimeError("persistent quote writer unavailable")
                writer(successful)
            return {"status": "updated" if successful else "unavailable", "requested": len(due), "updated": len(successful)}
        except Exception as error:
            LOGGER.warning("quote refresh unavailable: %s", type(error).__name__)
            return {"status": "unavailable", "requested": len(due), "updated": 0}

    def resolve(self, identities, *, refresh=False, force=False, now=None):
        refresh_result = {"status": "idle", "requested": 0, "updated": 0}
        if refresh:
            refresh_result = self.refresh(identities, force=force, now=now)
        return self.read(identities, now=now), refresh_result
