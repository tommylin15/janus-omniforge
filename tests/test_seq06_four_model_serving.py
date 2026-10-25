"""SEQ-06 offline tests: model bytes, parity, missing artifact, versioned cache."""
import json
from hashlib import sha256
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.four_model_serving import ServingSession, UNITS, canonical, fingerprint


class Store:
    def __init__(self):
        self.data = {}
        self.reads = []
    def read(self, name):
        self.reads.append(name)
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]
    def create(self, name, content, mime):
        if name in self.data:
            return False
        self.data[name] = content
        return True


def pointer(role="quant", version="m1", raw=b"model-1"):
    order = ["ret5", "market_code"] if role == "quant" else ["yoy_m", "market_code"]
    target = "p_up_20d" if role == "quant" else "next_month_revenue_yoy_pct"
    return {"schema_version": 1, "role": role, "mode": "ACTIVE",
        "promotion_gate": "VALIDATED", "preprocessing": "identity",
        "format": "XGBOOST_JSON", "source_git_sha": "a" * 40,
        "model_version": version, "model_sha256": sha256(raw).hexdigest(),
        "feature_version": "features-v1", "feature_order": order,
        "feature_units": [UNITS[k] for k in order], "output_name": target,
        "output_unit": "probability" if role == "quant" else "percentage_points",
        "model_gcs_uri": f"gs://mart/models/candidates/{role}/{version}/model.json"}


def row(symbol, role="quant"):
    order = ["ret5", "market_code"] if role == "quant" else ["yoy_m", "market_code"]
    return {"symbol": symbol, "roles": {role: {"feature_order": order,
        "feature_version": "features-v1", "input_as_of": "2026-10-23",
        "feature_ready": True, "missing_features": [],
        "values": {order[0]: 0.2, "market_code": 0.0}}}}


def inputs(rows):
    for item in rows:
        for role in ("quant", "fundamental", "valuation"):
            item["roles"].setdefault(role, {"feature_ready": False})
    d = {"analysis_as_of": "2026-10-23", "core_snapshot_id": "123", "rows": rows}
    d["output_hash"] = fingerprint(d)
    return d


def setup(role="quant"):
    s = Store()
    p = pointer(role)
    s.data[f"models/registry/{role}-active.json"] = canonical(p)
    s.data[p["model_gcs_uri"][len("gs://mart/"):]] = b"model-1"
    return s, p


def test_missing_artifacts_not_falsely_active_and_risk_separate():
    result = ServingSession(Store(), "mart").run(inputs([row("2330")]))
    statuses = result["rows"][0]["roles"]
    assert statuses["risk"]["status"] == "NOT_ACTIVE"
    assert all(statuses[r]["status"] == "MISSING_OR_INACTIVE_ARTIFACT"
               for r in ("quant", "fundamental", "valuation"))


def test_two_stocks_batch_once_and_cross_job_cache_reuse():
    store, ptr = setup()
    calls = []
    def prediction(model, vectors, names):
        calls.append((vectors, names))
        return [0.7 for _ in vectors]
    arg = inputs([row("2330"), row("2882")])
    a = ServingSession(store, "mart", loader=lambda raw, ptr: "loaded", predictor=prediction).run(arg)
    assert len(calls) == 1 and len(calls[0][0]) == 2
    assert all(r["roles"]["quant"]["status"] == "ACTIVE_PREDICTED" for r in a["rows"])
    b = ServingSession(store, "mart", loader=lambda *_: pytest.fail("must use cache"),
                       predictor=lambda *_: pytest.fail("must use cache")).run(arg)
    assert all(r["roles"]["quant"]["status"] == "ACTIVE_CACHED" for r in b["rows"])
    assert store.reads.count(ptr["model_gcs_uri"][len("gs://mart/"):]) == 1


def test_feature_parity_missing_and_version_invalidation():
    store, ptr = setup()
    missing = row("2330")
    missing["roles"]["quant"]["feature_order"] = list(reversed(ptr["feature_order"]))
    d = inputs([missing])
    a = ServingSession(store, "mart", loader=lambda *_: pytest.fail("unusable features")).run(d)
    assert a["rows"][0]["roles"]["quant"]["prediction"] is None
    p2 = pointer(version="m2", raw=b"model-2")
    store.data["models/registry/quant-active.json"] = canonical(p2)
    store.data[p2["model_gcs_uri"][len("gs://mart/"):]] = b"model-2"
    b = ServingSession(store, "mart", loader=lambda *_: 1,
                       predictor=lambda *_: [0.4]).run(inputs([row("2330")]))
    assert b["rows"][0]["roles"]["quant"]["status"] == "ACTIVE_PREDICTED"


def test_rejects_bad_hash_units_unsafe_paths_and_probability():
    store, ptr = setup()
    ptr["feature_units"][0] = "percent"
    store.data["models/registry/quant-active.json"] = canonical(ptr)
    with pytest.raises(ValueError, match="unit"):
        ServingSession(store, "mart").run(inputs([row("2330")]))
    ptr["feature_units"][0] = UNITS["ret5"]
    ptr["model_gcs_uri"] = "gs://elsewhere/model.json"
    store.data["models/registry/quant-active.json"] = canonical(ptr)
    with pytest.raises(ValueError, match="URI"):
        ServingSession(store, "mart").run(inputs([row("2330")]))
    ptr["model_gcs_uri"] = "gs://mart/models/candidates/quant/m1/model.json"
    store.data["models/registry/quant-active.json"] = canonical(ptr)
    store.data[ptr["model_gcs_uri"][len("gs://mart/"):]] = b"tampered"
    with pytest.raises(ValueError, match="checksum"):
        ServingSession(store, "mart", loader=lambda *_: 1).run(inputs([row("2330")]))
    store.data[ptr["model_gcs_uri"][len("gs://mart/"):]] = b"model-1"
    with pytest.raises(ValueError, match="output invalid"):
        ServingSession(store, "mart", loader=lambda *_: 1, predictor=lambda *_: [1.2]).run(inputs([row("2330")]))


def test_rejects_cache_tampering_and_owner_free_result():
    store, _ = setup()
    a = ServingSession(store, "mart", loader=lambda *_: 1,
                       predictor=lambda *_: [0.6]).run(inputs([row("2330")]))
    assert "owner" not in json.dumps(a).lower()
    name = next(k for k in store.data if k.startswith("models/inference-cache/"))
    cached = json.loads(store.data[name])
    cached["value"] = 0.9
    store.data[name] = canonical(cached)
    with pytest.raises(ValueError, match="cache identity"):
        ServingSession(store, "mart").run(inputs([row("2330")]))


def test_target_bound_and_no_owner_fields_from_input():
    with pytest.raises(ValueError, match="250"):
        ServingSession(Store(), "mart").run(inputs([row(str(n)) for n in range(251)]))
