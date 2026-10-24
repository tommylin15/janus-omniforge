#!/usr/bin/env python3
"""P0-2: pinned image swap of EXISTING dev Controller ONLY.

No queues executed or recovered: readiness canary is read-only; historical
one-shot recovery remains disabled absent an explicit exact-row artifact gate.
"""
from __future__ import annotations
import json,os,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

SOURCE="4fbf330a600f5e4280bbf0de36cff261373daed4"
RELEASE_RUN="40045758731"
JOB="janus-batch-controller"
OUT=Path("/tmp/p02-controller-rollout.json")
REQUEST=Path("ops/p02-controller-rollout-request.json")


def guard(req):
    if not (req.get("intent")=="p02-controller-only-lease-fix"
            and req.get("approved") is True
            and req.get("source_sha")==SOURCE
            and str(req.get("release_run"))==RELEASE_RUN
            and req.get("job")==JOB
            and req.get("no_analysis_replay") is True
            and req.get("no_collection_replay") is True
            and req.get("no_data_mutation") is True
            and req.get("no_iam_expansion") is True
            and req.get("no_api_traffic_change") is True):
        raise ValueError("p02_rollout_request_invalid")


def verified_image():
    d=json.loads(gcp.command(["gh","run","view",RELEASE_RUN,
        "--json","status,conclusion,workflowName,headSha"]))
    if d.get("conclusion")!="success" or d.get("status")!="completed" or (
        d.get("workflowName")!="Janus GHCR operations"):
        raise RuntimeError("p02_release_not_success")
    # Release request push head can differ from the immutable image *source*.
    history=json.loads(gcp.command(["git","show",
       d["headSha"]+":ops/ghcr-release-request.json"]))
    if history.get("sha")!=SOURCE:
        raise ValueError("p02_release_source_mismatch")
    label="ghcr.io/tommylin15/janus-ingestion-core:sha-"+SOURCE
    info=json.loads(gcp.command(["skopeo","inspect","--no-creds",
                                 "docker://"+label]))
    target="ghcr.io/tommylin15/janus-ingestion-core@"+info.get("Digest","")
    if not gcp.PIN.fullmatch(target) or info.get("Labels",{}).get(
       "org.opencontainers.image.revision")!=SOURCE:
        raise ValueError("p02_target_unverified")
    gcp.command(["skopeo","inspect","--no-creds","docker://"+target])
    return target


def rollback_digest(job):
    old=gcp.image(job)
    if not gcp.PIN.fullmatch(old) or not old.startswith(
        "ghcr.io/tommylin15/janus-ingestion-core@sha256:"):
        raise RuntimeError("p02_rollback_digest_unknown")
    meta=json.loads(gcp.command(["skopeo","inspect","--no-creds",
                                  "docker://"+old]))
    if meta.get("Digest")!=old.rsplit("@",1)[-1]:
        raise RuntimeError("p02_rollback_digest_unavailable")
    return old


def main():
    guard(json.loads(REQUEST.read_text(encoding="utf-8")))
    target=verified_image()
    journal={"phase":"PRECHECK","source_sha":SOURCE,"release_run":RELEASE_RUN,
       "job":JOB,"job_updates":0,"queue_recovery_dispatches":0,
       "data_mutations":0,"iam_changes":0,"new_resources":0,
       "operations":[],"canaries":[],"scheduler":"UNKNOWN"}
    def save():OUT.write_text(json.dumps(journal,sort_keys=True,indent=2))
    save()
    lease=False
    paused=False
    old=None
    original_hash=None
    scheduler_hash=None
    try:
        gcp.command(gcp.LEASE+["acquire"]);lease=True
        gcp.writers()
        sch=gcp.scheduler()
        if sch.get("state")!="ENABLED":
            raise RuntimeError("p02_scheduler_not_enabled")
        scheduler_hash=gcp.scheduler_fingerprint(sch)
        gcp.wait_for_terminal_executions()
        current=gcp.job(JOB)
        original_hash=gcp.fingerprint(current)
        old=rollback_digest(current)
        journal["previous_digest"]=old.rsplit("@",1)[-1]
        journal["target_digest"]=target.rsplit("@",1)[-1]
        if old==target:
            journal["phase"]="ALREADY_APPLIED"
            gcp.checked_image(JOB,target,original_hash)
            journal["scheduler"]="ENABLED"
            save()
        else:
            journal["phase"]="PAUSING_SCHEDULER";save()
            gcp.set_scheduler("pause","PAUSED");paused=True
            journal["scheduler"]="PAUSED";save()
            gcp.writers()
            gcp.wait_for_terminal_executions()
            journal["phase"]="CONTROLLER_IMAGE_SWAP";save()
            gcp.update(JOB,target,original_hash)
            journal["job_updates"]+=1;save()
            journal["phase"]="READONLY_CANARY";save()
            gcp.canary(JOB,target,original_hash,journal,save)
            gcp.checked_image(JOB,target,original_hash)
            gcp.wait_for_terminal_executions()
            if gcp.scheduler_fingerprint(gcp.scheduler())!=scheduler_hash:
                raise RuntimeError("p02_scheduler_config_drift")
            gcp.set_scheduler("resume","ENABLED")
            paused=False
            journal["scheduler"]="ENABLED"
            journal["phase"]="PASS";save()
    except Exception:
        journal["failed_phase"]=journal["phase"]
        journal["phase"]="RECOVERY_REQUIRED";save()
        if paused and old and original_hash:
            gcp.wait_for_terminal_executions()
            x=gcp.job(JOB)
            if gcp.fingerprint(x)!=original_hash or gcp.image(x) not in (old,target):
                raise RuntimeError("p02_recovery_external_drift_lease_retained")
            if gcp.image(x)==target:
                gcp.update(JOB,old,original_hash)
            gcp.checked_image(JOB,old,original_hash)
            if scheduler_hash!=gcp.scheduler_fingerprint(gcp.scheduler()):
                raise RuntimeError("p02_scheduler_drift_lease_retained")
            gcp.set_scheduler("resume","ENABLED")
            journal["scheduler"]="ENABLED"
            journal["phase"]="RESTORED_OLD_IMAGE";save()
        elif not paused:
            journal["phase"]="BLOCKED_BEFORE_MUTATION";save()
        raise
    finally:
        if lease and journal["phase"] in ("PASS","ALREADY_APPLIED",
                                           "RESTORED_OLD_IMAGE","BLOCKED_BEFORE_MUTATION"):
            gcp.command(gcp.LEASE+["release","--safe-to-release"])
            journal["lease_released"]=True;save()
    if journal["phase"] not in ("PASS","ALREADY_APPLIED"):
        raise RuntimeError("p02_controller_not_accepted")
    print(json.dumps({"status":"PASS","job":JOB,"source_sha":SOURCE,
       "scheduler":"ENABLED","queue_recovery_dispatches":0,
       "canaries":journal["canaries"],"data_mutations":0,
       "previous_digest":journal["previous_digest"],
       "target_digest":journal["target_digest"]},sort_keys=True))


if __name__=="__main__":
    main()
