"""SEQ-08: market holidays use observed sessions without stale or target-only ranks."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))

from intelligence_mart.analyst_inputs import latest_eligible_market_session
from intelligence_mart.market_screening import rank_features


def test_last_observed_trading_session_on_long_weekend():
    assert latest_eligible_market_session(
        "2026-10-22", ["2026-10-20", "2026-10-21", "2026-10-22"], "2026-10-25"
    ) == "2026-10-22"
    assert latest_eligible_market_session(
        "2026-10-22", ["2026-10-22", "2026-10-23"], "2026-10-25"
    ) is None  # stock is halted/missing while market has newer session
    assert latest_eligible_market_session(
        "2026-10-22", ["2026-10-22"], "2026-10-31"
    ) is None  # never serve stale indefinitely
    assert latest_eligible_market_session(
        "2026-10-26", ["2026-10-26"], "2026-10-25"
    ) is None  # future session
    assert latest_eligible_market_session(None, [], "2026-10-25") is None


def sample(symbol, market, latest, ret, as_of="2026-10-25"):
    return {
        "symbol": str(symbol),
        "latest_trade_date": latest,
        "metrics": {
            "return_20d_percent": ret,
            "relative_strength_20d_percent": None,
            "turnover_20d_mean_twd": None,
        },
        "screening_score": None,
        "seq08_quant_rank_input": {
            "market": market, "ret20": ret,
            "core_snapshot_id": "core-full", "analysis_as_of": as_of,
        },
    }


def test_holiday_rank_uses_latest_whole_market_session_not_owner_subset():
    rows = [sample(i, "twse", "2026-10-22", float(i//2)) for i in range(101)]
    rows += [sample("stale", "twse", "2026-10-21", -10)]
    rows += [sample("other-market", "tpex", "2026-10-22", 1000.)]
    ranked = {r["symbol"]: r for r in rank_features(rows, "2026-10-25")}
    first = ranked["0"]["seq08_quant_rank"]
    assert first["source_trade_date"] == "2026-10-22"
    assert first["analysis_as_of"] == "2026-10-25"
    assert first["cohort_size"] == 101
    assert first["value"] == 1.5/101
    assert ranked["100"]["seq08_quant_rank"]["value"] == 1.
    assert ranked["stale"]["seq08_quant_rank"] is None
    assert ranked["other-market"]["seq08_quant_rank"] is None


def test_holiday_rank_fails_closed_when_cohort_incomplete_or_old():
    assert all(r["seq08_quant_rank"] is None for r in
               rank_features([sample(i, "twse", "2026-10-22", i) for i in range(8)],
                             "2026-10-25"))
    assert all(r["seq08_quant_rank"] is None for r in
               rank_features([sample(i, "twse", "2026-10-22", i) for i in range(101)],
                             "2026-10-31"))
