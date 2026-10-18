#!/usr/bin/env python3
"""DRL-01 bounded official TWSE/TPEx market-volume continuity repair.

One legacy Cloud Run Job per historical slice, no template or Scheduler changes.
Any incomplete/ambiguous execution fails closed; never rerun unknown writes.
Uses the existing approved market-history ingestion entrypoint and Stage/Core.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from ghcr_jobs_rollout import ROOT, cloud, job, terminal, wait_for_terminal_executions

PROJECT = "gen-lang-client-0593591102"
JOB = "janus-ingestion-core"
SLICES = (
    ("2026-07-01", "2026-07-31"),
    ("2026-08-01", "2026-08-31"),
    ("2026-09-01", "2026-09-30"),
    ("2026-10-01", "2026-10-12"),
)
RECEIPT = Path("/tmp/drl01-market-continuity.json")


def checked(path):
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    if (r.get("intent") != "drl01-existing-official-market-volume-history"
        or r.get("approved") is not True
        or r.get("no_new_source") is not True
        or r.get("no_owner_mutation") is not True
        or r.get("no_job_template_mutation") is not True
        or r.get("slices") != [list(pair) for pair in SLICES]
        or not re.fullmatch("[0-9a-f]{40}", str(r.get("deployed_sha","")))):
        raise ValueError("unapproved_market_continuity_scope")
    return r


def digest_matches(sha, current):
    containers = current["template"]["template"]["containers"]
    if len(containers) != 1 or containers[0].get("command") not in (None, [], ["python"]):
        return False
    image = containers[0].get("image","").removeprefix("cache.us-docker.pkg.dev/")
    if not image.startswith("ghcr.io/tommylin15/janus-ingestion-core@sha256:"):
        return False
    cmd = ["skopeo","inspect","--no-creds",
           f"docker://ghcr.io/tommylin15/janus-ingestion-core:sha-{sha}"]
    p = subprocess.run(cmd,capture_output=True,text=True,timeout=65,check=False)
    if p.returncode:
        return False
    data=json.loads(p.stdout)
    return bool(image.endswith("@"+str(data.get("Digest","")))
                and data.get("Labels",{}).get("org.opencontainers.image.revision")==sha)


def save(report):
    RECEIPT.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"component":"drl01_market_continuity",
        "status":report["status"],"completed_slices":len(report["slices"])},sort_keys=True),flush=True)


def final_log(execution):
    query=('resource.type="cloud_run_job" AND '
           'labels."run.googleapis.com/execution_name"="'+execution+'"')
    for attempt in range(6):
        p=subprocess.run(["gcloud","logging","read",query,"--project="+PROJECT,
                          "--limit=350","--format=json"],text=True,capture_output=True,timeout=55)
        if p.returncode==0:
            for row in json.loads(p.stdout):
                obj=row.get("jsonPayload")
                if not isinstance(obj,dict):
                    try:obj=json.loads(row.get("textPayload",""))
                    except (ValueError,TypeError):continue
                if isinstance(obj,dict) and obj.get("operation")=="market-history" and "months" in obj:
                    return obj
        time.sleep(4+attempt)
    return None


def run(path):
    request=checked(path)
    report={"schema_version":"drl01-market-history.v1","deployed_sha":request["deployed_sha"],
            "scope":"existing verified TWSE/TPEX current-market equity members",
            "no_owner_mutation":True,"no_job_template_mutation":True,
            "slices":[],"status":"PARTIAL"}
    save(report)
    for start,end in SLICES:
        wait_for_terminal_executions(timeout=900)
        current=job(JOB)
        if not digest_matches(request["deployed_sha"],current):
            report["status"]="BLOCKED_IMAGE_DIGEST_DRIFT"
            save(report)
            raise RuntimeError(report["status"])
        container=current["template"]["template"]["containers"][0]
        options={
            "JANUS_DATA_SUPPLEMENT_MODE":"market-history",
            "BACKFILL_START_DATE":start,
            "BACKFILL_END_DATE":end,
            "QUEUE_CONSUMER":"false",
            "MART_JOB":"",
            "ICEBERG_MAINTENANCE_MODE":"",
        }
        overrides={"env":[{"name":key,"value":value} for key,value in options.items()]}
        if container.get("name"):
            overrides["name"]=container["name"]
        op=cloud(f"{ROOT}/jobs/{JOB}:run",
            {"etag":current["etag"],"overrides":{
                "taskCount":1,"timeout":"2100s","containerOverrides":[overrides]}}, "POST")
        name=op.get("name","")
        if not name.startswith(ROOT+"/operations/"):
            raise RuntimeError("submission_unknown_do_not_retry")
        until=time.monotonic()+2160
        while not op.get("done") and time.monotonic()<until:
            time.sleep(10)
            op=cloud(name)
        if not op.get("done"):
            report["status"]="BLOCKED_EXECUTION_UNKNOWN"
            report["blocked_operation"]=name
            save(report)
            raise RuntimeError("market_history_not_terminal_do_not_retry")
        if op.get("error"):
            report["status"]="FAILED_EXECUTION"
            report["blocked_operation"]=name
            save(report)
            raise RuntimeError("market_history_job_failed_inspect_logs_before_retry")
        exe=op.get("response",{})
        if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
            raise RuntimeError("market_history_no_terminal_success")
        ename=exe.get("name","").rsplit("/",1)[-1]
        if not ename.startswith(JOB+"-"):
            raise RuntimeError("market_history_execution_identity_drift")
        observed=final_log(ename)
        if observed is None:
            raise RuntimeError("market_history_receipt_missing")
        months=observed.get("months") or []
        expected={start[:7],end[:7]}
        actual={m.get("month") for m in months if isinstance(m,dict)}
        if (actual!=expected or any(m.get("status")!="accepted" for m in months)
            or observed.get("failures")
            or observed.get("status")!="succeeded"
            or not all(m.get("market_volume_source_rows",{}).get(x,0)>0
                       for m in months for x in ("TWSE","TPEX"))):
            report["status"]="PARTIAL_MARKET_SOURCE_OR_QUALITY"
            report["slices"].append({"start":start,"end":end,"execution":ename,
                  "source_months":[{"month":m.get("month"),"status":m.get("status"),
                     "missing_ratio_by_market":m.get("missing_ratio_by_market"),
                     "volume_source_rows":m.get("market_volume_source_rows")}
                     for m in months],"failure_count":len(observed.get("failures",[]))})
            save(report)
            raise RuntimeError("market_history_not_full_source_success")
        report["slices"].append({"start":start,"end":end,"execution":ename,
              "core_created":observed.get("core_created"),
              "core_updated":observed.get("core_updated"),
              "core_reused":observed.get("core_reused"),
              "source_months":[{"month":m["month"],
                "volume_source_rows":m.get("market_volume_source_rows"),
                "missing_ratio_by_market":m.get("missing_ratio_by_market"),
                "threshold_by_market":m.get("threshold_by_market")}
                for m in months]})
        save(report)
    report["status"]="PASS_BOUNDED_OFFICIAL_HISTORY_WRITTEN"
    save(report)


if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("one explicit request required")
    run(sys.argv[1])
