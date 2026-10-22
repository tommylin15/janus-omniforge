"""Validated, immutable product projections; research quality stays separate."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import re

ROLES = ("fundamental", "valuation", "quant", "risk", "event")


def content_hash(value):
    return "sha256:" + sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def baseline_projection(manifest, artifacts):
    """Validate source artifacts without upgrading their model/publication status."""
    from intelligence_mart.specialist_contract import MartSpecialistV1
    from intelligence_mart.specialists import digest
    symbol = artifacts[0]["symbol"] if artifacts else None
    if not symbol or len(artifacts) != 5 or {a["role"] for a in artifacts} != set(ROLES):
        raise ValueError("five distinct specialist roles required")
    if manifest.get("output_hash") != digest({k: v for k, v in manifest.items() if k != "output_hash"}):
        raise ValueError("manifest hash mismatch")
    scoped_references = [r for r in manifest['specialists'] if r['symbol'] == symbol]
    if len(scoped_references) != 5 or {r['role'] for r in scoped_references} != set(ROLES):
        raise ValueError('ambiguous specialist references')
    references = {r['role']: r for r in scoped_references}
    projected = []
    for value in sorted(artifacts, key=lambda a: ROLES.index(a["role"])):
        MartSpecialistV1.model_validate(value)
        ref = references.get(value["role"], {})
        if (value["symbol"] != symbol or value["output_hash"] != digest(
                {k: v for k, v in value.items() if k != "output_hash"})
                or value["input_hash"] != ref.get("input_hash")
                or value["core_snapshot_id"] != ref.get("source_core_snapshot_id")
                or value["analysis_as_of"] > manifest["analysis_as_of"]):
            raise ValueError("specialist source fence mismatch")
        metrics = dict(value["metrics"])
        if any(v is not None for k, v in metrics.items()
                if k in {"outperform_probability", "regime_probability", "classifier_probability", "expected_excess_return"}):
            raise ValueError("unvalidated model signal")
        usable = any(v is not None for v in metrics.values()) and not value["rejected_evidence"]
        if usable and (not value["evidence_ids"] or not value["provenance_ids"]):
            raise ValueError("baseline lacks source evidence")
        projected.append({k: value[k] for k in (
            "role", "analysis_as_of", "core_snapshot_id", "output_hash", "input_hash", "model_version",
            "feature_version", "engine_version", "model_status", "status", "metrics", "missing_data",
            "evidence_ids", "provenance_ids", "plain_language", "feature_contributions")}
            | {"baseline_status": "available" if usable else "unavailable", "reused": ref.get("reused", False)})
    result = {"schema_version": "analysis-product.v1", "symbol": symbol,
              "execution_id": str(manifest["execution_id"]), "analysis_as_of": manifest["analysis_as_of"],
              "core_snapshot_id": manifest["core_snapshot_id"], "source_manifest_hash": manifest["output_hash"],
              "specialists": projected, "model_quality": "NOT_VERIFIED", "llm_api_tokens": 0,
              "publication_authority": False}
    result["content_hash"] = content_hash(result)
    return result



def approved_first_release_risk_projection(baseline, prediction):
    """Overlay a pinned immutable Risk result on a private baseline projection.

    Unlike the original research shadow, this evidence is explicitly approved
    for first release by the separate, version-fenced Mart registry. This does
    not mean a pristine prospective OOS cohort has already matured.
    """
    from math import isfinite
    MODEL_SHA256 = "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"
    MODEL_VERSION = "risk-xgboost8-2025h2-v1"
    if (prediction.get("symbol") != baseline["symbol"]
            or prediction.get("analysis_as_of") != baseline["analysis_as_of"]
            or prediction.get("core_snapshot_id") != baseline["core_snapshot_id"]
            or prediction.get("model_sha256") != MODEL_SHA256):
        raise ValueError("Risk first-release snapshot/model identity mismatch")
    forecast = prediction.get("future_20d_volatility_annualized")
    recent = prediction.get("recent_20d_volatility_annualized")
    if (any(isinstance(v, bool) or not isinstance(v, (int, float))
            or not isfinite(v) or v < 0 for v in (forecast, recent)) or recent == 0):
        raise ValueError("nonfinite or invalid Risk serving prediction")
    value = dict(baseline)
    value.pop("risk_first_release_candidate", None)
    specialists = []
    for item in baseline["specialists"]:
        if item["role"] != "risk":
            specialists.append(item)
            continue
        metrics = dict(item["metrics"])
        metrics["future_20d_volatility_annualized"] = float(forecast)
        metrics["recent_20d_volatility_annualized"] = float(recent)
        specialists.append({**item, "metrics": metrics,
            "model_version": MODEL_VERSION, "model_status": "first_release_approved",
            "status": "ready", "baseline_status": "available",
            "risk_first_release_limit": "prospective_20_session_oos_pending",
            "risk_prediction_model_sha256": MODEL_SHA256})
    value["specialists"] = specialists
    if sum(i["role"] == "risk" for i in specialists) != 1:
        raise ValueError("exact Risk specialist required")
    value["risk_serving_status"] = "FIRST_RELEASE_APPROVED"
    value["model_quality"] = "RESEARCH_OOS_FIRST_RELEASE_PROSPECTIVE_PENDING"
    value["content_hash"] = content_hash({k: v for k, v in value.items() if k != "content_hash"})
    return value

def numeric_facts(baseline):
    facts = {f'{a["role"]}.{key}': value for a in baseline['specialists']
             for key, value in a['metrics'].items()
             if isinstance(value, (int, float)) and not isinstance(value, bool)}
    market = baseline.get('market_context') or {}
    facts.update({f'market.{group}.{key}': value for group in ('metrics', 'cross_sectional_rank')
                  for key, value in market.get(group, {}).items() if value is not None})
    facts.update({f'market.{key}': market[key] for key in ('cohort_size', 'candidate_rank') if market.get(key) is not None})
    if str(baseline['symbol']).isdigit():
        facts['symbol'] = int(baseline['symbol'])
    return facts


def validate_ceo_output(output, baseline, *, has_previous=False):
    from intelligence_mart.ai_contract import CEOOutput
    value = CEOOutput.model_validate(output).model_dump()
    specialists = baseline["specialists"]
    hashes = [a["output_hash"] for a in specialists]
    if sorted(value["validated_role_artifact_hashes"]) != sorted(hashes):
        raise ValueError("CEO artifact fence mismatch")
    allowed = {i for a in specialists for i in a["evidence_ids"]}
    def check(item):
        if isinstance(item, dict):
            if not set(item.get("evidence_ids", [])) <= allowed:
                raise ValueError("CEO cites unknown evidence")
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    if value['change_since_previous_analysis'] and not has_previous:
        raise ValueError('CEO invented a previous analysis comparison')
    # Bind a number to its supplied fact key. A value seen as a return cannot
    # silently become an invented target price; canonical UI formats separately.
    facts = numeric_facts(baseline)
    token = r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'
    claims = [value.get('thesis'), *[c for key in ('contradictions', 'bull_case', 'bear_case',
              'principal_risks', 'watch_items', 'change_since_previous_analysis') for c in value[key]]]
    texts = [item['text'] for item in claims if item] + value['missing_information']
    for text in texts:
        remainder = text
        for key, supplied in facts.items():
            def replace(match):
                if Decimal(match.group(1)) != Decimal(str(supplied)):
                    raise ValueError('CEO changed a canonical numeric fact')
                return ''
            remainder = re.sub(r'(?<![A-Za-z0-9_.])'+re.escape(key)+r'\s*=\s*('+token+r')(?![\d.])', replace, remainder)
        if re.search(r'\d', remainder):
            raise ValueError("CEO invented a numeric claim")
    if any(a["baseline_status"] != "available" or a["missing_data"] for a in specialists):
        if not value["missing_information"]:
            raise ValueError("CEO concealed missing data")
    return value


def freshness(baseline, today=None):
    today = today or date.today()
    age = (today - date.fromisoformat(baseline["analysis_as_of"])).days
    return "stale" if age > 7 or age < 0 else "current"
