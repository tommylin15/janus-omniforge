#!/usr/bin/env python3
"""P0-2: one bounded owner-safe Core artifact audit in existing dev ingestion Job.

Never starts queued workers, marks execution status, modifies GCS, or edits templates.
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

JOB="janus-ingestion-core"
PREFIX="JANUS_P02_CORE_ARTIFACT_AUDIT_V1:"
OUT=Path("p02-core-artifact-audit-receipt.json")

PROBE=r'''
import hashlib,json,os,re
import google.auth
from google.auth.transport.requests import AuthorizedSession
from urllib.parse import quote
import psycopg
from packages.postgres_bundle import load_postgres_bundle

PREFIX="JANUS_P02_CORE_ARTIFACT_AUDIT_V1:"
load_postgres_bundle("JANUS_INGESTION_POSTGRES_BUNDLE",{
    "CONTROL_DB_PASSWORD":("ingestion_control_password","control_password")})
settings={key:os.environ["CONTROL_DB_"+key] for key in
          ("HOST","NAME","USER","PASSWORD")}
fields=dict(host=settings["HOST"],dbname=settings["NAME"],user=settings["USER"],
  password=settings["PASSWORD"],sslmode=os.environ.get("CONTROL_DB_SSLMODE","require"),
  connect_timeout=8,autocommit=True,options="-cdefault_transaction_read_only=on")
bucket=os.environ["CORE_BUCKET"]
source=os.environ["JANUS_P02_SOURCE_SHA"]
if not re.fullmatch("[0-9a-f]{40}",source):raise RuntimeError("P02_SOURCE_UNVERIFIED")
with psycopg.connect(**fields) as c:
    c.execute("BEGIN READ ONLY")
    c.execute("SET LOCAL statement_timeout='15000ms'")
    rows=c.execute("""
        SELECT md5(e.execution_id::text) AS ref,
               e.trigger_type,e.status,e.started_at::text,
               e.claimed_until::text,e.retry_count,
               CASE WHEN e.trigger_type='analysis'
                      THEN e.request_options->>'core_snapshot_uri'
                    ELSE 'gs://' || %s || '/executions/' ||
                         e.execution_id::text || '/core-snapshot.json' END AS uri,
               e.request_options->>'core_snapshot_hash' AS expected_hash,
               e.request_options->>'core_snapshot_id' AS expected_id,
               r.payload->>'coreSnapshotHash' AS source_hash,
               r.payload->>'coreSnapshotId' AS source_id,
               r.payload->>'coreSnapshotUri' AS source_uri,
               (SELECT count(*)::int FROM control.execution_items i
                 WHERE i.execution_id=e.execution_id) AS items,
               EXISTS(SELECT 1 FROM control.batch_occurrences b
                 WHERE b.state->>'queued_execution_id'=e.execution_id::text
                   AND b.state->>'status' IN
                     ('pending','dispatching','running','ambiguous')) AS active_occurrence
          FROM control.executions e
          LEFT JOIN control.core_ready_events r
            ON r.analysis_execution_id=e.execution_id
         WHERE (e.status IN ('queued','running','retrying')
               AND e.requested_at >= now()-interval '30 days')
            OR md5(e.execution_id::text) IN (
              'ebd446b690bcab42cbec3945cde8bb46',
              'a402e714840ce3ff2452850474890857')
         ORDER BY e.requested_at,e.execution_id LIMIT 301
    """,(bucket,)).fetchall()
    c.execute("ROLLBACK")
if len(rows)>300:raise RuntimeError("P02_ROW_LIMIT_EXCEEDED")
credentials,_=google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
client=AuthorizedSession(credentials)
pat=re.compile("^gs://"+re.escape(bucket)+r"/executions/[0-9a-f-]{36}/core-snapshot\.json$")
output=[]
for ref,trigger,status,started,lease,retry,uri,expected_hash,expected_id,source_hash,source_id,source_uri,item_count,busy in rows:
    record={"ref":ref,"trigger":trigger,"status":status,
        "items":item_count,"active_occurrence":busy,
        "has_started":bool(started),"has_lease":bool(lease),
        "retry_count":retry,"result":"UNKNOWN"}
    if not isinstance(uri,str) or not pat.fullmatch(uri):
        record["result"]="MISSING_OR_UNAUTHORIZED_CORE_LOCATOR"
    elif trigger=="analysis" and (
        uri!=source_uri or source_id!=expected_id or source_hash!=expected_hash
        or not isinstance(expected_hash,str) or
        not re.fullmatch(r"sha256:[0-9a-f]{64}",expected_hash)):
        record["result"]="CORE_READY_OPTIONS_BINDING_MISMATCH"
    else:
        name=uri.split("/",3)[3]
        url=("https://storage.googleapis.com/storage/v1/b/"+quote(bucket,safe="")+
             "/o/"+quote(name,safe=""))
        meta=client.get(url,timeout=20)
        if meta.status_code==404:
            record["result"]="MISSING_CORE_MANIFEST"
        elif meta.status_code!=200:
            record["result"]="CORE_GCS_METADATA_HTTP_"+str(meta.status_code)
        elif not str(meta.json().get("size","")).isdigit() or not (
              80<=int(meta.json()["size"])<=200000):
            record["result"]="CORE_MANIFEST_SIZE_OUTSIDE_BOUND"
        else:
            generation=str(meta.json().get("generation",""))
            if not generation.isdigit():
                record["result"]="CORE_MANIFEST_GENERATION_MISSING"
                output.append(record)
                continue
            media=client.get(url,params={"alt":"media",
                  "ifGenerationMatch":generation},timeout=25)
            if media.status_code!=200:
                record["result"]="CORE_GCS_MEDIA_HTTP_"+str(media.status_code)
                output.append(record)
                continue
            raw=media.content
            try:
                payload=json.loads(raw)
            except (ValueError,TypeError):
                payload={}
            digest="sha256:"+hashlib.sha256(raw).hexdigest()
            if payload.get("artifact_kind")!="core_snapshot_v1" or not payload.get("snapshot_id"):
                record["result"]="CORE_MANIFEST_SCHEMA_UNKNOWN"
            elif trigger=="analysis" and (
                digest!=expected_hash or payload.get("snapshot_id")!=expected_id):
                record["result"]="CORE_MANIFEST_HASH_OR_SNAPSHOT_MISMATCH"
            elif busy or lease:
                record["result"]="ACTIVE_OR_UNKNOWN_FENCE_NOT_FOR_REPLAY"
            elif trigger=="analysis":
                record["result"]="CORE_MANIFEST_VERIFIED_PUBLICATION_CHECK_REQUIRED"
            else:
                record["result"]="COLLECTION_MANIFEST_PRESENT_DB_COMMIT_REVIEW"
            record["generation_present"]=True
    output.append(record)
for ix in range(0,len(output),15):
    print(PREFIX+json.dumps({"source_sha":source,"chunk":ix//15+1,
          "items":output[ix:ix+15]},sort_keys=True),flush=True)
print(PREFIX+json.dumps({"source_sha":source,"summary":True,
      "total":len(output),"results":{k:sum(x["result"]==k for x in output)
          for k in sorted({x["result"] for x in output})},
      "data_mutations":0,"job_dispatches":0,"gcs_deletions":0},sort_keys=True),flush=True)
'''

def main():
    sha=os.environ.get("GITHUB_SHA","")
    if not re.fullmatch("[0-9a-f]{40}",sha):
        raise ValueError("P02_GITHUB_SHA_REQUIRED")
    job=gcp.job(JOB)
    before=gcp.fingerprint(job)
    cont=job["template"]["template"]["containers"]
    if len(cont)!=1 or (cont[0].get("command") or []) not in ([],["python"]):
        raise ValueError("P02_JOB_ENTRYPOINT_NOT_ALLOWED")
    ov={"args":["-c",PROBE] if cont[0].get("command") else ["python","-c",PROBE],
        "env":[{"name":"QUEUE_CONSUMER","value":"false"},
               {"name":"JANUS_P02_SOURCE_SHA","value":sha}]}
    if cont[0].get("name"): ov["name"]=cont[0]["name"]
    op=gcp.cloud(gcp.ROOT+"/jobs/"+JOB+":run",{
        "etag":job["etag"],"overrides":{"taskCount":1,"timeout":"300s","containerOverrides":[ov]}
    },"POST")
    name=op.get("name","")
    if not name.startswith(gcp.ROOT+"/operations/"):raise RuntimeError("P02_OPERATION_UNKNOWN")
    limit=time.monotonic()+420
    while not op.get("done") and time.monotonic()<limit:
        time.sleep(8);op=gcp.cloud(name)
    if not op.get("done") or op.get("error"):raise RuntimeError("P02_OPERATION_FAILED")
    full=(op.get("response") or {}).get("name","")
    if not full.startswith(gcp.ROOT+"/jobs/"+JOB+"/executions/"):
        raise RuntimeError("P02_EXECUTION_IDENTITY_UNKNOWN")
    execution=gcp.cloud(full)
    if not gcp.terminal(execution) or execution.get("succeededCount")!=1:
        raise RuntimeError("P02_EXECUTION_FAILED")
    target=full.rsplit("/",1)[-1]
    selector=('resource.type="cloud_run_job" AND '
      'labels."run.googleapis.com/execution_name"="'+target+'"')
    records=[]
    for _ in range(8):
        lines=json.loads(gcp.command(["gcloud","logging","read",selector,
           "--project="+gcp.PROJECT,"--limit=300","--format=json"]))
        records=[]
        for line in lines:
            payload=line.get("textPayload") or ""
            if PREFIX not in payload:continue
            try:record=json.loads(payload.split(PREFIX,1)[1])
            except ValueError:continue
            if record.get("source_sha")==sha:records.append(record)
        if any(x.get("summary") for x in records):break
        time.sleep(5)
    summary=[x for x in records if x.get("summary")]
    if len(summary)!=1:raise RuntimeError("P02_SUMMARY_MISSING")
    chunks=[x for x in records if not x.get("summary")]
    if len(chunks)!=(summary[0]["total"]+14)//15:
        raise RuntimeError("P02_CHUNKS_MISSING")
    items=sum((x["items"] for x in sorted(chunks,key=lambda x:x["chunk"])),[])
    if len(items)!=summary[0]["total"] or len({x["ref"] for x in items})!=len(items):
        raise RuntimeError("P02_ITEM_COUNT_OR_IDENTITY_DRIFT")
    if before!=gcp.fingerprint(gcp.job(JOB)):
        raise RuntimeError("P02_EXISTING_JOB_TEMPLATE_MUTATED")
    receipt={"status":"PASS","source_sha":sha,"execution":target,
      "count":len(items),"classes":summary[0]["results"],"items":items,
      "job_template_unchanged":True,"data_mutations":0,"job_dispatches":0,
      "gcs_deletions":0}
    OUT.write_text(json.dumps(receipt,sort_keys=True,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items() if k!="items"},sort_keys=True))

if __name__=="__main__":
    main()
