"""RV-02 pure unit tests: no network, DB, model training or publication."""
import calendar
from decimal import Decimal
from datetime import date

import pytest

from packages.valuation_range import calculate_reference_range


def quarter(year, q, value="1.5", **overrides):
    return {
        "fiscal_year": year, "fiscal_quarter": q, "metric": "eps_single_quarter",
        "unit": "TWD_per_share", "period_basis": "single_quarter",
        "share_basis": "reported_unadjusted", "report_scope": "consolidated",
        "value": value, **overrides,
    }


def months(count=24, *, metric="pe_ratio"):
    out = []
    for n in range(count):
        index = 2024 * 12 + 10 + n - 1
        year, month = divmod(index, 12)
        month += 1
        out.append({
            "observed_date": f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}",
            "metric": metric, "value": str(10 + n),
        })
    return out


def data(**override):
    params = dict(
        symbol="2330", market="twse", security_type="ordinary_stock",
        is_financial=False, as_of="2026-10-24",
        financial_rows=[quarter(2025, q) for q in range(1, 5)],
        multiple_rows=months(), rights_status="approved",
        price="129", price_as_of="2026-10-23",
    )
    params.update(override)
    return params


def test_pe_quantile_exact_and_deterministic():
    result = calculate_reference_range(**data())
    assert result["status"] == "available"
    assert result["valid_month_count"] == 24
    assert result["financial_period"] == "2025Q4"
    assert tuple(Decimal(result[key]) for key in ("lower", "mid", "upper")) == (Decimal("94.50"), Decimal("129.00"), Decimal("163.50"))
    assert result["price_gap_to_reference_mid_pct"] == "0"
    assert result["historical_pit_status"] == "not_verified"
    assert result["input_hash"] == calculate_reference_range(**data())["input_hash"]


def test_etf_not_applicable_even_with_valid_facts():
    result = calculate_reference_range(**data(security_type="etf"))
    assert result["status"] == "not_applicable"
    assert result["mid"] is None


def test_explicit_denied_or_unknown_rights_never_prices():
    for rights in ("denied", "unknown"):
        result = calculate_reference_range(**data(rights_status=rights))
        assert result["status"] == "blocked_rights"
        assert result["mid"] is None


def test_ttm_must_be_four_consecutive_single_quarters():
    rows = [quarter(2025, q) for q in (1, 2, 4, 4)]
    result = calculate_reference_range(**data(financial_rows=rows))
    assert result["status"] == "missing"
    assert result["mid"] is None


def test_eps_cumulative_and_unknown_share_basis_are_blocked():
    rows = [quarter(2025, q) for q in range(1, 5)]
    rows[0]["period_basis"] = "ytd"
    assert calculate_reference_range(**data(financial_rows=rows))["status"] == "blocked_basis"
    rows[0]["period_basis"] = "single_quarter"
    rows[0]["share_basis"] = ""
    assert calculate_reference_range(**data(financial_rows=rows))["status"] == "blocked_basis"


def test_nonpositive_ttm_eps_does_not_hardcode_pe_range():
    rows = [quarter(2025, q, "-1") for q in range(1, 5)]
    result = calculate_reference_range(**data(financial_rows=rows))
    assert result["status"] == "missing"
    assert "nonpositive_ttm_eps" in result["excluded_reasons"]


def test_future_financial_fact_cannot_leak_to_asof():
    rows = [quarter(2025, q) for q in range(1, 5)]
    rows[-1]["source_published_at"] = "2026-10-25T01:00:00Z"
    result = calculate_reference_range(**data(financial_rows=rows))
    assert result["status"] == "missing"


def test_less_than_24_months_is_limited_without_price_band():
    result = calculate_reference_range(**data(multiple_rows=months(23)))
    assert result["status"] == "limited"
    assert result["valid_month_count"] == 23
    assert result["mid"] is None


def test_conflicting_same_month_and_future_month_excluded():
    entries = months()
    entries.append({**entries[1], "value": "999"})
    entries.append({"observed_date": "2026-10-31", "metric": "pe_ratio", "value": "999"})
    result = calculate_reference_range(**data(multiple_rows=entries))
    assert result["status"] == "limited"
    assert result["valid_month_count"] == 23


def test_invalid_ratio_nan_and_midmonth_are_excluded():
    entries = months()
    entries[0]["value"] = "NaN"
    entries[1]["observed_date"] = "2024-11-15"
    result = calculate_reference_range(**data(multiple_rows=entries))
    assert result["status"] == "limited"
    assert result["valid_month_count"] == 22


def test_financial_stock_uses_bvps_and_pb_only():
    financial = [{
        "metric": "bvps", "fiscal_year": 2026, "fiscal_quarter": 2,
        "unit": "TWD_per_share", "share_basis": "reported",
        "value": "20",
    }]
    result = calculate_reference_range(**data(
        is_financial=True, financial_rows=financial,
        multiple_rows=months(metric="pb_ratio"),
        price="430", price_as_of="2026-10-24",
    ))
    assert result["status"] == "available"
    assert result["basis_type"] == "bvps"
    assert result["financial_period"] == "2026Q2"
    assert Decimal(result["mid"]) == Decimal("430")


def test_negative_bvps_or_bad_share_basis_fails_closed():
    row = {
        "metric": "bvps", "fiscal_year": 2026, "fiscal_quarter": 2,
        "unit": "TWD_per_share", "share_basis": "reported", "value": "-5",
    }
    result = calculate_reference_range(**data(
        is_financial=True, financial_rows=[row], multiple_rows=months(metric="pb_ratio")
    ))
    assert result["status"] == "missing"
    row["value"] = "5"
    row["share_basis"] = ""
    assert calculate_reference_range(**data(
        is_financial=True, financial_rows=[row], multiple_rows=months(metric="pb_ratio")
    ))["status"] == "blocked_basis"


def test_future_price_never_produces_gap_even_with_valid_range():
    result = calculate_reference_range(**data(price_as_of="2026-10-25"))
    assert result["status"] == "available"
    assert result["price_gap_to_reference_mid_pct"] is None


def test_invalid_identity_and_date_rejected():
    with pytest.raises(ValueError, match="invalid_valuation_as_of"):
        calculate_reference_range(**data(as_of="2026-10-99"))
    with pytest.raises(ValueError, match="invalid_valuation_identity"):
        calculate_reference_range(**data(market="unknown"))
