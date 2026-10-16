"""Feature-driven data readiness regressions: no new upstream sources."""
from decimal import Decimal

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
