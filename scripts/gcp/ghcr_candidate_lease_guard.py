#!/usr/bin/env python3
"""Fail closed before releasing a GHCR API candidate's deployment lease.

This tool reads sanitized Cloud Run Service snapshots only. It never changes
traffic, Jobs, Schedulers, images, or secrets; output omits service payloads.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

IMAGE = re.compile(r"^ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}$")
TAG = re.compile(r"^ghcr-[0-9a-f]{12}$")


def _mapping(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, dict) else {}


def _array(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def positive_traffic(data: Mapping[str, Any]) -> list[tuple[str, int]]:
    result = []
    for v in _array(_mapping(data.get("status")).get("traffic")):
        if not isinstance(v, dict):
            return []
        percent = v.get("percent", 0)
        if isinstance(percent, bool) or not isinstance(percent, int):
            return []
        if percent > 0:
            result.append((v.get("revisionName"), percent))
    return result


def ready_and_reconciled(data: Mapping[str, Any]) -> bool:
    meta = _mapping(data.get("metadata"))
    status = _mapping(data.get("status"))
    generation = meta.get("generation")
    observed = status.get("observedGeneration")
    return bool(
        str(generation).isdigit() and str(observed).isdigit()
        and int(generation) == int(observed)
        and any(isinstance(c, dict) and c.get("type") == "Ready"
                and c.get("status") == "True"
                for c in _array(status.get("conditions")))
    )


def validate(before: Any, after: Any, expected_image: str, candidate_tag: str) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {"status": "BLOCKED", "reasons": ["snapshot_invalid"], "gcp_writes": 0}
    if not IMAGE.fullmatch(expected_image) or not TAG.fullmatch(candidate_tag):
        errors.append("expected_identity_invalid")
    old = positive_traffic(before)
    current = positive_traffic(after)
    if _mapping(before.get("metadata")).get("name") != "janus-api":
        errors.append("baseline_service_mismatch")
    if _mapping(after.get("metadata")).get("name") != "janus-api":
        errors.append("live_service_mismatch")
    if len(old) != 1 or old[0][1] != 100 or not isinstance(old[0][0], str) or not old[0][0]:
        errors.append("baseline_traffic_unverifiable")
    if current != old or len(current) != 1 or current[0][1] != 100:
        errors.append("active_traffic_changed_or_split")
    if not ready_and_reconciled(after):
        errors.append("service_not_ready_or_unreconciled")
    # The new immutable image must be the deployed template; if deployment was
    # never attempted, the old stable baseline is sufficient for release.
    status = _mapping(after.get("status"))
    template = _mapping(_mapping(_mapping(after.get("spec")).get("template")).get("spec"))
    containers = _array(template.get("containers"))
    target = containers[0].get("image") if containers and isinstance(containers[0], dict) else ""
    tagged = [t for t in _array(status.get("traffic"))
              if isinstance(t, dict) and t.get("tag") == candidate_tag]
    if len(tagged) > 1:
        errors.append("candidate_tag_duplicated")
    if tagged:
        candidate = tagged[0]
        if candidate.get("percent", 0) != 0 or not candidate.get("revisionName"):
            errors.append("candidate_tag_unsafe")
        if target != expected_image:
            errors.append("candidate_digest_mismatch")
    else:
        # Missing candidate is legitimate only before mutation began; callers
        # must not infer that from a failed or ambiguous gcloud deploy.
        errors.append("candidate_tag_not_observed")
    # Preserve all previous tagged routes. No implicit deletion during a
    # candidate deployment is acceptable when releasing the global lease.
    previous_tags = {
        (t.get("tag"), t.get("revisionName"), t.get("percent", 0))
        for t in _array(_mapping(before.get("status")).get("traffic"))
        if isinstance(t, dict) and t.get("tag") and t.get("tag") != candidate_tag
    }
    after_tags = {
        (t.get("tag"), t.get("revisionName"), t.get("percent", 0))
        for t in _array(status.get("traffic"))
        if isinstance(t, dict) and t.get("tag") and t.get("tag") != candidate_tag
    }
    if not previous_tags.issubset(after_tags):
        errors.append("prior_tag_routes_changed")
    return {"status": "SAFE_TO_RELEASE" if not errors else "BLOCKED",
            "reasons": sorted(set(errors)), "gcp_writes": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        report = validate(json.loads(args.before.read_text()),
                          json.loads(args.after.read_text()),
                          args.image, args.tag)
    except (OSError, ValueError, UnicodeError):
        report = {"status": "BLOCKED", "reasons": ["snapshot_missing_or_invalid"],
                  "gcp_writes": 0}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "SAFE_TO_RELEASE" else 78


if __name__ == "__main__":
    raise SystemExit(main())
