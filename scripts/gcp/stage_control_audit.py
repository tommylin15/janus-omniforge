"""Read-only audit of aged Stage references and duplicate physical payloads.

Run only inside the existing ingestion-core Job with a fenced Scheduler.
This script never updates PostgreSQL nor deletes GCS objects.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os

from ingestion_core.__main__ import _control_plane
from ingestion_core.stage import GcsObjectStore

BUCKET = "gen-lang-client-0593591102-dev-stage"
NOW = datetime.now(timezone.utc)
CUT7 = NOW - timedelta(days=7)
COMPONENT = "stage-explicit-purge-audit"


def utc(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    return None


def main():
    if os.getenv("STAGE_BUCKET") != BUCKET or os.getenv("JANUS_STAGE_AUDIT") != "true":
        raise RuntimeError("stage_audit_wrong_bucket_or_missing_approval")
    with _control_plane() as control, control.connection.cursor() as cursor:
        cursor.execute(
            "SELECT execution_id, status, requested_at, started_at, finished_at, claimed_until, trigger_type "
            "FROM control.executions WHERE status IN ('queued','running','retrying')")
        rows = cursor.fetchall()
    active = {str(x[0]): x for x in rows}
    store = GcsObjectStore(BUCKET)
    current = store.objects("")
    if len(current) > 20000:
        raise RuntimeError("stage_audit_bounded_inventory_required")
    counts = defaultdict(lambda: {"objects": 0, "bytes": 0})
    active_stats = Counter()
    committed = set()
    for item in current:
        parts = item["name"].split("/")
        if len(parts) == 3 and parts[0] == "executions" and parts[2] == "core-commit.json":
            committed.add(parts[1])
    for item in current:
        parts = item["name"].split("/")
        if utc(item["updated"]) >= CUT7:
            continue
        ident = parts[1] if len(parts) > 2 and parts[0] == "executions" else None
        state = active.get(ident) if ident else None
        key = ("active_" + str(state[1]) if state else
               "nonactive_" + ("execution" if ident else "shared"))
        counts[key]["objects"] += 1
        counts[key]["bytes"] += int(item["size"])
        if state:
            active_stats[ident] += 1
    old = [x for x in rows if utc(x[2]) is not None and utc(x[2]) < CUT7]
    print(json.dumps({
        "component": COMPONENT, "status": "PASS", "mode": "read-only",
        "stage_bucket": BUCKET, "inventory_objects": len(current),
        "inventory_bytes": sum(int(x["size"]) for x in current),
        "active_control_executions": len(rows),
        "active_by_status": dict(Counter(str(x[1]) for x in rows)),
        "active_control_executions_requested_older7d": len(old),
        "active_with_live_claim": sum(1 for x in rows if utc(x[5]) is not None and utc(x[5]) > NOW),
        "old_active_claim_expired_or_unclaimed": sum(1 for x in old if utc(x[5]) is None or utc(x[5]) <= NOW),
        "old_active_trigger_types": dict(Counter(str(x[6]) for x in old)),
        "old_active_statuses": dict(Counter(str(x[1]) for x in old)),
        "active_control_executions_with_older7d_stage": len(active_stats),
        "active_executions_with_core_commit_marker": len(set(active_stats).intersection(committed)),
        "older7d_stage_by_execution_state": dict(counts),
        "all_job_states_gcs_mutations": 0,
        "age_cutoff_utc": CUT7.isoformat(),
        "classification": "DB_CONTROL_ACTIVE_NOT_PROOF_OF_RUNNING_CLOUD_JOB",
        "next_action": "Review queued/running/retrying control before retirement; never delete live references blindly."
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
