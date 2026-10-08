#!/usr/bin/env python3
"""Fail-closed, pure readback checks for Janus GHCR Cloud Run Jobs cutover.

No GCP mutations, no credentials, no canonical values and no secret output.
Do not use this guard alone to authorize Job image changes: evidence must come
from live GCP with a durable deployment mutex and authenticated acceptance.
"""
from __future__ import annotations

import argparse
import json
import re
import runpy
from pathlib import Path
from typing import Any, Mapping

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
SCHEDULER = "janus-ingestion-daily"
SCHEDULER_TARGET = (
    "https://run.googleapis.com/v2/projects/"
    f"{PROJECT}/locations/{REGION}/jobs/janus-batch-controller:run"
)
SCHEDULER_IDENTITY = f"janus-ingestion-scheduler@{PROJECT}.iam.gserviceaccount.com"
REQUIRED_JOBS = (
    "janus-batch-controller",
    "janus-ingestion-core",
    "janus-intelligence-mart",
    "janus-private-pipeline",
    "janus-research-big-move-500",
)
EXPECTED_COMPONENTS = ("ingestion-core", "intelligence-mart", "private-pipeline")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PINNED_IMAGE_RE = re.compile(r"^[-a-z0-9./]+@sha256:[0-9a-f]{64}$")

verify_historical_failures = runpy.run_path(
    str(Path(__file__).with_name("ghcr_private_historical_fence.py"))
)["verified_failed_count"]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def assess(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded non-sensitive readiness report; absent fields block."""
    blockers: list[str] = []

    if evidence.get("project") != PROJECT or evidence.get("region") != REGION:
        blockers.append("project_region_mismatch")

    source_sha = evidence.get("source_sha")
    if not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        blockers.append("source_sha_unknown")

    images = _dict(evidence.get("ghcr_images"))
    for component in EXPECTED_COMPONENTS:
        row = _dict(images.get(component))
        if (
            not isinstance(row.get("digest"), str)
            or not DIGEST_RE.fullmatch(row["digest"])
            or row.get("source_sha") != source_sha
            or row.get("anonymous_pull_verified") is not True
        ):
            blockers.append(f"ghcr_{component}_unverified")

    scheduler = _dict(evidence.get("scheduler"))
    if scheduler.get("full_region_enumeration") is not True:
        blockers.append("scheduler_enumeration_incomplete")
    jobs = _list(scheduler.get("jobs"))
    controller = [_dict(j) for j in jobs if _dict(j).get("name") == SCHEDULER]
    retired = [
        _dict(j) for j in jobs
        if str(_dict(j).get("name", "")).startswith("janus-private-pipeline-")
    ]
    if len(controller) != 1 or retired:
        blockers.append("scheduler_controller_topology_mismatch")
    else:
        entry = controller[0]
        if (
            entry.get("target") != SCHEDULER_TARGET
            or entry.get("identity") != SCHEDULER_IDENTITY
            or entry.get("schedule") != "30 * * * *"
            or entry.get("time_zone") != "Asia/Taipei"
            or entry.get("retry_count") != 1
        ):
            blockers.append("scheduler_controller_contract_mismatch")
        # For image promotion, this must be verified PAUSED, not merely ENABLED.
        if entry.get("state") != "PAUSED":
            blockers.append("scheduler_still_enabled")

    snapshots = _dict(evidence.get("job_snapshots"))
    private_proof = _dict(evidence.get("private_historical_failure_readback"))
    private_count = _dict(snapshots.get("janus-private-pipeline")).get("potentially_active")
    # Reject all guessed counts and pre-recorded green flags: derive from the
    # same run's exact v1 execution, task and v2 terminal-failure evidence.
    historical_terminal_failed = verify_historical_failures(
        private_proof.get("v1_records"),
        private_proof.get("task_records"),
        private_proof.get("v2_readback"),
        private_count,
    )
    for name in REQUIRED_JOBS:
        snapshot = _dict(snapshots.get(name))
        if (
            not isinstance(snapshot.get("image"), str)
            or not PINNED_IMAGE_RE.fullmatch(snapshot["image"])
            or snapshot.get("rollback_image_readable") is not True
        ):
            blockers.append(f"rollback_{name}_unverified")
        if (
            snapshot.get("execution_list_complete") is not True
            or not isinstance(snapshot.get("potentially_active"), int)
            or isinstance(snapshot.get("potentially_active"), bool)
            or snapshot.get("potentially_active") != (
                historical_terminal_failed if name == "janus-private-pipeline" else 0
            )
        ):
            blockers.append(f"execution_{name}_unfenced")

    if evidence.get("durable_deployment_mutex_verified") is not True:
        blockers.append("durable_deployment_mutex_unverified")
    if evidence.get("owner_oauth_and_data_acceptance_verified") is not True:
        blockers.append("authenticated_acceptance_unverified")
    if evidence.get("rollback_procedure_verified") is not True:
        blockers.append("rollback_procedure_unverified")

    # Safe to show in GitHub summary. Never echo original JSON or private env.
    return {
        "status": "READY_FOR_CONTROLLED_JOB_ROLLOUT" if not blockers else "BLOCKED",
        "project": PROJECT,
        "region": REGION,
        "source_sha": source_sha if isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{40}", source_sha) else "UNKNOWN",
        "blockers": blockers,
        "historical_failed_pretask_terminal_count": historical_terminal_failed,
        "historical_success_claimed": False,
        "resource_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise SystemExit("Evidence must be a JSON object")
    report = assess(evidence)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0  # 'BLOCKED' is a valid diagnostic outcome; NEVER a promotion signal.


if __name__ == "__main__":
    raise SystemExit(main())
