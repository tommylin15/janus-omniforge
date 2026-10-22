import json
from datetime import date, timedelta, datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/ingestion-core"))
from intelligence_mart.market_screening import market_features, screening_processor
from intelligence_mart.analytics_reader import AnalyticsSnapshot
from intelligence_mart.runtime import AnalysisExecution


def data():
    start = date(2026, 1, 1)
    prices = [{"symbol": "2330", "source_id": "twse", "provenance_id": f"p{i}",
               "observed_at": str(start + timedelta(days=i)), "trade_date": str(start + timedelta(days=i)),
               "close": 100 + i, "volume_shares": 1000, "turnover_twd": 10000} for i in range(121)]
    return {"ohlcv": prices, "benchmark": [dict(r, symbol=None, benchmark_id="TAIEX", close=100 + i / 2)
                                            for i, r in enumerate(prices)]}


def test_features_ranks_missing_and_pit():
    datasets = data()
    datasets["ohlcv"] += [dict(r, symbol="2317") for r in datasets["ohlcv"]]
    rows = market_features(datasets, ("2330", "2317", "missing"), "2026-05-01", "core")
    assert rows == market_features({k: list(reversed(v)) for k, v in datasets.items()},
                                   ("missing", "2317", "2330"), "2026-05-01", "core")
    by_symbol = {r["symbol"]: r for r in rows}
    assert by_symbol["2317"]["candidate_rank"] == 1
    assert by_symbol["2330"]["candidate_rank"] == 2
    metrics = by_symbol["2330"]["metrics"]
    assert metrics["turnover_20d_mean_twd"] == 10000
    assert metrics["volatility_20d_annualized"] > 0
    assert metrics["relative_strength_120d_percent"] == 60
    assert metrics["pe_ratio"] is None
    assert by_symbol["missing"]["candidate_rank"] is None
    assert all(v is None for v in by_symbol["missing"]["cross_sectional_rank"].values())
    datasets["ohlcv"].append(dict(datasets["ohlcv"][-1], trade_date="2026-05-02", close=10000))
    assert market_features(datasets, ("2330",), "2026-05-01", "core")[0]["latest_close"] == 220
    datasets["benchmark"] = [dict(r, source_authorization="blocked") for r in datasets["benchmark"]]
    assert market_features(datasets, ("2330",), "2026-05-01", "core")[0]["metrics"]["relative_strength_20d_percent"] is None


def test_reuse_precedes_read_canary_failure_is_audited_and_tampering_fails(monkeypatch):
    from unittest.mock import Mock
    stores = {"core": {}, "mart": {}}
    class Store:
        def __init__(self, bucket): self.rows = stores[bucket]
        def read(self, name):
            if name not in self.rows: raise FileNotFoundError(name)
            return self.rows[name]
        def create(self, name, raw, kind):
            if name in self.rows: return False
            self.rows[name] = raw
            return True
    core = {"execution_id": "core-ex", "analysis_as_of": "2026-05-01", "snapshot_id": "core", "datasets": data()}
    raw = json.dumps(core).encode()
    stores["core"]["snapshot.json"] = raw
    options = {"analysis_as_of": "2026-05-01", "core_execution_id": "core-ex", "core_snapshot_id": "core",
               "core_snapshot_uri": "gs://core/snapshot.json", "core_snapshot_hash": "sha256:" + sha256(raw).hexdigest()}
    monkeypatch.setenv("MART_BUCKET", "mart")
    monkeypatch.setattr("intelligence_mart.specialist_runtime.load_market_membership",
                        lambda *args: {"symbols": ["2330"], "membership_version": "1", "analysis_as_of": "2026-05-01"})
    reader = SimpleNamespace(read=lambda *a, **kw: AnalyticsSnapshot("core", data(), {"source": "pyiceberg"}), close=Mock())
    factory = Mock(return_value=reader)
    candidate = Mock(side_effect=TimeoutError("secret must not appear in audit"))
    first = screening_processor(AnalysisExecution("first", "screen", (), 0, options), None,
                               store_factory=Store, reader_factory=factory, candidate_factory=candidate)
    assert first["canary"]["candidate"] == "failed" and first["canary"]["error_code"] == "TIMEOUTERROR"
    assert "secret" not in json.dumps(first)
    second = screening_processor(AnalysisExecution("second", "screen", (), 0, options), None,
                                store_factory=Store, reader_factory=factory, candidate_factory=candidate)
    assert second["reused"] and first["screening"] == second["screening"]
    replay = screening_processor(AnalysisExecution("first", "screen", (), 0, options), None,
                                 store_factory=Store, reader_factory=factory, candidate_factory=candidate)
    assert replay["reused"] and replay["artifact_growth_bytes"] == 0
    assert factory.call_count == candidate.call_count == reader.close.call_count == 1
    assert first["specialist_count"] == first["llm_api_tokens"] == 0 and not first["ceo_triggered"]
    name = first["screening"]["artifact_uri"].split("gs://mart/")[1]
    artifact = json.loads(stores["mart"][name])
    artifact["rows"][0]["latest_close"] = 999
    stores["mart"][name] = json.dumps(artifact).encode()
    with pytest.raises(RuntimeError, match="identity/hash"):
        screening_processor(AnalysisExecution("third", "screen", (), 0, options), None,
                            store_factory=Store, reader_factory=factory)


