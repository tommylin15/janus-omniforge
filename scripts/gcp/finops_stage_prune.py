"""Bounded one-shot pruning of expired public Stage objects in existing Cloud Run job.

No Core/Mart/Private write. Invoked only under the existing scheduler/worker fence.
Uses immutable GCS generation deletion, never releases object holds.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from ingestion_core.__main__ import _control_plane
from ingestion_core.retention import POLICY, clean_stage
from ingestion_core.stage import GcsObjectStore

BUCKET = "gen-lang-client-0593591102-dev-stage"
COMPONENT = "finops-stage-prune"
MAX_OBJECTS = 6000
MAX_BYTES = 256 * 1024 * 1024
MAX_BUCKET_OBJECTS = 20000


def _capacity(items):
    return {"objects": len(items), "bytes": sum(int(x["size"]) for x in items)}


def run():
    mode = os.environ.get("JANUS_STAGE_PRUNE_MODE", "")
    if (os.environ.get("JANUS_APPROVED_STAGE_PRUNE") != "true"
            or mode not in ("dry-run", "apply")
            or os.environ.get("STAGE_BUCKET") != BUCKET):
        raise ValueError("stage_prune_requires_explicit_bounded_dev_approval")
    now = datetime.now(timezone.utc)
    store = GcsObjectStore(BUCKET)
    # Read the actual control-plane state, never assume that all executions are terminal.
    with _control_plane() as control, control.connection.cursor() as cursor:
        cursor.execute(
            "SELECT execution_id FROM control.executions "
            "WHERE status IN ('queued','running','retrying')"
        )
        active = frozenset(str(row[0]) for row in cursor.fetchall())
    before_items = store.objects("")
    if len(before_items) > MAX_BUCKET_OBJECTS:
        raise RuntimeError("stage_bucket_inventory_exceeds_limit")
    before = _capacity(before_items)
    planned = clean_stage(store, apply=False, now=now, active_executions=active)
    if (planned["planned_objects"] > MAX_OBJECTS
            or planned["planned_bytes"] > MAX_BYTES):
        raise RuntimeError("stage_prune_budget_exceeded")
    # For a write pass, reject a changed inventory before any delete.
    if mode == "apply":
        latest = store.objects("")
        if {(i["name"], i["generation"]) for i in before_items} != {
                (i["name"], i["generation"]) for i in latest}:
            raise RuntimeError("stage_prune_inventory_changed")
        result = clean_stage(store, apply=True, now=now, active_executions=active)
        remaining = store.objects("")
        after = _capacity(remaining)
        if (result["deleted_objects"] != planned["planned_objects"]
                or result["deleted_bytes"] != planned["planned_bytes"]
                or before["objects"] - after["objects"] != result["deleted_objects"]
                or before["bytes"] - after["bytes"] != result["deleted_bytes"]):
            raise RuntimeError("stage_prune_generation_readback_mismatch")
    else:
        result = planned
        after = before
    evidence = {
        "component": COMPONENT, "status": "PASS", "mode": mode,
        "bucket": BUCKET, "policy_stage_days": POLICY["stage_days"],
        "protected_active_executions": len(active),
        "held_active_objects": result["held_active_objects"],
        "planned_objects": planned["planned_objects"],
        "planned_bytes": planned["planned_bytes"],
        "deleted_objects": result["deleted_objects"],
        "deleted_bytes": result["deleted_bytes"],
        "before": before, "after": after,
        "core_objects_deleted": 0, "mart_objects_deleted": 0,
        "private_objects_deleted": 0, "holds_overridden": False,
        "uses_generation_preconditions": True
    }
    print(json.dumps(evidence, sort_keys=True), flush=True)
    return evidence


if __name__ == "__main__":
    run()
