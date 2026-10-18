"""DRL-01 reporting never weakens the official market denominators or PIT."""
from datetime import date, timedelta

from ingestion_core.readiness import summarize_readiness


AS_OF = date(2026, 10, 16)


def _fixture():
    members = ([{"symbol": str(1000+i), "market": "TWSE"} for i in range(10)]
               + [{"symbol": str(2000+i), "market": "TPEX"} for i in range(10)])
    sessions = [AS_OF-timedelta(days=i+1) for i in range(21)]
    benchmark = [{"benchmark_id": "TAIEX", "trade_date": d.isoformat(),
                  "source_id": "taiex", "provenance_id": "b"} for d in sessions]
    prices = []
    for market, base, eligible in (("TWSE", 1000, 9), ("TPEX", 2000, 7)):
        for i in range(eligible):
            for day in sessions[:20]:
                prices.append({"market": market, "symbol": str(base+i),
                               "trade_date": day.isoformat(), "close": "10",
                               "source_id": market.lower(), "provenance_id": "p"})
    focused = [{"symbol": "1000", "trade_date": (AS_OF-timedelta(days=i+1)).isoformat(),
                "close": "1", "source_id": "twse", "provenance_id": "p"}
               for i in range(120)]
    financials = []
    # Thirteen immediately due months ending September 2026.
    for i in range(13):
        index = 2026*12+8-i
        year, month = divmod(index, 12)
        month += 1
        end = date(year, month+1, 1)-timedelta(days=1) if month != 12 else date(year, 12, 31)
        financials.append({"symbol": "1000", "source_id": "mops", "provenance_id": "m",
                           "statement_type": "monthly_revenue", "metric": "monthly_revenue",
                           "value": "1000", "availability_at": "2026-10-01T00:00:00Z",
                           "fiscal_period_end": end.isoformat(), "fiscal_month": month,
                           "period_basis": "monthly", "unit": "TWD_thousands"})
    for quarter, end in enumerate(("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"), 1):
        financials.append({"symbol": "1000", "source_id": "mops", "provenance_id": "m",
                           "statement_type": "income", "metric": "eps_single_quarter",
                           "value": "1.25", "availability_at": "2026-10-01T00:00:00Z",
                           "fiscal_period_end": end, "fiscal_quarter": quarter,
                           "period_basis": "single_quarter", "unit": "TWD_per_share"})
    return members, benchmark, prices, financials, focused


def _report(members, benchmark, prices, financial, focused):
    return summarize_readiness(
        members, benchmark, prices, financial, focused, {"1000"},
        snapshot_ids={"ohlcv": "1", "benchmark": "2", "financials": "3"},
        as_of=AS_OF, market_version="universe-verified")


def test_drl_market_boundaries_and_contiguous_financial_windows():
    report = _report(*_fixture())
    assert report["market_price_window"]["TWSE"]["status"] == "PASS"
    assert report["market_price_window"]["TPEX"]["status"] == "PASS"
    assert report["market_price_window"]["TWSE"]["coverage"] == .9
    assert report["market_price_window"]["TPEX"]["coverage"] == .7
    assert report["monthly_revenue_13"]["qualified"] == 1
    assert report["monthly_revenue_13"]["status"] == "PARTIAL"
    assert report["monthly_revenue_13"]["markets"]["TWSE"] == {
        "expected": 10, "qualified": 1, "coverage": 0.1,
        "minimum_coverage": 0.9, "status": "PARTIAL",
    }
    assert report["monthly_revenue_13"]["markets"]["TPEX"]["qualified"] == 0
    assert report["eps_4_comparable"]["qualified"] == 1
    assert report["eps_4_comparable"]["markets"]["TWSE"]["qualified"] == 1
    assert report["eps_4_comparable"]["markets"]["TPEX"]["qualified"] == 0
    assert report["focus_120d"]["qualified"] == 1
    assert report["historical_pit_certified"] is False
    assert report["canonical_mutation"] is False


def test_drl_missing_benchmark_session_is_not_reported_as_pass():
    members, benchmark, prices, financial, focused = _fixture()
    report = _report(members, benchmark[:20], prices, financial, focused)
    assert report["market_price_window"]["TWSE"]["status"] == "PARTIAL"
    assert report["market_price_window"]["TWSE"]["observed_sessions"] == 20


def test_drl_source_and_price_provenance_cannot_be_faked_by_row_counts():
    members, benchmark, prices, financial, focused = _fixture()
    prices = [{**row, "provenance_id": None} if row["market"] == "TPEX" else row for row in prices]
    report = _report(members, benchmark, prices, financial, focused)
    assert report["market_price_window"]["TPEX"]["symbols_with_20_of_21_sessions"] == 0
    assert report["market_price_window"]["TPEX"]["status"] == "PARTIAL"


def test_drl_nonconsecutive_months_and_cumulative_eps_do_not_qualify():
    members, benchmark, prices, financial, focused = _fixture()
    financial = [r for r in financial if not (
        r["metric"] == "monthly_revenue" and r["fiscal_month"] == 8
    ) and not (r["metric"] == "eps_single_quarter" and r["fiscal_quarter"] == 3)]
    financial.append({"symbol": "1000", "source_id": "mops", "provenance_id": "m",
                      "statement_type": "income", "metric": "eps_year_to_date",
                      "value": "2.0", "availability_at": "2026-10-01T00:00:00Z",
                      "fiscal_period_end": "2025-09-30", "unit": "TWD_per_share",
                      "period_basis": "year_to_date"})
    report = _report(members, benchmark, prices, financial, focused)
    assert report["monthly_revenue_13"]["qualified"] == 0
    assert report["eps_4_comparable"]["qualified"] == 0



def test_readiness_unfiltered_financial_scan_omits_none_predicate():
    """A None PyIceberg row_filter raises NotImplementedError in the binder."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from ingestion_core.readiness import _scan
    table = MagicMock()
    table.schema.return_value.fields = [
        SimpleNamespace(name="symbol"), SimpleNamespace(name="metric")]
    table.current_snapshot.return_value = SimpleNamespace(snapshot_id=123)
    table.scan.return_value.to_arrow.return_value.to_pylist.return_value = [
        {"symbol": "2330", "metric": "eps"}]
    core = MagicMock()
    core.table_exists.return_value = True
    core.table_identifier.return_value = "core.financials_v1"
    core.catalog.load_table.return_value = table
    rows, snapshot_id = _scan(core, "financials", ("symbol", "metric"))
    assert rows == [{"symbol": "2330", "metric": "eps"}]
    assert snapshot_id == "123"
    table.scan.assert_called_once_with(
        snapshot_id=123, selected_fields=("symbol", "metric"))

    sentinel = object()
    table.scan.reset_mock()
    _scan(core, "financials", ("symbol", "metric"), row_filter=sentinel)
    table.scan.assert_called_once_with(
        snapshot_id=123, selected_fields=("symbol", "metric"),
        row_filter=sentinel)
