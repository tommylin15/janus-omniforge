from datetime import date, timedelta
from ingestion_core.data_quality import assess_rows


def test_quality_reports_bad_units_conflicts_and_missing_history_without_exposing_values():
    row = {"symbol": "2330", "fiscal_year": 2026, "fiscal_quarter": 2,
           "statement_type": "income", "metric": "eps_single_quarter", "value": "1.04",
           "unit": "TWD_per_share", "currency": "TWD", "period_basis": "single_quarter",
           "report_scope": "consolidated", "version_at": "2026-10-03T01:00:00Z",
           "availability_at": "2026-10-03T01:00:00Z", "source_id": "mops", "source_document_sha256": "hash"}
    coverage, issues = assess_rows([row, {**row, "value": "2", "unit": "USD"}], [], ("2330",), date(2026, 10, 2))
    assert coverage["2330"]["financial_quarters"] == 1
    assert coverage["2330"]["historical_publication_status"] == "unknown"
    assert {i["reason"] for i in issues} >= {"history_incomplete", "conflicting_version"}
    assert all("value" not in i for i in issues)
    stale = [{"symbol": "2330", "trade_date": date(2020, 1, 1)+timedelta(days=n)} for n in range(121)]
    coverage, _ = assess_rows([], stale, ("2330",), date(2026, 10, 2))
    assert coverage["2330"]["price_trading_dates"] == 0
