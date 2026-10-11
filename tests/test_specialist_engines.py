import json
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))
from intelligence_mart.analytics_reader import AnalyticsSnapshot, AnalyticsSnapshotReader, IcebergSnapshotReader
from intelligence_mart.specialists import (analyze_specialists, discounted_cash_flow, reverse_dcf,
                                         screening, risk_metrics, digest, validated_inputs)
from intelligence_mart.specialist_runtime import specialist_processor
from intelligence_mart.storage import load_core_datasets
from intelligence_mart.runtime import AnalysisExecution


def source():
    start = date(2026, 1, 1)
    prices = [{"symbol": "2330", "source_id": "twse", "provenance_id": f"p-{i}",
               "observed_at": str(start + timedelta(days=i)), "trade_date": str(start + timedelta(days=i)),
               "close": 100 + i, "volume_shares": 100000, "turnover_twd": 10000000}
              for i in range(121)]
    return {"ohlcv": prices, "events": [], "benchmark": [dict(r, symbol=None, benchmark_id="TAIEX", close=10000 + i)
                                                            for i, r in enumerate(prices)]}



def test_iceberg_snapshot_reader_preserves_exact_snapshot_semantics():
    class Arrow:
        def to_pylist(self):
            return [
                {"symbol": "2330", "trade_date": "2026-10-06", "close": 100, "provenance_id": "p1"},
                {"symbol": "2330", "trade_date": "2026-10-06", "close": None, "provenance_id": "p2"},
            ]

    class Scan:
        def plan_files(self):
            return [SimpleNamespace(length=120), SimpleNamespace(length=80)]
        def to_arrow(self):
            return Arrow()

    class Table:
        def schema(self):
            return SimpleNamespace(fields=[SimpleNamespace(name="symbol"), SimpleNamespace(name="trade_date")])
        def scan(self, **kwargs):
            assert kwargs["snapshot_id"] == 42
            assert kwargs["limit"] == 11
            assert "row_filter" in kwargs
            return Scan()

    class Catalog:
        def load_table(self, identifier):
            assert identifier == "core.ohlcv_v1"
            return Table()

    manifest = {
        "snapshot_id": "sha256:core",
        "iceberg_tables": {"core.ohlcv_v1": {"snapshot_id": 42}},
    }
    reader = IcebergSnapshotReader(Catalog())
    assert isinstance(reader, AnalyticsSnapshotReader)
    result = reader.read(manifest, ("2330",), core_snapshot_id="sha256:core", row_limit=10)
    assert result.core_snapshot_id == "sha256:core"
    assert len(result.datasets["ohlcv"]) == 2
    assert result.datasets["ohlcv"][1]["close"] is None
    assert result.datasets["ohlcv"][1]["provenance_id"] == "p2"
    assert result.datasets["ohlcv"][1]["__snapshot_id"] == 42
    assert result.telemetry["source"] == "pyiceberg"
    assert result.telemetry["core_snapshot_id"] == "sha256:core"
    assert result.telemetry["total_rows"] == 2
    assert result.telemetry["rows_by_dataset"] == {"ohlcv": 2}
    assert result.telemetry["scan_evidence"]["ohlcv"] == {
        "table_identifier": "core.ohlcv_v1", "snapshot_id": 42, "row_count": 2,
        "symbol_filter_applied": True, "planned_file_count": 2, "planned_scan_bytes": 200,
        "actual_gcs_read_bytes": None, "planning_error_code": None,
    }

    telemetry = {}
    assert load_core_datasets(Catalog(), manifest, ("2330",), row_limit=10, telemetry=telemetry) == result.datasets
    assert telemetry == result.telemetry
    with pytest.raises(ValueError, match="identity mismatch"):
        reader.read(manifest, ("2330",), core_snapshot_id="sha256:different", row_limit=10)


@pytest.mark.parametrize("manifest,identity,limit,message", [
    ({"snapshot_id": "core"}, "", 10, "core_snapshot_id is required"),
    ({}, "core", 10, "missing immutable snapshot identity"),
    ({"snapshot_id": "core"}, "core", 0, "row_limit must be positive"),
    ({"snapshot_id": "core", "iceberg_tables": {"core.ohlcv_v1": {}}}, "core", 10, "immutable snapshot ID"),
    ({"snapshot_id": "core", "iceberg_tables": {"private.ohlcv_v1": {"snapshot_id": 1}}}, "core", 10, "non-Core table"),
    ({"snapshot_id": "core", "datasets": {"ohlcv": [{}, {}]}}, "core", 1, "row limit exceeded"),
])
def test_snapshot_reader_rejects_invalid_fences_before_catalog_access(manifest, identity, limit, message):
    class Catalog:
        def load_table(self, identifier):
            raise AssertionError("invalid read must not access the catalog")
    with pytest.raises(ValueError, match=message):
        IcebergSnapshotReader(Catalog()).read(manifest, ("2330",), core_snapshot_id=identity, row_limit=limit)


