"""Live non-canonical P0-V CEO acceptance using the deployed Mart Job identity.

Production code is imported from the already released immutable worker image.
No real owner requests or market data are touched. Live PG writes use only a
transaction-scoped TEMP table; GCS uses a unique isolated disposable prefix.
"""
from __future__ import annotations
import json
import time

from ceo_worker_deploy import execution_fence
from ghcr_jobs_rollout import ROOT, cloud, terminal

JOB = "janus-ceo-analysis"
RELEASE_SHA = "b63bf350213fa7c3933724fa38006d8ab7b8033f"
PROBE_CODE = """
import json, os
from uuid import uuid4
from copy import deepcopy
from types import SimpleNamespace

from packages.analysis_product import content_hash
from intelligence_mart.product_runtime import execute_ceo
from intelligence_mart.runtime import _write_immutable_json, _settings
from ingestion_core.stage import GcsObjectStore
from packages.postgres_bundle import load_postgres_bundle
import psycopg
from psycopg.rows import dict_row

roles=('fundamental','valuation','quant','risk','event')
hashes=['sha256:' + str(i+1)*64 for i in range(5)]
baseline={'symbol':'P0VTEST','analysis_as_of':'2026-10-13',
 'execution_id':str(uuid4()),'model_quality':'NOT_VERIFIED',
 'specialists':[{'role':role,'output_hash':hashes[index],
   'evidence_ids':[], 'metrics':{}, 'baseline_status':'unavailable',
   'missing_data':['synthetic-no-market-data']} for index,role in enumerate(roles)]}
baseline['content_hash']=content_hash(baseline)
output={'schema_version':'1.0.0','role':'ceo','stance':'insufficient_data',
 'thesis':None,'missing_information':['隔離合成資料，不能發佈正式分析'],
 'confidence':0.0,'evidence_ids':[],'supporting_roles':[],
 'opposing_roles':[],'contradictions':[],'bull_case':[],'bear_case':[],
 'principal_risks':[],'watch_items':[],'change_since_previous_analysis':[],
 'validated_role_artifact_hashes':hashes}
request={'request_id':str(uuid4()),'symbol':'P0VTEST','baseline_json':baseline,
 'baseline_hash':baseline['content_hash'],'profile_id':'default','profile_version':1}
class Router:
    def __init__(self,answer):self.answer=answer
    def invoke(self,role,inputs,**kwargs):
        assert role=='ceo' and len(inputs['validated_specialists'])==5
        assert inputs['canonical_numbers_are_read_only']
        return SimpleNamespace(status='succeeded',output=self.answer,
         attempts=[{'provider':'gemini','transport':'omniagent_gateway',
                    'raw_text':'never-written'}],
         routing={'routing_hash':'acceptance-synthetic',
                  'providers':['gemini'],'execution_policy':'omniagent_gateway_gemini_lite_only'},
         provider='gemini',model='gemini-3.5-flash-lite')
state,report,audit,reason=execute_ceo(request,Router(output))
if state!='PARTIAL' or report is None or reason or audit.get('publication_authority') is not False:
    raise RuntimeError('synthetic_full_ceo_validator_failed')
if report.get('output',{}).get('validated_role_artifact_hashes')!=hashes:
    raise RuntimeError('synthetic_five_hashes_failed')
if 'raw_text' in str(audit):raise RuntimeError('audit_redaction_failed')
for mode in ('hash','evidence','numeric','missing'):
    invalid=deepcopy(output)
    if mode=='hash':invalid['validated_role_artifact_hashes'][0]='sha256:'+'f'*64
    if mode=='evidence':invalid['thesis']={'text':'合成主張','evidence_ids':['ev-'+'0'*24]}
    if mode=='numeric':invalid['missing_information']=['虛構 999999 目標價']
    if mode=='missing':invalid['missing_information']=[]
    rejected,payload,_,problem=execute_ceo(request,Router(invalid))
    if rejected!='BLOCKED' or payload is not None or problem!='output_validation_failed':
        raise RuntimeError('synthetic_negative_validator_failed')
report_digest=content_hash(report)

# Real PG connectivity with a private temp table; ON COMMIT DROP cannot
# create durable private.ceo_requests or fake analyst history.
load_postgres_bundle('JANUS_MART_POSTGRES_BUNDLE',{
  'PUBLICATION_DB_PASSWORD':('mart_publication_password','publication_password')})
config=_settings('PUBLICATION_DB')
with psycopg.connect(host=config['host'], dbname=config['name'],
    user=config['user'],password=config['password'],sslmode='require',
    connect_timeout=5,options='-c statement_timeout=15000',
    row_factory=dict_row) as connection:
    with connection.transaction():
        connection.execute('CREATE TEMP TABLE ceo_p0v_tech_only (report jsonb NOT NULL, digest text NOT NULL) ON COMMIT DROP')
        connection.execute('INSERT INTO ceo_p0v_tech_only(report,digest) VALUES (%s::jsonb,%s)',
            (json.dumps(report,ensure_ascii=False),report_digest))
        row=connection.execute('SELECT report,digest FROM ceo_p0v_tech_only').fetchone()
        if row['report']!=report or row['digest']!=report_digest:
            raise RuntimeError('isolated_live_postgres_roundtrip_invalid')
    if connection.execute("SELECT to_regclass('pg_temp.ceo_p0v_tech_only') AS temp").fetchone()['temp'] is not None:
        raise RuntimeError('postgres_temp_table_not_dropped')

# Immutable GCS creation/readback and cleanup only under a unique P0-V
# acceptance prefix. No write to ceo/<request_id>/report.json.
bucket=os.environ['MART_BUCKET']
store=GcsObjectStore(bucket)
name='acceptance/p0v-ceo-technical/'+str(uuid4())+'/report.json'
try:
    reference=_write_immutable_json(store,bucket,name,report)
    observed=json.loads(store.read(name))
    if observed!=report or reference['artifact_hash']!='sha256:'+__import__('hashlib').sha256(
       json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest():
        raise RuntimeError('isolated_gcs_immutable_report_invalid')
finally:
    store.delete(name)
print(json.dumps({'kind':'p0v-ceo-technical-live-data-contract','status':'PASS',
  'synthetic_roles':5,'full_validator':'PASS','negative_contracts':4,
  'gcs_immutable_readback':'PASS','gcs_cleanup':'PASS',
  'postgres_temp_write_readback':'PASS','postgres_persistent_rows':0,
  'owner_requests_created':0,'llm_calls':0,'canonical_publication':False}))
"""


