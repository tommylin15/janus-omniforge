import json
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))
from intelligence_mart.specialists import (analyze_specialists, discounted_cash_flow, reverse_dcf,
                                         screening, risk_metrics, digest, validated_inputs)
from intelligence_mart.specialist_runtime import specialist_processor
from intelligence_mart.runtime import AnalysisExecution


def source():
    start = date(2026, 1, 1)
    prices = [{"symbol": "2330", "source_id": "twse", "provenance_id": f"p-{i}",
               "observed_at": str(start + timedelta(days=i)), "trade_date": str(start + timedelta(days=i)),
               "close": 100 + i, "volume_shares": 100000, "turnover_twd": 10000000}
              for i in range(121)]
    return {"ohlcv": prices, "events": [], "benchmark": [dict(r, symbol=None, benchmark_id="TAIEX", close=10000 + i)
                                                            for i, r in enumerate(prices)]}


def test_replay_is_deterministic_and_no_probabilities_are_invented():
    a = analyze_specialists(source(), "2330", "2026-05-01", "core")
    assert a == analyze_specialists(source(), "2330", "2026-05-01", "core")
    assert {r["role"] for r in a} == {"fundamental", "valuation", "quant", "risk", "event"}
    assert all(r["llm_api_tokens"] == 0 and not r["ceo_triggered"] and not r["publication_authority"] for r in a)
    assert next(r for r in a if r["role"] == "quant")["metrics"]["outperform_probability"] is None
    assert all(r["output_hash"] == digest({k: v for k, v in r.items() if k != "output_hash"}) for r in a)


def test_legacy_daily_roles_are_not_supported_by_provider_transports():
    from intelligence_mart.ai_contract import OUTPUT_MODELS, PROVIDER_ROLES
    from intelligence_mart.codex_worker import CodexCLIProvider
    assert PROVIDER_ROLES == {"ceo"}
    assert set(OUTPUT_MODELS) == {"ceo"}
    for role in ("fundamental", "valuation", "positioning", "quant", "event_risk"):
        with pytest.raises(ValueError, match="invalid AI analyst role"):
            CodexCLIProvider().invoke(role, {})


@pytest.mark.parametrize("field", ["availability_at", "published_at", "observed_at", "record_at", "trade_date"])
def test_every_pit_timestamp_is_fenced(field):
    data = source()
    bad = dict(data["ohlcv"][-1], provenance_id="future", close=9999, **{field: "2026-05-02"})
    data["ohlcv"].append(bad)
    rows, _, rejected = validated_inputs(data, "2330", "2026-05-01", "core")
    assert bad not in rows["ohlcv"]
    assert rejected


@pytest.mark.parametrize("observed,accepted", [("2026-05-01T15:59:59Z", True), ("2026-05-01T16:00:00Z", False)])
def test_pit_fence_uses_taipei_end_of_day(observed, accepted):
    data = source()
    data["ohlcv"] = [dict(data["ohlcv"][-1], observed_at=observed)]
    rows, _, _ = validated_inputs(data, "2330", "2026-05-01", "core")
    assert bool(rows["ohlcv"]) is accepted


def test_event_update_does_not_change_price_role_inputs():
    before = {r["role"]: r for r in analyze_specialists(source(), "2330", "2026-05-01", "core")}
    data = source()
    data["events"] = [{"symbol": "2330", "source_id": "mops", "provenance_id": "e1", "severity": "high",
                       "published_at": "2026-05-01", "observed_at": "2026-05-01", "event_type": "earnings"}]
    after = {r["role"]: r for r in analyze_specialists(data, "2330", "2026-05-01", "core")}
    assert before["quant"] == after["quant"]
    assert before["risk"] == after["risk"]
    assert before["event"]["input_hash"] != after["event"]["input_hash"]
    assert after["event"]["metrics"]["max_severity"] == 75


def test_screening_does_not_create_deep_targets_and_has_stable_rank():
    rows = screening(source(), ["2330", "no-data"], "2026-05-01", "core")
    assert rows[0]["candidate_rank"] == 1
    assert rows[1]["candidate_rank"] is None
    assert all(r["llm_api_tokens"] == 0 for r in rows)
    data = source()
    data["financials"] = [{"symbol": "2330", "source_id": "unapproved", "value": 999}]
    assert screening(data, ["2330", "no-data"], "2026-05-01", "core") == rows


def test_screening_rank_compares_the_same_window_for_short_and_long_history():
    data = source()
    data["ohlcv"] += [dict(r, symbol="new") for r in data["ohlcv"][-21:]]
    rows = screening(data, ["2330", "new"], "2026-05-01", "core")
    assert rows[0]["screening_score"] == rows[1]["screening_score"]
    assert rows[0]["metrics"]["return_120d_percent"] is not None
    assert rows[1]["metrics"]["return_120d_percent"] is None


