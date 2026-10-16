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


def test_quarterly_eps_requires_adjacent_ytd_with_matching_scope():
    rows = [_eps(2026, 1, "-0.40"), _eps(2026, 2, "0.70"),
            _eps(2026, 4, "3.10")]
    derived = _comparable_single_quarter_eps(rows)
    assert [(r["fiscal_quarter"], Decimal(r["value"])) for r in derived] == [
        (1, Decimal("-0.40")), (2, Decimal("1.10"))
    ]
    assert all(r["period_basis"] == "single_quarter" for r in derived)
    assert derived[0]["fiscal_period_end"] == "2026-03-31"
    assert derived[1]["fiscal_period_end"] == "2026-06-30"
    assert _comparable_single_quarter_eps([_eps(2026, 1, "1", report_scope="consolidated"),
                                            _eps(2026, 2, "4", report_scope="standalone")])[0]["value"] == "1"


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


def test_eps_chart_displays_qualified_quarter_not_cumulative_ytd():
    rows = [_eps(2026, 1, "0.20"), _eps(2026, 2, "0.05"),
            _eps(2026, 4, "2.00")]
    service = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows)
    report = service.visual_series("2330", "eps")
    assert report["data_status"] == "available"
    assert [r["date"] for r in report["points"]] == ["2026-03-31", "2026-06-30"]
    assert [Decimal(r["value"]) for r in report["points"]] == [Decimal("0.20"), Decimal("-0.15")]
    assert report["calculation_version"] == "eps-single-quarter-with-qualified-ytd-difference-v1"


def test_bad_eps_missing_provenance_or_units_never_promotes_to_chart():
    rows = [{**_eps(2026, 1, "0.20"), "provenance_id": ""}]
    assert _comparable_single_quarter_eps(rows) == []
    assert _comparable_single_quarter_eps([{**_eps(2026, 1, "0.20"), "unit": "TWD_thousands"}]) == []
