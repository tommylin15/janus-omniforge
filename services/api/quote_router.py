"""Persistent DB-first latest-price resolver for TWSE stocks and TAIEX."""
from datetime import date, datetime, timedelta
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
    def __init__(self, repository, source, tpex_source=None):
        self.repository, self.source = repository, source
        if tpex_source is None:
            from .tpex_quotes import TpexDailyQuotes
            tpex_source = TpexDailyQuotes()
        self.tpex_source = tpex_source

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
            # A future-dated or undated serving row cannot outrank a real
            # observation, and must never be labelled as today's final close.
            if (eod_row and eod_day is not None and
                    eod_day <= now.astimezone(TAIPEI).date() and
                    (not live_row or live_day is None or eod_day >= live_day)):
                result[symbol] = {
                    **eod_row,
                    "source": "core_ohlcv",
                    "route_version": ROUTE_VERSION,
                    # A last-success Core close remains readable for a suspended
                    # security, but it is not a current quote indefinitely.
                    "state": ("eod_final" if eod_day is not None and
                              0 <= (now.astimezone(TAIPEI).date() - eod_day).days <= 7
                              else "stale"),
                    "is_final": True,
                    "price_date": eod_day.isoformat() if eod_day else eod_row.get("price_date"),
                }
                continue
            if not live_row:
                continue
            if live_row.get("source") == "tpex_openapi_eod":
                # Persistent TPEx official close is not a TWSE MIS tick.
                # Published Core wins for the same or newer trade date.
                if live_day is not None and 0 <= (now.astimezone(TAIPEI).date() - live_day).days <= 7:
                    result[symbol] = {
                        **live_row, "source": "tpex_openapi_eod",
                        "route_version": ROUTE_VERSION,
                        "state": "eod_final", "is_final": True,
                        "price_date": live_day.isoformat(),
                    }
                else:
                    result[symbol] = {
                        **live_row, "state": "stale", "is_final": True,
                        "price_date": live_day.isoformat() if live_day else None,
                    }
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
            # The newest legitimate MIS observation may be older than 120s
            # and newer than the latest official close. Keep it as an
            # explicitly STALE/indicative observation; the owner UI can value
            # holdings without falsely marking it as a real-time quote.
            # The formally publishable total remains independently gated.
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
            if identity.get("enabled") is False or market not in {"TWSE", "TWSE_INDEX", "TPEX", "OTC", "TPEX_UNVERIFIED"}:
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
                try:
                    prior = Decimal(str(row.get("previous_close"))) if row.get("previous_close") is not None else None
                    if prior is not None and (not prior.is_finite() or prior <= 0):
                        prior = None
                except (ValueError, TypeError, InvalidOperation):
                    prior = None
                successful[symbol] = {
                    **row,
                    "previous_close": str(prior) if prior is not None else None,
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


    def refresh_tpex(self, identities, *, now=None, as_of=None):
        """Persist official daily sessions, then update latest operational quote.

        The historical write is independent of the latest quote's freshness;
        otherwise an older PIT date becomes irretrievable after next close.
        """
        now = now or datetime.now(TAIPEI)
        scoped = {symbol for symbol, identity in identities.items()
                  if str(identity.get("market") or "").upper()
                  in {"TPEX", "TPEX_UNVERIFIED", "OTC"}
                  and identity.get("enabled") is not False}
        if not scoped:
            return {"status": "idle", "requested": 0, "updated": 0}
        try:
            current = self._live({s: identities[s] for s in scoped})
            persisted = self._eod({s: identities[s] for s in scoped})
            local = now.astimezone(TAIPEI)
            expected_day = as_of or local.date()
            if as_of is None and (local.weekday() >= 5 or (local.hour, local.minute) < (14, 30)):
                expected_day -= timedelta(days=1)
                while expected_day.weekday() >= 5:
                    expected_day -= timedelta(days=1)
            missing_history = set()
            history_reader = getattr(self.repository, "official_eod_quotes", None)
            if history_reader is not None:
                known = history_reader(scoped, expected_day)
                missing_history = {
                    symbol for symbol in scoped if symbol not in known or
                    (as_of is not None and
                     _day(known[symbol]) is not None and _day(known[symbol]) < expected_day)
                }
            due = {
                symbol for symbol in scoped
                if (_day(persisted.get(symbol, {})) is None or _day(persisted[symbol]) < expected_day)
                and (current.get(symbol, {}).get("source") != "tpex_openapi_eod"
                     or _day(current[symbol]) is None or _day(current[symbol]) < expected_day)
            } | missing_history
            if not due:
                return {"status": "fresh", "requested": 0, "updated": 0}
            history = {}
            # Rolling OpenAPI may return HTML/JSONDecodeError in Cloud Run.
            # Dated official history remains independently eligible and
            # checks TPEx's response date; never label newer data as past.
            try:
                history = self.tpex_source.history(due, now)
            except Exception as error:
                LOGGER.warning("official TPEx rolling source unavailable: %s",
                               type(error).__name__)
            on_day = getattr(self.tpex_source, "dated_history", None)
            if on_day is not None:
                covered = {symbol for symbol, rows in history.items()
                           if any(_day(row) == expected_day for row in rows)}
                wanted = due - covered
                if wanted:
                    try:
                        dated = on_day(wanted, expected_day, now)
                        for symbol, records in dated.items():
                            history.setdefault(symbol, []).extend(records)
                    except Exception as error:
                        LOGGER.warning("official TPEx exact-date source unavailable: %s",
                                       type(error).__name__)
            if history:
                writer = getattr(self.repository, "save_official_eod_quotes", None)
                if writer is not None:
                    writer(history)
                latest = {symbol: max(records, key=lambda row: row["price_date"])
                          for symbol, records in history.items() if records}
                if latest:
                    writer_latest = getattr(self.repository, "save_last_quotes", None)
                    if writer_latest is None:
                        raise RuntimeError("persistent latest quote writer unavailable")
                    writer_latest(latest)
            return {"status": "updated" if history else "unavailable",
                    "requested": len(due), "updated": len(history)}
        except Exception as error:
            LOGGER.warning("official TPEx EOD refresh unavailable: %s", type(error).__name__)
            return {"status": "unavailable", "requested": len(scoped), "updated": 0}

    def resolve(self, identities, *, refresh=False, force=False, now=None):
        refresh_result = {"status": "idle", "requested": 0, "updated": 0}
        if refresh:
            refresh_result = self.refresh(identities, force=force, now=now)
        return self.read(identities, now=now), refresh_result
