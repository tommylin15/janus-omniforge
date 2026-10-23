#!/usr/bin/env python3
"""Mart-side bounded Iceberg *metadata* readback with the EXISTING dev Mart Job.

This intentionally does not widen ingestion-core or GitHub IAM. Table metadata
is read by janus-intelligence-mart, whose existing dev identity can access Mart.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp
from governance_metadata_readonly import REQUEST, validate_request

JOB = "janus-intelligence-mart"
PREFIX = "JANUS_GOVERNANCE_MART_METADATA_RECEIPT_V1:"
OUTPUT = Path("governance-mart-metadata-readonly-receipt.json")

MART_PROBE = r'''
import json, os
from datetime import datetime, timezone
from packages.postgres_bundle import load_postgres_bundle

PREFIX = "JANUS_GOVERNANCE_MART_METADATA_RECEIPT_V1:"
now = datetime.now(timezone.utc).isoformat()
git_sha = os.environ.get("JANUS_GOVERNANCE_SOURCE_SHA", "UNKNOWN")
job = {"component": "janus_governance_mart_metadata_readonly_v1",
       "checked_at_utc": now, "git_sha": git_sha,
       "project": os.environ.get("GCP_PROJECT_ID", "UNKNOWN"),
       "environment": "dev", "read_only": True, "data_mutations": 0}
def err(e):
    return {"error_class":type(e).__name__[:64],
            "sqlstate":str(getattr(e, "sqlstate", None) or "")[:5] or None}
def emit(section, rows, status):
    count=max(1,(len(rows)+9)//10)
    for index in range(count):
        print(PREFIX + json.dumps({**job, "section":section,"status":status,
            "chunk":index+1,"chunks":count,
            "items":rows[index*10:(index+1)*10]},
            ensure_ascii=False,sort_keys=True,default=str), flush=True)
status="PARTIAL"
try:
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD":("mart_catalog_password","catalog_password")})
    # Existing Mart publication role receives SELECT only on approved metadata
    # columns (migrations 035/038); no owner/symbol/scope_id/URI is selected.
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "PUBLICATION_DB_PASSWORD":("mart_publication_password","publication_password")})
    import psycopg
    from intelligence_mart.runtime import _settings
    try:
        cfg=_settings("PUBLICATION_DB")
        cfg["dbname"]=cfg.pop("name")
        with psycopg.connect(**cfg,sslmode=os.environ.get("PUBLICATION_DB_SSLMODE","require"),
                             connect_timeout=5,autocommit=True,
                             options="-cdefault_transaction_read_only=on") as conn:
            for sec,query in [
                ("publication_index_all", """
                    SELECT table_identifier,publication_status,analysis_outcome,
                           count(*)::bigint,min(analysis_as_of)::text,
                           max(analysis_as_of)::text,
                           count(DISTINCT iceberg_snapshot_id)::bigint
                      FROM publication.mart_report_index
                     GROUP BY table_identifier,publication_status,analysis_outcome
                     ORDER BY table_identifier,publication_status,analysis_outcome LIMIT 51
                """),
                ("publication_index_30d", """
                    SELECT table_identifier,publication_status,analysis_outcome,
                           count(*)::bigint,max(analysis_as_of)::text
                      FROM publication.mart_report_index
                     WHERE analysis_as_of>=current_date-interval '30 days'
                     GROUP BY table_identifier,publication_status,analysis_outcome
                     ORDER BY table_identifier,publication_status,analysis_outcome LIMIT 51
                """)]:
                try:
                    conn.execute("BEGIN READ ONLY")
                    conn.execute("SET LOCAL statement_timeout='10000ms'")
                    result=conn.execute(query).fetchall()
                    conn.execute("ROLLBACK")
                    if len(result)>50:
                        emit(sec,[{"error_class":"RESULT_LIMIT_EXCEEDED"}],"BLOCKED")
                    else:
                        emit(sec,[list(row) for row in result],"PASS")
                except Exception as e:
                    try:conn.execute("ROLLBACK")
                    except Exception:pass
                    emit(sec,[err(e)],"BLOCKED")
    except Exception as e:
        emit("publication_reader_connection",[err(e)],"BLOCKED")
    from intelligence_mart.storage import sql_catalog_from_environment
    catalog = sql_catalog_from_environment()
    try:
        # PyIceberg catalog namespace listing is metadata-only; no writes or scans.
        names = sorted(str(ns)+"."+str(table) for ns,table in catalog.list_tables(("mart",)))
        if not names:
            emit("mart_catalog_names", [{"error_class":"EMPTY_OR_UNREADABLE"}],"BLOCKED")
        else:
            emit("mart_catalog_names",[{"name":n} for n in names],"PASS")
        details=[]
        for name in names[:100]:
            item={"name":name}
            try:
                table=catalog.load_table(name)
                snap=table.current_snapshot()
                item.update(status="READABLE",
                    metadata_location=table.metadata_location,
                    schema=[[f.name,str(f.field_type),f.required] for f in table.schema().fields],
                    partition_spec=[[f.name,str(f.transform)] for f in table.spec().fields],
                    snapshot_id=str(snap.snapshot_id) if snap else None,
                    row_count=int(snap.summary["total-records"])
                        if snap and snap.summary and "total-records" in snap.summary else None)
            except Exception as e:
                item.update(status="UNKNOWN",error=err(e))
            details.append(item)
        emit("mart_snapshots",details,"PASS" if names and len(names)<=100 and
            len(details)==len(names) and all(x["status"]=="READABLE" for x in details)
            else "PARTIAL")
        status="PASS" if names and len(names)<=100 and len(details)==len(names) and all(
            x["status"]=="READABLE" for x in details) else "PARTIAL"
        emit("summary",[{"status":status,"catalog_names":len(names),
            "snapshots_readable":sum(x["status"]=="READABLE" for x in details),
            "data_mutations":0}],"PASS" if status=="PASS" else "PARTIAL")
    finally:
        engine=getattr(catalog,"engine",None)
        if engine is not None:engine.dispose()
except Exception as e:
    emit("summary",[{"status":"BLOCKED","error":err(e),"data_mutations":0}],"BLOCKED")
'''

def override(job: dict, git_sha: str) -> dict:
    cs=job["template"]["template"]["containers"]
    if len(cs)!=1:raise ValueError("single_container_required")
    c=cs[0]
    cmd=c.get("command") or []
    if cmd not in ([],["python"]):raise ValueError("readonly_entrypoint_drift")
    out={"args":(["-c",MART_PROBE] if cmd else ["python","-c",MART_PROBE]),
         "env":[{"name":"JANUS_GOVERNANCE_SOURCE_SHA","value":git_sha}]}
    if c.get("name"):out["name"]=c["name"]
    return out

def main():
    validate_request(json.loads(REQUEST.read_text(encoding="utf-8")))
    sha=os.environ.get("GITHUB_SHA","")
    if not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise ValueError("github_sha_missing")
    job=gcp.job(JOB)
    config=gcp.fingerprint(job)
    op=gcp.cloud(gcp.ROOT+"/jobs/"+JOB+":run",{
        "etag":job["etag"],
        "overrides":{"taskCount":1,"timeout":"280s",
                     "containerOverrides":[override(job,sha)]}},"POST")
    op_name=op.get("name","")
    if not op_name.startswith(gcp.ROOT+"/operations/"):
        raise RuntimeError("mart_readonly_operation_unknown")
    due=time.monotonic()+390
    while not op.get("done") and time.monotonic()<due:
        time.sleep(7)
        op=gcp.cloud(op_name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("mart_readonly_operation_failed")
    e=op.get("response") or {}
    full=str(e.get("name",""))
    if not full.startswith(gcp.ROOT+"/jobs/"+JOB+"/executions/"):
        raise RuntimeError("mart_readonly_execution_unknown")
    e=gcp.cloud(full)
    if not gcp.terminal(e) or e.get("succeededCount")!=1 or e.get("failedCount",0):
        raise RuntimeError("mart_readonly_execution_failed")
    name=full.rsplit("/",1)[-1]
    selector=('resource.type="cloud_run_job" AND '
              'labels."run.googleapis.com/execution_name"="'+name+'"')
    receipts=[]
    for _ in range(7):
        raw=gcp.command(["gcloud","logging","read",selector,
                         "--project="+gcp.PROJECT,"--limit=150","--format=json"])
        receipts=[]
        for entry in json.loads(raw):
            payload=entry.get("textPayload") or ""
            if PREFIX not in payload:continue
            try:doc=json.loads(payload.split(PREFIX,1)[1])
            except (ValueError,IndexError):continue
            if doc.get("component")=="janus_governance_mart_metadata_readonly_v1" and doc.get("git_sha")==sha:
                receipts.append(doc)
        if any(x.get("section")=="summary" for x in receipts):break
        time.sleep(5)
    if not any(x.get("section")=="summary" for x in receipts):
        raise RuntimeError("mart_readonly_receipt_missing")
    sections={}
    for row in receipts:
        sections.setdefault(row["section"],[]).append(row)
    for name_,rows in sections.items():
        if len(rows)!=rows[0]["chunks"] or {x["chunk"] for x in rows}!=set(range(1,rows[0]["chunks"]+1)):
            raise RuntimeError("mart_readonly_chunk_missing_"+name_)
    if config!=gcp.fingerprint(gcp.job(JOB)):
        raise RuntimeError("mart_job_configuration_drift")
    result={"component":"janus_governance_mart_metadata_readonly_v1",
            "git_sha":sha,"execution":name,"data_mutations":0,
            "job_configuration_unchanged":True,
            "sections":{key:{"status":rows[0]["status"],
                "items":sum((x["items"] for x in sorted(rows,key=lambda r:r["chunk"])),[])}
                for key,rows in sections.items()}}
    OUTPUT.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2),encoding="utf-8")
    for row in sorted(receipts,key=lambda x:(x["section"],x["chunk"])):
        print(PREFIX+json.dumps(row,sort_keys=True,ensure_ascii=False))
    status=result["sections"]["summary"]["items"][0]["status"]
    print(json.dumps({"component":result["component"],"status":status,
                      "execution":name,"sections":{k:len(x["items"]) for k,x in result["sections"].items()}},sort_keys=True))
    if status!="PASS":raise RuntimeError("mart_readonly_metadata_partial")

if __name__=="__main__":
    main()