def test_dcf_reverse_dcf_and_invalid_assumptions():
    price = discounted_cash_flow(10, .1, .02, .08)
    assert reverse_dcf(price, 10, .1, .02) == pytest.approx(.08)
    with pytest.raises(ValueError):
        discounted_cash_flow(10, .02, .03, .08)
    with pytest.raises(ValueError):
        discounted_cash_flow(float("nan"), .1, .02, .08)


def test_screening_accepts_exactly_ten_percent_and_requests_discussion_above():
    from intelligence_mart.specialists import screening_quality
    good = {"latest_trade_date": "2026-05-01", "latest_close": 10,
            "latest_volume_shares": 0, "latest_turnover_twd": 0,
            "metrics": {f"return_{w}d_percent": None for w in (5, 20, 60, 120)}}
    bad = dict(good, latest_close=None)
    accepted = screening_quality([good] * 450 + [bad] * 50)
    assert accepted["eod"]["status"] == "accepted"
    assert accepted["eod"]["missing_ratio"] == .1
    poor = screening_quality([good] * 449 + [bad] * 51)
    assert poor["eod"]["status"] == "discussion_required"
    assert not poor["auto_fail"]
    assert accepted["history"]["120"]["status"] == "discussion_required"


def test_beta_joins_same_intervals_and_short_history_is_missing():
    result = risk_metrics({"a": 100, "c": 110}, {"a": 100, "b": 105, "c": 110})
    assert result["aligned_intervals"] == 0
    assert result["beta_120d"] is None
    assert result["volatility_annualized"] is None


def test_evaluation_rejects_label_leakage_and_tied_ranks():
    from intelligence_mart.evaluation import evaluate_predictions, ranks, walk_forward
    assert ranks([1, 1, 3]) == [.5, .5, 2]
    with pytest.raises(ValueError, match="leakage"):
        evaluate_predictions([{"training_label_cutoff": "2026-05-01", "analysis_as_of": "2026-05-01",
                               "outcome_as_of": "2026-05-06"}], cost_bps=10, annual_periods=50)
    result = walk_forward([], model_name="linear", features=["momentum"], cost_bps=10, horizon_days=5)
    assert result["status"] == "insufficient_history"
    assert result["metrics"]["rank_ic"] is None
    assert not result["promotion_eligible"]


def test_core_sample_authorization_uses_validated_source_default():
    from intelligence_mart.evaluation import build_quant_samples, walk_forward
    rows, _ = build_quant_samples(source(), ["2330"], "2026-05-01", "core", 5)
    assert rows and all(r["source_authorization"] == "official" for r in rows)
    result = walk_forward(rows, model_name="linear", features=["momentum_5d"], cost_bps=30, horizon_days=5)
    assert result["status"] == "insufficient_history"


def test_financial_benchmark_does_not_backdate_received_financials():
    from intelligence_mart.evaluation import build_financial_samples
    data = source()
    data["valuation"] = [{"symbol": "2330", "source_id": "twse", "provenance_id": "v1",
        "observed_date": "2026-03-01", "observed_at": "2026-03-01", "availability_at": "2026-05-01",
        "pe_ratio": 20, "pb_ratio": 3, "dividend_yield_percent": 2}]
    samples, exclusions = build_financial_samples(data, ["2330"], "2026-05-01", "core", 5, "valuation")
    assert not samples and exclusions["insufficient_pit_financial_features"] > 0
    data["valuation"][0]["availability_at"] = "2026-03-01"
    samples, _ = build_financial_samples(data, ["2330"], "2026-05-01", "core", 5, "valuation")
    assert samples and all(sample["pe_ratio"] == 20 for sample in samples)


def test_qlib_challenger_replays_and_explains_selected_features():
    import numpy as np
    from intelligence_mart.qlib_double_ensemble.adapter import fit, predict_explained
    rng = np.random.default_rng(17)
    inputs = rng.normal(size=(120, 3))
    labels = inputs[:, 0] * .01 - inputs[:, 1] * .02
    features = ["momentum_5d", "momentum_20d", "momentum_60d"]
    before = np.random.get_state()
    first = predict_explained(fit(inputs, labels, features), inputs[:10], features)
    after = np.random.get_state()
    second = predict_explained(fit(inputs, labels, features), inputs[:10], features)
    assert np.array_equal(before[1], after[1]) and before[2:] == after[2:]
    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))
    assert np.allclose(first[0], first[2] + first[1].sum(axis=1))


def test_ic_decay_uses_the_same_oos_signal_across_future_horizons():
    from intelligence_mart.evaluation import evaluate_predictions
    rows = [{"symbol": "2330", "training_label_cutoff": "2025-01-01", "analysis_as_of": f"2025-02-{i+1:02d}",
        "outcome_as_of": "2025-03-01", "prediction": i / 100, "excess_return": i / 1000,
        "future_outcomes": {"5": {"outcome_as_of": "2025-03-01", "excess_return": i / 1000},
                            "20": {"outcome_as_of": "2025-04-01", "excess_return": -i / 1000}}} for i in range(25)]
    metrics = evaluate_predictions(rows, cost_bps=30, annual_periods=252/5)
    assert metrics["ic_decay"]["5"]["time_series_by_symbol"]["2330"]["rank_ic"] == pytest.approx(1)
    assert metrics["ic_decay"]["20"]["time_series_by_symbol"]["2330"]["rank_ic"] == pytest.approx(-1)
    assert metrics["ic_decay"]["120"]["time_series_by_symbol"]["2330"]["rank_ic"] is None


