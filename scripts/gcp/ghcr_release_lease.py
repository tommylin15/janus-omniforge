#!/usr/bin/env python3
"""Atomic, owner-fenced GitHub Git-ref lease for Janus dev GHCR releases.

The lease is *not* permission to promote Cloud Run: legacy Cloud Build may
still mutate runtime without observing this ref. No clocks/TTLs or force-unlock.
Only the recorded owner may release; failed/unknown runtime recovery must keep
its lease instead of silently discarding the fencing signal.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

TAG = "janus-ghcr-deploy-global-v1"
MARKER = "JANUS_DEPLOY_LEASE_V1:"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


class LeaseBlocked(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status: int | None):
        self.status = status
        super().__init__("GitHub API returned an error")


@dataclass(frozen=True)
class Owner:
    repo: str
    run_id: int
    run_attempt: int
    source_sha: str

    def validate(self) -> None:
        if not REPO_RE.fullmatch(self.repo) or not SHA_RE.fullmatch(self.source_sha):
            raise LeaseBlocked("invalid_restrictive_owner_identity")
        if self.run_id < 1 or self.run_attempt < 1:
            raise LeaseBlocked("invalid_workflow_run_identity")

    def fields(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "run_attempt": self.run_attempt,
                "source_sha": self.source_sha}


class GhApi:
    def __call__(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        args = ["gh", "api", "--method", method, path]
        if body is not None:
            args += ["--input", "-"]
        output = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                                text=True, capture_output=True, check=False, timeout=25)
        if output.returncode:
            # Do not propagate GitHub response body, URLs, headers, or credentials.
            status = None
            match = re.search(r"HTTP (\d{3})", output.stderr)
            if match:
                status = int(match.group(1))
            raise ApiError(status)
        if method == "DELETE":
            return None
        return json.loads(output.stdout)


def ref_path(owner: Owner) -> str:
    return f"repos/{owner.repo}/git/ref/tags/{TAG}"


def get_ref(api: Callable, owner: Owner) -> dict[str, Any] | None:
    try:
        result = api("GET", ref_path(owner))
    except ApiError as exc:
        if exc.status == 404:
            return None
        raise LeaseBlocked("lease_ref_readback_failed") from exc
    if not isinstance(result, dict):
        raise LeaseBlocked("invalid_lease_ref_response")
    return result


def _validated_lease(api: Callable, owner: Owner) -> str:
    ref = get_ref(api, owner)
    if ref is None:
        raise LeaseBlocked("lease_missing")
    obj = ref.get("object") if isinstance(ref.get("object"), dict) else {}
    tagsha = obj.get("sha")
    if (obj.get("type") != "tag" or not isinstance(tagsha, str)
            or not SHA_RE.fullmatch(tagsha)):
        raise LeaseBlocked("lease_ref_not_annotated_tag")
    try:
        tag = api("GET", f"repos/{owner.repo}/git/tags/{tagsha}")
    except ApiError as exc:
        raise LeaseBlocked("lease_tag_unreadable") from exc
    if not isinstance(tag, dict) or tag.get("tag") != TAG:
        raise LeaseBlocked("invalid_lease_tag")
    raw = tag.get("message")
    if not isinstance(raw, str) or not raw.startswith(MARKER):
        raise LeaseBlocked("invalid_lease_metadata")
    try:
        recorded = json.loads(raw[len(MARKER):])
    except ValueError as exc:
        raise LeaseBlocked("lease_metadata_unreadable") from exc
    if recorded != owner.fields():
        raise LeaseBlocked("lease_owned_by_other_run")
    target = tag.get("object") if isinstance(tag.get("object"), dict) else {}
    if target.get("type") != "commit" or target.get("sha") != owner.source_sha:
        raise LeaseBlocked("lease_source_commit_mismatch")
    return tagsha


def acquire(api: Callable, owner: Owner) -> str:
    owner.validate()
    # Inspection improves diagnostics; only GitHub's atomic POST-ref is the lock.
    if get_ref(api, owner) is not None:
        raise LeaseBlocked("lease_busy")
    body = {"tag": TAG, "message": MARKER + json.dumps(owner.fields(), sort_keys=True,
                                                           separators=(",", ":")),
            "object": owner.source_sha, "type": "commit"}
    try:
        tag = api("POST", f"repos/{owner.repo}/git/tags", body)
        tagsha = tag.get("sha") if isinstance(tag, dict) else None
        if not isinstance(tagsha, str) or not SHA_RE.fullmatch(tagsha):
            raise LeaseBlocked("annotated_tag_creation_unverified")
        # GitHub rejects an existing ref atomically (422); never overwrite.
        api("POST", f"repos/{owner.repo}/git/refs",
            {"ref": f"refs/tags/{TAG}", "sha": tagsha})
    except ApiError as exc:
        raise LeaseBlocked("atomic_lease_claim_rejected_or_unavailable") from exc
    verified = _validated_lease(api, owner)
    if verified != tagsha:
        raise LeaseBlocked("lease_readback_mismatch")
    return tagsha


def release(api: Callable, owner: Owner) -> None:
    owner.validate()
    # Caller must first establish workload/scheduler/traffic recovery. This
    # function never infers safe recovery from age, timeout, or owner death.
    _validated_lease(api, owner)
    try:
        api("DELETE", f"repos/{owner.repo}/git/refs/tags/{TAG}")
    except ApiError as exc:
        raise LeaseBlocked("lease_release_failed") from exc
    if get_ref(api, owner) is not None:
        raise LeaseBlocked("lease_release_readback_failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("acquire", "assert", "release"))
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--run-id", type=int, default=int(os.getenv("GITHUB_RUN_ID", "0")))
    parser.add_argument("--run-attempt", type=int, default=int(os.getenv("GITHUB_RUN_ATTEMPT", "0")))
    parser.add_argument("--sha", default=os.getenv("GITHUB_SHA", ""))
    parser.add_argument("--safe-to-release", action="store_true")
    args = parser.parse_args()
    owner = Owner(args.repo, args.run_id, args.run_attempt, args.sha)
    try:
        owner.validate()
        if args.operation == "release" and not args.safe_to_release:
            raise LeaseBlocked("explicit_recovery_or_success_evidence_required")
        api = GhApi()
        if args.operation == "acquire":
            acquire(api, owner)
            state = "CLAIMED"
        elif args.operation == "assert":
            _validated_lease(api, owner)
            state = "OWNED"
        else:
            release(api, owner)
            state = "RELEASED"
        print(json.dumps({"status": state, "tag": TAG, "run_id": owner.run_id,
                          "run_attempt": owner.run_attempt, "source_sha": owner.source_sha,
                          "gcp_writes": 0}, sort_keys=True))
        return 0
    except LeaseBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "gcp_writes": 0}),
              file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
