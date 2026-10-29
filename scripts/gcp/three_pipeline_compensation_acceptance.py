"""Exercise existing durable compensation without changing any ledger events."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from datetime import date
import three_pipeline_acceptance as acceptance
from ghcr_mcp_route import LEASE


def executions():
    data = acceptance.jobs.cloud(f"{acceptance.jobs.ROOT}/jobs/janus-private-pipeline/executions?pageSize=20")
    return {item["name"] for item in data.get("executions", [])}


def run(args):
    jobs = acceptance.jobs
    proof = {"phase": "PREFLIGHT", "trigger": "controlled", "no_ledger_mutation": True}
    def save():
        args.receipt.write_text(json.dumps(proof, sort_keys=True))
    save()
    date.fromisoformat(args.source_date)
    proof["source_sha"] = acceptance.source_gate(args.release_run, args.jobs_run)
    before = jobs.scheduler()
    if before["state"] != "ENABLED":
        raise ValueError("scheduler_not_enabled")
    snapshots = jobs.existing_jobs()
    jobs.command(LEASE + ["acquire"])
    safe = False
    request = str(uuid4())
    proof["test_request_id"] = request
    save()
    try:
        jobs.legacy_writers()
        jobs.set_scheduler("pause", "PAUSED")
        jobs.wait_for_terminal_executions(timeout=900)
        initial = executions()
        common = {"JANUS_PRIVATE_RECALC_ACCEPTANCE_REQUEST_ID": request,
                  "QUEUE_CONSUMER": "false", "MART_JOB": "", "JANUS_UNIFIED_COLLECTION": "false"}
        acceptance.invoke("janus-ingestion-core", {**common, "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE": "seed"}, proof, save)
        env = {"BATCH_CONTROLLER_MODE": "active", "BATCH_ACCEPTANCE_GROUP": "compensation",
               "BATCH_ACCEPTANCE_DATE": args.source_date}
        acceptance.invoke("janus-batch-controller", env, proof, save)
        jobs.wait_for_terminal_executions(timeout=900)
        after = executions()
        created = after - initial
        if len(created) != 1:
            raise ValueError("compensation_worker_not_exactly_one")
        worker = next(iter(created)).split("/")[-1]
        acceptance.invoke("janus-ingestion-core", {**common, "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE": "verify",
            "JANUS_PRIVATE_RECALC_ACCEPTANCE_EXECUTION": worker}, proof, save)
        # Same controlled identity, now empty: it must not dispatch another worker.
        acceptance.invoke("janus-batch-controller", env, proof, save)
        jobs.wait_for_terminal_executions(timeout=900)
        if executions() != after:
            raise ValueError("duplicate_or_empty_compensation_dispatched_worker")
        acceptance.invoke("janus-ingestion-core", {**common, "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE": "cleanup"}, proof, save)
        for name, snapshot in snapshots.items():
            jobs.checked_image(name, jobs.image(snapshot), jobs.fingerprint(snapshot))
        if jobs.scheduler_fingerprint(jobs.scheduler()) != jobs.scheduler_fingerprint(before):
            raise ValueError("scheduler_configuration_drift")
        jobs.set_scheduler("resume", "ENABLED")
        proof.update(phase="PASS", positive_compensation=True, duplicate_and_empty_no_new_worker=True,
                     checkpoint_verified=True, worker=worker)
        save()
        safe = True
    except Exception:
        proof["phase"] = "FAILED_INSPECT_REQUEST_AND_EXECUTIONS"
        save()
        # Never cleanup or release while a worker may still be alive.
        try:
            jobs.wait_for_terminal_executions(timeout=900)
            acceptance.invoke("janus-ingestion-core", {**common, "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE": "cleanup"}, proof, save)
            for name, snapshot in snapshots.items():
                jobs.checked_image(name, jobs.image(snapshot), jobs.fingerprint(snapshot))
            if jobs.scheduler_fingerprint(jobs.scheduler()) != jobs.scheduler_fingerprint(before):
                raise ValueError("recovery_configuration_drift")
            jobs.set_scheduler("resume", "ENABLED")
            proof["phase"] = "FAILED_SAFE_SCHEDULER_RESTORED"
            save()
            safe = True
        except Exception:
            pass
        raise
    finally:
        if safe:
            jobs.command(LEASE + ["release", "--safe-to-release"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-run", required=True)
    parser.add_argument("--jobs-run", required=True)
    parser.add_argument("--source-date", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    try:
        run(parser.parse_args())
    except Exception:
        print(json.dumps({"status": "FAILED", "reason": "inspect_bounded_receipt"}))
        raise SystemExit(1)