def test_regime_oos_only_fits_prior_months_and_keeps_research_status():
    import numpy as np
    from datetime import date, timedelta
    from intelligence_mart.evaluation import fit_regime_challenger
    days = [(date(2024, 1, 1)+timedelta(days=i)).isoformat() for i in range(560)
            if (date(2024, 1, 1)+timedelta(days=i)).weekday() < 5]
    rng = np.random.default_rng(17)
    values = rng.normal(size=len(days))*np.where(np.arange(len(days)) % 70 < 35, .005, .02)
    result = fit_regime_challenger(values.tolist(), dates=days)
    assert result["status"] == "research_oos_evaluated" and result["oos_returns"] >= 30
    assert all(f["training_end"] < f["test_start"] <= f["test_end"] for f in result["oos_folds"])
    assert not result["promotion_eligible"]


@pytest.mark.parametrize("model", ["linear", "lightgbm", "catboost", "qlib_double_ensemble"])
def test_real_model_walk_forward_purges_unmatured_labels(model):
    from intelligence_mart.evaluation import walk_forward
    rows = []
    for offset in range(8):
        month = f"2025-{offset + 1:02d}"
        for i in range(50):
            rows.append({"symbol": str(i), "analysis_as_of": month + "-01", "feature_available_at": month + "-01",
                         "label_available_at": month + "-10", "outcome_as_of": month + "-10",
                         "source_authorization": "official", "provenance_id": f"p{offset}-{i}",
                         "momentum": i / 100, "excess_return": i / 1000 - .025})
    result = walk_forward(rows, model_name=model, features=["momentum"], cost_bps=10, horizon_days=5)
    assert result["status"] == "evaluated"
    assert len(result["folds"]) == 5
    assert all(p["training_label_cutoff"] < p["analysis_as_of"] for p in result["predictions"])
    assert all(p["explanation_base_value"] + sum(p["feature_contributions"].values()) == pytest.approx(p["prediction"])
               for p in result["predictions"])
    assert any(p["probability"] is not None for p in result["predictions"])
    assert all(p["probability"] is None or 0 <= p["probability"] <= 1 for p in result["predictions"])
    assert not result["promotion_eligible"]


class Store:
    def __init__(self): self.data = {}
    def create(self, name, data, kind):
        if name in self.data: return False
        self.data[name] = data
        return True
    def read(self, name):
        if name not in self.data: raise FileNotFoundError(name)
        return self.data[name]


def test_runtime_watch_only_held_only_overlap_off_market_and_exit(monkeypatch):
    stores = {"core": Store(), "mart": Store()}
    core = {"execution_id": "core-ex", "snapshot_id": "core", "datasets": source()}
    payload = json.dumps(core).encode()
    stores["core"].data["snapshot.json"] = payload
    options = {"analysis_as_of": "2026-05-01", "core_execution_id": "core-ex", "core_snapshot_id": "core",
               "core_snapshot_uri": "gs://core/snapshot.json", "core_snapshot_hash": "sha256:" + sha256(payload).hexdigest(),
               "schema_version": "1", "feature_version": "2", "model_version": "rules", "governance_snapshot_version": "1"}
    monkeypatch.setenv("MART_BUCKET", "mart")
    monkeypatch.setattr("intelligence_mart.specialist_runtime.load_market_membership",
                        lambda *args: {"symbols": ["2330"], "membership_version": "1", "analysis_as_of": "2026-05-01"})
    members = [{"symbol": "2330", "watchlisted": True, "held": False},
               {"symbol": "2330", "watchlisted": False, "held": True},
               {"symbol": "off-market", "watchlisted": False, "held": True}]
    monkeypatch.setattr("intelligence_mart.coverage.load_target_rows", lambda *args: members)
    run = lambda identity: specialist_processor(AnalysisExecution(identity, "config", ("2330",), 0, options), None,
                                               store_factory=stores.__getitem__, catalog_factory=lambda: SimpleNamespace())
    first = run("ex1")
    assert first["specialist_count"] == 10
    assert first["screening_count"] == 1
    assert first["publishable"] == 0
    assert run("ex1") == {k: v for k, v in first.items() if k != "artifact_hash"}
    saved = json.loads(stores["mart"].read("executions/ex1/specialist-manifest.json"))
    assert "user_id" not in json.dumps(saved)
    assert {r["symbol"] for r in saved["specialists"]} == {"2330", "off-market"}
    members.pop()
    second = run("ex2")
    assert second["specialist_count"] == 5
    assert json.loads(stores["mart"].read("executions/ex1/specialist-manifest.json")) == saved