def test_snapshot_reader_closes_catalog_engine():
    disposed = []
    reader = IcebergSnapshotReader(SimpleNamespace(engine=SimpleNamespace(dispose=lambda: disposed.append(True))))
    reader.close()
    assert disposed == [True]

def test_replay_is_deterministic_and_no_probabilities_are_invented():
    a = analyze_specialists(source(), "2330", "2026-05-01", "core")
    assert a == analyze_specialists(source(), "2330", "2026-05-01", "core")
    assert {r["role"] for r in a} == {"fundamental", "valuation", "quant", "risk", "event"}
    assert all(r["llm_api_tokens"] == 0 and not r["ceo_triggered"] and not r["publication_authority"] for r in a)
    assert next(r for r in a if r["role"] == "quant")["metrics"]["outperform_probability"] is None
    assert all(r["output_hash"] == digest({k: v for k, v in r.items() if k != "output_hash"}) for r in a)


def test_same_filing_growth_is_model_feature_but_unverified_raw_eps_stays_missing():
    from intelligence_mart.facts import _financial_features_v2
    from intelligence_mart.evaluation import ROLE_FEATURES
    base = {"symbol": "2330", "source_id": "mops", "statement_type": "income", "report_scope": "consolidated",
            "currency": "TWD", "period_basis": "single_quarter", "is_single_quarter": True,
            "fiscal_period_end": "2026-06-30", "availability_at": "2026-10-03T01:00:00Z",
            "financial_feature_version": "same-filing-comparatives-v1"}
    rows = [{**base, "metric": "eps_single_quarter", "unit": "TWD_per_share", "value": "27.25", "share_basis_status": "unknown"},
            {**base, "metric": "eps_yoy_percent_same_filing", "unit": "percent", "value": "77.4"},
            {**base, "metric": "net_income_parent_yoy_percent_same_filing", "unit": "percent", "value": "70"}]
    facts = _financial_features_v2(rows)["fundamental"]
    assert facts["eps_trend_percent"] is None
    assert facts["eps_yoy_percent_same_filing"] == 77.4
    assert set(ROLE_FEATURES["fundamental"]) == {"eps_yoy_percent_same_filing", "net_income_parent_yoy_percent_same_filing"}


def test_financial_history_uses_data_without_proven_original_revision_and_labels_time_assumptions():
    from intelligence_mart.evaluation import financial_training_history, build_financial_samples
    base = {"symbol": "2330", "source_id": "mops", "provenance_id": "filing", "fiscal_year": 2025,
            "fiscal_quarter": 3, "fiscal_period_end": "2025-09-30", "statement_type": "income", "unit": "percent",
            "availability_at": "2026-10-03T01:00:00Z", "observed_at": "2026-10-03T01:00:00Z",
            "publication_time_authoritative": False, "published_at": None, "numeric_revision_verified": False,
            "financial_feature_version": "same-filing-comparatives-v1", "official_filing_uploaded_at": "2025-11-14T15:00:00+08:00"}
    rows = [{**base, "metric": metric, "value": "10", "period_basis": "single_quarter",
             "comparison_period_end": "2024-09-30", "source_document_sha256": "doc-2025q3"}
            for metric in ("eps_yoy_percent_same_filing", "net_income_parent_yoy_percent_same_filing")]
    original = json.dumps(rows, sort_keys=True)
    history = financial_training_history(rows)
    assert history[0]["availability_at"] == "2025-11-14T07:00:00+00:00"
    assert history[0]["financial_training_time_basis"] == "official_filing_upload_current_revision"
    assert history[0]["original_receipt_at"] == base["availability_at"]
    data = source() | {"financials": rows}
    samples, _ = build_financial_samples(data, ["2330"], "2026-05-01", "core", 5, "fundamental")
    assert samples and all(sample["eps_yoy_percent_same_filing"] == 10 for sample in samples)
    assert json.dumps(rows, sort_keys=True) == original
    assumed = financial_training_history([{**rows[0], "official_filing_uploaded_at": None}])[0]
    assert assumed["financial_training_time_basis"] == "period_end_plus_90_days_assumption"
    assert assumed["availability_at"].startswith("2025-12-29")
    accepted, _, _ = validated_inputs({"financials": [assumed]}, "2330", "2025-12-28", "core")
    assert not accepted["financials"]
    blocked, _, _ = validated_inputs({"financials": [{**assumed, "source_id": "unapproved"}]}, "2330", "2026-05-01", "core")
    assert not blocked["financials"]


