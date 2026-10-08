#!/usr/bin/env python3
"""Generate a reversible Janus GHCR Job image plan without touching GCP.

This module only plans an image-only update for existing jobs. It never
pauses or resumes Cloud Scheduler, patches a Job, executes a workload, or
claims authenticated acceptance. No secret/env/config values are exported.
"""
from __future__ import annotations

import argparse
import json
import re
import runpy
from pathlib import Path
from typing import Any, Mapping

_GUARD = runpy.run_path(str(Path(__file__).with_name("ghcr_job_cutover_guard.py")))
assess = _GUARD["assess"]

# The research job has no GHCR equivalent and MUST NOT be updated in this
# migration. The controller shares the ingestion-core image but has a
# separate command/env configuration that must remain untouched.
JOB_COMPONENT = (
    ("janus-private-pipeline", "private-pipeline"),
    ("janus-intelligence-mart", "intelligence-mart"),
    ("janus-ingestion-core", "ingestion-core"),
    ("janus-batch-controller", "ingestion-core"),
)
VALID_PIN = re.compile(r"^[a-z0-9][a-z0-9./-]*@sha256:[0-9a-f]{64}$")


def build_plan(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return only reversible pinned image mapping; never a mutation command."""
    decision = assess(evidence)
    old = evidence.get("job_snapshots")
    images = evidence.get("ghcr_images")
    if not isinstance(old, dict) or not isinstance(images, dict):
        decision["blockers"].append("image_snapshots_missing")
    updates: list[dict[str, str]] = []
    for name, component in JOB_COMPONENT:
        previous = (old or {}).get(name, {}) if isinstance(old, dict) else {}
        proposed = (images or {}).get(component, {}) if isinstance(images, dict) else {}
        before = previous.get("image") if isinstance(previous, dict) else None
        digest = proposed.get("digest") if isinstance(proposed, dict) else None
        if (
            not isinstance(before, str) or not VALID_PIN.fullmatch(before)
            or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        ):
            decision["blockers"].append(f"image_mapping_{name}_unknown")
            continue
        after = f"ghcr.io/tommylin15/janus-{component}@{digest}"
        if before == after:
            decision["blockers"].append(f"image_mapping_{name}_not_a_change")
        updates.append({"job": name, "component": component,
                        "previous_pinned_image": before, "target_pinned_image": after})
    decision["blockers"] = sorted(set(decision["blockers"]))
    # The plan is never executable by itself, even with zero blockers.
    decision["status"] = "DRY_RUN_READY" if not decision["blockers"] else "BLOCKED"
    return {
        "intent": "image-only-dry-run",
        "status": decision["status"],
        "source_sha": decision["source_sha"],
        "project": decision["project"],
        "region": decision["region"],
        "protected_unchanged_jobs": ["janus-research-big-move-500"],
        "updates": updates,
        "rollback_order": [
            {"job": item["job"], "restore_pinned_image": item["previous_pinned_image"]}
            for item in reversed(updates)
        ],
        "blockers": decision["blockers"],
        "required_control": [
            "independently_verified_owner_candidate_acceptance",
            "separate_durable_cross_workflow_lock",
            "scheduler_paused_and_readback",
            "all_execution_states_resolved_and_rechecked",
            "restore_and_resume_even_on_failure",
            "post_release_canary_and_rollback_drill",
        ],
        "resource_writes": 0,
        "automatic_apply": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise SystemExit("Evidence must be an object")
    report = build_plan(snapshot)
    data = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0  # BLOCKED is a valid read-only finding, never a release decision.


if __name__ == "__main__":
    raise SystemExit(main())
