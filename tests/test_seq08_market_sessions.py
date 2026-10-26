"""SEQ-08: market holidays use observed sessions without stale or target-only ranks."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))

from intelligence_mart.analyst_inputs import latest_eligible_market_session
from intelligence_mart.market_screening import rank_features, eligible_screening_market_date


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


def test_screening_accepts_recent_market_day_but_not_missing_or_stale():
    assert eligible_screening_market_date("2026-10-25", "2026-10-22")
    assert eligible_screening_market_date("2026-10-22", "2026-10-22")
    assert not eligible_screening_market_date("2026-10-25", "2026-10-26")
    assert not eligible_screening_market_date("2026-10-31", "2026-10-22")
    assert not eligible_screening_market_date("2026-10-25", None)
    assert not eligible_screening_market_date("2026-10-25", "invalid")


def test_quant_full_market_21_sessions_ends_at_core_day_not_newer_index_day():
    """Only Core price points inside 21 same-market benchmark sessions count."""
    from datetime import date, timedelta
    from intelligence_mart.market_screening import market_features

    cutoff = date(2026, 10, 22)
    from intelligence_mart.market_sessions import verified_stock_market_day
    days = [(cutoff - timedelta(days=offset)).isoformat()
            for offset in range(70, -1, -1)
            if verified_stock_market_day((cutoff - timedelta(days=offset)).isoformat())][-21:]
    assert len(days) == 21 and days[-1] == "2026-10-22"
    def bar(sym, day, idx):
        return {"symbol": sym, "market": "TWSE", "trade_date": day,
                "observed_at": day, "source_id": "twse",
                "provenance_id": f"stock-{sym}-{day}", "close": 100 + idx,
                "volume_shares": 1000, "turnover_twd": 100_000}
    symbols = [str(i + 1000) for i in range(101)]
    ohlcv = [bar(sym, day, i) for sym in symbols for i, day in enumerate(days)]
    # One held-like ticker misses a market day, and may not borrow a stock-row
    # session (or a rank) from the rest of the public cohort.
    ohlcv.extend(bar("missing", day, i) for i, day in enumerate(days) if i != 10)
    benchmark = [
        {"symbol": None, "benchmark_id": "TAIEX", "index_kind": "price",
         "trade_date": day, "observed_at": day, "source_id": "twse",
         "provenance_id": "index-" + day, "close": 120 + i}
        for i, day in enumerate(days + ["2026-09-25", "2026-10-23"])
    ]
    # An extra benchmark session (even though it is newer than the Core
    # stock cohort) cannot invalidate the already observed 10/22 window.
    rows = market_features({"ohlcv": ohlcv, "benchmark": benchmark},
                           symbols + ["missing"], "2026-10-26", "fixed")
    ranked = {row["symbol"]: row for row in rows}
    assert sum(row["seq08_quant_rank"] is not None for row in rows) == 101
    assert ranked[symbols[0]]["seq08_quant_rank"]["source_trade_date"] == "2026-10-22"
    assert ranked[symbols[0]]["seq08_quant_rank"]["cohort_size"] == 101
    assert ranked[symbols[0]]["seq08_quant_rank_gate"] == "ranked"
    assert ranked["missing"]["seq08_quant_rank"] is None
    assert ranked["missing"]["seq08_quant_rank_gate"] == "core_stock_21_sessions_incomplete"


def test_rank_failure_keeps_specific_input_gate_when_benchmark_has_no_21_sessions():
    from intelligence_mart.market_screening import market_features
    row = {"symbol": "2330", "market": "TWSE", "trade_date": "2026-10-22",
           "observed_at": "2026-10-22", "source_id": "twse",
           "provenance_id": "stock-2330", "close": 100}
    result = market_features({"ohlcv": [row], "benchmark": []},
                             ("2330",), "2026-10-26", "fixed")
    assert result[0]["seq08_quant_rank"] is None
    assert result[0]["seq08_quant_rank_gate"] == "benchmark_21_sessions_missing"


def test_quant_rank_cohort_day_is_dominant_not_one_newer_symbol():
    # Screening may contain a few Core bars beyond the last complete cohort.
    # Their date must not shift everybody else's denominator.
    rows = [sample(i, "twse", "2026-10-22", float(i), "2026-10-26")
            for i in range(101)]
    rows.extend(sample("new-" + str(i), "twse", "2026-10-23", float(i),
                       "2026-10-26") for i in range(3))
    ranked = {r["symbol"]: r for r in rank_features(rows, "2026-10-26")}
    assert ranked["0"]["seq08_quant_rank"]["source_trade_date"] == "2026-10-22"
    assert ranked["0"]["seq08_quant_rank"]["cohort_size"] == 101
    assert all(ranked["new-" + str(i)]["seq08_quant_rank"] is None for i in range(3))
    assert all(ranked["new-" + str(i)]["seq08_quant_rank_gate"] ==
               "not_latest_market_core_session" for i in range(3))


def test_risk_session_alignment_requires_verified_public_cohort_rank():
    from intelligence_mart.analyst_inputs import verified_market_rank
    proof = {"market": "twse", "analysis_as_of": "2026-10-26",
             "source_trade_date": "2026-10-22", "core_snapshot_id": "fixed",
             "source": "full_market_core_same_day_pct_rank",
             "cohort_size": 101, "value": 0.5}
    ctx = {"market": "twse", "latest_day": "2026-10-22",
           "as_of": "2026-10-26", "snapshot": "fixed"}
    assert verified_market_rank(proof, **ctx)
    for key, invalid in [("cohort_size", 8), ("value", None),
                         ("core_snapshot_id", "other"),
                         ("source_trade_date", "2026-10-21"),
                         ("market", "tpex"), ("value", float("nan")),
                         ("source", "owner_eight_stock_rank")]:
        assert not verified_market_rank({**proof, key: invalid}, **ctx)
    assert not verified_market_rank(None, **ctx)


def test_verified_2026_exchange_closures_rejected_for_both_roles():
    from intelligence_mart.market_sessions import verified_stock_market_day
    # 09/25 official Mid-Autumn holiday, 10/23 typhoon shutdown,
    # 10/26 restoration-day observed holiday. None can be an index session.
    for closed in ("2026-09-25","2026-09-28","2026-10-09",
                   "2026-10-23","2026-10-26","2026-10-25"):
        assert not verified_stock_market_day(closed)
    assert verified_stock_market_day("2026-10-22")
    assert verified_stock_market_day("2026-09-24")
    assert not verified_stock_market_day("not-a-date")


def test_no_synthetic_quant_rank_when_stock_mislabeled_as_closed_day():
    from intelligence_mart.market_screening import rank_features
    stale=[sample(i,"twse","2026-09-25",float(i),"2026-09-25")
           for i in range(110)]
    output=rank_features(stale,"2026-09-25")
    assert all(row["seq08_quant_rank"] is None for row in output)
