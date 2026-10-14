#!/usr/bin/env python3
"""Bounded dev queue canary via existing Cloud Run v2 *execution* overrides.

Legacy migration 048 seed/verify/cleanup logic is reused unchanged. No Job
template mutations, ledger writes, new users, IAM grants or API traffic moves.
The canary may re-materialize an existing owner's *derived* Private Mart.
"""
import json
from pathlib import Path
import time
from uuid import uuid4
import ghcr_jobs_rollout as rollout

SOURCE = "1e9c31d148db540ee06cac5ccccd8fac8d619511"
IMAGES = {
    "janus-ingestion-core": "ghcr.io/tommylin15/janus-ingestion-core@sha256:512b05013029934d3b02254a9451136ea40c0bd738c6c7561a7c0f333e7d4648",
    "janus-private-pipeline": "ghcr.io/tommylin15/janus-private-pipeline@sha256:d06ffd5a56439d00780af8e9908a060f154c53a69768915ebd5581d3a58cb95e",
}


def invoke(name, env, *, task_count=1, timeout="600s"):
    job = rollout.job(name)
    if rollout.image(job) != IMAGES[name]:
        raise ValueError("source_image_or_job_drift")
    containers = job["template"]["template"]["containers"]
    if len(containers) != 1 or task_count not in (1, 2):
        raise ValueError("unsupported_job_execution_shape")
    container = containers[0]
    entry = {"env": [{"name":key,"value":val} for key,val in env.items()]}
    if container.get("name"):
        entry["name"] = container["name"]
    payload = {"etag":job["etag"],"overrides":{"taskCount":task_count,"timeout":timeout,
                                               "containerOverrides":[entry]}}
    op = rollout.cloud(f"{rollout.ROOT}/jobs/{name}:run",payload,"POST")
    operation = op.get("name","")
    if not operation.startswith(rollout.ROOT + "/operations/"):
        raise RuntimeError("operation_unknown_retain_lease")
    end = time.monotonic() + (1500 if task_count == 2 else 600)
    while not op.get("done") and time.monotonic() < end:
        time.sleep(6)
        op = rollout.cloud(operation)
    if not op.get("done"):
        raise RuntimeError("execution_not_terminal_retain_lease")
    if op.get("error"):
        raise RuntimeError("execution_failed_inspect_before_retry")
    e = op.get("response",{})
    if e.get("name","").startswith(rollout.ROOT + f"/jobs/{name}/executions/"):
        # Operation response sometimes omits terminal counters.
        e = rollout.cloud(e["name"])
    if (not rollout.terminal(e) or e.get("failedCount",0) or
            e.get("succeededCount") != task_count):
        raise RuntimeError("execution_not_verified_retain_lease")
    return str(e["name"]).split("/")[-1]


def main():
    request = json.loads(Path("ops/private-recalc-ghcr-canary-request.json").read_text())
    if (request.get("intent") != "bounded-existing-dev-recalc-queue-canary" or
        request.get("approved") is not True or request.get("source_sha") != SOURCE or
        request.get("seeded_requests") != 1 or request.get("worker_tasks") != 2 or
        request.get("no_ledger_mutation") is not True or
        request.get("derived_mart_may_refresh") is not True or
        request.get("no_job_template_mutation") is not True):
        raise ValueError("queue_canary_authorization_drift")
    rollout.legacy_writers()
    if rollout.scheduler().get("state") != "ENABLED":
        raise ValueError("scheduler_not_enabled")
    rollout.fence()
    for name, digest in IMAGES.items():
        if rollout.image(rollout.job(name)) != digest:
            raise ValueError("live_image_drift")
    # This is an owner data writer. Protect it with the same cross-run Git ref
    # and all-page execution fence as GHCR rollout / official bootstrap.
    rollout.command(rollout.LEASE + ["acquire"])
    request_id = str(uuid4())
    result = {"component":"janus-dev-private-recalc-canary",
              "source_sha":SOURCE,"status":"UNKNOWN",
              "no_ledger_mutation":True,"job_template_mutation":False,
              "api_traffic_changed":False,"seeded_requests":1,"worker_tasks":2}
    Path("/tmp/private-recalc-ghcr-canary.json").write_text(json.dumps(result))
    # If an operation becomes UNKNOWN, stop: leave the durable lease in place.
    # Do not spawn another worker or pretend cleanup is safe.
    rollout.fence()
    seed = invoke("janus-ingestion-core",{
        "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE":"seed",
        "JANUS_PRIVATE_RECALC_ACCEPTANCE_REQUEST_ID":request_id,
        "QUEUE_CONSUMER":"false","MART_JOB":""})
    worker = None
    try:
        worker = invoke("janus-private-pipeline", {
            "PRIVATE_RECALC_QUEUE_MODE":"true",
        },task_count=2,timeout="1800s")
        verified = invoke("janus-ingestion-core",{
            "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE":"verify",
            "JANUS_PRIVATE_RECALC_ACCEPTANCE_REQUEST_ID":request_id,
            "JANUS_PRIVATE_RECALC_ACCEPTANCE_EXECUTION":worker,
            "QUEUE_CONSUMER":"false","MART_JOB":""})
        result.update(status="PASS",seed_execution=seed,
                      worker_execution=worker,verify_execution=verified)
        Path("/tmp/private-recalc-ghcr-canary.json").write_text(json.dumps(result))
    finally:
        # The existing acceptance cleanup never deletes ledger events:
        # it only marks an *active* test request FAILED and resets idle
        # singleton dispatch. It leaves a SUCCEEDED request immutable.
        if worker:
            try:
                cleanup = invoke("janus-ingestion-core",{
                    "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE":"cleanup",
                    "JANUS_PRIVATE_RECALC_ACCEPTANCE_REQUEST_ID":request_id,
                    "QUEUE_CONSUMER":"false","MART_JOB":""})
                result["cleanup_execution"] = cleanup
            except Exception:
                result["status"]="UNKNOWN"
                Path("/tmp/private-recalc-ghcr-canary.json").write_text(json.dumps(result))
                raise
    if result["status"] != "PASS":
        raise RuntimeError("business_canary_not_passed")
    rollout.fence()
    rollout.command(rollout.LEASE + ["release","--safe-to-release"])
    Path("/tmp/private-recalc-ghcr-canary.json").write_text(json.dumps(result))
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
