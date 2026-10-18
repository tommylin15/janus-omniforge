"""One-shot, owner-approved Janus GCP dev Iceberg maintenance acceptance.

Only existing janus-ingestion-core; no GitHub recurring Iceberg job.
Fails closed if the previous full Jobs rollout has not passed, image differs,
Scheduler is disabled, or a live ingestion execution is present.
"""
from contextlib import contextmanager
from copy import deepcopy
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from hashlib import sha256

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


def log_evidence(execution, component, *, all_entries=False, job_name=JOB):
    selector = ('resource.type="cloud_run_job" AND '
                f'resource.labels.job_name="{job_name}" AND '
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
            return evidence if all_entries else evidence[-1]
        time.sleep(5)
    raise RuntimeError("expected sanitized Iceberg execution evidence not found")


def unlinked_cleanup(job):
    import ghcr_jobs_rollout as rollout
    code=Path('scripts/gcp/finops_unlinked_small_files.py').read_text()
    container=list(containers(job))[0]
    command=container.get('command') or []
    if command not in ([],['python']) or '|' in code:
        raise RuntimeError('unlinked_cleanup_entrypoint_invalid')
    args=(['-c',code] if command else ['python','-c',code])
    name=call('gcloud','run','jobs','execute',JOB,'--project='+PROJECT,'--region='+REGION,
        '--args=^|^'+'|'.join(args),'--update-env-vars=JANUS_APPROVED_UNLINKED_CLEANUP=true',
        '--tasks=1','--task-timeout=1200s','--async','--format=value(metadata.name)').rsplit('/',1)[-1]
    if not name.startswith(JOB+'-'): raise RuntimeError('unlinked_cleanup_execution_unknown')
    dispatch={'execution':name,'image':container['image'],
              'worker_code_sha256':'sha256:'+sha256(code.encode()).hexdigest()}
    Path('finops-unlinked-dispatch.json').write_text(json.dumps(dispatch,sort_keys=True))
    deadline=time.monotonic()+1500
    while True:
        execution=rollout.cloud(rollout.ROOT+'/jobs/'+JOB+'/executions/'+name)
        if rollout.terminal(execution): break
        if time.monotonic()>=deadline: raise RuntimeError('unlinked_cleanup_execution_not_terminal')
        time.sleep(10)
    evidence=log_evidence(name,'finops-unlinked-small-files')
    chunks=log_evidence(name,'finops-unlinked-small-files-generations',all_entries=True) if evidence.get('generation_chunks') else []
    if sorted(x.get('chunk') for x in chunks)!=list(range(evidence.get('generation_chunks',0))):
        raise RuntimeError('unlinked_cleanup_generation_receipt_incomplete')
    generations=[item for chunk in sorted(chunks,key=lambda x:x['chunk']) for item in chunk['objects']]
    if len(generations)!=evidence.get('deleted_objects'):
        raise RuntimeError('unlinked_cleanup_deleted_generation_count_mismatch')
    result={**dispatch,**evidence,'execution_terminal':True,
            'execution_succeeded':execution.get('succeededCount')==1 and execution.get('failedCount',0)==0}
    Path('finops-unlinked-receipt.json').write_text(json.dumps(result,sort_keys=True))
    Path('finops-unlinked-generations.json').write_text(json.dumps(generations,sort_keys=True))
    print(json.dumps(result,sort_keys=True))
    if result.get('status')!='PASS' or not result['execution_succeeded']:
        raise RuntimeError('unlinked_cleanup_not_pass')


@contextmanager
def runtime_fence(rollout):
    """Keep Scheduler and lease until every existing writer is terminal again."""
    schedule = rollout.scheduler()
    if schedule.get("state") != "ENABLED":
        raise RuntimeError("maintenance_scheduler_not_enabled")
    fingerprint = rollout.scheduler_fingerprint(schedule)
    jobs = {name: rollout.job(name) for name, _ in rollout.JOB_COMPONENT}
    snapshots = {name: (rollout.image(job), rollout.fingerprint(job)) for name, job in jobs.items()}
    rollout.command(rollout.LEASE + ["acquire"])
    try:
        rollout.writers()
        rollout.set_scheduler("pause", "PAUSED")
        rollout.wait_for_terminal_executions()
        yield snapshots
    finally:
        # Unknown execution, drift or failed restore retains the lease.
        rollout.wait_for_terminal_executions()
        for name, (image, config) in snapshots.items():
            rollout.checked_image(name, image, config)
        current = rollout.scheduler()
        if rollout.scheduler_fingerprint(current) != fingerprint:
            raise RuntimeError("maintenance_scheduler_configuration_drift")
        if current.get("state") == "PAUSED":
            rollout.set_scheduler("resume", "ENABLED")
        elif current.get("state") != "ENABLED":
            raise RuntimeError("maintenance_scheduler_state_unknown")
        rollout.command(rollout.LEASE + ["release", "--safe-to-release"])


def main():
    request = json.loads(REQUEST.read_text())
    if (request.get("intent") != "one-shot-existing-dev-iceberg-maintenance"
            or request.get("no_new_resources") is not True
            or request.get("mode") not in {"compact-nightly", "retention-apply", "retention-dry-run", "audit-cleanup", "unlinked-small-files", "ci-approved-orphans", "enable-weekly", "mart-retention"}
            or len(request.get("expected_source_sha", "")) != 40):
        raise RuntimeError("invalid one-shot GCP maintenance authorization")
    if request['mode'] in {'unlinked-small-files','ci-approved-orphans'} and request.get('user_approved_unlinked_small_file_cleanup') is not True:
        raise RuntimeError('explicit_unlinked_small_file_approval_required')
    release_id = str(request["rollout_run"])
    release = jsoncall("gh", "run", "view", release_id,
                       "--json", "headSha,status,conclusion,workflowName")
    import ghcr_jobs_rollout as rollout
    if not rollout.successful_operation(release, release_id, "Janus GHCR controlled Jobs rollout", "jobs-rollout"):
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
    with runtime_fence(rollout) as snapshots:
        execute_maintenance(request, job, rollout, snapshots)


def execute_maintenance(request, job, rollout, snapshots=None):
    if request['mode'] == 'mart-retention':
        name = 'janus-intelligence-mart'
        if snapshots is None or name not in snapshots:
            raise RuntimeError('mart_cleanup_requires_owned_runtime_fence')
        expected = request.get('expected_mart_image', '')
        if not expected.startswith('ghcr.io/tommylin15/janus-intelligence-mart@sha256:'):
            raise RuntimeError('immutable_mart_cleanup_image_required')
        if rollout.image(rollout.checked_image(name, *snapshots[name])) != expected:
            raise RuntimeError('mart_cleanup_image_not_verified')
        output = call('gcloud', 'run', 'jobs', 'execute', name, '--project='+PROJECT, '--region='+REGION,
                      '--update-env-vars=MART_OPERATION=retention,MART_RETENTION_MODE=apply,MART_AI_ENABLED=false',
                      '--tasks=1', '--wait', '--format=value(metadata.name)', timeout=1500)
        execution = output.splitlines()[-1].rsplit('/', 1)[-1]
        if not execution.startswith(name+'-'):
            raise RuntimeError('mart_cleanup_execution_unknown')
        evidence = log_evidence(execution, 'mart-retention', job_name=name)
        if evidence.get('policy_version') != 'current-only-snapshots-v1' or evidence.get('mode') != 'apply':
            raise RuntimeError('mart_cleanup_policy_readback_failed')
        print(json.dumps({'status':'PASS','operation':'mart-retention','cloud_execution':execution,
                          'source_sha':request['expected_source_sha'],'evidence':evidence}, sort_keys=True))
        return
    if request['mode'] == 'enable-weekly':
        name = 'janus-batch-controller'
        if snapshots is None or name not in snapshots:
            raise RuntimeError('weekly_toggle_requires_owned_runtime_fence')
        before = deepcopy(rollout.checked_image(name, *snapshots[name]))
        if rollout.image(before) != request['expected_image']:
            raise RuntimeError('weekly_controller_image_not_verified')
        call('gcloud', 'run', 'jobs', 'update', name, '--project='+PROJECT, '--region='+REGION,
             '--update-env-vars=FINOPS_WEEKLY_MAINTENANCE=true', '--quiet', timeout=300)
        after = rollout.job(name)
        values = [item.get('value') for item in after['template']['template']['containers'][0].get('env', [])
                  if item.get('name') == 'FINOPS_WEEKLY_MAINTENANCE']
        if values != ['true'] or rollout.image(after) != rollout.image(before):
            raise RuntimeError('weekly_controller_flag_readback_failed')
        cleaned = []
        for value in (before, after):
            value = deepcopy(value)
            container = value['template']['template']['containers'][0]
            container['env'] = [item for item in container.get('env', [])
                                if item.get('name') != 'FINOPS_WEEKLY_MAINTENANCE']
            cleaned.append(rollout.fingerprint(value))
        if cleaned[0] != cleaned[1]:
            raise RuntimeError('weekly_toggle_changed_other_configuration')
        snapshots[name] = (rollout.image(after), rollout.fingerprint(after))
        print(json.dumps({'status':'PASS','operation':'enable-weekly','job':name,
                          'image':rollout.image(after),'weekly_maintenance':True,
                          'scheduler_schedule_changed':False}, sort_keys=True))
        return
    if request['mode']=='ci-approved-orphans':
        from finops_ci_orphans import run
        run(call,jsoncall,inventory,rollout)
        return
    if request['mode']=='unlinked-small-files':
        unlinked_cleanup(job)
        return
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
                 else "iceberg-audit-only-cleanup" if mode == "audit-cleanup"
                 else "data-retention")
    evidence = log_evidence(execution_name, component)
    if mode == "audit-cleanup" and (evidence.get("mode") != "audit-cleanup" or evidence.get("status") != "PASS"):
        raise RuntimeError("Audit-only cleanup evidence mismatch")
    if mode == "compact-nightly" and evidence.get("mode") not in {"dry-run-then-apply", "skipped_no_work"}:
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
              "audit_only_deleted_objects": evidence.get("deleted_objects") if mode == "audit-cleanup" else None,
              "audit_only_expired_snapshots": evidence.get("expired_snapshots") if mode == "audit-cleanup" else None,
              "audit_only_canonical_tables_modified": evidence.get("canonical_tables_modified") if mode == "audit-cleanup" else None,
              "error_payload": None}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "BLOCKED_OR_FAILED", "reason": type(error).__name__,
                          "details": str(error)[:100] if isinstance(error, RuntimeError) else None}))
        raise SystemExit(2)
