import json
from datetime import date, timedelta, datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
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
    assert not any(r[1].name == "market-screening" for r in due_batches(now.replace(day=10)))


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
