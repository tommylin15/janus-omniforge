from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from services.api.private_pipeline import calculate_marts, calculate_risk_marts


USER = UUID("00000000-0000-0000-0000-000000000001")


def event(version: int, event_type: str, when: date, *, shares: str = "1", price: str = "100") -> dict:
    return {
        "event_id": uuid4(),
        "user_id": USER,
        "ledger_version": version,
        "event_action": "ORIGINAL",
        "event_type": event_type,
        "trade_date": when,
        "symbol": "2330",
        "shares": Decimal(shares),
        "price": Decimal(price),
        "cash_amount": None,
        "fee": Decimal("0"),
        "tax": Decimal("0"),
        "currency": "TWD",
        "reverses_event_id": None,
    }


def test_position_publishes_canonical_unrealized_return():
    buy = event(1, "BUY", date(2026, 9, 1), shares="2", price="100")

    marts = calculate_marts(
        [buy],
        {"2330": (Decimal("120"), date(2026, 9, 4))},
        date(2026, 9, 4),
    )

    position = marts["mart_user_positions"][0]
    unrealized = marts["mart_user_unrealized_pnl"][0]
    assert position["market_value"] == Decimal("240")
    assert unrealized["unrealized_pnl"] == Decimal("40")
    assert unrealized["unrealized_return"] == Decimal("0.2")


def test_missing_quote_keeps_safe_bounded_reason():
    buy = event(1, "BUY", date(2026, 9, 1))

    marts = calculate_marts([buy], {}, date(2026, 9, 4))

    position = marts["mart_user_positions"][0]
    unrealized = marts["mart_user_unrealized_pnl"][0]
    assert position["price_status"] == "missing"
    assert position["price_date"] is None
    assert position["missing_reason"] == "no_eligible_persisted_ohlcv"
    assert unrealized["unrealized_return"] is None


def test_aggregate_is_withheld_and_identifies_affected_symbols_when_stale():
    buy = event(1, "BUY", date(2026, 9, 1), shares="2", price="100")
    marts = calculate_marts(
        [buy],
        {"2330": (Decimal("120"), date(2026, 9, 3))},
        date(2026, 9, 4),
    )

    risk = calculate_risk_marts(
        [buy],
        marts["mart_user_positions"],
        None,
        {},
        date(2026, 9, 4),
    )
    summary = risk["mart_user_portfolio_summary"][0]

    assert summary["valuation_status"] == "stale"
    assert summary["aggregate_status"] == "withheld"
    assert summary["market_value"] is None
    assert summary["unrealized_pnl"] is None
    assert summary["unrealized_return"] is None
    assert summary["affected_symbol_count"] == 1
    assert summary["affected_symbols"] == '["2330"]'


def test_aggregate_return_is_published_only_for_complete_same_currency_snapshot():
    buy = event(1, "BUY", date(2026, 9, 1), shares="2", price="100")
    marts = calculate_marts(
        [buy],
        {"2330": (Decimal("120"), date(2026, 9, 4))},
        date(2026, 9, 4),
    )

    risk = calculate_risk_marts(
        [buy],
        marts["mart_user_positions"],
        None,
        {},
        date(2026, 9, 4),
    )
    summary = risk["mart_user_portfolio_summary"][0]

    assert summary["aggregate_status"] == "available"
    assert summary["market_value"] == Decimal("240")
    assert summary["cost_basis"] == Decimal("200")
    assert summary["unrealized_pnl"] == Decimal("40")
    assert summary["unrealized_return"] == Decimal("0.2")
    assert summary["affected_symbol_count"] == 0
    assert summary["affected_symbols"] == "[]"