def run_once():
    path=f"{ROOT}/jobs/{JOB}"
    job=cloud(path)
    task=job["template"]["template"]
    if job.get("reconciling") or job.get("labels",{}).get("janus-git-sha")!=RELEASE_SHA:
        raise RuntimeError("ceo_release_not_pinned")
    if task.get("serviceAccount") != (
        "intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com"
    ) or task.get("maxRetries",0)!=0:
        raise RuntimeError("ceo_identity_or_retry_drift")
    execution_fence()
    operation=cloud(path+":run",{
      "overrides":{"taskCount":1,"timeout":"240s",
          "containerOverrides":[{"name":"ceo","args":["-c",PROBE_CODE]}]}
    },"POST")
    name=operation.get("name","")
    if not name.startswith(ROOT+"/operations/"):
        raise RuntimeError("technical_acceptance_operation_unknown")
    end=time.monotonic()+350
    while time.monotonic()<end:
        op=cloud(name)
        if op.get("done"):
            if op.get("error"):
                raise RuntimeError("technical_acceptance_execution_failed_no_retry")
            execution=op.get("response",{}).get("name","")
            if not execution.startswith(path+"/executions/"):
                raise RuntimeError("technical_acceptance_execution_unknown")
            state=cloud(execution)
            if not terminal(state) or state.get("succeededCount")!=1 or state.get("failedCount",0):
                raise RuntimeError("technical_acceptance_worker_failed_no_retry")
            return {"status":"PASS","execution":execution,"source_sha":RELEASE_SHA,
                "synthetic_roles":5,"live_pg_transactional_temp":True,
                "live_gcs_isolated_immutable_readback":True,
                "canonical_write":False,"real_owner_data":False,"model_calls":0}
        time.sleep(3)
    raise RuntimeError("technical_acceptance_terminal_unknown_no_retry")


if __name__=="__main__":
    print(json.dumps(run_once(),sort_keys=True))