def test_eod_batch_dependency_and_date_override():
    from ingestion_core.batch_controller import due_batches, occurrence_env
    now = datetime(2026, 10, 7, 8, 30, tzinfo=timezone.utc)
    row = next(r for r in due_batches(now) if r[1].name == "market-screening")
    assert row[3] == ["ingestion/2026-10-07/14", "data-supplement/2026-10-07/08"]
    env = dict(occurrence_env(row[1], row[2]))
    assert env["SCREENING_DATE"] == "2026-10-07" and env["MART_OOS_EVALUATION"] == "false"
    assert env["MART_RISK_SHADOW_ENABLED"] == "true"
    assert env["MART_AI_ENABLED"] == "false"
    assert not any(r[1].name == "market-screening" for r in due_batches(now.replace(day=10)))


def test_full_market_reader_covers_all_chunks_and_ranks_globally():
    from intelligence_mart.market_screening import read_market_chunks
    symbols = tuple(str(1000+i) for i in range(1010))
    seen = []
    class Reader:
        def read(self, inputs, chunk, **options):
            seen.extend(chunk)
            assert len(chunk) <= 250 and options['core_snapshot_id'] == 'fixed'
            return AnalyticsSnapshot('fixed', {}, {'source': 'pyiceberg', 'rows_by_dataset': {}})
    rows, telemetry = read_market_chunks(Reader(), {}, symbols, '2026-10-13', 'fixed')
    assert seen == list(symbols) and len(rows) == 1010 and telemetry['chunks'] == 5
    assert all(row['candidate_rank'] is None for row in rows)


def test_screening_retention_is_bounded_to_90_days():
    from intelligence_mart.artifact_retention import clean_specialist_artifacts
    store = SimpleNamespace(bucket="mart", objects=lambda _: [
        {"name": "screening/old.json", "updated": "2026-01-01T00:00:00Z", "size": 100, "generation": 1},
        {"name": "executions/old/screening-manifest.json", "updated": "2026-01-01T00:00:00Z", "size": 50, "generation": 1},
        {"name": "screening/new.json", "updated": "2026-05-01T00:00:00Z", "size": 100, "generation": 1}])
    result = clean_specialist_artifacts(store, apply=False, now=datetime(2026, 5, 2, tzinfo=timezone.utc))
    assert result["planned_objects"] == 2 and result["planned_bytes"] == 150
    store.objects = lambda _: [
        {"name": "screening/old.json", "updated": "2026-01-01T00:00:00Z", "size": 100, "generation": 1},
        {"name": "executions/new/screening-manifest.json", "updated": "2026-05-01T00:00:00Z", "size": 50, "generation": 1}]
    store.read = lambda _: json.dumps({"screening": {"artifact_uri": "gs://mart/screening/old.json"}}).encode()
    assert clean_specialist_artifacts(store, apply=False, now=datetime(2026, 5, 2, tzinfo=timezone.utc))["planned_objects"] == 0

