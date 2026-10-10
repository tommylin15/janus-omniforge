"""B9 read-only quality audit of existing dev Mart immutable artifacts.

An audit SUCCESS is not a B9 model-quality PASS. No retraining or publication.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

BUCKET = "gen-lang-client-0593591102-dev-mart"
PREFIX = "gs://" + BUCKET + "/"
ROLES = ("fundamental", "valuation", "quant", "risk", "event")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PATH_RE = re.compile(
    r"^(?:executions/" + UUID_RE +
    r"/(?:specialist-manifest|oos-evaluation)\.json|specialists/[0-9a-f]{64}\.json)$"
)


class AuditError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise AuditError(message)


def _read_gcs_json(uri):
    _require(isinstance(uri, str) and uri.startswith(PREFIX) and
             PATH_RE.fullmatch(uri[len(PREFIX):]), "GCS path outside B9 read-only allowlist")
    try:
        result = subprocess.run(
            ["gcloud", "storage", "cat", uri],
            capture_output=True, check=True, timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise AuditError("GCS immutable artifact readback unavailable") from error
    return json.loads(result.stdout), "sha256:" + sha256(result.stdout).hexdigest()


def _role_for_evaluation(item):
    if item.get("model_name") == "statsmodels_markov_regime":
        return "risk"
    return item.get("specialist_role", "quant")


def summarize(manifest, evaluations, artifacts, *, expected_core):
    """Independent structural/quality evidence; never grants champion authority."""
    _require(HASH_RE.fullmatch(expected_core) is not None, "invalid expected Core fence")
    _require(manifest.get("artifact_kind") == "mart_specialist_execution_v1",
             "unexpected Mart execution contract")
    _require(manifest.get("core_snapshot_id") == expected_core,
             "OOS execution Core differs from B7 fixed current-source evidence")
    _require(manifest.get("llm_api_tokens") == 0 and
             manifest.get("ceo_triggered") is False and
             manifest.get("publication_authority") is False,
             "specialist execution violated zero-LLM/publication boundary")
    refs = manifest.get("specialists")
    _require(isinstance(refs, list) and len(refs) > 0, "missing specialist references")
    _require(len(refs) == len(artifacts), "specialist reference/readback mismatch")
    grouped = defaultdict(lambda: Counter())
    seen = set()
    for ref, artifact in zip(refs, artifacts, strict=True):
        role = ref.get("role")
        _require(role in ROLES and role == artifact.get("role") and
                 ref.get("symbol") == artifact.get("symbol") and
                 ref.get("input_hash") == artifact.get("input_hash") and
                 ref.get("source_core_snapshot_id") == artifact.get("core_snapshot_id"),
                 "specialist identity/source-reference mismatch")
        pair = (ref["symbol"], role)
        _require(pair not in seen, "duplicate specialist symbol/role")
        seen.add(pair)
        _require(artifact.get("artifact_kind") == "mart_specialist_v1" and
                 artifact.get("model_status") in {"oos_not_validated", "oos_validated"} and
                 artifact.get("publication_authority") is False and
                 artifact.get("llm_api_tokens") == 0 and
                 artifact.get("ceo_triggered") is False and
                 isinstance(artifact.get("plain_language"), str) and
                 bool(artifact["plain_language"].strip()) and
                 isinstance(artifact.get("feature_contributions"), list) and
                 isinstance(artifact.get("metrics"), dict) and
                 isinstance(artifact.get("missing_data"), list) and
                 isinstance(artifact.get("provenance_ids"), list),
                 "specialist structured/explanation/governance contract mismatch")
        role_counts = grouped[role]
        role_counts["artifacts"] += 1
        role_counts[artifact["model_status"]] += 1
        role_counts[artifact.get("status", "unknown")] += 1
        if not artifact["provenance_ids"]:
            role_counts["missing_provenance"] += 1
        if any(item.get("method") == "observed_metric_not_shap"
               for item in artifact["feature_contributions"] if isinstance(item, dict)):
            role_counts["deterministic_contribution_only"] += 1
    _require(set(grouped) == set(ROLES), "not all five specialist roles have persisted artifacts")
    _require(isinstance(evaluations, list) and evaluations, "missing persisted OOS evaluations")
    by_role = defaultdict(list)
    evaluated = 0
    for item in evaluations:
        role = _role_for_evaluation(item)
        _require(role in ROLES and item.get("core_snapshot_id") == expected_core,
                 "OOS evaluation Core/role mismatch")
        if role == "risk":
            _require(item.get("promotion_eligible") is False, "regime promotion must remain disabled")
            status = item.get("status")
            sample_count = item.get("oos_returns", 0)
        else:
            _require(item.get("artifact_kind") == "mart_oos_evaluation_v1" and
                     item.get("promotion_eligible") is False,
                     "invalid OOS evaluation/promotion contract")
            preds = item.get("predictions", [])
            _require(isinstance(preds, list), "invalid OOS predictions")
            for row in preds:
                _require(row.get("training_label_cutoff", "~") < row.get("analysis_as_of", "") <
                         row.get("outcome_as_of", ""), "OOS training/label leakage in persisted predictions")
            status = item.get("status")
            sample_count = len(preds)
        _require(isinstance(sample_count, int) and sample_count >= 0,
                 "invalid OOS sample count")
        if status in {"evaluated", "research_oos_evaluated"} and sample_count:
            evaluated += 1
        by_role[role].append({
            "model": item.get("model_name"),
            "horizon_days": item.get("horizon_days"),
            "status": status,
            "oos_samples": sample_count,
            "folds": len(item.get("folds", item.get("oos_folds", []))),
            "rank_ic": item.get("metrics", {}).get("rank_ic"),
            "brier": item.get("metrics", {}).get("brier"),
            "calibration": item.get("metrics", {}).get("probability_calibration"),
            "after_cost_return": item.get("metrics", {}).get("after_cost_return"),
            "average_log_score_improvement": item.get("average_log_score_improvement"),
            "financial_history_strict_pit": item.get("financial_history_policy", {}).get("strict_pit"),
        })
    roles = {}
    for role in ROLES:
        counts = grouped[role]
        role_evals = by_role[role]
        roles[role] = {
            "artifact_summary": dict(counts),
            "oos_evaluations": role_evals,
            "quality_gate": "not_verified",
            "reason": ("no_persisted_event_classifier_oos" if role == "event"
                       else "no_champion_vs_baseline_quality_acceptance"),
        }
    return {
        "schema_version": "b9-specialist-oos-quality-readback-v1",
        "source_core_snapshot_id": expected_core,
        "source_relation_to_b7_freshness": "same_verified_core_fence",
        "newest_core_at_audit_time": "not_verified",
        "artifact_integrity": "pass",
        "five_specialist_roles": list(ROLES),
        "specialist_artifacts_verified": len(refs),
        "evaluation_records_verified": len(evaluations),
        "oos_evaluations_with_samples": evaluated,
        "per_prediction_source_authorization_and_provenance": "not_independently_in_persisted_predictions",
        "historical_membership_replay": "not_verified",
        "champion_promotion": False,
        "model_quality": "not_verified",
        "b9_status": "partial",
        "llm_api_tokens": 0,
        "canonical_write": False,
        "monthly_retraining_triggered": False,
        "roles": roles,
    }


def audit(manifest_uri, expected_core):
    manifest, _ = _read_gcs_json(manifest_uri)
    _require(manifest_uri == PREFIX + "executions/" +
             str(manifest.get("execution_id")) + "/specialist-manifest.json",
             "execution/manifest identity mismatch")
    evaluation_ref = manifest.get("evaluation", {})
    _require(isinstance(evaluation_ref, dict), "missing OOS evaluation pointer")
    evaluation_uri = PREFIX + "executions/" + manifest["execution_id"] + "/oos-evaluation.json"
    _require(evaluation_ref.get("artifact_uri") == evaluation_uri, "OOS pointer path mismatch")
    evaluations, evaluation_hash = _read_gcs_json(evaluation_uri)
    _require(evaluation_ref.get("artifact_hash") == evaluation_hash,
             "OOS immutable bytes hash mismatch")
    artifacts = []
    for ref in manifest.get("specialists", []):
        uri, expected_hash = ref.get("artifact_uri"), ref.get("artifact_hash")
        _require(isinstance(expected_hash, str) and HASH_RE.fullmatch(expected_hash) is not None and
                 uri == PREFIX + "specialists/" + expected_hash[7:] + ".json",
                 "invalid specialist immutable reference")
        artifact, actual_hash = _read_gcs_json(uri)
        _require(actual_hash == expected_hash, "specialist immutable bytes hash mismatch")
        artifacts.append(artifact)
    return summarize(manifest, evaluations, artifacts, expected_core=expected_core)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-core", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.manifest_uri, args.expected_core)
    report["recorded_at"] = datetime.now(timezone.utc).isoformat()
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "roles"}, sort_keys=True))
    print("B9 READBACK PASS; B9 MODEL QUALITY NOT VERIFIED; no retrain/promotion")


if __name__ == "__main__":
    main()