def test_official_financial_pair_never_mixes_period_basis_revision_or_scope():
    from intelligence_mart.evaluation import _fundamental_filing_features, financial_training_history
    common = {"symbol": "2330", "source_id": "mops", "statement_type": "income",
        "fiscal_year": 2025, "fiscal_quarter": 2, "fiscal_period_end": "2025-06-30",
        "comparison_period_end": "2024-06-30", "report_scope": "consolidated",
        "financial_feature_version": "same-filing-comparatives-v1", "unit": "percent",
        "availability_at": "2025-08-15T01:00:00Z", "provenance_id": "filing",
        "source_document_sha256": "doc-q2"}
    eps, income = ("eps_yoy_percent_same_filing", "net_income_parent_yoy_percent_same_filing")
    rows = [
        {**common, "metric": eps, "period_basis": "single_quarter", "value": "60"},
        {**common, "metric": income, "period_basis": "single_quarter", "value": "40"},
        {**common, "metric": eps, "period_basis": "year_to_date", "value": "-10"},
        {**common, "metric": income, "period_basis": "year_to_date", "value": "-20"},
    ]
    history = financial_training_history(rows)
    assert len(history) == 4  # old dedup silently lost one of the two comparisons
    pit, _, _ = validated_inputs({"financials": history}, "2330", "2026-02-01", "core",
                                 preserve_financial_basis=True)
    assert len(pit["financials"]) == 4  # PIT de-duplication must also preserve both bases
    values, selected, meta = _fundamental_filing_features(history)
    assert values == {income: 40, eps: 60}
    assert meta["financial_period_basis"] == "single_quarter"
    assert len(selected) == 2
    # Newer EPS-only quarter must not be paired with an older income value.
    newer = {**rows[0], "fiscal_year": 2025, "fiscal_quarter": 3,
        "fiscal_period_end": "2025-09-30", "comparison_period_end": "2024-09-30",
        "source_document_sha256": "doc-q3", "value": "99"}
    assert _fundamental_filing_features(rows + [newer])[0] == values
    # Wrong comparison period, different source document or report scope is not a pair.
    for update in ({"comparison_period_end": "2024-03-31"},
                   {"source_document_sha256": "other-filing"},
                   {"report_scope": "separate"}):
        broken = [rows[0], {**rows[1], **update}]
        assert _fundamental_filing_features(broken)[0] is None


def test_fundamental_baselines_share_purged_oos_and_preserve_missing_truth():
    from intelligence_mart.evaluation import walk_forward, ROLE_FEATURES
    rows = []
    for month in range(1, 8):
        for i in range(40):
            date_key = f"2025-{month:02d}-01"
            rows.append({"symbol": f"{i:04d}", "analysis_as_of": date_key,
                "outcome_as_of": f"2025-{month:02d}-08", "label_available_at": f"2025-{month:02d}-09",
                "feature_available_at": f"2025-{month:02d}-01T07:00:00Z",
                "source_authorization": "official", "provenance_id": f"official-{month}-{i}",
                "excess_return": 0.005, "eps_yoy_percent_same_filing": 60,
                "net_income_parent_yoy_percent_same_filing": 40})
    zero = walk_forward(rows, model_name="zero", features=ROLE_FEATURES["fundamental"],
                        cost_bps=30, horizon_days=5)
    rule = walk_forward(rows, model_name="financial_rule", features=ROLE_FEATURES["fundamental"],
                        cost_bps=30, horizon_days=5)
    assert zero["status"] == rule["status"] == "evaluated"
    assert [p["analysis_as_of"] for p in zero["predictions"]] == [
        p["analysis_as_of"] for p in rule["predictions"]]
    assert all(p["prediction"] == 0 for p in zero["predictions"])
    assert all(p["prediction"] == pytest.approx(.005) for p in rule["predictions"])
    assert all(p["explanation_method"] == "fixed_financial_rule" for p in rule["predictions"])
    assert rule["promotion_eligible"] is False
    # An earnings metric is never fabricated to rescue a missing official pair.
    missing, _, reason = __import__("intelligence_mart.evaluation",
        fromlist=["_fundamental_filing_features"])._fundamental_filing_features([])
    assert missing is None and reason == "no_complete_same_filing_comparative_pair"


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


