"""Additive mart.v1 compatibility sidecar for AI interpretation and validation artifacts."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


VERSION = "1.0.0"
BASE_CONTRACT = "mart.v1"
BASE_CONTRACT_VERSION = "1.1.0"
BASE_SCHEMA = "MartScopedAnalysisV1"
AI_OUTPUT_CONTRACT_VERSION = "1.0.0"
VALIDATOR_VERSION = "role-validator-v1"

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Hash = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
GcsUri = Annotated[str, Field(pattern=r"^gs://[^/]+/.+$")]
Role = Literal["fundamental", "valuation", "positioning", "quant", "event_risk"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class BaseMartIdentityV1(Contract):
    contract: Literal["mart.v1"]
    contract_version: Literal["1.1.0"]
    contract_schema: Literal["MartScopedAnalysisV1"]
    report_schema_version: Text
    execution_id: Text
    analysis_as_of: Text
    core_snapshot_id: Text
    scope_type: Literal["market", "industry", "symbol"]
    scope_id: Text
    deterministic_hash: Hash

    @model_validator(mode="after")
    def require_as_of_date(self):
        date.fromisoformat(self.analysis_as_of)
        return self


class InterpretationArtifactReferenceV1(Contract):
    artifact_kind: Literal["mart_ai_interpretation_v1"]
    role: Literal["fundamental", "valuation", "positioning", "quant", "event_risk", "cio"]
    artifact_hash: Hash
    artifact_uri: GcsUri
    status: Literal["schema_validated", "failed"]
    output_contract_version: Literal["1.0.0"]


class ValidationArtifactReferenceV1(Contract):
    artifact_kind: Literal["mart_ai_validation_v1"]
    role: Role
    artifact_hash: Hash
    artifact_uri: GcsUri
    status: Literal["validated", "blocked"]
    validator_version: Literal["role-validator-v1"]
    source_artifact_hash: Hash
    publication_authority: Literal[False]


ArtifactReferenceV1 = Annotated[
    InterpretationArtifactReferenceV1 | ValidationArtifactReferenceV1,
    Field(discriminator="artifact_kind"),
]


def _content_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


class MartAIAdditiveSidecarV1(Contract):
    schema_version: Literal["1.0.0"]
    compatibility_mode: Literal["additive_sidecar"]
    base: BaseMartIdentityV1
    artifacts: Annotated[list[ArtifactReferenceV1], Field(min_length=1, max_length=11)]
    publication_authority: Literal[False]
    sidecar_hash: Hash

    @model_validator(mode="after")
    def require_consistent_references(self):
        seen = set()
        interpretations = {}
        for item in self.artifacts:
            identity = (item.artifact_kind, item.role)
            if identity in seen:
                raise ValueError("duplicate artifact kind and role")
            seen.add(identity)
            if item.artifact_kind == "mart_ai_interpretation_v1":
                interpretations[item.role] = item.artifact_hash
        for item in self.artifacts:
            if item.artifact_kind == "mart_ai_validation_v1":
                if interpretations.get(item.role) != item.source_artifact_hash:
                    raise ValueError("validation must reference the same-role interpretation")
        payload = self.model_dump(exclude={"sidecar_hash"})
        if self.sidecar_hash != _content_hash(payload):
            raise ValueError("sidecar hash mismatch")
        return self


def compatibility_contract() -> dict:
    schema = MartAIAdditiveSidecarV1.model_json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": VERSION,
        "$defs": schema.pop("$defs"),
        "schemas": {"MartAIAdditiveSidecarV1": schema},
    }


def artifact_reference(artifact: dict, reference: dict) -> dict:
    kind = artifact.get("artifact_kind")
    common = {
        "artifact_kind": kind,
        "role": artifact.get("role"),
        "artifact_hash": artifact.get("artifact_hash"),
        "artifact_uri": reference.get("artifact_uri"),
        "status": artifact.get("status"),
    }
    if kind == "mart_ai_interpretation_v1":
        common["output_contract_version"] = artifact.get("lineage", {}).get("output_schema_version", AI_OUTPUT_CONTRACT_VERSION)
        return InterpretationArtifactReferenceV1.model_validate(common).model_dump()
    if kind == "mart_ai_validation_v1":
        common.update(
            validator_version=artifact.get("validator_version"),
            source_artifact_hash=artifact.get("source_artifact_hash"),
            publication_authority=artifact.get("publication_authority"),
        )
        return ValidationArtifactReferenceV1.model_validate(common).model_dump()
    raise ValueError("unsupported additive artifact kind")


def build_compatibility_sidecar(report: dict, references: list[dict]) -> dict:
    """Bind additive AI artifacts to a v1 report without mutating or republishing it."""
    scope = report.get("scope", {})
    base = BaseMartIdentityV1.model_validate({
        "contract": BASE_CONTRACT,
        "contract_version": BASE_CONTRACT_VERSION,
        "contract_schema": BASE_SCHEMA,
        "report_schema_version": report.get("schema_version"),
        "execution_id": report.get("execution_id"),
        "analysis_as_of": report.get("analysis_as_of"),
        "core_snapshot_id": report.get("core_snapshot_id"),
        "scope_type": scope.get("type"),
        "scope_id": scope.get("id"),
        "deterministic_hash": report.get("deterministic_hash"),
    }).model_dump()
    payload = {
        "schema_version": VERSION,
        "compatibility_mode": "additive_sidecar",
        "base": base,
        "artifacts": references,
        "publication_authority": False,
    }
    payload["sidecar_hash"] = _content_hash(payload)
    return MartAIAdditiveSidecarV1.model_validate(payload).model_dump()


def validate_compatibility_sidecar(sidecar: dict, report: dict) -> dict:
    parsed = MartAIAdditiveSidecarV1.model_validate(sidecar).model_dump()
    expected = build_compatibility_sidecar(report, parsed["artifacts"])
    if parsed["base"] != expected["base"]:
        raise ValueError("sidecar base identity does not match mart.v1 report")
    return parsed
