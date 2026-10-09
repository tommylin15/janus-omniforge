#!/usr/bin/env python3
"""Single-use Cloud Run dev routing reconciliation under the ORIGINAL owner lease.

Only reassert the already serving GHCR revision's 100% traffic. No image,
revision, tag, Scheduler or Job changes. Fail closed and retain the lease if
Cloud Run cannot reconcile an old-image-import-failed routing condition.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import ghcr_api_forward_finalize as final
import ghcr_api_promote as api
from ghcr_mcp_route import LEASE, PROJECT, REGION, SERVICE, command, describe, probe, BASE

REQUEST = Path("ops/ghcr-api-route-reconcile-request.json")


def checked_request():
    d = json.loads(REQUEST.read_text())
    if (d.get("intent") != "reassert-existing-ghcr-api-route-under-owner-lease"
            or d.get("approved") is not True
            or d.get("scope") != "existing-dev-janus-api-only"
            or d.get("source_sha") != final.SHA
            or d.get("original_owner_run") != final.ORIGINAL_RUN
            or d.get("route_target") != final.CANDIDATE
            or d.get("allow_only_same_100_percent") is not True
            or d.get("allow_no_old_ar_rollback") is not True):
        raise ValueError("route_reconcile_not_approved")
    return d


def preflight():
    # Independent checks from the original release/Jobs proof and live runtime.
    api.acceptance(final.SHA)
    approved = api.check_forward_promotion_request(final.RELEASE, final.JOBS_RUN, final.SHA)
    proof = json.loads(final.PROOF.read_text())
    api.check_jobs_receipt(proof, final.SHA)
    if proof.get("phase") != "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED":
        raise ValueError("forward_jobs_proof_wrong_phase")
    try:
        api.verify_forward_runtime(approved)
    except ValueError as error:
        if str(error) != "execution_not_terminal":
            raise
        final.wait_for_terminal_executions()
        api.verify_forward_runtime(approved)
    current = describe()
    if api.active(current) != final.CANDIDATE:
        raise ValueError("current_route_not_same_target")
    if api.tags(current).get("ghcr-" + final.SHA[:12]) != final.CANDIDATE:
        raise ValueError("current_candidate_tag_drift")
    revision = json.loads(command([
        "gcloud", "run", "revisions", "describe", final.CANDIDATE,
        f"--project={PROJECT}", f"--region={REGION}", "--format=json"]))
    if api.revision_image(revision) != final.EXPECTED_IMAGE:
        raise ValueError("candidate_image_drift")
    state = final.bounded_readiness_evidence(current, revision)
    if (not state["service_generation_reconciled"]
            or not state["latest_ready_is_candidate"]
            or not state["latest_created_is_candidate"]
            or not state["template_image_is_expected"]):
        raise ValueError("control_plane_baseline_unverified")
    if (not any(c["type"] == "Ready" and c["status"] == "True"
                for c in state["revision_conditions"])):
        raise ValueError("candidate_revision_not_ready")
    conditions = {c["type"]: c for c in state["service_conditions"]}
    if (conditions.get("Ready", {}).get("reason") != "ContainerImageImportFailed"
            or conditions["Ready"]["status"] != "False"
            or conditions.get("RoutesReady", {}).get("reason") != "ContainerImageImportFailed"
            or conditions["RoutesReady"]["status"] != "False"):
        raise ValueError("not_exact_known_route_failure")
    api.health(final.SHA)
    probe("https://ghcr-" + final.SHA[:12] + "---" + BASE.removeprefix("https://"), final.SHA)
    return current, state


def run(receipt: Path) -> int:
    evidence = {"source_sha": final.SHA, "phase": "PREFLIGHT",
                "original_owner_run": final.ORIGINAL_RUN,
                "traffic_reassertion_attempted": False, "lease_released": False,
                "old_ar_revision_rollback_verified": False,
                "private_job_config_parity": "NOT_VERIFIED"}
    def save():
        receipt.write_text(json.dumps(evidence, sort_keys=True))
    save()
    try:
        checked_request()
        owned = final.assert_original_lease()
        before, summary = preflight()
        evidence["before"] = summary
        evidence["phase"] = "SAME_REVISION_ROUTE_REASSERTION"
        save()
        # Never change the selected revision. Existing tagged routes are not edited.
        command(["gcloud", "run", "services", "update-traffic", SERVICE,
                 f"--project={PROJECT}", f"--region={REGION}",
                 f"--to-revisions={final.CANDIDATE}=100", "--quiet"])
        evidence["traffic_reassertion_attempted"] = True
        evidence["phase"] = "POST_ROUTE_READBACK"
        save()
        after = describe()
        if (api.active(after) != final.CANDIDATE
                or api.tags(after) != api.tags(before)
                or after.get("status", {}).get("latestCreatedRevisionName") != final.CANDIDATE):
            raise ValueError("post_route_traffic_or_tags_drift")
        revision = json.loads(command([
            "gcloud", "run", "revisions", "describe", final.CANDIDATE,
            f"--project={PROJECT}", f"--region={REGION}", "--format=json"]))
        if api.revision_image(revision) != final.EXPECTED_IMAGE:
            raise ValueError("post_route_image_drift")
        after_state = final.bounded_readiness_evidence(after, revision)
        evidence["after"] = after_state
        save()
        final.assert_ready_readback(after, revision)
        api.health(final.SHA)
        probe("https://ghcr-" + final.SHA[:12] + "---" + BASE.removeprefix("https://"), final.SHA)
        api.verify_forward_runtime(api.check_forward_promotion_request(
            final.RELEASE, final.JOBS_RUN, final.SHA))
        command(owned + ["release", "--safe-to-release"])
        evidence["lease_released"] = True
        evidence["phase"] = "PASS_SAME_REVISION_ROUTE_RECONCILED"
        save()
        return 0
    except Exception as error:
        evidence["error_type"] = type(error).__name__
        reason = str(error)
        evidence["reason"] = (reason if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", reason)
                              else "control_failure")
        save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    return run(parser.parse_args().receipt)


if __name__ == "__main__":
    sys.exit(main())
