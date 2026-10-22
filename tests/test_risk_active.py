"""Risk ACTIVE must be target-only, immutable, source pinned and instantly reversible."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))

from intelligence_mart.risk_active import (
    load_active_pointer, build_risk_active_artifact, validate_risk_active_artifact)
from intelligence_mart.risk_activation_runtime import activation_plan
from intelligence_mart.risk_shadow import MODEL_SHA256
from scripts.gcp.risk_registry_cas import _candidate_pointer, BUCKET


class DummyModel:
    def predict(self, features):
        assert features.shape[1] == 8 and features.dtype == np.float32
        return np.repeat(.33, len(features))


def sample():
    from test_risk_shadow import bars
    return bars()


def test_registry_absent_is_deterministic_and_pinned_sha_required():
    class Missing:
        def read(self, name):
            raise FileNotFoundError
    assert load_active_pointer(Missing(), bucket=BUCKET) is None
    assert load_active_pointer(Missing(), bucket="wrong") is None
    class Actual:
        def read(self, name):
            import json
            return json.dumps(_candidate_pointer(
                model_active=True, source_sha="a"*40)).encode()
    assert load_active_pointer(Actual(), bucket=BUCKET)["model_sha256"] == MODEL_SHA256
    with pytest.raises(ValueError, match="bucket"):
        load_active_pointer(Actual(), bucket="wrong")


def test_active_only_ordinary_targets_and_pit_manifest_identity():
    rows = sample()
    date = max(r["trade_date"] for r in rows)
    pointer = _candidate_pointer(model_active=True, source_sha="a"*40)
    artifact = build_risk_active_artifact(
        rows, targets=["2330", "6488", "0050"],
        ordinary_symbols={"2330", "6488"}, as_of=date,
        core_snapshot_id="core-frozen", core_manifest_hash="sha256:"+"b"*64,
        model=DummyModel(), active_pointer=pointer)
    assert [p["symbol"] for p in artifact["rows"]] == ["2330", "6488"]
    assert artifact["target_count"] == 3
    assert artifact["excluded_nonordinary_target_count"] == 1
    assert artifact["excluded_reasons"]["NOT_IN_ORDINARY_STOCK_UNIVERSE_INCLUDING_ETF"] == 1
    assert not any("held" in p or "watchlisted" in p for p in artifact["rows"])
    manifest = {"analysis_as_of": date, "core_snapshot_id": "core-frozen",
                "source_core_manifest_hash": "sha256:"+"b"*64}
    assert set(validate_risk_active_artifact(artifact, manifest)) == {"2330", "6488"}
    with pytest.raises(ValueError):
        validate_risk_active_artifact(artifact, dict(manifest, core_snapshot_id="mismatched"))
    from copy import deepcopy
    changed = deepcopy(artifact)
    changed["rows"][0]["symbol"] = "9999"
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_risk_active_artifact(changed, manifest)
    with pytest.raises(ValueError, match="ACTIVE pointer"):
        build_risk_active_artifact(rows, targets=["2330"], ordinary_symbols={"2330"},
            as_of=date, core_snapshot_id="core", core_manifest_hash="hash",
            model=DummyModel(), active_pointer=_candidate_pointer(
                model_active=False, source_sha="a"*40))


def test_postgres_activation_requires_live_gcs_generation_match():
    active = _candidate_pointer(model_active=True, source_sha="b"*40)
    requested = activation_plan(last=None, requested_mode="ACTIVE",
        expected_mode="DETERMINISTIC", generation=13,
        expected_generation=13, pointer=active)
    assert requested["model_sha256"] == MODEL_SHA256
    assert requested["gcs_registry_generation"] == 13
    with pytest.raises(ValueError, match="generation drift"):
        activation_plan(last=None, requested_mode="ACTIVE",
            expected_mode="DETERMINISTIC", generation=12,
            expected_generation=13, pointer=active)
    with pytest.raises(ValueError, match="mode mismatch"):
        activation_plan(last=None, requested_mode="DETERMINISTIC",
            expected_mode="DETERMINISTIC", generation=13,
            expected_generation=13, pointer=active)
    previous = {"mode": "ACTIVE", "gcs_registry_generation": 13}
    rollback = _candidate_pointer(model_active=False, source_sha="b"*40)
    plan = activation_plan(last=previous, requested_mode="DETERMINISTIC",
        expected_mode="ACTIVE", generation=14,
        expected_generation=14, pointer=rollback)
    assert plan["model_sha256"] is None
    with pytest.raises(ValueError, match="stale"):
        activation_plan(last=previous, requested_mode="DETERMINISTIC",
            expected_mode="DETERMINISTIC", generation=14,
            expected_generation=14, pointer=rollback)
