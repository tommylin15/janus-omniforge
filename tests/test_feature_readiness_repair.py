"""Feature-driven data readiness regressions: no new upstream sources."""
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from ingestion_core.first_batch import normalise_monthly_revenue
from packages.duckdb_query.iceberg import DuckDBIcebergCore
from packages.web_api.core import CoreQueryService, _comparable_single_quarter_eps


def test_revenue_month_is_part_of_current_and_prior_month_identity():
    rows = normalise_monthly_revenue([{
        "資料年月": "11501", "出表日期": "1150210", "公司代號": "6488",
        "營業收入-當月營收": "1,234", "營業收入-上月營收": "0",
    }])
    assert [(r["metric"], r["fiscal_year"], r["fiscal_month"], r["fiscal_quarter"],
             r["fiscal_period_end"], r["period_basis"], r["value"]) for r in rows] == [
        ("monthly_revenue", 2026, 1, 1, "2026-01-31", "monthly", "1234"),
        ("previous_month_revenue", 2025, 12, 4, "2025-12-31", "monthly", "0"),
    ]


def test_revenue_metadata_repair_is_not_skipped_as_same_observation():
    prior = [{
        "symbol": "6488", "fiscal_year": 2026, "fiscal_quarter": 1,
        "statement_type": "monthly_revenue", "metric": "monthly_revenue",
        "source_id": "mops", "value": "1234", "unit": "TWD_thousands",
        "currency": "TWD", "publication_time_authoritative": False,
        "period_basis": None, "fiscal_month": None,
        "fiscal_period_end": "2026-01-31", "availability_at": "2026-02-10T00:00:00Z",
    }]
    updated = [{**prior[0], "period_basis": "monthly", "fiscal_month": 1,
                "observed_at": "2026-10-16T00:00:00Z"}]
    accepted, reused = DuckDBIcebergCore._financial_observations(prior, updated)
    assert accepted == updated and reused == 0
    accepted, reused = DuckDBIcebergCore._financial_observations(updated, updated)
    assert accepted == [] and reused == 1


def _eps(year, quarter, value, **extra):
    return {
        "symbol": "2330", "fiscal_year": year, "fiscal_quarter": quarter,
        "statement_type": "income", "metric": "基本每股盈餘（元）",
        "unit": "TWD_per_share", "currency": "TWD", "source_id": "mops",
        "provenance_id": "official-core", "value": str(value),
        "period_basis": "year_to_date", **extra,
    }


def test_quarterly_eps_never_subtracts_cumulative_eps_without_share_basis():
    # Q1 YTD equals Q1; later YTD EPS may use a different weighted-average
    # denominator, so subtracting Q2 and Q1 would invent a single-quarter EPS.
    rows = [_eps(2026, 1, "-0.40"), _eps(2026, 2, "0.70"),
            _eps(2026, 4, "3.10")]
    result = _comparable_single_quarter_eps(rows)
    assert [(r["fiscal_quarter"], Decimal(r["value"])) for r in result] == [
        (1, Decimal("-0.40"))
    ]
    assert result[0]["period_basis"] == "single_quarter"
    assert result[0]["fiscal_period_end"] == "2026-03-31"
    assert result[0]["calculation_version"] == "mops-q1-ytd-is-quarter-v2"
    assert _comparable_single_quarter_eps([
        _eps(2026, 1, "1", report_scope="consolidated"),
        _eps(2026, 2, "4", report_scope="standalone"),
    ])[0]["value"] == "1"



def test_reported_xbrl_single_quarter_wins_over_derived_basic_eps():
    xbrl = {
        **_eps(2026, 2, "-0.50"), "metric": "eps_single_quarter",
        "period_basis": "single_quarter", "source_id": "mops",
        "fiscal_period_end": "2026-06-30",
    }
    rows = [_eps(2026, 1, "1"), _eps(2026, 2, "4"), xbrl]
    derived = _comparable_single_quarter_eps(rows)
    assert len([r for r in derived if r["fiscal_quarter"] == 2]) == 1
    assert next(r for r in derived if r["fiscal_quarter"] == 2)["value"] == "-0.50"


