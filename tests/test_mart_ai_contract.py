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


from intelligence_mart.ai_validation import validate_role, summarize_roles
sys.path.insert(0, str(ROOT / "tests"))
from test_intelligence_mart_pipeline import report as canonical_report


def grounded_fixture(role, source=None):
    source = source or canonical_report()
    pack = next(p for p in source["fact_packs"] if p["pack_type"] == role)
    context = {key: source[key] for key in ("execution_id", "analysis_as_of", "core_snapshot_id",
                                           "governance_snapshot_version")}
    context.update(scope_type=source["scope"]["type"], scope_id=source["scope"]["id"])
    context.update({key: pack[key] for key in ("fact_pack_hash", "evidence_hash", "feature_version")})
    context.update(provider="fixture", model="fixture-v1", parameters={}, profile_reference="repository-default-v1")
    value = output(role)
    value["missing_information"] = pack["missing_data"] or ["研究資料仍有限"]
    if pack["evidence_ids"]:
        claim = dict(text="依已驗證證據維持中性，仍需觀察", evidence_ids=pack["evidence_ids"])
        value.update(stance="neutral", thesis=claim, evidence_ids=pack["evidence_ids"])
    return source, value, context


@pytest.mark.parametrize("role", list(OUTPUT_MODELS)[:-1])
def test_semantic_validation_replay_and_no_publication(role):
    source, value, context = grounded_fixture(role)
    before = copy.deepcopy(source)
    artifact = interpretation_artifact(role, value, context)
    result = validate_role(artifact, source)
    assert result["status"] == "validated", result["errors"]
    assert validate_role(artifact, source) == result
    assert source == before and result["publication_authority"] is False
    store = Store()
    assert save_interpretation(store, "mart", result) == save_interpretation(store, "mart", result)


@pytest.mark.parametrize("mutation,reason", [
    ({"thesis": {"text": "沒有來源", "evidence_ids": ["ev-" + "f" * 24]}}, "invalid_claim_evidence"),
    ({"evidence_ids": []}, "claim_coverage_mismatch"),
    ({"missing_information": []}, "missing_information_omitted"),
    ({"thesis": {"text": "價格999元", "evidence_ids": None}}, "ungrounded_numeric_claim"),
    ({"thesis": {"text": "價格三百元", "evidence_ids": None}}, "ungrounded_numeric_claim"),
])
def test_invalid_claims_blocked(mutation, reason):
    source, value, context = grounded_fixture("valuation")
    mutation = copy.deepcopy(mutation)
    if mutation.get("thesis", {}).get("evidence_ids", []) is None:
        mutation["thesis"]["evidence_ids"] = value["evidence_ids"]
    value.update(mutation)
    result = validate_role(interpretation_artifact("valuation", value, context), source)
    assert result["status"] == "blocked" and reason in result["errors"]


def test_numeric_grounding_requires_exact_supplied_key_and_value():
    source, value, context = grounded_fixture("valuation")
    value["thesis"]["text"] = "pe_ratio=15.0"
    assert validate_role(interpretation_artifact("valuation", value, context), source)["status"] == "validated"
    for text in ("pe_ratio=16.0", "pe_ratio=15.00", "pe_ratio=15.0%", "new_ratio=15.0", "pe_ratio=15.0 目標價300"):
        value["thesis"]["text"] = text
        assert "ungrounded_numeric_claim" in validate_role(interpretation_artifact("valuation", value, context), source)["errors"]


