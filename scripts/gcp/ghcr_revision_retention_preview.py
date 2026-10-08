#!/usr/bin/env python3
"""Pre-promotion Cloud Run Service revision retention preview (strictly read-only).

This is NOT a deletion candidate manifest: rollback ancestry, authenticated
release acceptance, all traffic/tag references and a held cross-system mutex
must be revalidated after actual promotion. No GCP writes or delete commands.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

SERVICE = "janus-api"
RETAIN = 10


class PreviewBlocked(ValueError):
    pass


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PreviewBlocked("missing_revision_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone_required")
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise PreviewBlocked("invalid_revision_timestamp") from exc


def _referenced(traffic: Any, *, require_100: bool) -> tuple[set[str], set[str], list[str]]:
    if not isinstance(traffic, list) or (require_100 and not traffic):
        raise PreviewBlocked("missing_traffic")
    protected, tagged, active = set(), set(), []
    total = 0
    for item in traffic:
        if not isinstance(item, dict) or item.get("latestRevision") is True:
            raise PreviewBlocked("dynamic_or_invalid_traffic_target")
        name = item.get("revisionName")
        if not isinstance(name, str) or not name:
            raise PreviewBlocked("missing_traffic_revision")
        percent = item.get("percent")
        if percent is None:
            percent = 0
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            raise PreviewBlocked("invalid_traffic_percent")
        total += percent
        tag = item.get("tag")
        if tag is not None:
            if not isinstance(tag, str) or not tag:
                raise PreviewBlocked("invalid_tag")
            tagged.add(name)
        if percent:
            active.append(name)
        # Even zero-percent untagged explicit routes are protected.
        protected.add(name)
    if require_100 and (total != 100 or len(active) != 1):
        raise PreviewBlocked("live_traffic_not_single_100")
    return protected, tagged, active


def preview(service: Any, revisions: Any) -> dict[str, Any]:
    if not isinstance(service, dict) or not isinstance(revisions, list):
        raise PreviewBlocked("invalid_runtime_payload")
    metadata = service.get("metadata")
    status = service.get("status")
    if not isinstance(metadata, dict) or metadata.get("name") != SERVICE or not isinstance(status, dict):
        raise PreviewBlocked("wrong_or_missing_service")
    conditions = status.get("conditions")
    if not isinstance(conditions, list) or not any(
        isinstance(x, dict) and x.get("type") == "Ready" and x.get("status") == "True"
        for x in conditions
    ):
        raise PreviewBlocked("service_not_ready")
    generation = metadata.get("generation")
    observed = status.get("observedGeneration")
    if not (str(generation).isdigit() and str(observed).isdigit()
            and int(generation) == int(observed)):
        raise PreviewBlocked("service_not_reconciled")
    routes, tagged, active = _referenced(status.get("traffic"), require_100=True)
    spec = service.get("spec", {})
    if not isinstance(spec, dict):
        raise PreviewBlocked("invalid_spec")
    spec_traffic = spec.get("traffic")
    if spec_traffic is not None:
        specified, _, _ = _referenced(spec_traffic, require_100=False)
        routes.update(specified)
    inventory = {}
    for row in revisions:
        meta = row.get("metadata") if isinstance(row, dict) else None
        if not isinstance(meta, dict):
            raise PreviewBlocked("invalid_revision")
        name = meta.get("name")
        labels = meta.get("labels")
        if (not isinstance(name, str) or not name or name in inventory
                or not isinstance(labels, dict)
                or labels.get("serving.knative.dev/service") != SERVICE):
            raise PreviewBlocked("revision_inventory_incomplete_or_wrong_service")
        inventory[name] = _utc(meta.get("creationTimestamp"))
    if not inventory:
        raise PreviewBlocked("no_revisions")
    latest = status.get("latestReadyRevisionName")
    latest_created = status.get("latestCreatedRevisionName")
    if not isinstance(latest, str) or not isinstance(latest_created, str):
        raise PreviewBlocked("latest_revision_unknown")
    preserve = routes | {latest, latest_created}
    if not preserve.issubset(inventory):
        raise PreviewBlocked("referenced_revision_missing_from_inventory")
    last_ten = sorted(inventory, key=lambda n: (inventory[n], n), reverse=True)[:RETAIN]
    preserved = preserve | set(last_ten)
    # Not a deletion authorization: we don't know the last successfully
    # promoted release nor the rollback digest at this pre-promotion stage.
    return {
        "status": "PREPROMOTION_PREVIEW_ONLY",
        "service": SERVICE,
        "total_revisions": len(inventory),
        "latest_ten_count": len(last_ten),
        "protected_references_count": len(preserve),
        "protected_tagged_count": len(tagged),
        "tagged_revision_names": sorted(tagged),
        "active_revision_names": active,
        "latest_ready_revision": latest,
        "latest_created_revision": latest_created,
        "provisional_unreferenced_count": len(inventory) - len(preserved),
        "revisions_to_delete_now": 0,
        "resource_writes": 0,
        "apply_authorized": False,
        "remaining_release_gates": [
            "authenticated_owner_candidate_acceptance",
            "full_100_percent_promotion_and_readback",
            "verified_previous_successful_rollback_revision_and_digest",
            "shared_release_lock_across_all_writers",
            "post_promotion_reinventory_and_tag_protection",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-json", type=Path, required=True)
    parser.add_argument("--revisions-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = preview(json.loads(args.service_json.read_text()),
                         json.loads(args.revisions_json.read_text()))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED",
                          "reason": str(exc) if isinstance(exc, PreviewBlocked)
                          else "invalid_or_missing_readback",
                          "resource_writes": 0,
                          "apply_authorized": False}, sort_keys=True))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
