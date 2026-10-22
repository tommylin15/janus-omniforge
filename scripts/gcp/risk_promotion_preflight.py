#!/usr/bin/env python3
"""Read-only, fail-closed Risk v1 ACTIVE promotion preflight.

This is NOT an active-pointer mutator or evidence certifier. It reports which
formal gates remain unproven, using real immutable GCS evidence where available.
An audit PASS only means the probe ran, never that promotion is authorized.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

MODEL_SHA = "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"
BUCKET = "gen-lang-client-0593591102-dev-mart"
MODEL = f"gs://{BUCKET}/risk-models/candidates/2026Q3-20261022/risk-xgboost8-2025h2-v1.ubj"
SHADOW_PREFIX = f"gs://{BUCKET}/risk-shadow/"
SCREENING_DATE = "2026-10-21"
# The first-promotion gate is finite; missing whole-market historical PIT or
# 20 new prospective mature labels is a recorded limitation, not an excuse
# to waive actual cutoff leakage, source rights or reversible publication.
MANDATORY_PROOFS = (
    "scoped_source_use_rights_by_dataset",
    "eight_feature_cutoff_and_revision_pit_guard",
    "window_scoped_corporate_action_screen",
    "training_serving_feature_parity_test_vectors",
    "validated_bundle_manifest_and_registry_import",
    "target_only_daily_inference_and_exclusion_receipt",
    "atomic_registry_cas_with_rollback",
)
ACCEPTED_FIRST_RELEASE_LIMITS = (
    "retrospective_oos_previously_seen_not_independent",
    "historical_delisted_master_not_reconstructed",
    "full_history_corporate_actions_not_required",
)
POST_ACTIVATION_ACCEPTANCE = (
    "prospective_20_market_sessions_maturity_and_monthly_evaluation",
    "published_api_ui_owner_boundary_readback",
    "natural_scheduled_daily_run_acceptance",
)


def elapsed_weekdays_after(start: date, end: date) -> int:
    """An UPPER bound on trading sessions, never a fabricated exchange calendar."""
    if end <= start:
        return 0
    return sum((start + timedelta(days=n)).weekday() < 5
               for n in range(1, (end - start).days + 1))


def evaluate(model_sha: str | None, shadow: dict | None, today: date) -> dict:
    blockers = list(MANDATORY_PROOFS)
    verified = {}
    if model_sha == MODEL_SHA:
        verified["candidate_gcs_sha256"] = MODEL_SHA
    else:
        blockers.insert(0, "candidate_gcs_sha256_unverified")
    if shadow is not None:
        if (shadow.get("analysis_as_of") == SCREENING_DATE
                and shadow.get("model_sha256") == MODEL_SHA
                and shadow.get("publication_allowed") is False
                and shadow.get("status") == "SHADOW_UNVALIDATED"
                and isinstance(shadow.get("rows"), list)
                and len(shadow["rows"]) > 0
                and isinstance(shadow.get("core_snapshot_id"), str)
                and shadow.get("source_manifest_hash", "").startswith("sha256:")):
            verified["shadow_prediction_count"] = len(shadow["rows"])
            # Historical shadow receipt counts only ordinary-stock targets;
            # it cannot reconstruct ETFs absent from the old target selector.
            # Never expose owner details or fabricate exclusion reasons.
            total = shadow.get("target_count")
            if isinstance(total, int) and not isinstance(total, bool) and total >= len(shadow["rows"]):
                verified["historical_ordinary_target_count"] = total
                verified["historical_unclassified_excluded_count"] = total - len(shadow["rows"])
                verified["historical_etf_exclusions_observed"] = False
            verified["shadow_analysis_as_of"] = SCREENING_DATE
            verified["shadow_core_snapshot_id"] = shadow["core_snapshot_id"]
        else:
            blockers.insert(0, "immutable_shadow_evidence_invalid")
    else:
        blockers.insert(0, "immutable_shadow_evidence_missing")
    earliest = date.fromisoformat(SCREENING_DATE)
    elapsed = elapsed_weekdays_after(earliest, today)
    # There cannot be 20 exchange trading sessions when even the maximal
    # weekday count is smaller than 20. The reverse is NOT proof of maturity.
    verified["upper_bound_weekdays_after_shadow"] = elapsed
    # A pending mature label is not an error, not a win, and not pre-promotion proof.
    verified["prospective_oos_state"] = "PENDING" if elapsed < 20 else "MATURITY_REQUIRES_CALENDAR_AND_EOD_EVIDENCE"
    return {
        "component": "risk_xgboost_v1_promotion_preflight",
        "audit_status": "COMPLETED",
        "promotion_status": "BLOCKED_NOT_ACTIVE",
        "model_sha256": MODEL_SHA,
        "as_of_taipei": today.isoformat(),
        "verified": verified,
        "blocked_or_unverified_gates": sorted(set(blockers)),
        "accepted_first_release_limits": list(ACCEPTED_FIRST_RELEASE_LIMITS),
        "post_activation_acceptance": list(POST_ACTIVATION_ACCEPTANCE),
        "publication_allowed": False,
        "would_write_registry": False,
        "would_change_api": False,
        "would_execute_model": False,
    }


def _run(*args: str) -> bytes:
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=65)


def read_live() -> tuple[str | None, dict | None]:
    try:
        model_sha = sha256(_run("gcloud", "storage", "cat", MODEL,
                                "--project", "gen-lang-client-0593591102")).hexdigest()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        model_sha = None
    shadow = None
    try:
        listed = _run("gcloud", "storage", "ls", "--recursive", SHADOW_PREFIX,
                      "--project", "gen-lang-client-0593591102").decode().splitlines()
        objects = [s for s in listed if s.startswith(SHADOW_PREFIX) and s.endswith(".json")]
        if len(objects) > 100:
            raise ValueError("shadow_inventory_over_bound")
        eligible = []
        for uri in objects:
            try:
                item = json.loads(_run("gcloud", "storage", "cat", uri,
                                        "--project", "gen-lang-client-0593591102"))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                    json.JSONDecodeError):
                continue
            if (item.get("analysis_as_of") == SCREENING_DATE
                    and item.get("model_sha256") == MODEL_SHA
                    and item.get("status") == "SHADOW_UNVALIDATED"):
                eligible.append(item)
        valid = [x for x in eligible if isinstance(x.get("rows"), list) and len(x["rows"]) > 0]
        if len(valid) == 1:
            shadow = valid[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        pass
    return model_sha, shadow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    result = evaluate(*read_live(), datetime.now(ZoneInfo("Asia/Taipei")).date())
    receipt = Path(args.receipt)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False) + "\n")
    # Safe totals/status only; never output prediction or owner data.
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
