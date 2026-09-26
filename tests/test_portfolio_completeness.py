from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from services.api.private_pipeline import calculate_marts, calculate_risk_marts
from services.api.repository import PostgresWorkspaceRepository
from services.api.store import PrivateIcebergStore


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


def test_position_identity_is_canonical_and_missing_identity_is_explicit():
    buy = event(1, "BUY", date(2026, 9, 1))

    resolved = calculate_marts(
        [buy],
        {"2330": (Decimal("120"), date(2026, 9, 4))},
        date(2026, 9, 4),
        {"2330": {"name": "台積電", "market": "TWSE", "enabled": True}},
    )["mart_user_positions"][0]
    unresolved = calculate_marts(
        [buy],
        {"2330": (Decimal("120"), date(2026, 9, 4))},
        date(2026, 9, 4),
        {},
    )["mart_user_positions"][0]

    assert resolved["stock_name"] == "台積電"
    assert resolved["identity_status"] == "available"
    assert resolved["identity_missing_reason"] is None
    assert unresolved["stock_name"] is None
    assert unresolved["identity_status"] == "missing"
    assert unresolved["identity_missing_reason"] == "stock_master_not_found"


def test_repository_reads_stock_identity_from_canonical_stock_master():
    class Rows:
        def fetchall(self):
            return [{"symbol": "2330", "name": "台積電", "market": "TWSE", "enabled": True}]

    class Connection:
        def execute(self, sql, values):
            assert "FROM control.stock_master" in sql
            assert values == (["2330", "9999"],)
            return Rows()

    repository = object.__new__(PostgresWorkspaceRepository)

    @contextmanager
    def connection():
        yield Connection()

    repository._connection = connection
    assert repository.stock_identities({"9999", "2330"}) == {
        "2330": {"symbol": "2330", "name": "台積電", "market": "TWSE", "enabled": True}
    }


def test_private_store_additively_evolves_position_schema(tmp_path):
    from pyiceberg.catalog.sql import SqlCatalog

    warehouse = (tmp_path / "warehouse").as_posix()
    catalog = SqlCatalog("test", uri="sqlite:///" + (tmp_path / "catalog.db").as_posix(), warehouse=warehouse)
    store = PrivateIcebergStore(catalog, warehouse)
    base = {
        "user_id": str(USER),
        "symbol": "2330",
        "currency": "TWD",
        "ledger_version": 1,
        "valuation_date": "2026-09-04",
        "shares": "1",
        "average_cost": "100",
        "market_price": "120",
        "market_value": "120",
        "price_status": "available",
        "price_date": "2026-09-04",
        "lineage": "{}",
        "cost_basis_method": "MOVING_AVERAGE",
    }
    store.upsert("mart_user_positions", [base])
    store.upsert("mart_user_positions", [{
        **base,
        "stock_name": "台積電",
        "identity_status": "available",
        "identity_missing_reason": None,
        "missing_reason": None,
    }])

    fields = {field.name for field in catalog.load_table("private.mart_user_positions").schema().fields}
    assert {"stock_name", "identity_status", "identity_missing_reason", "missing_reason"} <= fields
