"""B9 Valuation PIT, missing/extreme official features and overfit diagnostics."""
import sys
from datetime import date, timedelta
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.specialists import comparable_valuation_features, analyze_specialists
from intelligence_mart.evaluation import build_financial_samples, walk_forward


def test_official_multiple_guards_keep_null_and_zero_yield():
    values, reasons = comparable_valuation_features({"pe_ratio": None, "pb_ratio": 3, "dividend_yield_percent": 0})
    assert values == {"pe_ratio": None, "pb_ratio": 3., "dividend_yield_percent": 0.}
    assert reasons["pe_ratio"] == "missing_or_nonfinite"
    values, reasons = comparable_valuation_features({"pe_ratio": 999, "pb_ratio": -1, "dividend_yield_percent": 110})
    assert all(v is None for v in values.values())
    assert reasons["pe_ratio"] == "extreme_research_excluded"
    assert reasons["pb_ratio"] == "invalid_nonpositive_or_negative"


def test_relative_valuation_keeps_original_official_and_dcf_missing():
    row = {"symbol": "2330", "source_id": "twse", "provenance_id": "off1",
           "observed_at": "2026-03-01", "observed_date": "2026-03-01",
           "pe_ratio": 500, "pb_ratio": 2.8, "dividend_yield_percent": 0}
    report = analyze_specialists({"valuation": [row]}, "2330", "2026-04-01", "core", roles=["valuation"])[0]
    assert row["pe_ratio"] == 500 and report["metrics"]["pe_ratio"] is None
    assert report["metrics"]["dividend_yield_percent"] == 0
    assert report["metrics"]["dcf_value_per_share"] is None
    assert report["data_quality"]["pe_ratio"] == "extreme_research_excluded"
    assert "no_verified_fcf" in report["data_quality"]["dcf_value_per_share"]
    assert "pe_ratio" in report["missing_data"]
    assert not report["publication_authority"]


def test_sparse_valuation_respects_historical_availability():
    first = date(2026, 1, 1)
    prices = [{"symbol": "2330", "source_id": "twse", "provenance_id": str(i),
               "trade_date": str(first + timedelta(days=i)), "observed_at": str(first + timedelta(days=i)),
               "close": 100+i, "volume_shares": 1000, "turnover_twd": 10000}
              for i in range(121)]
    data = {"ohlcv": prices,
            "benchmark": [{**r, "symbol": None, "benchmark_id": "TAIEX", "close": 10000+i}
                          for i, r in enumerate(prices)],
            "valuation": [{"symbol": "2330", "source_id": "twse", "provenance_id": "v1",
                           "observed_date": "2026-03-01", "observed_at": "2026-03-01",
                           "availability_at": "2026-03-01", "pe_ratio": None, "pb_ratio": 3,
                           "dividend_yield_percent": None}]}
    rows, excluded = build_financial_samples(data, ["2330"], "2026-05-01", "core", 5, "valuation")
    assert rows and all(r["pb_ratio"] == 3 and r["pe_ratio"] is None for r in rows)
    assert excluded["valuation_missing_or_nonfinite"] > 0
    data["valuation"][0]["availability_at"] = "2026-05-01"
    rows, excluded = build_financial_samples(data, ["2330"], "2026-05-01", "core", 5, "valuation")
    assert not rows
    assert excluded["insufficient_pit_financial_features"] > 0


@pytest.mark.parametrize("model_name", ["catboost", "lightgbm"])
def test_sparse_tree_oos_reports_overfit_without_promotion(model_name):
    rows = [{"symbol": str(i), "analysis_as_of": f"2025-{month:02d}-01",
             "feature_available_at": f"2025-{month:02d}-01",
             "outcome_as_of": f"2025-{month:02d}-10",
             "label_available_at": f"2025-{month:02d}-10",
             "source_authorization": "official", "provenance_id": f"p{month}-{i}",
             "pe_ratio": 10+i/5, "pb_ratio": 1+i/20, "dividend_yield_percent": None if i%2 else 2.,
             "excess_return": (i-25)/2000} for month in range(1,9) for i in range(50)]
    result = walk_forward(rows, model_name=model_name,
                          features=["pe_ratio","pb_ratio","dividend_yield_percent"],
                          cost_bps=30, horizon_days=5, allow_missing_features=True)
    assert result["status"] == "evaluated"
    assert result["missing_feature_policy"] == "native_tree_missing_no_imputation"
    assert result["folds"] and all(f["missing_oos_features"]["dividend_yield_percent"] > 0 for f in result["folds"])
    assert all(isinstance(f["overfit_warning"], bool) for f in result["folds"])
    assert not result["promotion_eligible"]


def test_sparse_policy_not_applied_to_linear():
    with pytest.raises(ValueError, match="only supported by tree"):
        walk_forward([], model_name="linear", features=["pe_ratio"], cost_bps=30, horizon_days=5,
                     allow_missing_features=True)
