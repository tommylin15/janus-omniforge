"""SEQ-05: pinned Core -> Mart reference -> Fact Pack/API contract checks."""
import calendar
from datetime import date, timedelta

import pytest

from intelligence_mart.valuation_reference import reference_from_core
from packages.valuation_reference import validate_published_card

AS_OF = "2026-10-24"
SNAPSHOT = "6880250134433223964"


def _datasets(symbol="2330", months=24, include_financial=True, source="mops"):
    rows = []
    for shift in range(months):
        total = 2024 * 12 + 10 - 1 + shift
        year, m = divmod(total, 12)
        month = m + 1
        day = date(year, month, calendar.monthrange(year, month)[1])
        while day.weekday() > 4:
            day -= timedelta(days=1)
        rows.append({"symbol": symbol, "market": "twse",
                     "observed_date": day.isoformat(),
                     "pe_ratio": str(11 + shift), "pb_ratio": "2.5",
                     "source_id": "twse", "provenance_id": "from-core"})
    finances = []
    if include_financial:
        for q in range(1, 5):
            end = date(2025, q * 3, calendar.monthrange(2025, q * 3)[1])
            finances.append({"symbol": symbol, "metric": "eps_single_quarter",
                             "fiscal_year": 2025, "fiscal_quarter": q,
                             "fiscal_period_end": end.isoformat(),
                             "period_basis": "single_quarter", "unit": "TWD_per_share",
                             "report_scope": "consolidated", "share_basis": "same_actual_shares",
                             "value": "2.5", "availability_at": "2026-01-10",
                             "source_id": source, "provenance_id": "from-core"})
    return {"valuation": rows, "financials": finances, "ohlcv": []}


def _card(data, symbol="2330", market="twse"):
    return reference_from_core(
        data, symbol=symbol, as_of=AS_OF, core_snapshot_id=SNAPSHOT,
        market=market, latest_close="150", latest_trade_date="2026-10-23")


def test_proven_official_inputs_produce_only_one_non_ml_valuation_reference():
    card = _card(_datasets())
    assert card["status"] == "available"
    assert card["valid_month_count"] == 24
    assert card["classification"]["industry"] == "半導體業"
    assert card["input_refs"]["financial_source"] == "core.financials_v1/pinned"
    assert card["input_refs"]["core_snapshot_id"] == SNAPSHOT
    assert card["is_ml_forecast"] is False
    assert card["is_trading_signal"] is False
    assert validate_published_card(card, symbol="2330", as_of=AS_OF,
                                   core_snapshot_id=SNAPSHOT)["mid"] == card["mid"]


def test_two_stock_real_gap_semantics_keep_null_prices():
    ts = _card(_datasets(months=12, include_financial=False))
    bank = _card(_datasets(symbol="2882", months=1, include_financial=False),
                 symbol="2882")
    assert (ts["status"], ts["valid_month_count"], ts["excluded_reasons"]) == (
        "missing", 12, ["four_quarter_eps_missing"])
    assert (bank["status"], bank["valid_month_count"], bank["excluded_reasons"]) == (
        "missing", 1, ["bvps_missing"])
    for x in (ts, bank):
        assert x["lower"] is x["mid"] is x["upper"] is None
        validate_published_card(x, symbol=x["symbol"], as_of=AS_OF,
                                core_snapshot_id=SNAPSHOT)


def test_unknown_stock_no_reference_without_reclassification_guess():
    assert _card(_datasets("2317"), symbol="2317") is None


@pytest.mark.parametrize("source", ["yahoo-finance", "unreviewed-provider"])
def test_third_party_requires_explicit_control_review(source):
    result = _card(_datasets(source=source))
    assert result["status"] == "blocked_rights"
    assert result["mid"] is None


def test_market_mismatch_never_creates_a_price():
    with pytest.raises(ValueError, match="market_identity_conflict"):
        _card(_datasets(), market="tpex")


def test_snapshot_mismatch_or_price_on_missing_rejected_before_api():
    card = _card(_datasets(months=12, include_financial=False))
    with pytest.raises(ValueError, match="identity_invalid"):
        validate_published_card(card, symbol="2882", as_of=AS_OF,
                                core_snapshot_id=SNAPSHOT)
    card["mid"] = "999"
    with pytest.raises(ValueError, match="missing_price_invalid"):
        validate_published_card(card, symbol="2330", as_of=AS_OF,
                                core_snapshot_id=SNAPSHOT)
