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




def natural_stage_closeout(config):
    """Read-only evidence for the approved 2026-10-20 18:30 Taipei Stage slot."""
    from datetime import datetime, timezone
    window = config.get("window_utc")
    expected = ["2026-10-20T10:25:00Z", "2026-10-20T13:00:00Z"]
    if (window != expected or config.get("no_gcp_mutation") is not True
            or config.get("project") != PROJECT
            or config.get("stage_bucket") != BUCKET):
        raise ValueError("stage48_exact_read_only_scope_required")
    selector = ('resource.type="cloud_run_job" AND '
                'resource.labels.job_name="janus-ingestion-core" AND '
                f'timestamp>="{expected[0]}" AND timestamp<="{expected[1]}"')
    entries = command("gcloud", "logging", "read", selector,
                      "--project="+PROJECT, "--limit=2000", "--order=asc", "--format=json")
    receipts = sanitize_logs(entries)
    good = [r for r in receipts if
            r["component"] == "stage-only-retention" and
            r["status"] == "PASS" and r["mode"] == "apply" and
            r["generation_readback"] == "PASS"]
    results = []
    for record in good[:5]:
        name = record["execution"]
        if not isinstance(name, str) or not name.startswith("janus-ingestion-core-"):
            results.append({"execution": None, "terminal": "UNVERIFIED"})
            continue
        try:
            execution = command("gcloud", "run", "jobs", "executions", "describe", name,
                                "--project="+PROJECT, "--region=us-central1", "--format=json")
            conditions = execution.get("status", {}).get("conditions", []) or execution.get("conditions", [])
            completed = [c for c in conditions if c.get("type") == "Completed"]
            succeeded = bool(execution.get("completionTime") or
                             execution.get("status", {}).get("completionTime"))
            succeeded = succeeded and not execution.get("failedCount") and not execution.get("status", {}).get("failedCount")
            succeeded = succeeded and not any(c.get("state") == "CONDITION_FAILED" or c.get("status") == "False"
                                             for c in completed)
            results.append({"execution": name, "terminal": "PASS" if succeeded else "UNVERIFIED"})
        except (subprocess.CalledProcessError, ValueError):
            results.append({"execution": name, "terminal": "UNVERIFIED"})
    try:
        controller = command("gcloud", "run", "jobs", "describe", "janus-batch-controller",
                             "--project="+PROJECT, "--region=us-central1", "--format=json")
        containers = (controller.get("spec", {}).get("template", {}).get("spec", {}).get("template", {}).get("spec", {}).get("containers")
                      or controller.get("template", {}).get("template", {}).get("containers") or [])
        config_values = [entry.get("value") for item in containers for entry in item.get("env", [])
                         if entry.get("name") == "FINOPS_WEEKLY_MAINTENANCE"]
        weekly = config_values[0] if len(config_values) == 1 else "UNKNOWN"
    except (subprocess.CalledProcessError, ValueError, KeyError):
        weekly = "UNKNOWN"
    # Independently check that the regular Controller tick was present near
    # the scheduled slot; log read does not create or replay an occurrence.
    controller_selector = ('resource.type="cloud_run_job" AND '
                           'resource.labels.job_name="janus-batch-controller" AND '
                           f'timestamp>="{expected[0]}" AND timestamp<="{expected[1]}"')
    try:
        controller_entries = command("gcloud", "logging", "read", controller_selector,
                                     "--project="+PROJECT, "--limit=500", "--order=asc",
                                     "--format=json")
        controller_ticks = []
        for entry in controller_entries:
            payload = entry.get("jsonPayload")
            if not isinstance(payload, dict):
                try:
                    payload = json.loads(entry.get("textPayload") or "")
                except (ValueError, TypeError):
                    payload = {}
            if isinstance(payload, dict) and payload.get("status") == "tick_completed":
                controller_ticks.append(entry.get("timestamp"))
    except (subprocess.CalledProcessError, ValueError):
        controller_ticks = []
    try:
        schedulers = command("gcloud", "scheduler", "jobs", "list",
                             "--project="+PROJECT, "--location=us-central1", "--format=json")
        scheduler_rows = [{"name": str(j.get("name", "")).rsplit("/", 1)[-1],
                           "state": j.get("state"), "schedule": j.get("schedule"),
                           "timeZone": j.get("timeZone")}
                          for j in schedulers
                          if "janus" in str(j.get("name", "")).lower()
                          and ("controller" in str(j.get("name", "")).lower()
                               or "ingestion-daily" in str(j.get("name", "")).lower())]
    except (subprocess.CalledProcessError, ValueError):
        scheduler_rows = []
    print(json.dumps({
        "component": "stage48-natural-closeout", "mode": "read-only",
        "slot_local": "2026-10-20T18:30:00+08:00",
        "window_utc": expected, "scanned_log_entries": len(entries),
        "scan_truncated_possible": len(entries) == 2000,
        "stage_apply_receipts": good, "execution_terminal_checks": results,
        "controller_tick_utc": controller_ticks[:20], "scheduler_readback": scheduler_rows,
        "weekly_maintenance_enabled": weekly,
        "natural_due_receipt": ("PASS" if good and any(r["terminal"] == "PASS" for r in results)
                                and len(entries) < 2000 else "NOT_VERIFIED"),
        "occurrence_database_readback": "NOT_VERIFIED",
        "gcp_mutations": 0, "stage_object_mutations": 0
    }, sort_keys=True))

def main():
    config = json.loads(__import__("pathlib").Path("ops/finops-stage-trace.json").read_text())
    if config.get("scope") == "STAGE48_NATURAL_20261020":
        return natural_stage_closeout(config)
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
