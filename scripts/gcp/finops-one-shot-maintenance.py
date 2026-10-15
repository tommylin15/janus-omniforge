"""One-shot, owner-approved Janus GCP dev Iceberg maintenance acceptance.

Only existing janus-ingestion-core; no GitHub recurring Iceberg job.
Fails closed if the previous full Jobs rollout has not passed, image differs,
Scheduler is disabled, or a live ingestion execution is present.
"""
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
JOB = "janus-ingestion-core"
REQUEST = Path("ops/finops-gcp-live-acceptance.json")


def call(*args, timeout=90):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()


def jsoncall(*args):
    return json.loads(call(*args))


def containers(value):
    if isinstance(value, dict):
        items = value.get("containers")
        if isinstance(items, list):
            yield from (item for item in items if isinstance(item, dict))
        for item in value.values():
            yield from containers(item)
    elif isinstance(value, list):
        for item in value:
            yield from containers(item)


def inventory():
    helper = importlib.machinery.SourceFileLoader(
        "iceberg_gcs_audit", "scripts/gcp/iceberg-gcs-ops-audit.py").load_module()
    token = call("gcloud", "auth", "print-access-token")
    result = helper.read_core_object_inventory(token)
    if result.get("status") != "observed" or not result.get("complete"):
        raise RuntimeError("Core GCS bounded inventory is incomplete")
    return {"objects": result["visible_objects"], "bytes": result["visible_bytes"],
            "under_1mib": result["under_1mib"]}


def log_evidence(execution, component):
    selector = ('resource.type="cloud_run_job" AND '
                'resource.labels.job_name="janus-ingestion-core" AND '
                f'labels."run.googleapis.com/execution_name"="{execution}"')
    for _ in range(12):
        entries = jsoncall("gcloud", "logging", "read", selector,
                           "--project=" + PROJECT, "--freshness=45m",
                           "--limit=200", "--order=asc", "--format=json")
        evidence = []
        for entry in entries:
            data = entry.get("jsonPayload")
            if not isinstance(data, dict):
                try:
                    data = json.loads(entry.get("textPayload") or "")
                except (ValueError, TypeError):
                    continue
            if isinstance(data, dict) and data.get("component") == component:
                evidence.append(data)
        if evidence:
            return evidence[-1]
        time.sleep(5)
    raise RuntimeError("expected sanitized Iceberg execution evidence not found")


def main():
    request = json.loads(REQUEST.read_text())
    if (request.get("intent") != "one-shot-existing-dev-iceberg-maintenance"
            or request.get("no_new_resources") is not True
            or request.get("mode") not in {"compact-nightly", "retention-apply", "retention-dry-run"}
            or len(request.get("expected_source_sha", "")) != 40):
        raise RuntimeError("invalid one-shot GCP maintenance authorization")
    release_id = str(request["rollout_run"])
    release = jsoncall("gh", "run", "view", release_id,
                       "--json", "status,conclusion,workflowName")
    if (release["status"] != "completed" or release["conclusion"] != "success"
            or release["workflowName"] != "Janus GHCR controlled Jobs rollout"):
        raise RuntimeError("reversible four-Jobs rollout acceptance not PASS")
    scheduler = jsoncall("gcloud", "scheduler", "jobs", "describe",
                         "janus-ingestion-daily", "--project=" + PROJECT,
                         "--location=" + REGION, "--format=json")
    if (scheduler.get("state") != "ENABLED" or scheduler.get("schedule") != "30 * * * *"
            or scheduler.get("timeZone") != "Asia/Taipei"):
        raise RuntimeError("existing hourly Scheduler baseline drift")
    job = jsoncall("gcloud", "run", "jobs", "describe", JOB, "--project=" + PROJECT,
                   "--region=" + REGION, "--format=json")
    images = [v["image"].removeprefix("cache.us-docker.pkg.dev/")
              for v in containers(job) if isinstance(v.get("image"), str)]
    expected = request["expected_image"]
    if len(images) != 1 or images[0] != expected or not expected.startswith(
            "ghcr.io/tommylin15/janus-ingestion-core@sha256:"):
        raise RuntimeError("currently deployed Core job digest is not the approved SHA image")
    executions = jsoncall("gcloud", "run", "jobs", "executions", "list",
                          "--job=" + JOB, "--project=" + PROJECT, "--region=" + REGION,
                          "--limit=100", "--format=json")
    if not isinstance(executions, list) or any(
            item.get("status", {}).get("completionTime") is None for item in executions):
        raise RuntimeError("existing Core execution active or execution status unknown")
    # The last 100 Cloud Run executions are not a complete terminal fence.
    # The shared all-page fence is mandatory before touching the live Core Job.
    import ghcr_jobs_rollout as rollout
    rollout.fence()
    before = inventory()
    mode = request["mode"]
    output = call("gcloud", "run", "jobs", "execute", JOB,
                  "--project=" + PROJECT, "--region=" + REGION,
                  "--update-env-vars=" + ",".join([
                      "ICEBERG_MAINTENANCE_MODE=" + mode, "QUEUE_CONSUMER=false",
                      "MART_JOB=", "JANUS_CONTROL_MIGRATION=", "JANUS_DATA_SUPPLEMENT_MODE=",
                      "JANUS_SERVING_SCHEMA_MIGRATION="]),
                  "--wait", "--format=value(metadata.name)", timeout=1500)
    execution_name = output.splitlines()[-1].split("/")[-1]
    if not execution_name.startswith(JOB + "-"):
        raise RuntimeError("Cloud Run Job execution identity missing")
    component = ("iceberg-nightly-compaction" if mode == "compact-nightly"
                 else "data-retention")
    evidence = log_evidence(execution_name, component)
    if mode == "compact-nightly" and evidence.get("mode") != "dry-run-then-apply":
        raise RuntimeError("Iceberg preflight and apply evidence mismatch")
    if mode.startswith("retention-") and evidence.get("mode") != ("apply" if mode == "retention-apply" else "dry-run"):
        raise RuntimeError("Core retention mode receipt mismatch")
    after = inventory()
    compact = evidence.get("apply", {}) if mode == "compact-nightly" else {}
    result = {"status": "PASS", "operation": mode,
              "source_sha": request["expected_source_sha"],
              "cloud_execution": execution_name,
              "before": before, "after": after,
              "core_planned_rewrite_bytes": evidence.get("preflight", {}).get("core", {}).get("planned_rewrite_bytes"),
              "core_rewritten_bytes": compact.get("core", {}).get("rewritten_bytes"),
              "core_tables": len(compact.get("core", {}).get("tables", [])),
              "audit_status": compact.get("audit", {}).get("status"),
              "expired_snapshots": sum(t.get("expired_snapshots", 0) for t in evidence.get("tables", [])),
              "planned_snapshots_to_expire": sum(t.get("planned_expiration", 0) for t in evidence.get("tables", [])),
              "planned_orphans": sum(o.get("planned_objects", 0) for o in evidence.get("orphans", [])),
              "planned_manifest_retirements": evidence.get("core_manifests", {}).get("planned_objects"),
              "orphan_objects_deleted": sum(o.get("deleted_objects", 0) for o in evidence.get("orphans", [])),
              "audit_orphans_deleted": evidence.get("controller_audit_orphans", {}).get("deleted_objects"),
              "core_manifest_reference_fence": evidence.get("core_manifests", {}).get("status"),
              "error_payload": None}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "BLOCKED_OR_FAILED", "reason": type(error).__name__,
                          "details": str(error)[:100] if isinstance(error, RuntimeError) else None}))
        raise SystemExit(2)