def test_retraining_selects_latest_fenced_snapshot_and_rejects_stale_data():
    from datetime import date
    from hashlib import sha256
    import json
    from types import SimpleNamespace
    from intelligence_mart.specialist_runtime import latest_training_input
    core = {"execution_id": "latest", "analysis_as_of": "2026-10-03", "snapshot_id": "sha256:core",
            "iceberg_tables": {"core.ohlcv_v1": {"snapshot_id": 1}}}
    raw = json.dumps(core).encode()
    store = SimpleNamespace(bucket="dev-core", read=lambda name: raw,
        objects=lambda prefix: [{"name": "executions/old/core-snapshot.json", "updated": "2026-10-02"},
                                {"name": "executions/latest/core-snapshot.json", "updated": "2026-10-03"}])
    result = latest_training_input(store, date(2026, 10, 4))
    assert result["coreSnapshotUri"] == "gs://dev-core/executions/latest/core-snapshot.json"
    assert result["coreSnapshotHash"] == "sha256:" + sha256(raw).hexdigest()
    assert result["analysisAsOf"] == "2026-10-03"
    for today in (date(2026, 10, 2), date(2026, 10, 11)):
        with pytest.raises(ValueError, match="stale"):
            latest_training_input(store, today)


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
    assert len(result["risk_oos_daily"]) == result["oos_returns"]
    assert sum(f["test_returns"] for f in result["oos_folds"]) == len(result["risk_oos_daily"])
    assert all(row["training_end"] < row["date"] and 0 <= row["predicted_high_vol_probability"] <= 1
               and 0 <= row["markov_tail_probability"] <= 1
               and 0 <= row["gaussian_tail_probability"] <= 1
               for row in result["risk_oos_daily"])
    for fold in result["oos_folds"]:
        matching = [row for row in result["risk_oos_daily"] if row["month"] == fold["month"]]
        assert len(matching) == fold["test_returns"]
        assert abs(sum(row["markov_log_score"] for row in matching) -
                   fold["markov_log_score_sum"]) < 1e-5
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
    assert result["protocol_version"] == "taiwan-purged-monthly-v5"
    assert all(p["sample_source_authorization"] == "official" and p["sample_provenance_id"].startswith("p")
               and p["feature_available_at"] == p["analysis_as_of"]
               and p["label_available_at"] >= p["outcome_as_of"] for p in result["predictions"])
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
    monkeypatch.setattr(
        "intelligence_mart.specialist_runtime.iceberg_snapshot_reader_from_environment",
        lambda: (_ for _ in ()).throw(AssertionError("default Iceberg reader should not be constructed")),
    )

    readers = []
    class InjectedReader:
        def __init__(self):
            self.closed = False
            readers.append(self)
        def read(self, manifest, requested_symbols, *, core_snapshot_id, row_limit=250_000):
            assert manifest["snapshot_id"] == core_snapshot_id == "core"
            assert requested_symbols in {("2330",), ("2330", "off-market")}
            datasets = {name: [dict(row) for row in rows] for name, rows in manifest["datasets"].items()}
            rows_by_dataset = {name: len(rows) for name, rows in sorted(datasets.items())}
            return AnalyticsSnapshot(
                core_snapshot_id=core_snapshot_id,
                datasets=datasets,
                telemetry={"source": "injected-test", "core_snapshot_id": core_snapshot_id,
                           "rows_by_dataset": rows_by_dataset, "total_rows": sum(rows_by_dataset.values()),
                           "scan_evidence": {}},
            )
        def close(self):
            self.closed = True

    run = lambda identity: specialist_processor(
        AnalysisExecution(identity, "config", ("2330",), 0, options),
        None,
        store_factory=stores.__getitem__,
        reader_factory=InjectedReader,
    )
    first = run("ex1")
    assert first["specialist_count"] == 10
    assert first["screening_count"] == 1
    assert first["publishable"] == 0
    assert readers and readers[-1].closed
    assert run("ex1") == {k: v for k, v in first.items() if k != "artifact_hash"}
    saved = json.loads(stores["mart"].read("executions/ex1/specialist-manifest.json"))
    assert saved["input_telemetry"]["source"] == "injected-test"
    assert "user_id" not in json.dumps(saved)
    assert {r["symbol"] for r in saved["specialists"]} == {"2330", "off-market"}
    members.pop()
    second = run("ex2")
    assert second["specialist_count"] == 5
    assert readers[-1].closed
    assert json.loads(stores["mart"].read("executions/ex1/specialist-manifest.json")) == saved

    monkeypatch.setattr(InjectedReader, "read", lambda *args, **kwargs: AnalyticsSnapshot("different", {}, {}))
    with pytest.raises(RuntimeError, match="different Core snapshot"):
        run("ex3")
    assert readers[-1].closed
    assert "executions/ex3/specialist-manifest.json" not in stores["mart"].data
