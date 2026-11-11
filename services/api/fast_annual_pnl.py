"""Owner-scoped, bounded annual realized PnL, independent of Private Iceberg.

Cash realized PnL only depends on ledger events.  The small process-local cache
is keyed by owner/year/ledger version and is NOT a canonical publication.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any

from .private_pipeline import TAIPEI, calculate_marts


class FastPnlTooLarge(ValueError):
    pass


class FastPnlVersionMoved(RuntimeError):
    pass


@lru_cache(maxsize=256)
def _cached_marts(repository: Any, user_id: Any, year: int, version: int) -> dict[str, tuple[dict[str, Any], ...]]:
    """Compute all three ledger-derived breakdowns once per owner/year/version.

    This is a short-lived derived view, not a publication to Private Mart.
    Unlike the persisted snapshots it is never stale after a new ledger event.
    """
    events = repository.ledger_for_fast_pnl(user_id)
    if len(events) > 20000:
        raise FastPnlTooLarge("owner ledger exceeds bounded inline path")
    actual_version = max((int(row["ledger_version"]) for row in events), default=0)
    if actual_version != version:
        raise FastPnlVersionMoved("ledger changed during inline calculation")
    # Identical moving-average, fee, dividend and reversal semantics for annual,
    # monthly and per-symbol numbers. No market network, GCS or Iceberg reads.
    marts = calculate_marts(events, {}, date(year, 12, 31))
    return {
        key: tuple(dict(row) for row in marts[key] if row["year"] == year)
        for key in ("mart_user_annual_pnl", "mart_user_monthly_ledger_summary",
                    "mart_user_symbol_ledger_summary")
    }


@lru_cache(maxsize=256)
def _cached_rows(repository: Any, user_id: Any, year: int, version: int) -> tuple[dict[str, Any], ...]:
    return _cached_marts(repository, user_id, year, version)["mart_user_annual_pnl"]


def read_pnl_breakdowns(repository: Any, user_id: Any, year: int) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """All realized PnL views at one ledger version; one cached calculation."""
    for _ in range(3):
        version = int(repository.latest_ledger_version(user_id))
        try:
            tables = _cached_marts(repository, user_id, year, version)
        except FastPnlVersionMoved:
            continue
        if int(repository.latest_ledger_version(user_id)) == version:
            as_of = min(datetime.now(TAIPEI).date(), date(year, 12, 31)).isoformat()
            return ({
                "annual": [{**row, "valuation_date": as_of}
                           for row in tables["mart_user_annual_pnl"]],
                "monthly": [{**row, "valuation_date": as_of}
                            for row in tables["mart_user_monthly_ledger_summary"]],
                "symbols": [{**row, "valuation_date": as_of}
                            for row in tables["mart_user_symbol_ledger_summary"]],
            }, version)
    raise FastPnlVersionMoved("ledger advanced during inline calculation")


def read_annual_pnl(repository: Any, user_id: Any, year: int) -> tuple[list[dict[str, Any]], int]:
    """Read from a validated per-ledger-version cache or calculate inline."""
    for _ in range(3):
        version = int(repository.latest_ledger_version(user_id))
        try:
            rows = _cached_rows(repository, user_id, year, version)
        except FastPnlVersionMoved:
            continue
        if int(repository.latest_ledger_version(user_id)) == version:
            # Annual PnL is trade-derived.  Never label a current-year
            # response as the future December 31 valuation date; update the
            # displayed as-of day even when cached numbers are unchanged.
            as_of = min(datetime.now(TAIPEI).date(), date(year, 12, 31))
            return [{**dict(row), "valuation_date": as_of.isoformat()} for row in rows], version
    raise FastPnlVersionMoved("ledger advanced during inline calculation")
