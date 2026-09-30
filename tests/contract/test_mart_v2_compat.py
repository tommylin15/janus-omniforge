import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))

from intelligence_mart.compat import (
    artifact_reference,
    build_compatibility_sidecar,
    compatibility_contract,
    validate_compatibility_sidecar,
)


def _hash(char):
    return "sha256:" + char * 64


def _report():
    return {
        "schema_version": "1",
        "execution_id": "execution-1",
        "analysis_as_of": "2026-09-30",
        "core_snapshot_id": "core-1",
        "scope": {"type": "symbol", "id": "2330"},
        "deterministic_hash": _hash("a"),
    }


def _references():
    interpretation = {
        "artifact_kind": "mart_ai_interpretation_v1",
        "role": "valuation",
        "artifact_hash": _hash("b"),
        "status": "schema_validated",
        "lineage": {"output_schema_version": "1.0.0"},
    }
    validation = {
        "artifact_kind": "mart_ai_validation_v1",
        "role": "valuation",
        "artifact_hash": _hash("c"),
        "status": "validated",
        "validator_version": "role-validator-v1",
        "source_artifact_hash": interpretation["artifact_hash"],
        "publication_authority": False,
    }
    return [
        artifact_reference(interpretation, {"artifact_uri": "gs://mart/interpretation.json"}),
        artifact_reference(validation, {"artifact_uri": "gs://mart/validation.json"}),
    ]


def test_saved_compat_contract_is_additive_and_registry_discoverable():
    saved = json.loads((ROOT / "packages/contracts/mart_compat.v1.json").read_text(encoding="utf-8"))
    assert saved == compatibility_contract()
    mart = json.loads((ROOT / "packages/contracts/mart.v1.json").read_text(encoding="utf-8"))
    assert mart["version"] == "1.1.0"
    scoped = mart["$defs"]["MartScopedAnalysisV1"]
    assert scoped["additionalProperties"] is False
    assert "ai_artifacts" not in scoped["properties"]
    assert "ai_validations" not in scoped["properties"]
    registry = json.loads((ROOT / "packages/contracts/registry.json").read_text(encoding="utf-8"))
    assert registry["schemas"]["MartAIAdditiveSidecarV1"]["$ref"] == "mart_compat.v1.json#/schemas/MartAIAdditiveSidecarV1"
    assert registry["schemas"]["MartAIInterpretationArtifactReferenceV1"]["$ref"].endswith("InterpretationArtifactReferenceV1")
    assert registry["schemas"]["MartAIValidationArtifactReferenceV1"]["$ref"].endswith("ValidationArtifactReferenceV1")


def test_sidecar_binds_ai_artifacts_without_mutating_mart_v1():
    source = _report()
    before = copy.deepcopy(source)
    sidecar = build_compatibility_sidecar(source, _references())
    assert source == before
    assert sidecar["compatibility_mode"] == "additive_sidecar"
    assert sidecar["base"]["contract"] == "mart.v1"
    assert sidecar["base"]["contract_version"] == "1.1.0"
    assert sidecar["base"]["deterministic_hash"] == source["deterministic_hash"]
    assert sidecar["publication_authority"] is False
    assert validate_compatibility_sidecar(sidecar, source) == sidecar


def test_sidecar_rejects_tampered_base_and_cross_artifact_validation():
    source = _report()
    sidecar = build_compatibility_sidecar(source, _references())
    other = copy.deepcopy(source)
    other["scope"]["id"] = "9999"
    with pytest.raises(ValueError, match="base identity"):
        validate_compatibility_sidecar(sidecar, other)
    references = _references()
    references[1]["source_artifact_hash"] = _hash("d")
    with pytest.raises(ValueError, match="same-role interpretation"):
        build_compatibility_sidecar(source, references)
