"""SEQ-05: fail-closed reference card and immutable product projection gates."""
import calendar
from datetime import date
from copy import deepcopy

import pytest

from packages.valuation_range import calculate_reference_range
from packages.valuation_reference import CARD_VERSION, project_reference_card

AS_OF = "2026-10-24"
SNAPSHOT = "126"


def sample(status="available"):
    months = []
    for shift in range(24):
        n = 2024 * 12 + 10 + shift - 1
        year, m = divmod(n, 12)
        end = date(year, m + 1, calendar.monthrange(year, m + 1)[1])
        months.append({
            "metric": "pe_ratio", "observed_date": end.isoformat(),
            "value": str(10 + shift),
        })
    quarters = [{
        "metric": "eps_single_quarter", "fiscal_year": 2025,
        "fiscal_quarter": q, "fiscal_period_end": f"2025-{q * 3:02d}-28",
        "value": "2", "unit": "TWD_per_share",
        "period_basis": "single_quarter", "report_scope": "consolidated",
        "share_basis": "same_share_basis",
    } for q in range(1, 5)]
    return calculate_reference_range(
        symbol="2330", market="twse", security_type="ordinary_stock",
        is_financial=False, as_of=AS_OF,
        financial_rows=[] if status == "missing" else quarters,
        multiple_rows=months, rights_status="approved", price="150",
        price_as_of="2026-10-23",
    )


def card(result):
    return project_reference_card(
        result, symbol="2330", as_of=AS_OF, core_snapshot_id=SNAPSHOT,
    )


def test_price_band_comes_only_from_verified_rv02_numbers():
    result = sample()
    assert result["status"] == "available"
    value = card(result)
    assert value["schema_version"] == CARD_VERSION
    assert value["role"] == "valuation"
    assert value["valid_month_count"] == 24
    assert value["lower"] == result["lower"]
    assert value["mid"] == result["mid"]
    assert value["upper"] == result["upper"]
    assert value["input_hash"] == result["input_hash"]
    assert value["is_ml_forecast"] is False
    assert value["is_trading_signal"] is False


def test_missing_eps_retains_real_coverage_without_any_price():
    result = sample("missing")
    assert result["status"] == "missing"
    assert result["valid_month_count"] == 24
    value = card(result)
    assert value["valid_month_count"] == 24
    assert value["lower"] is value["mid"] is value["upper"] is None
    assert value["price_gap_to_reference_mid_pct"] is None


@pytest.mark.parametrize("change", [
    {"symbol": "2882"},
    {"as_of": "2026-10-23"},
    {"schema_version": "unknown"},
    {"method_version": "unknown"},
    {"input_hash": "not-a-hash"},
    {"valid_month_count": 23},
    {"rights_status": "unknown"},
    {"security_type": "etf"},
    {"lower": "-3"},
    {"mid": "0"},
    {"upper": "0"},
])
def test_available_price_fails_closed_under_identity_or_basis_drift(change):
    bad = {**sample(), **change}
    with pytest.raises(ValueError, match="valuation_reference_"):
        card(bad)


def test_missing_must_not_leak_stale_price():
    bad = {**sample("missing"), "mid": "200"}
    with pytest.raises(ValueError, match="null_prices"):
        card(bad)


def test_malformed_asof_rejected():
    with pytest.raises(ValueError, match="source_identity_mismatch|date_invalid"):
        project_reference_card(
            sample(), symbol="2330", as_of="2026-10-23",
            core_snapshot_id=SNAPSHOT,
        )
