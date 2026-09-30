"""Deterministic, provider-neutral role validation; never grants publication authority."""

from copy import deepcopy
from datetime import date, datetime, time, timezone
import re

from .ai_contract import Lineage, OUTPUT_MODELS, content_hash, interpretation_artifact
from .analysis import ROLE_WEIGHTS, validate_evidence


VERSION = "role-validator-v1"
NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
CLAIM_FIELDS = ("thesis", "key_findings", "positive_evidence", "negative_evidence",
                "contradictions", "change_drivers", "risks", "what_would_change_my_view")


def validate_role(artifact: dict, report: dict) -> dict:
    """Bind every claim to this role's fenced evidence and expose all missing fact keys.

    Numeric prose is deliberately conservative: only verbatim `fact_key=value` copies
    from supplied facts are accepted. No calculations, rounding or free-text units.
    Evidence coverage is not a proof of qualitative entailment or investment usefulness.
    """
    errors = set()
    role, context = artifact.get("role"), artifact.get("lineage", {})
    source_hash = content_hash({k: v for k, v in artifact.items() if k != "artifact_hash"})
    if artifact.get("artifact_hash") != source_hash:
        errors.add("artifact_hash_mismatch")
    pack = next((p for p in report.get("fact_packs", []) if p.get("pack_type") == role), None)
    if role not in ROLE_WEIGHTS or pack is None:
        errors.add("invalid_role_or_fact_pack")
    else:
        for key in ("execution_id", "analysis_as_of", "core_snapshot_id",
                    "governance_snapshot_version"):
            if context.get(key) != report.get(key):
                errors.add("lineage_mismatch")
        if (context.get("scope_type") != report.get("scope", {}).get("type")
                or context.get("scope_id") != report.get("scope", {}).get("id")):
            errors.add("lineage_mismatch")
        for key in ("fact_pack_hash", "evidence_hash", "feature_version", "analysis_as_of", "core_snapshot_id"):
            if context.get(key) != pack.get(key):
                errors.add("fact_pack_lineage_mismatch")
        if pack.get("fact_pack_hash") != content_hash({k: v for k, v in pack.items() if k != "fact_pack_hash"}):
            errors.add("fact_pack_hash_mismatch")
        ids = pack.get("evidence_ids", [])
        selected = [e for e in report.get("evidence", []) if e.get("evidence_id") in ids]
        if len(set(ids)) != len(ids) or len(selected) != len(ids):
            errors.add("evidence_set_mismatch")
        if pack.get("evidence_hash") != content_hash(sorted(selected, key=lambda e: e["evidence_id"])):
            errors.add("evidence_hash_mismatch")
        try:
            as_of = date.fromisoformat(report["analysis_as_of"])
            valid, rejected, blockers = validate_evidence(selected, as_of)
            cutoff = datetime.combine(as_of, time.max, timezone.utc)
            for item in selected:
                if item.get("core_snapshot_id") != report.get("core_snapshot_id"):
                    errors.add("evidence_snapshot_mismatch")
                for key in ("published_at", "availability_at", "observed_at", "record_at"):
                    if item.get(key):
                        instant = datetime.fromisoformat(item[key].replace("Z", "+00:00"))
                        if instant.tzinfo is None or instant > cutoff:
                            errors.add("evidence_time_fence")
            if pack.get("provenance_ids") != sorted({e.get("provenance_id") for e in selected}):
                errors.add("provenance_set_mismatch")
            if rejected or blockers or len(valid) != len(selected):
                errors.add("invalid_evidence")
        except (ValueError, KeyError, TypeError):
            errors.add("invalid_evidence_context")
        missing = {k for k, v in pack.get("facts", {}).items() if v is None}
        if set(pack.get("missing_data", [])) != missing:
            errors.add("missing_fact_contract_mismatch")

    output = artifact.get("output")
    audit_context = {k: report.get(k) for k in ("execution_id", "analysis_as_of", "core_snapshot_id",
                                               "governance_snapshot_version")}
    audit_context.update(scope_type=report.get("scope", {}).get("type"), scope_id=report.get("scope", {}).get("id"))
    # Recheck schema AND system-controlled prompt/schema/guardrail, not caller status labels.
    try:
        expected = interpretation_artifact(role, output, {k: context[k] for k in Lineage.model_fields if k in context})
        if expected != artifact or expected.get("status") != "schema_validated":
            errors.add("invalid_interpretation_contract")
        else:
            audit_context = expected["lineage"]
    except (ValueError, TypeError):
        errors.add("invalid_interpretation_contract")
    if isinstance(output, dict) and role in ROLE_WEIGHTS and pack is not None:
        try:
            parsed = OUTPUT_MODELS[role].model_validate(output).model_dump()
        except ValueError:
            errors.add("invalid_structured_output")
        else:
            allowed = set(pack.get("evidence_ids", []))
            top_ids = parsed["evidence_ids"]
            claims = []
            for field in CLAIM_FIELDS:
                value = parsed[field]
                claims.extend([value] if isinstance(value, dict) else value or [])
            covered = set()
            for claim in claims:
                refs = claim["evidence_ids"]
                covered.update(refs)
                if len(set(refs)) != len(refs) or not set(refs) <= allowed:
                    errors.add("invalid_claim_evidence")
                remaining = claim["text"]
                # Longest first avoids interpreting key suffixes / prefixes as another fact.
                for key, value in sorted(pack["facts"].items(), key=lambda kv: -len(kv[0])):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        token = f"{key}={value}"
                        remaining = re.sub(r"(?<![\w.])" + re.escape(token) + r"(?=$|[\s,，;；。)）])", "", remaining)
                if NUMBER.search(remaining) or re.search(r"[零一二三四五六七八九十百千萬億]+(?:元|股|倍|%|％|百分之)", remaining):
                    errors.add("ungrounded_numeric_claim")
            if len(set(top_ids)) != len(top_ids) or set(top_ids) != covered or not covered <= allowed:
                errors.add("claim_coverage_mismatch")
            disclosures = "\n".join(parsed["missing_information"])
            if any(not re.search(r"(?<![\w])" + re.escape(key) + r"(?![\w])", disclosures)
                   for key in pack.get("missing_data", [])):
                errors.add("missing_information_omitted")
            if parsed["stance"] != "insufficient_data" and not covered:
                errors.add("unsupported_stance")
    result = {"artifact_kind": "mart_ai_validation_v1", "validator_version": VERSION,
              "role": role, "source_artifact_hash": source_hash, "lineage": deepcopy(audit_context),
              "status": "blocked" if errors else "validated", "errors": sorted(errors),
              "analysis_outcome": "insufficient_data" if isinstance(output, dict) and output.get("stance") == "insufficient_data" else "interpreted",
              "publication_authority": False}
    result["artifact_hash"] = content_hash(result)
    return result