def test_b3_fixed_membership_uses_json_api_listing_without_gcloud():
    import runpy
    script = runpy.run_path(str(Path(__file__).parents[1] / "scripts/gcp/b3-screening-canary.py"))
    membership = {
        "symbols": [str(i) for i in range(500)],
        "membership_version": "fixed-v1",
        "analysis_as_of": "2026-10-06",
    }
    seen = []
    b2 = {
        "MART_BUCKET": "mart",
        "gcs_list_objects": lambda bucket, prefix: [
            {"name": "executions/x/not-relevant.json"},
            {"name": "executions/a/market-membership.json"},
        ],
        "gcs_json": lambda uri: (seen.append(uri) or membership, "abc123"),
    }
    resolved, uri, digest_value = script["fixed_membership"](b2, {"analysis_as_of": "2026-10-06"})
    assert resolved == membership
    assert uri == "gs://mart/executions/a/market-membership.json"
    assert digest_value == "abc123"
    assert seen == [uri]


def test_b3_acceptance_result_is_persisted_to_bounded_prefix(monkeypatch):
    from unittest.mock import patch
    from intelligence_mart.market_screening import run_acceptance

    objects = {}
    class Store:
        def __init__(self, bucket): self.bucket = bucket
        def create(self, name, payload, _content_type):
            key = (self.bucket, name)
            if key in objects:
                return False
            objects[key] = payload
            return True
        def read(self, name):
            return objects[(self.bucket, name)]

    result = {
        "component": "intelligence-mart",
        "operation": "market-screening-acceptance",
        "execution_id": "exec-1",
        "analysis_as_of": "2026-10-06",
        "llm_api_tokens": 0,
    }
    monkeypatch.setenv("MART_BUCKET", "mart")
    monkeypatch.setenv("MART_ACCEPTANCE_RESULT_URI", "gs://mart/acceptance/b3-live/run-1.json")
    with patch("intelligence_mart.specialist_runtime.run_acceptance", return_value=result), \
         patch("ingestion_core.stage.GcsObjectStore", Store):
        assert run_acceptance() == result
    assert json.loads(objects[("mart", "acceptance/b3-live/run-1.json")]) == result



