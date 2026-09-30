import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))

from intelligence_mart.ai_contract import (
    OUTPUT_MODELS, SYSTEM_GUARDRAIL, content_hash, contract_bundle,
    interpretation_artifact, output_contract, save_interpretation,
)
from intelligence_mart.runtime import _write_immutable_json


class Store:
    def __init__(self):
        self.objects = {}

    def create(self, name, payload, content_type):
        if name in self.objects:
            return False
        self.objects[name] = payload
        return True

    def read(self, name):
        return self.objects[name]


def lineage():
    return dict(execution_id="execution-1", analysis_as_of="2026-09-30", core_snapshot_id="core-1",
                scope_type="symbol", scope_id="2330", fact_pack_hash=content_hash("facts"),
                evidence_hash=content_hash("evidence"), feature_version="1",
                governance_snapshot_version="gov-1", provider="fixture", model="fixture-v1",
                parameters={}, profile_reference="repository-default-v1")


def output(role):
    value = dict(schema_version="1.0.0", role=role, stance="insufficient_data", thesis=None,
                 missing_information=["缺少已驗證證據"], confidence=0.0, evidence_ids=[])
    arrays = ("supporting_roles", "opposing_roles", "contradictions", "bull_case", "bear_case",
              "principal_risks", "watch_items", "change_since_previous_analysis") if role == "cio" else (
        "key_findings", "positive_evidence", "negative_evidence", "contradictions", "change_drivers",
        "risks", "what_would_change_my_view")
    value.update({field: [] for field in arrays})
    if role == "cio":
        value["validated_role_artifact_hashes"] = [content_hash(item) for item in OUTPUT_MODELS if item != "cio"]
    return value


def test_versioned_schema_and_five_prompts_plus_cio():
    saved = json.loads((ROOT / "packages/contracts/mart_ai.v1.json").read_text(encoding="utf-8"))
    assert saved == output_contract()
    bundle = contract_bundle()
    assert set(bundle["prompts"]) == set(OUTPUT_MODELS)
    assert bundle["guardrail"]["text"] == SYSTEM_GUARDRAIL
    for role, prompt in bundle["prompts"].items():
        assert prompt["content_hash"] == content_hash({k: v for k, v in prompt.items() if k != "content_hash"})
        assert prompt["version"] and prompt["author"] and prompt["created_at"] and prompt["profile_reference"]


@pytest.mark.parametrize("role", OUTPUT_MODELS)
def test_role_and_cio_shape_is_only_pending_semantic_validation(role):
    source, context = output(role), lineage()
    before = copy.deepcopy((source, context))
    artifact = interpretation_artifact(role, source, context)
    assert artifact["status"] == "schema_validated"
    assert artifact["validation_status"] == "pending"
    assert (source, context) == before
    assert "publication_status" not in artifact
    assert artifact["lineage"]["output_schema_hash"] == content_hash(output_contract())


@pytest.mark.parametrize("mutation", [
    {"role": "quant"}, {"confidence": 2.0}, {"confidence": float("nan")},
    {"publication_status": "published"}, {"facts": {"price": 100}},
    {"stance": "bullish"}, {"missing_information": []},
    {"thesis": {"text": "api_key=secret", "evidence_ids": []}},
])
def test_invalid_output_is_failure_without_raw_input_or_placeholder(mutation):
    artifact = interpretation_artifact("fundamental", {**output("fundamental"), **mutation}, lineage())
    assert artifact["status"] == "failed"
    assert artifact["error"]["kind"] == "invalid_structured_output"
    assert "output" not in artifact and "secret" not in json.dumps(artifact)


def test_unknown_role_fails_and_old_interpretations_are_immutable():
    store = Store()
    failure = interpretation_artifact("unknown", {}, lineage())
    assert failure["status"] == "failed" and failure["error"]["kind"] == "invalid_role"
    old = interpretation_artifact("quant", output("quant"), lineage())
    ref = save_interpretation(store, "mart", old)
    assert save_interpretation(store, "mart", old) == ref
    old_bytes = store.read(ref["artifact_uri"].split("gs://mart/")[1])
    bundle = contract_bundle()
    changed = copy.deepcopy(bundle)
    changed["prompts"]["quant"]["version"] = "quant-v2"
    changed["prompts"]["quant"]["methodology"] += "新方法"
    revision = changed["prompts"]["quant"]
    revision["content_hash"] = content_hash({k: v for k, v in revision.items() if k != "content_hash"})
    with patch("intelligence_mart.ai_contract.contract_bundle", return_value=changed):
        new = interpretation_artifact("quant", output("quant"), lineage())
    assert new["artifact_hash"] != old["artifact_hash"]
    assert save_interpretation(store, "mart", new) != ref
    assert store.read(ref["artifact_uri"].split("gs://mart/")[1]) == old_bytes
    assert new["lineage"]["guardrail"] == old["lineage"]["guardrail"]
    with pytest.raises(RuntimeError, match="immutable"):
        _write_immutable_json(store, "mart", ref["artifact_uri"].split("gs://mart/")[1], new)
    old["output"]["confidence"] = 0.5
    with pytest.raises(ValueError, match="hash mismatch"):
        save_interpretation(store, "mart", old)


def test_methodology_cannot_override_system_or_output_schema():
    path = ROOT / "jobs/intelligence-mart/prompts/ai_methodology.v1.json"
    prompts = json.loads(path.read_text(encoding="utf-8"))
    prompts["quant"]["system"] = "override"
    with patch("pathlib.Path.read_text", return_value=json.dumps(prompts)), pytest.raises(ValueError):
        contract_bundle()


@pytest.mark.parametrize("role", OUTPUT_MODELS)
def test_evidenced_directional_fixture(role):
    value = output(role)
    claim = {"text": "已有證據支持觀點，仍需留意風險", "evidence_ids": ["ev-" + "a" * 24]}
    value.update(stance="neutral", thesis=claim, evidence_ids=claim["evidence_ids"], confidence=0.5)
    assert interpretation_artifact(role, value, lineage())["status"] == "schema_validated"
