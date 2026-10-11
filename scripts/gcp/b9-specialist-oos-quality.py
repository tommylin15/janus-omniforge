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
from statistics import median
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



def _finite_number(value):
    """Bounded numeric evidence; missing/non-finite values are not zero."""
    from math import isfinite
    return (float(value) if isinstance(value, (int, float)) and
            not isinstance(value, bool) and isfinite(value) else None)


def _evaluation_diagnostics(item, role):
    """Read-only model/horizon scorecard from persisted OOS, never a promotion gate."""
    from statistics import fmean, pstdev
    if role == "risk":
        folds = item.get("oos_folds", [])
        monthly = []
        missing_folds = 0
        for fold in folds:
            markov, gaussian, n = (_finite_number(fold.get("markov_log_score_sum")),
                                   _finite_number(fold.get("gaussian_log_score_sum")),
                                   fold.get("test_returns"))
            if markov is None or gaussian is None or type(n) is not int or n <= 0:
                missing_folds += 1
                continue
            monthly.append({"month": fold.get("month"), "test_returns": n,
                            "improvement_per_return": (markov - gaussian) / n,
                            "total_log_score_improvement": markov - gaussian})
        monthly.sort(key=lambda row: str(row["month"]))
        improvements = [row["improvement_per_return"] for row in monthly]
        total_days = sum(row["test_returns"] for row in monthly)
        worst_streak = streak = 0
        for value in improvements:
            streak = streak + 1 if value <= 0 else 0
            worst_streak = max(worst_streak, streak)
        split = len(improvements) // 2
        daily = item.get("risk_oos_daily")
        # Legacy immutable OOS has only monthly sums. Never derive daily vol,
        # tail calibration or Markov switching from monthly aggregates.
        environmental = None
        daily_status = "unavailable_legacy_monthly_aggregate"
        if daily is not None:
            _require(isinstance(daily, list), "invalid daily regime evidence")
            required = ("date", "month", "market_return", "markov_log_score",
                        "gaussian_log_score", "predicted_high_vol_probability",
                        "realized_high_vol", "realized_extreme_vol", "realized_left_tail",
                        "markov_tail_probability", "gaussian_tail_probability",
                        "realized_volatility_20d", "historical_volatility_20d_p75", "historical_abs_return_p95",
                        "historical_left_tail_p05")
            _require(len(daily) == total_days and missing_folds == 0,
                     "daily regime evidence coverage differs from monthly OOS")
            _require(len({row.get("date") for row in daily if isinstance(row, dict)}) == len(daily),
                     "duplicate regime OOS trading dates")
            for row in daily:
                _require(isinstance(row, dict) and all(key in row for key in required),
                         "partial regime OOS daily evidence")
                _require(isinstance(row["date"], str) and isinstance(row["month"], str) and
                         re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]) is not None and
                         isinstance(row.get("training_end"), str) and
                         row["training_end"] < row["date"] and
                         row["date"][:7] == row["month"] and
                         all(_finite_number(row[k]) is not None for k in
                             ("market_return", "markov_log_score", "gaussian_log_score",
                              "predicted_high_vol_probability", "markov_tail_probability",
                              "gaussian_tail_probability", "realized_volatility_20d", "historical_volatility_20d_p75",
                              "historical_abs_return_p95", "historical_left_tail_p05")) and
                         all(type(row[k]) is bool for k in
                             ("realized_high_vol", "realized_extreme_vol", "realized_left_tail")) and
                         all(0 <= row[k] <= 1 for k in
                             ("predicted_high_vol_probability", "markov_tail_probability",
                              "gaussian_tail_probability")) and
                         0 <= row["realized_volatility_20d"] and
                         0 <= row["historical_volatility_20d_p75"] and
                         0 <= row["historical_abs_return_p95"] and
                         row["realized_high_vol"] == (
                             row["realized_volatility_20d"] >= row["historical_volatility_20d_p75"]) and
                         row["realized_extreme_vol"] == (
                             abs(row["market_return"]) >= row["historical_abs_return_p95"]) and
                         row["realized_left_tail"] == (
                             row["market_return"] <= row["historical_left_tail_p05"]),
                         "nonfinite, invalid or future training regime OOS daily evidence")
            for fold in monthly:
                rows = [row for row in daily if row["month"] == fold["month"]]
                source_fold = next(f for f in folds if f.get("month") == fold["month"])
                _require(all(row["training_end"] == source_fold.get("training_end") and
                             source_fold.get("test_start", "") <= row["date"] <= source_fold.get("test_end", "~")
                             for row in rows), "regime daily fold violated prior-month training fence")
                _require(len(rows) == fold["test_returns"] and
                         abs(sum(row["markov_log_score"] for row in rows) -
                             _finite_number(source_fold.get("markov_log_score_sum"))) < 1e-5 and
                         abs(sum(row["gaussian_log_score"] for row in rows) -
                             _finite_number(source_fold.get("gaussian_log_score_sum"))) < 1e-5,
                         "daily regime log scores do not reconcile to immutable monthly fold")
            ordered = sorted(daily, key=lambda row: row["date"])
            groups = {}
            for name, group in (("high_realized_vol", [r for r in ordered if r["realized_high_vol"]]),
                                ("low_realized_vol", [r for r in ordered if not r["realized_high_vol"]]),
                                ("extreme_vol", [r for r in ordered if r["realized_extreme_vol"]]),
                                ("non_extreme_vol", [r for r in ordered if not r["realized_extreme_vol"]]),
                                ("left_tail", [r for r in ordered if r["realized_left_tail"]]),
                                ("non_left_tail", [r for r in ordered if not r["realized_left_tail"]])):
                groups[name] = {"observations": len(group),
                                "average_log_score_improvement": fmean(
                                    r["markov_log_score"] - r["gaussian_log_score"] for r in group)
                                if group else None}
            tail_brier_markov = fmean((r["markov_tail_probability"] -
                                     int(r["realized_left_tail"])) ** 2 for r in ordered) if ordered else None
            tail_brier_gaussian = fmean((r["gaussian_tail_probability"] -
                                       int(r["realized_left_tail"])) ** 2 for r in ordered) if ordered else None
            states = [r["predicted_high_vol_probability"] >= 0.5 for r in ordered]
            environmental = {
                "prior_only_training_thresholds": True,
                "high_low_is_ex_post_realized_vol_stratification": True,
                "groups": groups,
                "state_proxy": "prior_predictive_high_variance_probability_threshold_0_5",
                "state_switches": sum(a != b for a, b in zip(states, states[1:])),
                "state_transitions_observed": max(0, len(states) - 1),
                "tail_brier_markov": tail_brier_markov,
                "tail_brier_gaussian": tail_brier_gaussian,
                "tail_brier_improvement_over_gaussian":
                    tail_brier_gaussian - tail_brier_markov if ordered else None,
                "tail_events": sum(r["realized_left_tail"] for r in ordered),
                "extreme_vol_events": sum(r["realized_extreme_vol"] for r in ordered),
            }
            daily_status = "reconciled_prior_only_oos_daily_diagnostics"
        return {
            "method": "prior_only_regime_oos_fold_stability",
            "folds_with_comparable_log_scores": len(improvements),
            "folds_missing_or_invalid_log_scores": missing_folds,
            "oos_returns_reconciled_from_folds": total_days,
            "positive_improvement_months": sum(value > 0 for value in improvements),
            "nonpositive_improvement_months": sum(value <= 0 for value in improvements),
            "mean_monthly_improvement": fmean(improvements) if improvements else None,
            "monthly_improvement_stddev": pstdev(improvements) if len(improvements) >= 2 else None,
            "return_weighted_log_score_improvement":
                sum(row["total_log_score_improvement"] for row in monthly)/total_days if total_days else None,
            "worst_monthly_improvement": min(improvements) if improvements else None,
            "median_monthly_improvement": median(improvements) if improvements else None,
            "longest_nonpositive_month_streak": worst_streak,
            "first_half_mean_monthly_improvement": fmean(improvements[:split]) if split else None,
            "second_half_mean_monthly_improvement": fmean(improvements[split:]) if split else None,
            "monthly_scores": monthly,
            "daily_environment_evidence_status": daily_status,
            "environment_and_tail": environmental,
            "quality_blockers": ["regime_stability_and_event_state_calibration_not_verified",
                                 "champion_baseline_release_gate_not_verified"] +
                                (["daily_volatility_switch_and_tail_data_missing"] if daily is None else []),
        }
    rows = item.get("predictions", [])
    paired = [(p, y) for row in rows
              if (p := _finite_number(row.get("prediction"))) is not None and
              (y := _finite_number(row.get("excess_return"))) is not None]
    by_day = defaultdict(set)
    for row in rows:
        if isinstance(row.get("analysis_as_of"), str) and isinstance(row.get("symbol"), str):
            by_day[row["analysis_as_of"]].add(row["symbol"])
    max_section = max(map(len, by_day.values()), default=0)
    # Constant zero is a descriptive no-skill return forecast, NOT a fitted benchmark.
    mse_model = fmean((p - y) ** 2 for p, y in paired) if paired else None
    mse_zero = fmean(y ** 2 for _, y in paired) if paired else None
    probabilities = [(p, float(_finite_number(row.get("excess_return")) > 0))
        for row in rows if (p := _finite_number(row.get("probability"))) is not None
        and _finite_number(row.get("excess_return")) is not None and 0 <= p <= 1]
    brier = fmean((p - y) ** 2 for p, y in probabilities) if len(probabilities) >= 30 else None
    metrics = item.get("metrics") or {}
    blockers = ["historical_pit_membership_not_verified",
                "champion_vs_trained_baseline_not_verified"]
    if max_section < 10:
        blockers.append("fewer_than_10_stocks_in_any_oos_cross_section")
    if _finite_number(metrics.get("rank_ic")) is None:
        blockers.append("cross_section_rank_ic_unavailable")
    if _finite_number(metrics.get("after_cost_return")) is None:
        blockers.append("after_cost_cross_section_return_unavailable")
    if len(probabilities) < 30:
        blockers.append("probability_calibration_insufficient")
    overfit_folds = None
    if role == "valuation":
        folds = item.get("folds") or []
        overfit_folds = sum(f.get("overfit_warning") is True for f in folds)
        if overfit_folds:
            blockers.append("research_overfit_warning_in_prior_only_folds")
        if item.get("model_name") == "catboost" and paired and mse_model > mse_zero:
            blockers.append("catboost_oos_worse_than_zero_baseline")
    if role == "fundamental" and (item.get("financial_history_policy") or {}).get("strict_pit") is False:
        blockers.append("financial_history_current_revision_not_strict_pit")
    return {
        "method": "descriptive_persisted_oos_no_retraining",
        "paired_forecasts": len(paired),
        "oos_dates": len(by_day),
        "max_same_date_symbols": max_section,
        "dates_with_at_least_10_symbols": sum(len(symbols) >= 10 for symbols in by_day.values()),
        "mse_model": mse_model,
        "mse_constant_zero": mse_zero,
        "model_minus_zero_mse": mse_model - mse_zero if paired else None,
        "valuation_overfit_warning_folds": overfit_folds,
        "probability_predictions": len(probabilities),
        "brier": brier,
        "brier_constant_half": 0.25 if brier is not None else None,
        "brier_improvement_over_half": 0.25 - brier if brier is not None else None,
        "baseline_semantics": "constant_zero_return_and_constant_half_probability_descriptive_only",
        "quality_blockers": blockers,
    }


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
    lineage_present = 0
    lineage_legacy_missing = 0
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
                lineage_keys = ("sample_source_authorization", "sample_provenance_id",
                                "feature_available_at", "label_available_at")
                present = [key in row for key in lineage_keys]
                if not any(present):
                    lineage_legacy_missing += 1
                else:
                    _require(all(present), "partially persisted OOS provenance/authorization")
                    _require(row["sample_source_authorization"] in {"official", "approved_fallback"} and
                             isinstance(row["sample_provenance_id"], str) and
                             bool(row["sample_provenance_id"].strip()),
                             "invalid OOS sample authorization/provenance")
                    try:
                        feature_day = datetime.fromisoformat(
                            str(row["feature_available_at"]).replace("Z", "+00:00")).date()
                        label_day = datetime.fromisoformat(
                            str(row["label_available_at"]).replace("Z", "+00:00")).date()
                        entry_day = datetime.fromisoformat(str(row["analysis_as_of"])).date()
                        outcome_day = datetime.fromisoformat(str(row["outcome_as_of"])).date()
                    except (ValueError, TypeError) as error:
                        raise AuditError("invalid persisted OOS lineage availability date") from error
                    _require(feature_day <= entry_day and label_day >= outcome_day,
                             "OOS persisted lineage PIT/label availability violation")
                    lineage_present += 1
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
            "diagnostics": _evaluation_diagnostics(item, role),
        })
    roles = {}
    for role in ROLES:
        counts = grouped[role]
        role_evals = by_role[role]
        roles[role] = {
            "artifact_summary": dict(counts),
            "oos_evaluations": role_evals,
            "quality_gate": "not_verified",
            "research_remediation": {
                "fundamental": "official_filing_time_and_matured_labels_plus_rule_baseline",
                "valuation": "official_valuation_history_and_dcf_missingness_plus_two_challengers",
                "quant": "historical_pit_cohort_and_cross_section_cost_sensitive_oos",
                "risk": "month_by_month_regime_stability_vs_gaussian",
                "event": "authorized_human_labeled_chronological_holdout_and_local_classifier",
            }[role],
            "quality_blockers": (["authorized_human_labels_and_classifier_oos_missing"]
                                  if role == "event" else
                                  ["historical_pit_membership_or_model_baseline_release_evidence_pending"]
                                  if role in {"fundamental", "valuation", "quant"} else
                                  ["regime_stability_and_champion_acceptance_pending"]),
            "reason": ("no_persisted_event_classifier_oos" if role == "event"
                       else "no_champion_vs_baseline_quality_acceptance"),
        }
    return {
        "schema_version": "b9-specialist-oos-quality-readback-v3",
        "source_core_snapshot_id": expected_core,
        "source_relation_to_b7_freshness": "same_verified_core_fence",
        "newest_core_at_audit_time": "not_verified",
        "artifact_integrity": "pass",
        "five_specialist_roles": list(ROLES),
        "specialist_artifacts_verified": len(refs),
        "evaluation_records_verified": len(evaluations),
        "oos_evaluations_with_samples": evaluated,
        "per_prediction_source_authorization_and_provenance":
            ("fields_present_and_temporally_valid_source_readback_not_verified"
             if lineage_present and not lineage_legacy_missing
             else "not_independently_in_persisted_predictions"),
        "prediction_lineage_present": lineage_present,
        "prediction_lineage_legacy_missing": lineage_legacy_missing,
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
                 isinstance(uri, str) and uri.startswith(PREFIX) and
                 PATH_RE.fullmatch(uri[len(PREFIX):]) is not None,
                 "invalid specialist immutable reference")
        artifact, actual_hash = _read_gcs_json(uri)
        _require(actual_hash == expected_hash, "specialist immutable bytes hash mismatch")
        # Filename uses logical payload output_hash (before output_hash is added);
        # artifact_hash is SHA256 of the FULL immutable serialized JSON bytes.
        _require(isinstance(artifact.get("output_hash"), str) and
                 uri == PREFIX + "specialists/" + artifact["output_hash"][7:] + ".json",
                 "specialist logical output hash path mismatch")
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
    # Only aggregates enter Actions logs; raw predictions, symbols and owner data do not.
    summary = {role: [{
        "model": entry["model"], "horizon": entry["horizon_days"],
        "samples": entry["oos_samples"], "folds": entry["folds"],
        "max_same_date_symbols": entry["diagnostics"].get("max_same_date_symbols"),
        "model_minus_zero_mse": entry["diagnostics"].get("model_minus_zero_mse"),
        "brier_improvement_over_half": entry["diagnostics"].get("brier_improvement_over_half"),
        "positive_regime_months": entry["diagnostics"].get("positive_improvement_months"),
        "nonpositive_regime_months": entry["diagnostics"].get("nonpositive_improvement_months"),
        "regime_daily_evidence": entry["diagnostics"].get("daily_environment_evidence_status"),
        "regime_return_weighted_log_score_improvement": entry["diagnostics"].get("return_weighted_log_score_improvement"),
        "regime_median_monthly_improvement": entry["diagnostics"].get("median_monthly_improvement"),
        "regime_longest_nonpositive_month_streak": entry["diagnostics"].get("longest_nonpositive_month_streak"),
        "regime_first_half_mean_monthly_improvement": entry["diagnostics"].get("first_half_mean_monthly_improvement"),
        "regime_second_half_mean_monthly_improvement": entry["diagnostics"].get("second_half_mean_monthly_improvement"),
        "regime_tail_events": (entry["diagnostics"].get("environment_and_tail") or {}).get("tail_events"),
        "regime_high_vol_days": (entry["diagnostics"].get("environment_and_tail") or {})
            .get("groups", {}).get("high_realized_vol", {}).get("observations"),
        "regime_state_switches": (entry["diagnostics"].get("environment_and_tail") or {}).get("state_switches"),
    } for entry in data["oos_evaluations"]] for role, data in report["roles"].items()}
    print("B9 AGGREGATED MODEL DIAGNOSTICS " + json.dumps(summary, sort_keys=True, allow_nan=False))
    print("B9 READBACK PASS; B9 MODEL QUALITY NOT VERIFIED; no retrain/promotion")


if __name__ == "__main__":
    main()