@pytest.mark.parametrize("kind", ["future", "unauthorized", "snapshot", "stale", "duplicate", "unit", "provenance"])
def test_evidence_revalidated_even_when_hashes_are_recomputed(kind):
    source, value, context = grounded_fixture("valuation")
    selected = [e for e in source["evidence"] if e["evidence_id"] in value["evidence_ids"]]
    evidence = selected[0]
    if kind == "future":
        evidence["availability_at"] = "2099-01-01T00:00:00Z"
    elif kind == "unauthorized":
        evidence["source_authorization"] = "blocked"
    elif kind == "snapshot":
        evidence["core_snapshot_id"] = "other"
    elif kind == "stale":
        for item in selected:
            if item["dataset_id"] == evidence["dataset_id"]:
                item["observed_at"] = "2020-01-01T00:00:00Z"
    elif kind == "duplicate":
        source["evidence"].append(copy.deepcopy(evidence))
        selected.append(evidence)
    elif kind == "unit":
        evidence["unit"] = ""
    else:
        evidence["provenance_id"] = ""
    pack = next(p for p in source["fact_packs"] if p["pack_type"] == "valuation")
    pack["evidence_hash"] = content_hash(sorted(selected, key=lambda e: e["evidence_id"]))
    pack["fact_pack_hash"] = content_hash({k: v for k, v in pack.items() if k != "fact_pack_hash"})
    context.update(fact_pack_hash=pack["fact_pack_hash"], evidence_hash=pack["evidence_hash"])
    assert validate_role(interpretation_artifact("valuation", value, context), source)["status"] == "blocked"


def test_tampering_cross_scope_and_one_role_failure_cannot_be_full_success():
    results = []
    for role in list(OUTPUT_MODELS)[:-1]:
        source, value, context = grounded_fixture(role)
        artifact = interpretation_artifact(role, value, context)
        results.append(validate_role(artifact, source))
    assert summarize_roles(results)["validation_outcome"] == "complete"
    assert summarize_roles(results)["five_role_success"] is False  # Event Risk has no evidence.
    assert summarize_roles(results[:-1])["five_role_success"] is False
    assert summarize_roles([results[0]] * 5)["five_role_success"] is False
    altered = copy.deepcopy(results)
    altered[0]["status"] = "blocked"
    assert summarize_roles(altered)["validation_outcome"] == "partial"
    assert summarize_roles(altered)["five_role_success"] is False
    artifact["output"]["confidence"] = 0.9
    assert "artifact_hash_mismatch" in validate_role(artifact, source)["errors"]
    context["scope_id"] = "9999"
    assert "lineage_mismatch" in validate_role(interpretation_artifact(role, value, context), source)["errors"]
    altered = copy.deepcopy(results)
    altered[0]["lineage"]["execution_id"] = "other"
    altered[0]["artifact_hash"] = content_hash({k: v for k, v in altered[0].items() if k != "artifact_hash"})
    assert summarize_roles(altered)["validation_outcome"] == "partial"


@pytest.mark.parametrize("mutation,reason", [
    ("pack", "fact_pack_hash_mismatch"), ("evidence", "evidence_hash_mismatch"),
    ("prompt", "invalid_interpretation_contract"), ("guardrail", "invalid_interpretation_contract"),
    ("schema", "invalid_interpretation_contract"), ("output", "invalid_structured_output"),
])
def test_validator_rejects_rehashed_input_contract_tampering(mutation, reason):
    source, value, context = grounded_fixture("valuation")
    artifact = interpretation_artifact("valuation", value, context)
    if mutation == "pack":
        next(p for p in source["fact_packs"] if p["pack_type"] == "valuation")["facts"]["pe_ratio"] = 42.0
    elif mutation == "evidence":
        next(e for e in source["evidence"] if e["evidence_id"] in value["evidence_ids"])["value"] = 42.0
    elif mutation in ("prompt", "guardrail"):
        artifact["lineage"][mutation]["version"] = "arbitrary"
        artifact["lineage"][mutation]["text"] = "api_key=secret-canary"
    elif mutation == "schema":
        artifact["lineage"]["output_schema_version"] = "arbitrary"
    else:
        artifact["output"]["publication_status"] = "published"
    artifact["artifact_hash"] = content_hash({k: v for k, v in artifact.items() if k != "artifact_hash"})
    result = validate_role(artifact, source)
    assert result["status"] == "blocked" and reason in result["errors"]
    assert "secret-canary" not in json.dumps(result)
