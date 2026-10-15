"""Exact preflight-only abandoned deploy lease recovery; no GCP mutation."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import ghcr_jobs_rollout as rollout
import ghcr_release_lease as lease
import ghcr_terminal_lease_recovery as terminal

REPO = "tommylin15/janus-omniforge"
OWNER_RUN = 38673116310
OWNER_SHA = "884e289aab5ed59d93def3043da42047e84e4d0d"
TAG_SHA = "16dd8828c9161c64bbe6cdc10e8cff3f55dbc5bf"
RECEIPT_SHA256 = "12891d7f1064f0621c76a8b31f6da8b2d00366e74d6fce6c6a899761bfffe95d"
SOURCE_SHA = "a0ab38a545a786a33d6b68ce7493e625d94d8046"


def verify_receipt(raw: bytes) -> dict:
    if sha256(raw).hexdigest() != RECEIPT_SHA256:
        raise ValueError("preflight_receipt_hash_mismatch")
    journal = json.loads(raw)
    if (journal.get("source_sha") != SOURCE_SHA
            or journal.get("rollback_mode") != "reversible_ghcr"
            or journal.get("phase") != "RECOVERY_REQUIRED"
            or journal.get("failed_stage") != "preflight"
            or journal.get("operations") != []
            or journal.get("canaries") != []
            or journal.get("snapshots") != {}
            or not isinstance(journal.get("scheduler_hash"), str)
            or len(journal["scheduler_hash"]) != 64
            or set(journal.get("targets", {})) != {name for name, _ in rollout.JOB_COMPONENT}):
        raise ValueError("preflight_receipt_identity_mismatch")
    return journal


def verify_original_runtime(request: dict, journal: dict) -> None:
    rollout.legacy_writers()
    schedule = rollout.scheduler()
    if (schedule.get("state") != "ENABLED"
            or rollout.scheduler_fingerprint(schedule) != journal["scheduler_hash"]):
        raise ValueError("preflight_original_scheduler_drift")
    images = request["expected_images"]
    hashes = request["expected_config_hashes"]
    targets = {name for name, _ in rollout.JOB_COMPONENT}
    if set(images) != targets or set(hashes) != targets:
        raise ValueError("preflight_expected_job_set_mismatch")
    for name in targets:
        current = rollout.job(name)
        if rollout.image(current) != images[name] or rollout.fingerprint(current) != hashes[name]:
            raise ValueError("preflight_original_job_drift")
    rollout.job("janus-research-big-move-500")  # Read-only, never change research.


def main() -> None:
    if os.getenv("GITHUB_REPOSITORY") != REPO or os.getenv("GITHUB_REF") != "refs/heads/main":
        raise ValueError("wrong_repository_or_branch")
    request = json.loads(Path("ops/ghcr-preflight-lease-recovery-request.json").read_text())
    if (request.get("intent") != "release-exact-preflight-no-mutation-lease"
            or request.get("approved") is not True or request.get("no_gcp_mutation") is not True
            or request.get("owner_run") != OWNER_RUN or request.get("owner_source_sha") != OWNER_SHA
            or request.get("tag_sha") != TAG_SHA or request.get("receipt_sha256") != RECEIPT_SHA256):
        raise ValueError("preflight_recovery_request_invalid")
    run = terminal._gh(f"repos/{REPO}/actions/runs/{OWNER_RUN}")
    if (run.get("id") != OWNER_RUN or run.get("run_attempt") != 1
            or run.get("head_sha") != OWNER_SHA
            or run.get("name") != "Janus GHCR controlled Jobs rollout"
            or run.get("status") != "completed" or run.get("conclusion") != "failure"):
        raise ValueError("preflight_owner_not_terminal_failed")
    owner = lease.Owner(REPO, OWNER_RUN, 1, OWNER_SHA)
    api = lease.GhApi()
    if lease._validated_lease(api, owner) != TAG_SHA:
        raise ValueError("preflight_exact_lease_tag_mismatch")
    directory = Path("/tmp/ghcr-preflight-recovery-artifact")
    directory.mkdir(mode=0o700, exist_ok=True)
    subprocess.run(["gh", "run", "download", str(OWNER_RUN), "--name",
                    "ghcr-jobs-rollout-receipt", "--dir", str(directory)],
                   check=True, timeout=90, capture_output=True)
    journal = verify_receipt((directory / "ghcr-jobs-rollout.json").read_bytes())
    before_api = terminal.service_identity(terminal._service())
    verify_original_runtime(request, journal)
    # Preflight did not pause Scheduler or update Jobs; active natural executions
    # cannot be used to retain an otherwise abandoned, non-mutating Git ref.
    repeat = terminal._gh(f"repos/{REPO}/actions/runs/{OWNER_RUN}")
    if repeat.get("id") != OWNER_RUN or repeat.get("status") != "completed" or repeat.get("conclusion") != "failure":
        raise ValueError("preflight_owner_changed")
    if lease._validated_lease(api, owner) != TAG_SHA:
        raise ValueError("preflight_lease_changed")
    verify_original_runtime(request, journal)
    if before_api != terminal.service_identity(terminal._service()):
        raise ValueError("preflight_api_traffic_changed")
    api("DELETE", f"repos/{REPO}/git/refs/tags/{lease.TAG}")
    if lease.get_ref(api, owner) is not None:
        raise ValueError("preflight_lease_delete_not_confirmed")
    print(json.dumps({"status":"PASS","operation":"exact_preflight_no_mutation_lease_release",
                      "original_run":OWNER_RUN,"scheduler_unchanged":True,
                      "four_job_images_unchanged":True,"api_traffic_unchanged":True,
                      "gcp_writes":0,"canonical_writes":0},sort_keys=True))


if __name__ == "__main__":
    main()