def test_daily_screening_writes_immutable_research_shadow_without_upgrading_user_signal(monkeypatch):
    from unittest.mock import Mock
    from intelligence_mart.risk_shadow import MODEL_SHA256
    stores = {"core": {}, "mart": {}}
    class Store:
        def __init__(self, bucket): self.rows = stores[bucket]
        def read(self, name):
            if name not in self.rows: raise FileNotFoundError(name)
            return self.rows[name]
        def create(self, name, raw, kind):
            if name in self.rows: return False
            self.rows[name] = raw
            return True
    sets = data()
    for r in sets["ohlcv"]:
        r.update(market="TWSE", open=r["close"]*.999, high=r["close"]*1.015,
                 low=r["close"]*.985, quality_flag="pass")
    core = {"execution_id": "core-ex", "analysis_as_of": "2026-05-01",
            "snapshot_id": "core", "datasets": sets}
    raw = json.dumps(core).encode()
    stores["core"]["snapshot.json"] = raw
    options = {"analysis_as_of": "2026-05-01", "core_execution_id": "core-ex",
               "core_snapshot_id": "core", "core_snapshot_uri": "gs://core/snapshot.json",
               "core_snapshot_hash": "sha256:" + sha256(raw).hexdigest()}
    monkeypatch.setenv("MART_BUCKET", "mart")
    monkeypatch.setenv("MART_RISK_SHADOW_ENABLED", "true")
    monkeypatch.setattr("intelligence_mart.specialist_runtime.load_market_membership",
                        lambda *args: {"symbols": ["2330"], "membership_version": "1", "analysis_as_of": "2026-05-01"})
    monkeypatch.setattr("intelligence_mart.coverage.load_target_rows",
                        lambda *args: [{"symbol": "2330", "watchlisted": True, "held": False}])
    reader = SimpleNamespace(read=lambda *a, **kw: AnalyticsSnapshot("core", sets, {"source": "embedded"}), close=Mock())
    class Model:
        def predict(self, matrix):
            import numpy as np
            return np.full(len(matrix), .32)
    result = screening_processor(AnalysisExecution("risk-ex", "screen", (), 0, options), None,
                                 store_factory=Store, reader_factory=lambda *args: reader,
                                 risk_model_factory=Model)
    risk_ref = result["risk_shadow"]
    assert risk_ref["artifact_uri"].startswith("gs://mart/risk-shadow/")
    archived = json.loads(stores["mart"][risk_ref["artifact_uri"][len("gs://mart/"):]])
    assert archived["publication_allowed"] is False
    assert archived["model_sha256"] == MODEL_SHA256
    assert archived["status"] == "SHADOW_UNVALIDATED"
    assert archived["rows"][0]["future_20d_volatility_annualized"] == .32
    assert archived["rows"][0]["publication_allowed"] is False
    second = screening_processor(AnalysisExecution("risk-retry", "screen", (), 0, options), None,
                                 store_factory=Store, reader_factory=lambda *args: reader,
                                 risk_model_factory=Model)
    assert second["reused"] and second["risk_shadow"] == risk_ref

def test_market_screening_stays_full_universe_risk_model_only_selected_targets():
    from intelligence_mart.market_screening import read_market_chunks
    from intelligence_mart.analytics_reader import AnalyticsSnapshot
    import numpy as np
    start = date(2026, 5, 1)
    rows = []
    for sym in ("2330", "2317", "6488"):
        for i in range(125):
            day = start + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            close = 100. + i * .13 + i % 3 * .01
            rows.append({"symbol": sym, "market": "TWSE", "trade_date": day.isoformat(),
                "observed_at": day.isoformat(), "open": close * .99,
                "high": close * 1.02, "low": close * .98, "close": close,
                "volume_shares": 100000, "turnover_twd": 100000 * close,
                "source_id": "twse", "provenance_id": f"{sym}-{i}", "quality_flag": "pass"})
    class Reader:
        def read(self, _inputs, chunk, *, core_snapshot_id, row_limit):
            return AnalyticsSnapshot(core_snapshot_id,
                {"ohlcv": [r for r in rows if r["symbol"] in chunk]}, {"source": "core"})
    class Model:
        def predict(self, x):
            return np.full(len(x), .3)
    as_of = max(r["trade_date"] for r in rows)
    screened, telemetry = read_market_chunks(Reader(), {}, ("2330", "2317", "6488"),
        as_of, "core-fixed", risk_model=Model(), risk_target_symbols=("2330", "6488"))
    assert {x["symbol"] for x in screened} == {"2330", "2317", "6488"}
    assert {x["symbol"] for x in telemetry["risk_shadow"]} == {"2330", "6488"}
    assert telemetry["risk_target_count"] == 2
    assert telemetry["risk_prediction_count"] == 2
    assert all(x["publication_allowed"] is False for x in telemetry["risk_shadow"])
    _, none = read_market_chunks(Reader(), {}, ("2330", "2317", "6488"),
        as_of, "core-fixed", risk_model=Model(), risk_target_symbols=())
    assert none["risk_shadow"] == [] and none["risk_target_count"] == 0

