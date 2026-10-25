"""SEQ-08: bounded PostgreSQL product readback via one existing Dev Mart Job.

Requires an explicit exact execution ID from a successful real Mart receipt.
One Cloud Run override runs only SELECT under a read-only transaction; prints
aggregate model role statuses and explicitly requested public stock flags.
Never emits credentials, private symbol lists, holdings, prices or payload JSON.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import ghcr_jobs_rollout as jobs

PREFIX="SEQ08_PG_PROOF:"
PROJECT="gen-lang-client-0593591102"
JOB="janus-intelligence-mart"
SOURCE_PATTERN=re.compile(r"^[a-f0-9]{40}$")
EXEC_PATTERN=re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
ROLE_NAMES=("quant","risk","fundamental","valuation")

PROBE=r'''
import json, os, psycopg
from collections import Counter
from packages.postgres_bundle import load_postgres_bundle
from intelligence_mart.runtime import _settings
uid=os.environ["SEQ08_PROOF_MART_EXECUTION"]
load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
    "CATALOG_DB_PASSWORD":("mart_catalog_password","catalog_password"),
    "PUBLICATION_DB_PASSWORD":("mart_publication_password","publication_password")})
settings=_settings("PUBLICATION_DB")
with psycopg.connect(host=settings["host"],dbname=settings["name"],user=settings["user"],
                     password=settings["password"],sslmode=os.getenv("PUBLICATION_DB_SSLMODE","require"),
                     connect_timeout=8) as db:
    with db.transaction():
        db.execute("SET TRANSACTION READ ONLY")
        db.execute("SET LOCAL statement_timeout='25000ms'")
        with db.cursor() as cur:
            cur.execute("""SELECT symbol,payload_json->'four_model_serving'
                           FROM private.specialist_product
                           WHERE execution_id=%s""",(uid,))
            rows=cur.fetchall()
            statuses={r:Counter() for r in ("quant","risk","fundamental","valuation")}
            missing_serving=0
            for symbol,item in rows:
                if isinstance(item,str): item=json.loads(item)
                if not isinstance(item,dict):
                    missing_serving+=1
                    continue
                for role in statuses:
                    status=item.get(role,{}).get("status","MISSING_STATUS")
                    statuses[role][status]+=1
            cur.execute("""SELECT symbol,MAX(analysis_as_of) FROM private.specialist_product
                           WHERE symbol IN ('2330','2882') GROUP BY symbol""")
            public_samples={str(s):str(d) for s,d in cur.fetchall()}
proof={"status":"PG_SELECT_READBACK_PASS","mart_execution_id":uid,
       "rows":len(rows),"missing_serving":missing_serving,
       "status_counts":{k:dict(v) for k,v in statuses.items()},
       "public_samples_present":{code:code in public_samples for code in ("2330","2882")},
       "owner_login_ui":"NOT_VERIFIED","private_symbols_exposed":False}
print("SEQ08_PG_PROOF:"+json.dumps(proof,sort_keys=True),flush=True)
'''


def request():
    data=json.loads(Path("ops/seq08-pg-readback-request.json").read_text())
    if (data.get("intent")!="seq08-one-existing-dev-pg-readonly"
        or data.get("approved") is not True
        or data.get("scope")!="existing-dev-mart-one-select-execution"
        or data.get("no_pg_mutation") is not True
        or data.get("no_owner_mutation") is not True
        or data.get("no_new_resources") is not True
        or data.get("one_job_execution") is not True
        or not SOURCE_PATTERN.fullmatch(str(data.get("source_sha","")))
        or not EXEC_PATTERN.fullmatch(str(data.get("mart_execution_id","")))
        or os.getenv("GITHUB_RUN_ATTEMPT","1")!="1"):
        raise ValueError("seq08_pg_probe_request_invalid")
    return data


def parse_log(entries, operation_id):
    hits=[]
    for item in entries:
        blob=item.get("textPayload","")
        if PREFIX not in blob:
            continue
        try:
            result=json.loads(blob.split(PREFIX,1)[1].strip())
        except ValueError:
            continue
        if (result.get("mart_execution_id")==operation_id
                and result.get("status")=="PG_SELECT_READBACK_PASS"
                and result.get("private_symbols_exposed") is False):
            hits.append(result)
    if len(hits)!=1:
        raise ValueError("seq08_exact_pg_log_receipt_missing_or_ambiguous")
    return hits[0]


def main():
    file=Path("/tmp/seq08-pg-product-proof.json")
    phase="PREFLIGHT"
    maybe_dispatched=False
    try:
        req=request()
        job=jobs.job(JOB)
        ref=jobs.image(job)
        if "@sha256:" not in ref:
            raise ValueError("seq08_pg_probe_unpinned_job")
        # The Cloud Run container exposes the exact current immutable version.
        marker=jobs.command(["skopeo","inspect","--no-creds","docker://"+ref])
        data=json.loads(marker)
        if data.get("Labels",{}).get("org.opencontainers.image.revision")!=req["source_sha"]:
            raise ValueError("seq08_pg_probe_source_version_drift")
        jobs.wait_for_terminal_executions(timeout=400)
        job=jobs.job(JOB)
        if jobs.image(job)!=ref:
            raise ValueError("seq08_pg_probe_image_changed")
        container=job["template"]["template"]["containers"][0]
        if container.get("command") not in (None,["python"]):
            raise ValueError("seq08_pg_probe_entrypoint_unknown")
        override={"args":(["python"] if not container.get("command") else []) + ["-c",PROBE],
                  "env":[{"name":"SEQ08_PROOF_MART_EXECUTION","value":req["mart_execution_id"]}]}
        if container.get("name"): override["name"]=container["name"]
        phase="DISPATCH_UNKNOWN_DO_NOT_RETRY"
        file.write_text(json.dumps({"phase":phase,"maybe_dispatched":True}))
        maybe_dispatched=True
        op=jobs.cloud(f"{jobs.ROOT}/jobs/{JOB}:run",{"etag":job["etag"],
            "overrides":{"taskCount":1,"timeout":"240s","containerOverrides":[override]}},"POST")
        name=op.get("name","")
        if not name.startswith(jobs.ROOT+"/operations/"):
            raise ValueError("seq08_pg_probe_op_identity_unknown")
        deadline=time.monotonic()+320
        while not op.get("done") and time.monotonic()<deadline:
            time.sleep(6)
            op=jobs.cloud(name)
        if not op.get("done") or op.get("error"):
            raise ValueError("seq08_pg_probe_not_successful_or_unknown")
        result=op.get("response",{})
        if (not jobs.terminal(result) or result.get("succeededCount")!=1
                or result.get("failedCount",0)):
            raise ValueError("seq08_pg_probe_execution_not_pass")
        execution=result.get("name","").rsplit("/",1)[-1]
        if not re.fullmatch(r"janus-intelligence-mart-[a-z0-9-]+",execution):
            raise ValueError("seq08_pg_probe_execution_identity_invalid")
        phase="LOG_READBACK"
        query=('resource.type="cloud_run_job" AND '
               'labels."run.googleapis.com/execution_name"="'+execution+'"')
        for _ in range(4):
            cp=subprocess.run(["gcloud","logging","read",query,"--project="+PROJECT,
                              "--limit=150","--format=json"],capture_output=True,timeout=75)
            if cp.returncode:
                raise ValueError("seq08_pg_probe_log_read_denied")
            try:
                proof=parse_log(json.loads(cp.stdout),req["mart_execution_id"])
                proof["cloud_run_execution"]=execution
                proof["gcp_job_executions"]=1
                file.write_text(json.dumps(proof,sort_keys=True))
                print(json.dumps(proof,sort_keys=True))
                return
            except ValueError as error:
                if str(error)!="seq08_exact_pg_log_receipt_missing_or_ambiguous":
                    raise
            time.sleep(5)
        raise ValueError("seq08_pg_probe_log_receipt_not_found")
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) else type(error).__name__
        if not re.fullmatch("[a-z][a-z0-9_]{3,100}",code):code=type(error).__name__
        fail={"status":"BLOCKED","phase":phase,"reason":code,
              "may_have_dispatched":maybe_dispatched,"pg_mutations":0}
        file.write_text(json.dumps(fail,sort_keys=True))
        print(json.dumps(fail,sort_keys=True))
        sys.exit(78)


if __name__=="__main__":
    main()
