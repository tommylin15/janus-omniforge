#!/usr/bin/env python3
"""SEQ-05 single approved Cloud Run Job override; no image/template updates."""
import json
import re
import subprocess
import time
from pathlib import Path
from hashlib import sha256

from ghcr_jobs_rollout import ROOT, PROJECT, cloud, job, fingerprint, terminal, wait_for_terminal_executions

REQUEST = Path("ops/seq05-oneoff-quickfill.json")
RECEIPT = Path("/tmp/seq05-oneoff-quickfill-receipt.json")
JOB = "janus-ingestion-core"


def checked(data, code):
    if (data.get("intent") != "seq05-single-finmind-yahoo-stage-core-research"
        or data.get("approved") is not True
        or data.get("symbols") != ["2882"]
        or data.get("datasets") != ["valuation", "financials"]
        or data.get("pb_window") != ["2025-10", "2026-08"]
        or data.get("one_execution") is not True
        or data.get("new_resources") is not False
        or data.get("no_job_template_mutation") is not True
        or data.get("program") != "scripts/gcp/seq05_oneoff_core.py"):
        raise ValueError("seq05_quickfill_request_scope_invalid")
    return data


def save(data):
    RECEIPT.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print("SEQ05_GITHUB_RECEIPT:"+json.dumps(data,sort_keys=True),flush=True)


def read_log(execution):
    query=('resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+execution+'"')
    for attempt in range(6):
        result=subprocess.run(["gcloud","logging","read",query,"--project="+PROJECT,
            "--limit=150","--format=json"],capture_output=True,text=True,timeout=60,check=False)
        if result.returncode==0:
            for entry in json.loads(result.stdout):
                payload=entry.get("textPayload") or ""
                if "SEQ05_QUICKFILL_RECEIPT:" not in payload:
                    continue
                try:
                    return json.loads(payload.split("SEQ05_QUICKFILL_RECEIPT:",1)[1].strip())
                except (ValueError,TypeError):
                    pass
        time.sleep(4+attempt)
    return None


def main():
    code=Path("scripts/gcp/seq05_oneoff_core.py").read_text(encoding="utf-8")
    request=checked(json.loads(REQUEST.read_text(encoding="utf-8")),code)
    report={"operation":"seq05-oneoff-research-quickfill","status":"PREFLIGHT","symbols":request["symbols"],
            "source_code_sha256":sha256(code.encode()).hexdigest(),"one_execution":True}
    wait_for_terminal_executions(timeout=700)
    current=job(JOB)
    initial=fingerprint(current)
    containers=current["template"]["template"]["containers"]
    if len(containers)!=1:raise RuntimeError("ingestion_container_count_invalid")
    container=containers[0]
    image=container.get("image","").removeprefix("cache.us-docker.pkg.dev/")
    if not re.fullmatch(r"ghcr\.io/tommylin15/janus-ingestion-core@sha256:[0-9a-f]{64}",image):
        raise RuntimeError("ingestion_image_not_immutable")
    if container.get("command") not in (None,[],["python"]):
        raise RuntimeError("ingestion_entrypoint_unknown")
    override={"args":(["-c",code] if container.get("command") else ["python","-c",code]),
              "env":[{"name":"QUEUE_CONSUMER","value":"false"}]}
    if container.get("name"):override["name"]=container["name"]
    op=cloud(f"{ROOT}/jobs/{JOB}:run",
        {"etag":current["etag"],"overrides":{
             "taskCount":1,"timeout":"900s","containerOverrides":[override]}},"POST")
    name=op.get("name","")
    report["operation_id"]=name
    if not name.startswith(ROOT+"/operations/"):
        report["status"]="UNKNOWN_SUBMISSION_DO_NOT_RETRY"
        save(report)
        raise RuntimeError(report["status"])
    end=time.monotonic()+940
    while not op.get("done") and time.monotonic()<end:
        time.sleep(12)
        op=cloud(name)
    if not op.get("done"):
        report["status"]="RUNNING_UNKNOWN_DO_NOT_RETRY"
        save(report)
        raise RuntimeError(report["status"])
    if op.get("error"):
        report["status"]="JOB_FAILED_NEEDS_READBACK"
        report["cloud_error_code"]=str(op["error"].get("code","unknown"))[:16]
        save(report)
        raise RuntimeError(report["status"])
    execution=op.get("response",{})
    if not terminal(execution) or execution.get("succeededCount")!=1:
        report["status"]="JOB_TERMINAL_NOT_SUCCEEDED"
        save(report)
        raise RuntimeError(report["status"])
    execution_id=execution.get("name","").rsplit("/",1)[-1]
    if not execution_id.startswith(JOB+"-"):raise RuntimeError("execution_identity_invalid")
    report["execution_name"]=execution_id
    report["source_receipt"]=read_log(execution_id)
    report["job_template_unchanged"]=fingerprint(job(JOB))==initial
    if not report["job_template_unchanged"]:
        raise RuntimeError("job_template_modified")
    report["status"]=("CORE_INPUTS_COMPLETE" if isinstance(report["source_receipt"],dict)
                      and report["source_receipt"].get("status")=="CORE_INPUTS_COMPLETE"
                      else "PARTIAL_REQUIRES_INPUT_REVIEW")
    save(report)


if __name__=="__main__":
    main()