def test_eps_chart_only_displays_provable_quarters():
    rows = [_eps(2025, 1, "0.20"), _eps(2026, 1, "0.05"),
            _eps(2026, 2, "0.70"), _eps(2026, 4, "2.00")]
    service = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows)
    report = service.visual_series("2330", "eps")
    assert report["data_status"] == "available"
    assert [r["date"] for r in report["points"]] == ["2025-03-31", "2026-03-31"]
    assert [Decimal(r["value"]) for r in report["points"]] == [
        Decimal("0.20"), Decimal("0.05")]
    assert report["calculation_version"] == "eps-official-single-quarter-or-q1-ytd-v2"


def test_ytd_q2_without_official_single_quarter_stays_missing():
    rows = [_eps(2026, 2, "1.00"), _eps(2026, 3, "1.50")]
    report = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows).visual_series("2330", "eps")
    assert report["data_status"] == "missing"
    assert report["missing_reason"] == "no_verified_single_quarter_eps"
    assert report["usable_points"] == 0


def test_revenue_series_does_not_count_prior_month_comparator_as_observation():
    base = {"symbol": "2330", "source_id": "mops", "provenance_id": "official",
            "statement_type": "monthly_revenue", "unit": "TWD_thousands",
            "period_basis": "monthly"}
    rows = [
        {**base, "metric": "monthly_revenue", "fiscal_year": 2026,
         "fiscal_quarter": 1, "fiscal_month": 1, "fiscal_period_end": "2026-01-31", "value": "100"},
        {**base, "metric": "previous_month_revenue", "fiscal_year": 2026,
         "fiscal_quarter": 1, "fiscal_month": 1, "fiscal_period_end": "2026-01-31", "value": "10"},
        {**base, "metric": "monthly_revenue", "fiscal_year": 2026,
         "fiscal_quarter": 1, "fiscal_month": 2, "fiscal_period_end": "2026-02-28", "value": "200"},
    ]
    report = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows).visual_series("2330", "revenue")
    assert report["data_status"] == "available"
    assert [r["value"] for r in report["points"]] == ["100", "200"]



def test_bad_eps_missing_provenance_or_units_never_promotes_to_chart():
    rows = [{**_eps(2026, 1, "0.20"), "provenance_id": ""}]
    assert _comparable_single_quarter_eps(rows) == []
    assert _comparable_single_quarter_eps([{**_eps(2026, 1, "0.20"), "unit": "TWD_thousands"}]) == []

def test_revenue_yoy_is_only_computed_from_verifiable_same_month_last_year():
    base = {"symbol": "2330", "source_id": "mops", "provenance_id": "official",
            "statement_type": "monthly_revenue", "metric": "monthly_revenue",
            "period_basis": "monthly", "unit": "TWD_thousands"}
    rows = [
        {**base, "fiscal_year": 2025, "fiscal_quarter": 3, "fiscal_month": 9,
         "fiscal_period_end": "2025-09-30", "value": "100"},
        {**base, "fiscal_year": 2026, "fiscal_quarter": 3, "fiscal_month": 9,
         "fiscal_period_end": "2026-09-30", "value": "125"},
    ]
    report = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows).visual_series("2330", "revenue")
    assert report["data_status"] == "available"
    assert report["revenue_yoy"] == {
        "status": "available", "percent": "25.00",
        "current_period": "2026-09-30", "comparison_period": "2025-09-30",
        "calculation_version": "same-fiscal-month-official-published-v1",
    }
    missing = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows[1:]).visual_series("2330", "revenue")
    assert missing["revenue_yoy"]["status"] == "missing"
    assert missing["revenue_yoy"]["percent"] is None
    invalid = CoreQueryService(
        lambda *_: [], serving_series=lambda *_: [{**rows[0], "provenance_id": None}, rows[1]]
    ).visual_series("2330", "revenue")
    assert invalid["revenue_yoy"]["status"] == "missing"
    zero = CoreQueryService(
        lambda *_: [], serving_series=lambda *_: [{**rows[0], "value": "0"}, rows[1]]
    ).visual_series("2330", "revenue")
    assert zero["revenue_yoy"]["status"] == "missing"


