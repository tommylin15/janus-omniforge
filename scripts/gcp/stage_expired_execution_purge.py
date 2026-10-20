"""Explicitly approved aged Stage execution raw purge; no Core/Mart/Private writes.

This one-off operates inside the existing Cloud Run ingestion Job, under the
GitHub runtime lease and Scheduler pause + all-page execution fence. It ignores
STALE PostgreSQL 'running' state only when its lease has expired or is absent.
It does not change control rows, delete recent data, or use MD5 similarity.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import os
from collections import Counter

from ingestion_core.__main__ import _control_plane
from ingestion_core.stage import GcsObjectStore

BUCKET = "gen-lang-client-0593591102-dev-stage"
COMPONENT = "stage-aged-stale-execution-purge"
MAX_ITEMS = 5500
MAX_BYTES = 130_000_000
RETENTION_DAYS = 7


def parsed_time(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def stale_execution_ids(rows, now):
    """Only old RUNNING records without a live lease qualify for override."""
    cutoff = now - timedelta(days=RETENTION_DAYS)
    return frozenset(
        str(execution_id) for execution_id, status, requested_at, claimed_until in rows
        if status == "running"
        and parsed_time(requested_at) is not None
        and parsed_time(requested_at) < cutoff
        and (parsed_time(claimed_until) is None or parsed_time(claimed_until) <= now)
    )


def select_candidates(items, eligible_ids, now):
    cutoff = now - timedelta(days=RETENTION_DAYS)
    results = []
    for item in items:
        parts = item["name"].split("/")
        if (len(parts) >= 4
                and parts[0] == "executions"
                and parts[1] in eligible_ids
                and parts[2] == "stage"
                and parsed_time(item["updated"]) is not None
                and parsed_time(item["updated"]) < cutoff):
            results.append(item)
    return results


def control_rows():
    with _control_plane() as control, control.connection.cursor() as cur:
        cur.execute("SELECT execution_id, status, requested_at, claimed_until "
                    "FROM control.executions WHERE status IN ('queued','running','retrying')")
        return cur.fetchall()


def current_snapshot(store):
    current = store.objects("")
    if len(current) > 20000:
        raise RuntimeError("stage_object_inventory_over_budget")
    return current


def main():
    mode = os.environ.get("JANUS_STAGE_AGED_PURGE_MODE")
    if (os.environ.get("STAGE_BUCKET") != BUCKET
            or mode not in {"dry-run", "apply"}
            or os.environ.get("JANUS_STAGE_AGED_PURGE_APPROVED") != "true"):
        raise RuntimeError("user_authorized_stage_purge_scope_required")
    now = datetime.now(timezone.utc)
    store = GcsObjectStore(BUCKET)
    before = current_snapshot(store)
    rows = control_rows()
    eligible_ids = stale_execution_ids(rows, now)
    candidates = select_candidates(before, eligible_ids, now)
    count = len(candidates)
    total_bytes = sum(int(row["size"]) for row in candidates)
    if count > MAX_ITEMS or total_bytes > MAX_BYTES or len(eligible_ids) > 50:
        raise RuntimeError("stage_stale_purge_budget_exceeded")
    # During apply do not trust only the first PG snapshot or previous LIST;
    # fail closed if a record acquires a real lease or any object changes.
    result = {
        "component": COMPONENT, "status": "PASS", "mode": mode,
        "policy": {"older_than_days": RETENTION_DAYS, "stale_status": "running",
                   "live_claim_preservation": True},
        "control_active_count": len(rows), "stale_execution_count": len(eligible_ids),
        "planned_objects": count, "planned_bytes": total_bytes,
        "before": {"objects": len(before), "bytes": sum(int(x["size"]) for x in before)},
        "deleted_objects": 0, "deleted_bytes": 0, "core_deleted": 0,
        "mart_deleted": 0, "private_deleted": 0,
        "generation_readback": "NOT_APPLICABLE",
    }
    if mode == "dry-run":
        result["after"] = result["before"]
        print(json.dumps(result, sort_keys=True), flush=True)
        return
    if stale_execution_ids(control_rows(), now) != eligible_ids:
        raise RuntimeError("stage_control_lease_or_status_drift_before_purge")
    refreshed = current_snapshot(store)
    before_set = {(x["name"], x["generation"], str(x["size"])) for x in before}
    if {(x["name"], x["generation"], str(x["size"])) for x in refreshed} != before_set:
        raise RuntimeError("stage_generation_or_size_drift_before_purge")
    deleted = []
    try:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(store.delete, item["name"], generation=item["generation"]): item
                       for item in candidates}
            for future in as_completed(futures):
                item = futures[future]
                future.result()
                deleted.append(item)
    except Exception as error:
        # A network problem can leave partial deletions; never claim 0 or PASS.
        result.update(status="PARTIAL", error_type=type(error).__name__,
                      delete_calls_confirmed=len(deleted))
        print(json.dumps(result, sort_keys=True), flush=True)
        raise
    after = current_snapshot(store)
    after_set = {(x["name"], x["generation"], str(x["size"])) for x in after}
    deleted_set = {(x["name"], x["generation"], str(x["size"])) for x in candidates}
    actual_count = len(before_set) - len(after_set)
    actual_bytes = result["before"]["bytes"] - sum(int(x["size"]) for x in after)
    if (after_set != before_set - deleted_set or actual_count != count
            or actual_bytes != total_bytes):
        result.update(status="PARTIAL", observed_objects_removed=actual_count,
                      observed_bytes_removed=actual_bytes,
                      generation_readback="FAILED")
        print(json.dumps(result, sort_keys=True), flush=True)
        raise RuntimeError("stage_aged_generation_readback_mismatch")
    result.update(deleted_objects=count, deleted_bytes=total_bytes,
                  after={"objects": len(after), "bytes": sum(int(x["size"]) for x in after)},
                  generation_readback="PASS", status="PASS")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
