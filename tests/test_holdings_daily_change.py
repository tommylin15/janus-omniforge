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


def test_stale_or_wrong_reference_date_does_not_publish_day_change():
    for quote, prior in [
        ({**QUOTE, "state": "stale"}, {"previous_close": "335", "previous_close_date": "2026-10-07"}),
        (QUOTE, {"previous_close": "335", "previous_close_date": "2026-10-08"}),
        (QUOTE, {"previous_close": "0", "previous_close_date": "2026-10-07"}),
    ]:
        row = value_holdings([POSITION], {"2382": quote}, NOW, previous_closes={"2382": prior})["positions"][0]
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
