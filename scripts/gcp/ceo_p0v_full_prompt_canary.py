"""One real complete synthetic CEO Fact Pack via deployed market-mart Gateway.

No owner data, no persistent database write, no provider retry or fallback.
Unknown operation terminal is not retried; only read back the same execution.
"""
from __future__ import annotations
import argparse
import json
import time
from ceo_worker_deploy import execution_fence
from ghcr_jobs_rollout import ROOT, cloud, terminal

JOB="janus-ceo-analysis"
MARKET_URL="https://ghcr-965b05542a35---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app"
SOURCE="intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com"

CODE = """
import json
from uuid import uuid4
from packages.analysis_product import content_hash, numeric_facts
from intelligence_mart.product_runtime import execute_ceo
from intelligence_mart.provider_routing import ProviderRouter, _prompt, OMNI_MARKET_PROMPT_MAX_BYTES

roles=('fundamental','valuation','quant','risk','event')
hashes=['sha256:'+str(i+1)*64 for i in range(5)]
baseline={
  'schema_version':'analysis-product.v1',
  'analysis_as_of':'2026-10-13','symbol':'P0VTEST','execution_id':str(uuid4()),
  'model_quality':'NOT_VERIFIED','publication_authority':False,
  'specialists':[{'role':role,'status':'partial','baseline_status':'unavailable',
                  'output_hash':hashes[i],'evidence_ids':[],
                  'missing_data':['synthetic_missing_no_publication']}
                  for i,role in enumerate(roles)],
  'synthetic_missing_source_notes':[]
}
# Exercise the actual complete CEO _prompt, not a monkeypatched/toy prompt.
policy=('Prefer narrative prose without numbers. Any number in claim text or missing_information '
        'must appear as an exact numeric_facts key=value binding. Do not repeat numeric dates, horizons or stock codes '
        'outside a binding. The canonical UI already displays formatted numbers.')
def make_input():
    baseline['content_hash']=content_hash({k:v for k,v in baseline.items() if k!='content_hash'})
    return {'fact_pack':baseline,'validated_specialists':baseline['specialists'],
      'validated_role_artifact_hashes':hashes,'canonical_numbers_are_read_only':True,
      'previous_analysis':None,'numeric_facts':numeric_facts(baseline),
      'numeric_claim_policy':policy}
for i in range(380):
    role_input=make_input()
    prompt_bytes=len(_prompt('ceo',role_input).encode('utf-8'))
    if 29500 <= prompt_bytes <= 32768:
        break
    if prompt_bytes>32768:
        raise RuntimeError('synthetic_factpack_exceeded_32k_limit')
    baseline['synthetic_missing_source_notes'].append(
        '缺值資料；合成測試，不是市場事實，不得引用、補數值或發佈。'+'缺值' * 27)
else:
    raise RuntimeError('synthetic_factpack_size_not_reached')
assert len(baseline['specialists'])==5
assert 29500 <= prompt_bytes <= OMNI_MARKET_PROMPT_MAX_BYTES
request_id=str(uuid4())
request={'request_id':request_id,'symbol':'P0VTEST','profile_id':'default',
         'profile_version':1,'baseline_json':baseline,'baseline_hash':baseline['content_hash']}
router=ProviderRouter.from_environment({}, bounded_manual=True)
assert router.routing.get('execution_policy')=='omniagent_gateway_gemini_lite_only'
assert router.routing.get('effective_providers')==['gemini']
provider=router.providers['gemini']
provider.bind_context(owner_id='00000000-0000-4000-8000-000000000001',request_id=request_id)
state, report, audit, reason=execute_ceo(request,router)
# No raw Gemini text, evidence body, bearer or arbitrary error string in output.
if state!='PARTIAL' or report is None or reason is not None:
    safe=reason if reason in {'invalid_structured_output','gateway_prompt_too_large',
        'provider_unavailable','gateway_contract_mismatch','output_validation_failed',
        'quota','auth_required','transport_error'} else 'unexpected_rejection'
    raise RuntimeError('full_ceo_json_not_accepted_'+safe)
assert report['output']['validated_role_artifact_hashes']==hashes
assert report['publication_authority'] is False
assert report['output']['stance']=='insufficient_data'
assert not report['output']['evidence_ids']
assert audit['route']==['gemini']
assert len(audit['attempts'])==1
assert audit['attempts'][0]['transport']=='omniagent_gateway'
print(json.dumps({'kind':'janus_p0v_real_full_prompt_synthetic_ceo',
                  'status':'PASS','prompt_bytes':prompt_bytes,'gateway_limit_bytes':32768,
                  'specialist_roles':5,'ceo_validator':'PASS','real_provider_calls':1,
                  'model':'gemini-3.5-flash-lite','canonical_writes':0,
                  'owner_requests_created':0,'report_persisted':False}))
"""

def run_once(sha):
    import re
    if not re.fullmatch("[0-9a-f]{40}",sha):
        raise ValueError("verified source SHA required")
    path=f"{ROOT}/jobs/{JOB}"
    job=cloud(path)
    task=job["template"]["template"]
    if job.get("reconciling") or job.get("labels",{}).get("janus-git-sha")!=sha:
        raise RuntimeError("ceo_job_sha_mismatch")
    if task.get("serviceAccount")!=SOURCE or task.get("maxRetries",0)!=0:
        raise RuntimeError("ceo_runtime_identity_or_retry_drift")
    env={e['name']:e.get('value') for e in task['containers'][0].get('env',[]) if 'value' in e}
    if env.get("MART_OMNI_GATEWAY_URL")!=MARKET_URL or env.get("MART_CEO_GEMINI_ONLY")!="true" or env.get("MART_CEO_GEMINI_VIA_OMNIAGENT")!="true":
        raise RuntimeError("ceo_gateway_url_or_execution_policy_drift")
    execution_fence()
    operation=cloud(path+":run",{"overrides":{"taskCount":1,"timeout":"180s",
      "containerOverrides":[{"name":"ceo","args":["-c",CODE]}]}},"POST")
    name=operation.get('name','')
    if not name.startswith(ROOT+'/operations/'):
        raise RuntimeError("ceo_full_prompt_operation_unknown_no_retry")
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        op=cloud(name)
        if op.get('done'):
            if op.get('error'):
                raise RuntimeError("ceo_full_prompt_operation_failed_no_retry")
            execution=op.get("response",{}).get("name","")
            if not execution.startswith(path+'/executions/'):
                raise RuntimeError("ceo_full_prompt_execution_unknown")
            state=cloud(execution)
            if not terminal(state) or state.get("succeededCount")!=1 or state.get("failedCount",0):
                raise RuntimeError("ceo_full_prompt_worker_failed_no_retry")
            return {'status':'PASS','execution':execution,'source_sha':sha,
                    'gateway':MARKET_URL,'model_calls':1,'canonical_writes':0,
                    'owner_requests_created':0,'report_persisted':False,
                    'traffic_changed':False}
        time.sleep(3)
    raise RuntimeError("ceo_full_prompt_terminal_unknown_no_retry")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--release-sha',required=True)
    args=parser.parse_args()
    print(json.dumps(run_once(args.release_sha),sort_keys=True))
