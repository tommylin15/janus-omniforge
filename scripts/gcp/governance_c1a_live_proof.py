#!/usr/bin/env python3
"""C1-A bounded live table/reader/recovery evidence; never alters data or templates.

Two existing dev Cloud Run Jobs run metadata-only PyIceberg catalog probes.
Cloud Logging is GET-only, and positive string mentions are *not* confirmed reads.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

CORE = ("core.market_volume_v1", "core.ohlcv_v1")
MART = tuple("mart." + name + "_v1" for name in (
    "mart_screening_signals", "mart_core_alpha", "mart_risk_portfolio",
    "mart_alternative_sentiment", "mart_scoped_analysis",
    "mart_market_regime_daily", "mart_sector_rotation_daily",
    "mart_topic_trends_daily", "mart_candidate_health", "mart_daily_brief",
    "mart_llm_narratives",
))
JOBS = (("janus-ingestion-core", "core"), ("janus-intelligence-mart", "mart"))
PREFIX = "JANUS_C1A_CURRENT_TABLE_METADATA_V1:"
OUT = Path("governance-c1a-live-proof.json")
REQ = Path("ops/governance-metadata-readonly-request.json")
MAX_LOG_ENTRIES = 300
MAX_LOG_BYTES = 4_000_000
WINDOW_DAYS = 7

# No scan/to_arrow, data-file GET, UPDATE, or snapshot write. The existing job
# identity accesses only its existing Iceberg namespace through its own catalog.
PROBE = r'''
import json,os
from datetime import datetime,timezone
PREFIX="JANUS_C1A_CURRENT_TABLE_METADATA_V1:"
sha=os.environ.get("JANUS_GOVERNANCE_SOURCE_SHA","UNKNOWN")
layer=os.environ.get("JANUS_C1A_LAYER","")
names={"core":("core.market_volume_v1","core.ohlcv_v1"),
       "mart":("mart.mart_screening_signals_v1","mart.mart_core_alpha_v1",
       "mart.mart_risk_portfolio_v1","mart.mart_alternative_sentiment_v1",
       "mart.mart_scoped_analysis_v1","mart.mart_market_regime_daily_v1",
       "mart.mart_sector_rotation_daily_v1","mart.mart_topic_trends_daily_v1",
       "mart.mart_candidate_health_v1","mart.mart_daily_brief_v1",
       "mart.mart_llm_narratives_v1")}
def send(item):
    print(PREFIX+json.dumps(item,sort_keys=True,ensure_ascii=False),flush=True)
if layer not in names:
    raise ValueError("c1a_layer_outside_allowlist")
try:
    if layer=="core":
        from ingestion_core.__main__ import _iceberg_core
        core=_iceberg_core(os.environ["CORE_BUCKET"],read_only=True)
        catalog=core.catalog
    else:
        from packages.postgres_bundle import load_postgres_bundle
        load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE",{
            "CATALOG_DB_PASSWORD":("mart_catalog_password","catalog_password")})
        from intelligence_mart.storage import sql_catalog_from_environment
        catalog=sql_catalog_from_environment()
        core=None
    for name in names[layer]:
        item={"git_sha":sha,"layer":layer,"name":name,
              "checked_at_utc":datetime.now(timezone.utc).isoformat()}
        try:
            t=catalog.load_table(name)
            snapshot=t.current_snapshot()
            manifests=snapshot.manifests(t.io) if snapshot is not None else []
            if len(manifests)>500:
                raise ValueError("manifest_count_exceeds_bound")
            item.update(status="READABLE",current_snapshot_id=(
                 str(snapshot.snapshot_id) if snapshot else None),
                 current_record_count=(int(snapshot.summary["total-records"])
                   if snapshot and snapshot.summary and
                     "total-records" in snapshot.summary else None),
                 current_manifest_count=len(manifests),
                 current_manifest_list_readable=snapshot is not None,
                 schema=[[f.name,str(f.field_type),bool(f.required)]
                         for f in t.schema().fields][:100],
                 partition_spec=[[f.name,str(f.transform)]
                                 for f in t.spec().fields][:30],
                 metadata_location=t.metadata_location,
                 independent_recovery_verified=False,
                 recovery_evidence="CURRENT_METADATA_ONLY_NOT_INDEPENDENT_BACKUP")
        except Exception as e:
            item.update(status="UNKNOWN",error_class=type(e).__name__[:64],
                        independent_recovery_verified=False)
        send(item)
finally:
    if layer=="core" and "core" in locals() and core is not None:
        core.close()
    if layer=="mart" and "catalog" in locals():
        engine=getattr(catalog,"engine",None)
        if engine is not None:engine.dispose()
'''

def request_guard(req):
    if not (req.get("audit_focus")=="c1a-live-table-reader-recovery-20261024"
            and req.get("scope")=="existing-dev"
            and req.get("read_only") is True
            and req.get("no_data_mutation") is True
            and req.get("no_template_mutation") is True
            and req.get("no_private_row_data") is True
            and req.get("no_new_resources") is True
            and req.get("no_iam_expansion") is True
            and req.get("execution_count")==1):
        raise ValueError("c1a_live_audit_scope_invalid")

def overrides(job, sha, layer):
    containers=job["template"]["template"]["containers"]
    if len(containers)!=1:raise ValueError("single_container_required")
    c=containers[0]
    cmd=c.get("command") or []
    if cmd not in ([], ["python"]):raise ValueError("readonly_entrypoint_drift")
    row={"args":(["-c",PROBE] if cmd else ["python","-c",PROBE]),
         "env":[{"name":"JANUS_GOVERNANCE_SOURCE_SHA","value":sha},
                {"name":"JANUS_C1A_LAYER","value":layer}]}
    if c.get("name"):row["name"]=c["name"]
    return row

def job_metadata(job_name, layer, sha):
    job=gcp.job(job_name)
    before=gcp.fingerprint(job)
    op=gcp.cloud(gcp.ROOT+"/jobs/"+job_name+":run",{
        "etag":job["etag"],
        "overrides":{"taskCount":1,"timeout":"280s",
                     "containerOverrides":[overrides(job,sha,layer)]}
    },"POST")
    op_name=op.get("name","")
    if not op_name.startswith(gcp.ROOT+"/operations/"):
        raise RuntimeError("c1a_operation_identity_missing")
    end=time.monotonic()+390
    while not op.get("done") and time.monotonic()<end:
        time.sleep(7)
        op=gcp.cloud(op_name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("c1a_readonly_operation_failed")
    full=str((op.get("response") or {}).get("name",""))
    if not full.startswith(gcp.ROOT+"/jobs/"+job_name+"/executions/"):
        raise RuntimeError("c1a_execution_identity_missing")
    state=gcp.cloud(full)
    if not gcp.terminal(state) or state.get("succeededCount")!=1 or state.get("failedCount",0):
        raise RuntimeError("c1a_readonly_execution_failed")
    eid=full.rsplit("/",1)[-1]
    selector=('resource.type="cloud_run_job" AND '
              'labels."run.googleapis.com/execution_name"="'+eid+'"')
    received=[]
    for _ in range(7):
        raw=gcp.command(["gcloud","logging","read",selector,
                         "--project="+gcp.PROJECT,"--limit=120","--format=json"])
        received=[]
        for row in json.loads(raw):
            msg=row.get("textPayload") or ""
            if PREFIX not in msg:continue
            try:doc=json.loads(msg.split(PREFIX,1)[1])
            except (ValueError,IndexError):continue
            if doc.get("git_sha")==sha and doc.get("layer")==layer:
                received.append(doc)
        if len(received)==(len(CORE) if layer=="core" else len(MART)):break
        time.sleep(5)
    expected=CORE if layer=="core" else MART
    if len(received)!=len(expected) or {x["name"] for x in received}!=set(expected):
        raise RuntimeError("c1a_incomplete_exact_table_receipt")
    if before!=gcp.fingerprint(gcp.job(job_name)):
        raise RuntimeError("c1a_job_template_drift")
    return {"execution":eid,"job":job_name,"job_configuration_unchanged":True,
            "data_mutations":0,"tables":sorted(received,key=lambda x:x["name"])}

def log_mentions():
    cutoff=(datetime.now(timezone.utc)-timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    targets=CORE+MART
    result=[]
    # Even a complete non-match is NOT a zero-reader statement: structured
    # table access may not log the table identifier at all.
    for kind,name in (("cloud_run_job","janus-intelligence-mart"),
                      ("cloud_run_job","janus-ingestion-core"),
                      ("cloud_run_revision","janus-api")):
        field="job_name" if kind=="cloud_run_job" else "service_name"
        expr=(f'resource.type="{kind}" AND resource.labels.{field}="{name}"'
              f' AND timestamp>="{cutoff}"')
        cmd=["gcloud","logging","read",expr,"--project="+gcp.PROJECT,
             "--limit="+str(MAX_LOG_ENTRIES),"--format=json"]
        row={"kind":kind,"name":name,"lookback_days":WINDOW_DAYS,
             "status":"UNKNOWN","entries_examined":0,"truncated":None,
             "table_mentions":{},"table_reads_confirmed":False}
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=75,check=False)
            if p.returncode:raise RuntimeError("bounded_logging_read_denied_or_failed")
            if len(p.stdout)>MAX_LOG_BYTES:raise ValueError("logging_result_too_large")
            entries=json.loads(p.stdout)
            if not isinstance(entries,list):raise ValueError("logging_result_shape_invalid")
            row["status"]="LOG_SAMPLE_READABLE"
            row["entries_examined"]=len(entries)
            row["truncated"]=len(entries)>=MAX_LOG_ENTRIES
            for target in targets:
                n=target.split(".",1)[1]
                hits=0
                for event in entries:
                    if not isinstance(event,dict):continue
                    # Exclude governance probe log messages; these are not
                    # application usage and must never count as table readers.
                    msg=event.get("textPayload") or json.dumps(
                        event.get("jsonPayload") or {},ensure_ascii=False)
                    if "JANUS_C1A_CURRENT_TABLE_METADATA" in msg or "JANUS_GOVERNANCE_" in msg:
                        continue
                    if target in msg or re.search(r"\b"+re.escape(n)+r"\b",msg):
                        hits+=1
                if hits:row["table_mentions"][target]=hits
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as e:
            row["error_class"]=type(e).__name__
        result.append(row)
    return result

def decide(core, mart, logs):
    table_evidence={}
    for entry in core["tables"]+mart["tables"]:
        table_evidence[entry["name"]]={
            "current_metadata":entry["status"],
            "current_snapshot_id":entry.get("current_snapshot_id"),
            "current_record_count":entry.get("current_record_count"),
            "current_manifest_count":entry.get("current_manifest_count"),
            "independent_recovery_verified":False,
            "recovery_classification":"NO_INDEPENDENT_REBUILD_OR_RESTORE_RECEIPT",
            "actual_business_reader":"UNKNOWN_NO_TABLE_LEVEL_RUNTIME_TRACE"}
    for row in logs:
        for table,hits in row.get("table_mentions",{}).items():
            table_evidence[table].setdefault("log_mentions",[]).append({
                "resource":row["name"],"count":hits,
                "evidence":"NAME_MENTION_ONLY_NOT_PROVEN_READ"})
    return table_evidence

def main():
    request_guard(json.loads(REQ.read_text(encoding="utf-8")))
    sha=os.environ.get("GITHUB_SHA","")
    if not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise ValueError("c1a_invalid_source_git_sha")
    output={"component":"janus_governance_c1a_live_table_recovery_v1",
            "checked_at_utc":datetime.now(timezone.utc).isoformat(),
            "source_git_sha":sha,"read_only":True,"data_mutations":0,
            "iam_changes":0,"new_resources":0,"table_probes":{}}
    for job,layer in JOBS:
        try:output["table_probes"][layer]=job_metadata(job,layer,sha)
        except Exception as e:
            output["table_probes"][layer]={"status":"BLOCKED",
                                          "error_class":type(e).__name__,
                                          "error_code":str(e)[:90]}
    output["logs"]=log_mentions()
    if all("tables" in output["table_probes"][k] for k in ("core","mart")):
        output["table_evidence"]=decide(output["table_probes"]["core"],
                                        output["table_probes"]["mart"],output["logs"])
        core={t["name"]:t for t in output["table_probes"]["core"]["tables"]}
        a,b=core["core.market_volume_v1"],core["core.ohlcv_v1"]
        fields_a={f[0] for f in a.get("schema",[])}
        fields_b={f[0] for f in b.get("schema",[])}
        output["core_pair"]={"shared_columns":sorted(fields_a & fields_b),
                             "market_volume_only":sorted(fields_a-fields_b),
                             "ohlcv_only":sorted(fields_b-fields_a),
                             "same_key_value_parity":"NOT_VERIFIED_NO_ROW_SCAN",
                             "independent_rollback":"NOT_VERIFIED"}
    output["status"]="METADATA_PASS_READER_AND_RECOVERY_PARTIAL" if (
        len(output.get("table_evidence",{}))==13 and
        all(x["current_metadata"]=="READABLE"
            for x in output["table_evidence"].values())) else "PARTIAL"
    OUT.write_text(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2))
    print(json.dumps({"status":output["status"],"git_sha":sha,
                      "table_count":len(output.get("table_evidence",{})),
                      "current_metadata_readable":sum(x["current_metadata"]=="READABLE"
                          for x in output.get("table_evidence",{}).values()),
                      "log_sources_readable":sum(x["status"]=="LOG_SAMPLE_READABLE"
                          for x in output["logs"]),
                      "reader_usage":"UNKNOWN_UNLESS_PROVED_POSITIVE",
                      "independent_recovery":"NOT_VERIFIED",
                      "data_mutations":0,"new_resources":0},sort_keys=True))
if __name__=="__main__":
    main()
