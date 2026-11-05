import json
from datetime import date

from services.api.portfolio_value_history import build_portfolio_value_history


def snapshot(day, positions, version=1):
    return {
        "valuation_date": day,
        "ledger_version": version,
        "snapshot_id": f"{day}/{version}",
        "payload": json.dumps({"positions": positions, "ledger_version": version}),
    }


def position(symbol="2330", market="120", price_date="2026-10-20",
             status="available", currency="TWD"):
    return {
        "symbol": symbol, "stock_name": "台積電", "currency": currency,
        "shares": "2", "average_cost": "50", "market_value": market,
        "price_status": status, "price_date": price_date,
    }


def history(snapshots, *, truncated=False):
    return build_portfolio_value_history(
        snapshots, start=date(2026, 10, 1), end=date(2026, 10, 22),
        truncated=truncated)


def test_distinct_real_valuation_days_with_cost_and_value():
    result = history([
        snapshot("2026-10-20", [position()]),
        snapshot("2026-10-21", [position(market="130", price_date="2026-10-21")]),
    ])
    assert result["status"] == "available"
    assert [p["market_value"] for p in result["points"]] == ["120", "130"]
    assert [p["cost_basis"] for p in result["points"]] == ["100", "100"]
    assert result["points"][0]["positions"][0]["symbol"] == "2330"


def test_stale_price_withheld_not_assumed_zero():
    point = history([snapshot("2026-10-20", [position(status="stale")])])["points"][0]
    assert point["status"] == "partial"
    assert point["market_value"] is None
    assert point["positions"][0]["market_value"] is None
    assert point["cost_basis"] == "100"


def test_same_day_newer_ledger_version_and_no_mixed_currency_sum():
    point = history([
        snapshot("2026-10-20", [position()], version=1),
        snapshot("2026-10-20", [position(market="140"),
            position(symbol="AAPL", market="999", currency="USD")], version=3),
    ])["points"][0]
    assert point["ledger_version"] == 3
    assert point["market_value"] == "140"
    assert point["other_currency_excluded"] is True
    assert len(point["positions"]) == 1


def test_single_history_point_is_not_an_invented_line():
    result = history([snapshot("2026-10-20", [position()])])
    assert result["status"] == "insufficient_history"
    assert len(result["points"]) == 1


def test_missing_payload_and_truncation_are_not_full_success():
    result = history([
        {"valuation_date": "2026-10-20", "payload": "{broken"},
        snapshot("2026-10-20", [position()]),
    ], truncated=True)
    assert len(result["points"]) == 1
    assert result["status"] == "partial"
    assert result["truncated"] is True


def test_no_holdings_explicit_zero_not_missing():
    point = history([snapshot("2026-10-20", [])])["points"][0]
    assert point["status"] == "available"
    assert point["market_value"] == "0"
    assert point["cost_basis"] == "0"
