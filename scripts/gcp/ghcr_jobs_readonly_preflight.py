#!/usr/bin/env python3
"""Read-only live Jobs release diagnostics. No scheduler/job/traffic writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import re
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import ghcr_jobs_rollout as rollout


class RollbackImageBlocked(RuntimeError):
    def __init__(self, reason_code, job):
        self.reason_code = reason_code
        self.job = job
        super().__init__(reason_code)


def check(label, action, findings):
    try:
        action()
    except (Exception, SystemExit) as error:
        # Never emit an HTTP body, credential, command, env var or private payload.
        findings[label] = {"status": "BLOCKED", "error_type": type(error).__name__}
        if isinstance(error, RollbackImageBlocked):
            findings[label]["reason_code"] = error.reason_code
            findings[label]["job"] = error.job
        if isinstance(error, RuntimeIdentityPermissionsBlocked):
            findings[label]["reason_code"] = "runtime_identity_actas_missing_or_unknown"
            findings[label]["jobs"] = error.jobs
    else:
        findings[label] = {"status": "PASS"}


def assert_baseline_scheduler():
    state = rollout.scheduler().get("state")
    if state != "ENABLED":
        raise ValueError("unexpected_scheduler_baseline")


def jobs_ready_readback():
    for name in rollout.REQUIRED_JOBS:
        rollout.job(name)


def rollback_images_readable():
    """Check all existing immutable rollback refs without updating or pulling Jobs."""
    for name in rollout.REQUIRED_JOBS:
        target = rollout.image(rollout.job(name))
        if not rollout.PIN.fullmatch(target):
            raise RollbackImageBlocked("ROLLBACK_IMAGE_NOT_PINNED", name)
        if target.startswith("ghcr.io/"):
            cmd = ["skopeo", "inspect", "--no-creds", "docker://" + target]
        else:
            cmd = ["gcloud", "artifacts", "docker", "images", "describe", target,
                   "--format=value(image_summary.digest)"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
        if result.returncode:
            # Classify the failure; never disclose registry response bodies or URLs.
            low = result.stderr.lower()
            if "permission_denied" in low or "permission denied" in low or "403" in low:
                code = "ROLLBACK_IMAGE_READ_IAM"
            elif "not found" in low or "not_found" in low or "404" in low:
                code = "ROLLBACK_IMAGE_NOT_FOUND"
            else:
                code = "ROLLBACK_IMAGE_READ_UNKNOWN"
            raise RollbackImageBlocked(code, name)
        if not result.stdout.strip():
            raise RollbackImageBlocked("ROLLBACK_IMAGE_NO_DIGEST_READBACK", name)


class RuntimeIdentityPermissionsBlocked(RuntimeError):
    def __init__(self, jobs):
        self.jobs = sorted(jobs)
        super().__init__("runtime_identity_actas_missing_or_unknown")


def runtime_identity_permissions():
    """Read-only IAM self-test; print no identity addresses or HTTP responses."""
    names = [name for name, _ in rollout.JOB_COMPONENT]
    denied = []
    token = rollout.command(["gcloud", "auth", "print-access-token"]).strip()
    for name in names:
        data = rollout.job(name)
        account = data.get("template", {}).get("template", {}).get("serviceAccount")
        if not isinstance(account, str) or not account.endswith(".iam.gserviceaccount.com"):
            denied.append(name)
            continue
        uri = "https://iam.googleapis.com/v1/projects/-/serviceAccounts/" + quote(account, safe="@.-") + ":testIamPermissions"
        request = Request(uri, method="POST", data=b'{"permissions":["iam.serviceAccounts.actAs"]}',
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=35) as response:
                permitted = json.load(response).get("permissions", [])
        except (HTTPError, OSError, ValueError):
            denied.append(name)
            continue
        if "iam.serviceAccounts.actAs" not in permitted:
            denied.append(name)
    if denied:
        raise RuntimeIdentityPermissionsBlocked(denied)


def diagnose_private_config_fingerprint():
    """Read-only hash comparison against the pre-update receipt.

    Never disclose env values, service-account names or private config. This
    isolates whether a post-update fingerprint delta is a new default field.
    """
    request = json.loads(Path("ops/ghcr-jobs-preflight-request.json").read_text())
    if request.get("investigate_ghcr_config_drift") is not True:
        return None
    expected = request.get("private_pipeline_preupdate_hash", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("invalid_diagnostic_baseline_hash")
    data = rollout.job("janus-private-pipeline")
    config = {key: deepcopy(data.get(key, {}))
              for key in ("template", "labels", "annotations")}
    config["template"]["template"]["containers"][0].pop("image", None)
    for key in ("run.googleapis.com/client-name", "run.googleapis.com/client-version"):
        config["annotations"].pop(key, None)

    def hashed(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def walk(value, prefix=()):
        if isinstance(value, dict):
            for key, child in value.items():
                path = prefix + (key,)
                yield path
                yield from walk(child, path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, prefix + (index,))

    def remove_path(value, path):
        node = value
        for part in path[:-1]:
            node = node[part]
        if isinstance(node, dict):
            node.pop(path[-1], None)

    hits = []
    paths = [p for p in walk(config) if isinstance(p[-1], str)]
    for path in paths:
        trial = deepcopy(config)
        remove_path(trial, path)
        if hashed(trial) == expected:
            # Report only harmless platform-managed fields, not user config.
            leaf = path[-1]
            platform_metadata = any(p == "annotations" for p in path[:-1]) and (
                leaf.startswith("run.googleapis.com/") or leaf.startswith("client"))
            hits.append("platform_metadata" if platform_metadata else "nonplatform_field")
            if len(hits) >= 5:
                break
    return {
        "job": "janus-private-pipeline",
        "image_source": "ghcr" if rollout.image(data).startswith("ghcr.io/") else "other",
        "original_fingerprint_matches": hashed(config) == expected,
        "single_field_deletion_categories_matching_baseline": hits,
        "path_count_examined": len(paths),
        "baseline_hash_prefix": expected[:12],
        "current_hash_prefix": hashed(config)[:12],
        "gcp_writes": 0,
    }


def scan():
    findings = {}
    check("legacy_cloud_build_not_competing", rollout.legacy_writers, findings)
    check("scheduler_expected_enabled_baseline", assert_baseline_scheduler, findings)
    check("five_jobs_readable_and_ready", jobs_ready_readback, findings)
    check("five_jobs_executions_terminal", rollout.fence, findings)
    check("jobs_update_and_canary_iam", rollout.job_update_permissions, findings)
    check("four_runtime_identities_actas", runtime_identity_permissions, findings)
    check("five_rollback_images_registry_readable", rollback_images_readable, findings)
    drift = None
    try:
        drift = diagnose_private_config_fingerprint()
    except (Exception, SystemExit) as error:
        drift = {"status": "DIAGNOSTIC_BLOCKED", "error_type": type(error).__name__, "gcp_writes": 0}
    return {
        "diagnostics": {"private_config_drift": drift},
        "mode": "read_only",
        "project": rollout.PROJECT,
        "region": rollout.REGION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "READONLY_PREFLIGHT_PASS"
                  if all(g["status"] == "PASS" for g in findings.values()) else "BLOCKED",
        "gcp_writes": 0,
        "does_not_validate": ["cross_writer_durable_mutex", "scheduler_pause_resume",
                              "canary_runtime", "job_rollout_and_rollback", "api_traffic_promotion"],
        "gates": findings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = scan()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    # BLOCKED is an actual diagnostic finding; never a release approval.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
