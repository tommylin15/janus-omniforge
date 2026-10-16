from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from services.api.intraday_quotes import value_holdings

NOW = datetime(2026, 10, 8, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
POSITION = {"symbol": "2382", "currency": "TWD", "shares": "5000",
            "average_cost": "337.5", "ledger_version": 42}
QUOTE = {"price": "324.5", "price_date": "2026-10-08", "state": "intraday",
         "source": "twse_mis", "quote_at": "2026-10-08T09:59:00+08:00"}


def test_held_stock_day_change_uses_prior_official_close_not_cost_basis():
    result = value_holdings([POSITION], {"2382": QUOTE}, NOW, previous_closes={
        "2382": {"previous_close": "335", "previous_close_date": "2026-10-07"},
    })
    row = result["positions"][0]
    assert Decimal(row["change"]) == Decimal("-10.5")
    assert Decimal(row["change_percent"]) == Decimal("-10.5") / Decimal("335")
    assert Decimal(row["day_change_amount"]) == Decimal("-52500")
    assert Decimal(row["unrealized_pnl"]) == Decimal("-65000")
    assert row["previous_close_date"] == "2026-10-07"


def test_known_same_day_delayed_quote_has_indicative_change_not_formal_total():
    quote = {**QUOTE, "state": "stale"}
    result = value_holdings([POSITION], {"2382": quote}, NOW, previous_closes={
        "2382": {"previous_close": "335", "previous_close_date": "2026-10-07"},
    })
    row = result["positions"][0]
    assert Decimal(row["change"]) == Decimal("-10.5")
    assert Decimal(row["day_change_amount"]) == Decimal("-52500")
    assert row["price_status"] == "stale"
    assert row["reference_eligible"] is True
    assert result["items"][0]["aggregate_status"] == "withheld"
    assert result["items"][0]["reference_status"] == "available"


def test_wrong_reference_date_or_invalid_prior_close_never_invents_day_change():
    for prior in [
        {"previous_close": "335", "previous_close_date": "2026-10-08"},
        {"previous_close": "0", "previous_close_date": "2026-10-07"},
    ]:
        row = value_holdings([POSITION], {"2382": QUOTE}, NOW, previous_closes={"2382": prior})["positions"][0]
        assert row["change"] is None
        assert row["change_percent"] is None
        assert row["day_change_amount"] is None


def test_missing_reference_is_explicit_not_zero():
    row = value_holdings([POSITION], {"2382": QUOTE}, NOW)["positions"][0]
    assert row["previous_close"] is None
    assert row["day_change_amount"] is None


def test_previous_close_migration_is_bounded():
    migration = (Path(__file__).parents[1] / "infra/postgres/migrations/"
                 "050_holdings_previous_close_read.sql").read_text()
    assert "GRANT SELECT ON publication.stock_serving_recent TO janus_private_api" in migration
    assert "janus_public_api','private.current_positions','SELECT'" in migration


def test_one_stale_quote_withholds_complete_total_but_keeps_trusted_subtotal():
    fresh = {"price": "100", "price_date": "2026-10-08", "state": "intraday",
             "quote_at": "2026-10-08T09:59:00+08:00"}
    stale = {"price": "90", "price_date": "2026-09-30", "state": "stale",
             "quote_at": "2026-09-30T13:30:00+08:00"}
    rows = [POSITION, {"symbol": "9999", "currency": "TWD",
                       "shares": "2", "average_cost": "80", "ledger_version": 42}]
    result = value_holdings(rows, {"2382": fresh, "9999": stale}, NOW)
    total = result["items"][0]
    assert len(result["positions"]) == 2
    assert result["positions"][1]["market_price"] == "90"
    assert result["positions"][1]["price_status"] == "stale"
    assert total["aggregate_status"] == "withheld"
    assert total["market_value"] is None and total["unrealized_pnl"] is None
    assert total["priced_market_value"] == "500000"
    assert total["priced_symbol_count"] == 1
    assert total["stale_price_count"] == 1
    assert total["affected_symbols"] == ["9999"]


def test_mixed_dates_prevent_cross_session_portfolio_total():
    result = value_holdings(
        [POSITION, {"symbol": "9999", "currency": "TWD", "shares": "2", "average_cost": "80"}],
        {"2382": QUOTE, "9999": {"price": "90", "state": "eod_final",
                                 "price_date": "2026-10-07"}},
        NOW,
    )
    total = result["items"][0]
    assert total["aggregate_status"] == "withheld"
    assert total["aggregate_missing_reason"] == "mixed_price_dates"
    assert total["price_dates"] == ["2026-10-07", "2026-10-08"]
    assert total["market_value"] is None


def test_malformed_quote_only_affects_its_symbol_and_never_publishes_nan():
    positions = [POSITION, {"symbol": "9999", "currency": "TWD", "shares": "1", "average_cost": "80"}]
    for bad in ["NaN", "Infinity", "-2", "not-a-number"]:
        result = value_holdings(
            positions, {"2382": QUOTE, "9999": {"price": bad, "state": "eod_final",
                                                "price_date": "2026-10-08"}}, NOW)
        assert result["positions"][0]["market_value"] == "1622500.0"
        assert result["positions"][1]["market_price"] is None
        assert result["positions"][1]["price_status"] == "missing"
        assert result["items"][0]["market_value"] is None
        assert result["items"][0]["missing_price_count"] == 1
