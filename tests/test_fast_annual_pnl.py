"""Fast realized PnL: exact accounting and versioned no-job cache."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from services.api.private_pipeline import TAIPEI

from services.api.fast_annual_pnl import (
    FastPnlTooLarge, FastPnlVersionMoved, _cached_rows, read_annual_pnl,
)

USER = UUID("00000000-0000-0000-0000-000000000001")
OTHER = UUID("00000000-0000-0000-0000-000000000002")


def row(version, kind, when, shares=None, price=None, *, owner=USER, symbol="2330",
        fee=0, tax=0, cash=None, action="ORIGINAL", reverses=None, replaces=None):
    return {
        "user_id": owner, "event_id": f"evt-{owner}-{version}",
        "ledger_version": version, "event_action": action, "event_type": kind,
        "trade_date": when, "symbol": symbol, "currency": "TWD",
        "shares": shares, "price": price, "cash_amount": cash,
        "fee": Decimal(str(fee)), "tax": Decimal(str(tax)),
        "reverses_event_id": reverses, "replaces_event_id": replaces,
    }


class Repository:
    def __init__(self, events_by_user):
        self.events = events_by_user
        self.reads = 0

    def latest_ledger_version(self, owner):
        return max((r["ledger_version"] for r in self.events[owner]), default=0)

    def ledger_for_fast_pnl(self, owner):
        self.reads += 1
        return list(self.events[owner])


def test_cross_year_moving_average_fees_and_cash_dividend():
    events = [
        row(1, "BUY", date(2025, 12, 10), 10, 100, fee=10),
        row(2, "SELL", date(2026, 1, 10), 5, 120, fee=2, tax=3),
        row(3, "CASH_DIV", date(2026, 2, 1), cash=50, fee=1),
    ]
    repo = Repository({USER: events})
    result, version = read_annual_pnl(repo, USER, 2026)
    assert version == 3
    assert len(result) == 1
    assert result[0]["realized_pnl"] == Decimal("139")
    assert result[0]["fees"] == Decimal("3")
    assert result[0]["taxes"] == Decimal("3")
    assert result[0]["cash_dividends"] == Decimal("50")
    assert result[0]["ledger_version"] == 3
    assert result[0]["valuation_date"] == min(
        datetime.now(TAIPEI).date(), date(2026, 12, 31)
    ).isoformat()
    again, _ = read_annual_pnl(repo, USER, 2026)
    assert again == result
    assert repo.reads == 1


def test_reversal_replacement_and_new_version_invalidate_cache():
    original = row(1, "BUY", date(2026, 1, 2), 10, 100)
    sell = row(2, "SELL", date(2026, 2, 2), 5, 110)
    repo = Repository({USER: [original, sell]})
    first, _ = read_annual_pnl(repo, USER, 2026)
    assert first[0]["realized_pnl"] == Decimal("50")
    reversal = row(3, "SELL", date(2026, 2, 2), 5, 110, action="REVERSAL",
                   reverses=sell["event_id"])
    replacement = row(4, "SELL", date(2026, 2, 2), 5, 120,
                      action="REPLACEMENT", replaces=sell["event_id"])
    repo.events[USER].extend([reversal, replacement])
    latest, version = read_annual_pnl(repo, USER, 2026)
    assert version == 4
    assert latest[0]["realized_pnl"] == Decimal("100")
    assert repo.reads == 2


def test_owner_isolation_and_empty_year_zero_not_missing():
    repo = Repository({
        USER: [row(1, "BUY", date(2025, 1, 1), 1, 100)],
        OTHER: [
            row(1, "BUY", date(2025, 12, 1), 1, 100, owner=OTHER),
            row(2, "SELL", date(2026, 1, 1), 1, 150, owner=OTHER),
        ],
    })
    assert read_annual_pnl(repo, USER, 2026)[0] == []
    # The second owner must use its own trade set, not USER's cached zero.
    other, version = read_annual_pnl(repo, OTHER, 2026)
    assert version == 2
    assert other[0]["realized_pnl"] == Decimal("50")


def test_bounded_rejection_and_racing_version_are_explicit():
    class Many(Repository):
        def ledger_for_fast_pnl(self, owner):
            return [None] * 20001

    with pytest.raises(FastPnlTooLarge):
        read_annual_pnl(Many({USER: []}), USER, 2026)

    class Racing(Repository):
        def ledger_for_fast_pnl(self, owner):
            return []
        def latest_ledger_version(self, owner):
            return 1

    with pytest.raises(FastPnlVersionMoved):
        read_annual_pnl(Racing({USER: []}), USER, 2026)
