"""B7 monthly reconciliation integrity and conservative missing-data semantics."""
import json
from hashlib import sha256
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.monthly_reconciliation import reconcile_monthly_cache
from intelligence_mart.specialist_runtime import _cache_identity
from intelligence_mart.specialists import DEPENDENCIES, FEATURE_VERSION, MODEL_VERSION, VERSION, digest


class MemoryStore:
    def __init__(self):
        self.bucket = "dev-mart"
        self.data = {}
    def read(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]
    def list(self, prefix):
        return tuple(name for name in self.data if name.startswith(prefix))
    def objects(self, prefix):
        return tuple({"name": name, "updated": "2026-10-08T00:00:00Z"}
                     for name in self.data if name.startswith(prefix))


def build_refs(store, symbol="2330"):
    refs = []
    for role in DEPENDENCIES:
        input_hash = f"sha256:{role}-input"
        identity = _cache_identity(symbol, role, input_hash)
        artifact = {"symbol": symbol, "role": role, "input_hash": input_hash,
                    "feature_version": FEATURE_VERSION, "engine_version": VERSION,
                    "model_version": MODEL_VERSION, "core_snapshot_id": "core-a", "status": "ready"}
        artifact["output_hash"] = digest(artifact)
        data = json.dumps(artifact).encode()
        uri = f"gs://{store.bucket}/specialists/{artifact['output_hash'][7:]}.json"
        store.data[uri.split(f"gs://{store.bucket}/", 1)[1]] = data
        artifact_hash = "sha256:" + sha256(data).hexdigest()
        pointer = {"artifact_kind": "mart_specialist_cache_v1", "schema_version": "1.0.0",
                   "cache_identity": identity, "symbol": symbol, "role": role,
                   "input_hash": input_hash, "feature_version": FEATURE_VERSION,
                   "engine_version": VERSION, "model_version": MODEL_VERSION,
                   "source_core_snapshot_id": "core-a", "artifact_uri": uri,
                   "artifact_hash": artifact_hash}
        store.data[f"specialist-cache/v1/{symbol}/{role}/{identity[7:]}.json"] = json.dumps(pointer).encode()
        refs.append({"symbol": symbol, "role": role, "input_hash": input_hash,
                     "cache_identity": identity, "source_core_snapshot_id": "core-a",
                     "artifact_uri": uri, "artifact_hash": artifact_hash, "reused": True})
    return refs


def test_monthly_reconciliation_verifies_all_active_roles_and_marks_missing_b6_partial():
    store = MemoryStore()
    refs = build_refs(store)
    receipt = reconcile_monthly_cache(store, store.bucket, ["2330"], refs, "core-b")
    assert receipt["active_specialist_refs_verified"] == len(DEPENDENCIES)
    assert receipt["reused_specialist_refs_verified"] == len(DEPENDENCIES)
    assert receipt["ml_oos_derived_cache"]["status"] == "missing"
    assert receipt["status"] == "partial"
    assert receipt["champion_promotion"] is False
    assert receipt["llm_api_tokens"] == 0


def test_monthly_reconciliation_fails_closed_on_corrupt_or_missing_pointer():
    store = MemoryStore()
    refs = build_refs(store)
    store.data[refs[0]["artifact_uri"].split(f"gs://{store.bucket}/", 1)[1]] = b"corrupted"
    with pytest.raises(RuntimeError, match="hash mismatch"):
        reconcile_monthly_cache(store, store.bucket, ["2330"], refs, "core-a")
    store = MemoryStore()
    refs = build_refs(store)
    with pytest.raises(RuntimeError, match="coverage mismatch"):
        reconcile_monthly_cache(store, store.bucket, ["2330"], refs[:-1], "core-a")


def test_historical_unreferenced_pointer_not_misreported_as_confirmed_orphan():
    store = MemoryStore()
    refs = build_refs(store)
    store.data["specialist-cache/v1/2330/Quant/historical.json"] = b"{}"
    result = reconcile_monthly_cache(store, store.bucket, ["2330"], refs, "core-a")
    assert result["pointer_inventory"]["unreferenced_candidates"] == 1
    assert result["orphan_classification"] == "unverified_retention_candidates_no_deletion"
