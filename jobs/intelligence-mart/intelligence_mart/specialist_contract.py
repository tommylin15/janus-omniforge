"""Strict public specialist artifact contract, separate from historic Mart reports."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MartSpecialistV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    artifact_kind: Literal["mart_specialist_v1"]
    schema_version: Literal["1.0.0"]
    symbol: str = Field(min_length=1, max_length=32)
    role: Literal["fundamental", "valuation", "quant", "risk", "event"]
    analysis_as_of: str
    core_snapshot_id: str
    feature_version: str
    engine_version: str
    model_version: str
    model_status: Literal["oos_not_validated", "oos_validated"]
    status: Literal["ready", "partial", "blocked"]
    input_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    metrics: dict[str, object]
    missing_data: list[str]
    rejected_evidence: list[dict[str, str]]
    evidence_ids: list[str]
    provenance_ids: list[str]
    feature_contributions: list[dict[str, object]]
    publication_authority: Literal[False]
    llm_api_tokens: Literal[0]
    ceo_triggered: Literal[False]
    plain_language: str
