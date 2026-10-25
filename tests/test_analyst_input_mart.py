"""Handoff tests; authored without executing tests or acceptance."""
from datetime import date
from copy import deepcopy
import math
import pytest

from ingestion_core.stock_supplement import revenue_months
from intelligence_mart.analyst_inputs import revenue_rows, _features, bounded_inputs
from intelligence_mart.analytics_reader import IcebergSnapshotReader
from packages.stock_report_policy import report_decision, attach_stock_report, ROLES, VERSION


def test_revenue_window_has_fifteen_calendar_months_across_year():
    assert len(revenue_months(date(2026, 1, 20))) == 15
    assert (2024, 10) in revenue_months(date(2026, 1, 20))
    assert (2025, 12) in revenue_months(date(2026, 1, 20))


def revenue(value, unit):
    return {"symbol": "2330", "period_basis": "monthly", "metric": "monthly_revenue_01",
            "fiscal_year": 2026, "fiscal_month": 1, "unit": unit, "value": value}


def test_units_reuse_identical_amount_but_conflicting_month_stays_missing():
    rows = revenue_rows([revenue(1000, "TWD"), revenue(1, "TWD_thousands")], "2330", "twse")
    assert len(rows) == 1 and rows[0]["revenue_twd"] == 1000
    rows = revenue_rows([revenue(1000, "TWD"), revenue(2, "TWD_thousands")], "2330", "twse")
    assert math.isnan(rows[0]["revenue_twd"])


def test_feature_readiness_does_not_claim_model_compatibility():
    item = _features(["a", "b"], {"a": 0, "b": float("nan"), "target": 3},
                     input_as_of="2026-01", version="fixture")
    assert item["values"] == {"a": 0., "b": None}
    assert item["missing_features"] == ["b"] and not item["feature_ready"]
    assert item["model_compatible"] == "NOT_VERIFIED"
    assert "target" not in item["values"]


def test_shared_benchmark_is_not_filtered_as_stock():
    reader = IcebergSnapshotReader(None)
    result = reader.read({"snapshot_id": "s", "datasets": {
        "ohlcv": [{"symbol": "2330"}, {"symbol": "2882"}],
        "benchmark": [{"symbol": "TAIEX", "benchmark_id": "TAIEX"}]}},
        ("2330",), core_snapshot_id="s")
    assert result.datasets["ohlcv"] == [{"symbol": "2330"}]
    assert len(result.datasets["benchmark"]) == 1


def current(day="2026-10-26", signature="b", close=101):
    return {"analysis_as_of": day, "input_signature": signature, "latest_close": close,
            "model_signature": "m", "financial_input_hash": "f"}


def previous():
    return {"report_as_of": "2026-10-25", "input_signature": "a", "latest_close": 100,
            "model_signature": "m", "financial_input_hash": "f", "policy_version": VERSION}


def test_weekly_report_does_not_run_daily_or_refresh_unchanged_input():
    assert report_decision(current(), previous()) == (False, "reuse_until_change_or_week")
    assert report_decision(current("2026-11-01"), previous()) == (True, "weekly_new_inputs")
    assert report_decision(current("2026-11-01", signature="a"), previous()) == (False, "same_inputs")


@pytest.mark.parametrize("key,value,reason", [
    ("model_signature", "m2", "model_changed"), ("financial_input_hash", "f2", "financial_changed"),
    ("latest_close", 106, "price_move_5pct")])
def test_material_changes_refresh_early(key, value, reason):
    row = current()
    row[key] = value
    assert report_decision(row, previous()) == (True, reason)


def test_report_reuse_preserves_original_date_hash_and_partial_status():
    payload = {"symbol": "2330", "execution_id": "e1", "analysis_as_of": "2026-10-25",
               "specialists": [{"role": role, "status": "partial", "model_status": "unpromoted",
                                "model_version": "fixture"} for role in ROLES]}
    analyst = {"latest_close": 100, "financial_input_hash": "f",
               "roles": {r: {"input_as_of": "2026-10-23", "missing_features": ["x"]} for r in ROLES}}
    old = attach_stock_report(deepcopy(payload), analyst)
    new = attach_stock_report({**payload, "analysis_as_of": "2026-10-26", "execution_id": "e2"},
                              analyst, old)
    assert old["stock_report"] == new["stock_report"]
    assert new["stock_report"]["report_as_of"] == "2026-10-25"
    assert not new["stock_report_refresh"]["generated"]
    assert all(r["status"] == "partial" for r in new["stock_report"]["roles"])
    assert new["stock_report"]["llm_api_tokens"] == 0


def test_future_report_rejected():
    with pytest.raises(ValueError, match="backwards"):
        report_decision(current("2026-10-24"), previous())