def summarize_roles(results: list[dict]) -> dict:
    """Exactly five authentic validation results from the same execution scope, or partial."""
    roles = [r.get("role") for r in results]
    valid = len(roles) == 5 and set(roles) == set(ROLE_WEIGHTS)
    identities = set()
    for result in results:
        valid &= (result.get("artifact_kind") == "mart_ai_validation_v1"
                  and result.get("validator_version") == VERSION and result.get("status") == "validated"
                  and result.get("errors") == [] and result.get("publication_authority") is False
                  and result.get("artifact_hash") == content_hash({k: v for k, v in result.items() if k != "artifact_hash"}))
        ctx = result.get("lineage", {})
        identities.add(tuple(ctx.get(k) for k in ("execution_id", "analysis_as_of", "core_snapshot_id",
                                                "scope_type", "scope_id", "profile_reference", "governance_snapshot_version")))
    valid &= len(identities) == 1
    sufficient = all(r.get("analysis_outcome") == "interpreted" for r in results)
    return {"validation_outcome": "complete" if valid else "partial", "five_role_success": bool(valid and sufficient),
            "analysis_outcome": "complete" if valid and sufficient else "insufficient_data" if valid else "partial",
            "publication_authority": False, "validation_artifact_hashes": [r.get("artifact_hash") for r in results]}