def test_current_year_mvp_eps_does_not_require_last_year_q4_or_ttm():
    # Both due current-year quarters have official source, units and provenance.
    # A missing 2025Q4 is NOT permission to fabricate a TTM EPS.
    q1 = _eps(2026, 1, "0.35")
    q2 = {**_eps(2026, 2, "0.40"), "metric": "eps_single_quarter",
          "period_basis": "single_quarter", "fiscal_period_end": "2026-06-30"}
    with patch("packages.web_api.core.datetime") as clock:
        clock.now.return_value.date.return_value = date(2026, 10, 17)
        data = CoreQueryService(lambda *_: [], serving_series=lambda *_: [q1, q2]).visual_series("2330", "eps")
    assert data["data_status"] == "available"
    assert data["eps_current_year"] == {
        "year": 2026, "required_quarters": [1, 2],
        "available_quarters": [1, 2], "status": "ready",
        "trailing_four_quarter_status": "not_certified",
        "calculation_version": "official-due-quarters-mvp-v1",
    }
    assert data["usable_points"] == 2


def test_current_year_mvp_eps_missing_q2_cannot_pass():
    with patch("packages.web_api.core.datetime") as clock:
        clock.now.return_value.date.return_value = date(2026, 10, 17)
        data = CoreQueryService(lambda *_: [], serving_series=lambda *_: [
            _eps(2026, 1, "-0.35"),
            _eps(2026, 2, "0.70"),
        ]).visual_series("2330", "eps")
    assert data["data_status"] == "partial"
    assert data["usable_points"] == 1
    assert data["eps_current_year"]["available_quarters"] == [1]
    assert data["eps_current_year"]["status"] == "partial"
    assert data["eps_current_year"]["trailing_four_quarter_status"] == "not_certified"


def test_current_year_eps_cannot_pass_on_old_year_only():
    with patch("packages.web_api.core.datetime") as clock:
        clock.now.return_value.date.return_value = date(2026, 10, 17)
        data = CoreQueryService(lambda *_: [], serving_series=lambda *_: [
            _eps(2025, 1, "0.35"),
        ]).visual_series("2330", "eps")
    assert data["eps_current_year"]["available_quarters"] == []
    assert data["eps_current_year"]["status"] == "partial"


def test_public_api_response_model_preserves_current_year_eps_and_revenue_yoy():
    # FastAPI response_model previously silently dropped both computed fields.
    from services.api.models import PublicVisualSeriesOut
    expected = {
        "schema_version": "visual-series.v1", "symbol": "3231",
        "metric": "eps", "unit": "TWD_per_share",
        "data_status": "available", "points": [
            {"date": "2026-03-31", "value": "0.42", "source_id": "mops",
             "provenance_id": "official-provenance"}
        ],
        "usable_points": 1, "requested_rows": 20,
        "data_as_of": "2026-03-31", "source_ids": ["mops"],
        "missing_reason": None, "calculation_version": "eps-official-single-quarter-or-q1-ytd-v2",
        "eps_current_year": {
            "year": 2026, "required_quarters": [1, 2],
            "available_quarters": [1, 2], "status": "ready",
            "trailing_four_quarter_status": "not_certified",
            "calculation_version": "official-due-quarters-mvp-v1",
        },
    }
    serialized = PublicVisualSeriesOut.model_validate(expected).model_dump(exclude_none=True)
    assert serialized["eps_current_year"] == expected["eps_current_year"]
    revenue = {**expected, "metric": "revenue", "unit": "TWD_thousands",
               "revenue_yoy": {
                   "status": "available", "percent": "25.00",
                   "current_period": "2026-09-30", "comparison_period": "2025-09-30",
                   "calculation_version": "same-fiscal-month-official-published-v1"}}
    assert PublicVisualSeriesOut.model_validate(revenue).model_dump(
        exclude_none=True)["revenue_yoy"] == revenue["revenue_yoy"]
