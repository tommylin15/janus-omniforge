#!/usr/bin/env python3
"""Fail-closed, post-acceptance Cloud Run Service revision retention (latest 10).

This helper is intentionally NOT wired to the legacy Cloud Build release.
The future GitHub Actions release must call it only after all acceptance,
promotion, rollback-readiness and deployment-mutex gates have passed.
Dry-run is the default. No GCS, Artifact Registry, or Cloud Build operations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys


RETENTION_COUNT = 10


class CleanupBlocked(RuntimeError):
    """Deletion is unsafe or evidence is insufficient."""


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise CleanupBlocked("required revision or service identifier is missing")
    return value.strip()


def _traffic_references(entries):
    if not isinstance(entries, list) or not entries:
        raise CleanupBlocked("traffic readback is missing")
    protected = set()
    weights = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("latestRevision"):
            raise CleanupBlocked("dynamic or unknown traffic target")
        revision = _name(entry.get("revisionName"))
        try:
            percent = int(entry.get("percent", 0))
        except (TypeError, ValueError) as error:
            raise CleanupBlocked("unreadable traffic allocation") from error
        if percent < 0 or percent > 100:
            raise CleanupBlocked("invalid traffic allocation")
        if percent or entry.get("tag"):
            protected.add(revision)
        weights[revision] = weights.get(revision, 0) + percent
    if sum(weights.values()) != 100:
        raise CleanupBlocked("traffic readback does not total 100 percent")
    return protected, weights


def _timestamp(value):
    if not isinstance(value, str):
        raise CleanupBlocked("revision creation timestamp missing")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("timezone missing")
        return instant.astimezone(timezone.utc)
    except ValueError as error:
        raise CleanupBlocked("revision creation timestamp unreadable") from error


def plan(service, revisions, service_name, current, rollback):
    """Return deletion candidates; never choose a live, tagged, or rollback revision."""
    service_name, current, rollback = map(_name, (service_name, current, rollback))
    if current == rollback:
        raise CleanupBlocked("current and previous successful revisions must differ")
    if not isinstance(service, dict) or not isinstance(revisions, list):
        raise CleanupBlocked("service or revisions inventory unreadable")
    status = service.get("status") or {}
    if not any(c.get("type") == "Ready" and str(c.get("status")) == "True"
               for c in status.get("conditions", []) if isinstance(c, dict)):
        raise CleanupBlocked("service not Ready")
    if (status.get("latestCreatedRevisionName") != current
            or status.get("latestReadyRevisionName") != current):
        raise CleanupBlocked("unverified latest revision or pending candidate")
    protected, weights = _traffic_references(status.get("traffic"))
    if weights.get(current) != 100:
        raise CleanupBlocked("expected release is not serving 100 percent of traffic")
    # Spec traffic may still point to LATEST or a candidate that will receive requests.
    spec_traffic = (service.get("spec") or {}).get("traffic", [])
    if spec_traffic:
        spec_refs, _ = _traffic_references(spec_traffic)
        protected.update(spec_refs)
    inventory = {}
    for item in revisions:
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
        name = metadata.get("name")
        timestamp = metadata.get("creationTimestamp")
        labels = metadata.get("labels") or {}
        if not name or not timestamp or not isinstance(labels, dict):
            raise CleanupBlocked("incomplete revision inventory")
        if labels.get("serving.knative.dev/service") != service_name:
            raise CleanupBlocked("revision service ownership not confirmed")
        if name in inventory:
            raise CleanupBlocked("duplicate revision identity")
        inventory[name] = _timestamp(timestamp)
    if current not in inventory or rollback not in inventory:
        raise CleanupBlocked("current or verified rollback revision absent")
    if inventory[rollback] >= inventory[current]:
        raise CleanupBlocked("rollback is not older than promoted revision")
    if any(name not in inventory for name in protected):
        raise CleanupBlocked("traffic/tag references unknown revision")
    # Keep ten *newest* revisions even if none receives traffic. The verified
    # last successful release and all traffic/tag references may extend the
    # protected set beyond ten; never delete a referenced candidate to hit a cap.
    latest_ten = sorted(inventory,
                        key=lambda name: (inventory[name], name),
                        reverse=True)[:RETENTION_COUNT]
    keep = set(latest_ten) | {current, rollback} | protected
    delete = sorted((name for name in inventory if name not in keep),
                    key=lambda name: (inventory[name], name))
    return {"service": service_name, "current": current, "rollback": rollback,
            "retained": sorted(keep), "delete": delete,
            "extra_protected": sorted(protected - {current, rollback}),
            "retention_count": RETENTION_COUNT, "total": len(inventory)}


def _gcloud(project, region, *arguments, json_output=True):
    command = ["gcloud", *arguments, "--project", project, "--region", region]
    if json_output:
        command += ["--format=json"]
    else:
        command += ["--quiet"]
    result = subprocess.run(command, capture_output=True, text=True, check=False,
                            timeout=90)
    if result.returncode:
        # Never echo raw gcloud stderr: it may contain sensitive payloads.
        raise CleanupBlocked("GCP command failed; inspect protected Actions step logs")
    if json_output:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise CleanupBlocked("GCP inventory JSON unreadable") from error
    return None


def _inventory(project, region, service_name):
    service = _gcloud(project, region, "run", "services", "describe", service_name)
    revisions = _gcloud(project, region, "run", "revisions", "list",
                        "--service", service_name)
    return service, revisions


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep latest 10 Cloud Run Service revisions plus any protected references")
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--current-revision", required=True)
    parser.add_argument("--rollback-revision", required=True)
    parser.add_argument("--apply", action="store_true", help="irreversibly delete only safe older revisions")
    args = parser.parse_args(argv)
    try:
        if args.apply and not (
            os.environ.get("JANUS_RELEASE_ACCEPTANCE") == "PASS"
            and os.environ.get("JANUS_DEPLOYMENT_MUTEX_HELD") == "true"
            and os.environ.get("JANUS_ROLLBACK_DIGEST_VERIFIED") == "true"
        ):
            raise CleanupBlocked("acceptance, deployment mutex and rollback digest gates required")
        service, revisions = _inventory(args.project, args.region, args.service)
        proposed = plan(service, revisions, args.service,
                        args.current_revision, args.rollback_revision)
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", **proposed},
                         ensure_ascii=False), flush=True)
        if args.apply:
            for name in proposed["delete"]:
                # Recheck before EACH irreversible operation, even while holding the caller's mutex.
                fresh_service, fresh_revisions = _inventory(args.project, args.region, args.service)
                current_plan = plan(fresh_service, fresh_revisions, args.service,
                                    args.current_revision, args.rollback_revision)
                if name not in current_plan["delete"]:
                    raise CleanupBlocked("cleanup target changed; abort before delete")
                _gcloud(args.project, args.region, "run", "revisions", "delete", name,
                        json_output=False)
                print(json.dumps({"deleted": name}, ensure_ascii=False), flush=True)
            # Deletion is eventually consistent; report the immediate readback, not an invented PASS.
            fresh_service, fresh_revisions = _inventory(args.project, args.region, args.service)
            final = plan(fresh_service, fresh_revisions, args.service,
                         args.current_revision, args.rollback_revision)
            print(json.dumps({"post_cleanup": final, "pending_readback": bool(final["delete"])},
                             ensure_ascii=False), flush=True)
        return 0
    except (CleanupBlocked, subprocess.TimeoutExpired) as error:
        print(json.dumps({"cleanup": "BLOCKED", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
