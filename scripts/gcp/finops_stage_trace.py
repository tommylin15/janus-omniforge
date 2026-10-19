"""Read-only Stage retention provenance and lifecycle trace; sanitized logs."""
import json
import subprocess
from datetime import datetime

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-stage"
START = "2026-10-19T15:28:00Z"
END = "2026-10-19T23:05:00Z"


def command(*args):
    return json.loads(subprocess.check_output(
        args, text=True, stderr=subprocess.DEVNULL, timeout=100))


def sanitize_logs(entries):
    results = []
    for row in entries:
        payload = row.get("jsonPayload")
        if not isinstance(payload, dict):
            try:
                payload = json.loads(row.get("textPayload") or "")
            except (ValueError, TypeError):
                continue
        if not isinstance(payload, dict):
            continue
        component = payload.get("component")
        if component not in ("stage-only-retention", "data-retention"):
            continue
        stage = payload.get("stage") or {}
        if not isinstance(stage, dict):
            stage = {}
        results.append({
            "timestamp": row.get("timestamp"),
            "execution": (row.get("labels") or {}).get("run.googleapis.com/execution_name"),
            "component": component,
            "mode": payload.get("mode"),
            "status": payload.get("status"),
            "stage_deleted_objects": stage.get("deleted_objects"),
            "stage_deleted_bytes": stage.get("deleted_bytes"),
            "generation_readback": payload.get("generation_readback"),
        })
    return results


def main():
    selector = (f'resource.type="cloud_run_job" AND '
                f'resource.labels.job_name="janus-ingestion-core" AND '
                f'timestamp>="{START}" AND timestamp<="{END}"')
    entries = command("gcloud", "logging", "read", selector,
                      "--project="+PROJECT, "--limit=1500", "--order=asc",
                      "--format=json")
    bucket = command("gcloud", "storage", "buckets", "describe",
                     "gs://"+BUCKET, "--format=json")
    rules = []
    for rule in (bucket.get("lifecycle") or {}).get("rule", []):
        action, condition = rule.get("action") or {}, rule.get("condition") or {}
        rules.append({"action": action.get("type"), "age_days": condition.get("age"),
                      "is_live": condition.get("isLive"), "num_newer_versions": condition.get("numNewerVersions")})
    receipts = sanitize_logs(entries)
    target = [x for x in receipts if x.get("stage_deleted_objects") == 2050
              and x.get("stage_deleted_bytes") == 650115151]
    print(json.dumps({
        "component": "stage-retention-trace", "mode": "read-only",
        "window_utc": [START, END], "scanned_log_entries": len(entries),
        "log_scan_limit": 1500, "scan_truncated_possible": len(entries) == 1500,
        "lifecycle_rules": rules, "stage_cleanup_receipts": receipts,
        "exact_prior_dry_run_delta_receipts": len(target),
        "source_attribution": ("CONFIRMED_LOG_RECEIPT" if target else "NOT_VERIFIED"),
        "stage_object_mutations": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
