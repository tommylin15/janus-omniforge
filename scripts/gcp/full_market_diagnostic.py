#!/usr/bin/env python3
"""One-run, read-only Cloud Run full-market business-failure diagnostic.

No requests to run Jobs, mutate canonical/private data, change traffic, or
touch the release lease. Outputs only bounded sanitized diagnostic metadata.
"""
import json
import re
import subprocess
import sys
from datetime import datetime

RUN_ID = "38559419684"
JOB = "janus-ingestion-core"
PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
SINCE = "2026-10-14T11:59:00Z"
UNTIL = "2026-10-14T12:19:00Z"

def cmd(argv, *, limit=600_000):
    r = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=120)
    if r.returncode:
        raise RuntimeError("diagnostic_read_failed:" + argv[0] + ":" + (r.stderr[:160].replace("\n", " ")))
    if len(r.stdout) > limit:
        raise RuntimeError("diagnostic_read_oversize")
    return r.stdout

def sanitize(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    text = re.sub(r"(?:Bearer|access_token|refresh_token|Authorization|password|secret)[ =:\"']+[^\s,;]+",
                  "[credential-redacted]", text, flags=re.I)
    text = re.sub(r"(?i)postgres(?:ql)?://[^\s]+", "[db-url]", text)
    text = re.sub(r"(?i)(?:AIza[0-9A-Za-z_-]{20,}|ya29\.[A-Za-z0-9_-]+)", "[token]", text)
    return text[:350]

def safe_payload(x):
    if not isinstance(x, dict):
        return {}
    keys = ("operation","status","phase","component","dataset","source","market",
            "error_code","error_type","reason","stage","date","as_of","execution_id",
            "expected_count","received_count","missing_count","coverage_status",
            "coverage_accepted","staged","core_created","core_updated","core_reused",
            "serving_published","universe_status")
    d = {k: x[k] for k in keys if k in x and isinstance(x[k], (str, int, float, bool, type(None)))}
    return {k: sanitize(v) if isinstance(v, str) else v for k,v in d.items()}

def main():
    receipt=json.loads(open(sys.argv[1],encoding="utf8").read())
    if receipt.get("source_sha") != "61796cbc2cd973d694e1d203e7ea9e8af07804c1" or receipt.get("phase") != "bootstrap":
        raise ValueError("source_or_phase_mismatch")
    operation=receipt.get("operation")
    if not isinstance(operation,str) or not operation.startswith(
        f"projects/{PROJECT}/locations/{REGION}/operations/"):
        raise ValueError("exact_operation_missing")
    executions=json.loads(cmd(["gcloud","run","jobs","executions","list",f"--job={JOB}",f"--project={PROJECT}",
                               f"--region={REGION}","--limit=30","--format=json"]))
    matched=[]
    for item in executions:
        meta=item.get("metadata",{})
        when=meta.get("creationTimestamp") or item.get("createTime") or ""
        if "2026-10-14T11:" in when or "2026-10-14T12:" in when:
            matched.append({"name":meta.get("name") or item.get("name"),"created":when,
                            "succeeded":item.get("status",{}).get("succeededCount"),
                            "failed":item.get("status",{}).get("failedCount"),
                            "condition":[{"type":c.get("type"),"status":c.get("status"),"reason":sanitize(str(c.get("reason","")))}
                                         for c in item.get("status",{}).get("conditions",[])][:8]})
    flt=(f'resource.type="cloud_run_job" AND resource.labels.job_name="{JOB}" '
         f'AND timestamp>="{SINCE}" AND timestamp<="{UNTIL}"')
    records=json.loads(cmd(["gcloud","logging","read",flt,f"--project={PROJECT}",
                            "--limit=1000","--order=asc","--format=json"],limit=2_500_000))
    summary=[]
    notable=[]
    for x in records:
        val=x.get("jsonPayload")
        if val is None:
            t=x.get("textPayload","")
            try:
                val=json.loads(t)
            except (TypeError,ValueError):
                val=None
            if isinstance(t,str) and (
                re.search(r"Traceback|Error|Exception|failed|coverage|source|missing",t,re.I)):
                notable.append({"timestamp":x.get("timestamp"),"text":sanitize(t)})
        d=safe_payload(val)
        if d and (d.get("error_code") or d.get("coverage_status") or
                  d.get("status") in ("FAIL","failed","partial","blocked")):
            summary.append({"timestamp":x.get("timestamp"),**d})
    output={"run_id":RUN_ID,"operation":operation,"receipt_status":receipt.get("status"),
            "read_scope":"single_2026-10-14_failed_bootstrap_window",
            "executions":matched[-10:],"log_entry_count":len(records),
            "structured":summary[-65:],"error_text":notable[-45:]}
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
    main()
