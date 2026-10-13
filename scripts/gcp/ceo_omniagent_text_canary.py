"""One real, non-personal Flash-Lite roundtrip through the deployed Janus CEO Router.

No database access, no canonical publication, one provider attempt, no blind retry.
Requires an explicit GitHub request and the same shared dev release lease.
"""
from __future__ import annotations
import json
import time
from ceo_worker_deploy import execution_fence
from ghcr_jobs_rollout import ROOT, cloud, terminal

PROJECT="gen-lang-client-0593591102"
JOB="janus-ceo-analysis"
TEST_CODE = """
import json
from uuid import UUID,uuid4
from intelligence_mart import provider_routing as routing
hashes=['sha256:' + str(i)*64 for i in range(5)]
sample={'schema_version':'1.0.0','role':'ceo','stance':'insufficient_data',
 'thesis':None, 'missing_information':['資料不足'], 'confidence':0.0,
 'evidence_ids':[], 'supporting_roles':[], 'opposing_roles':[],
 'contradictions':[], 'bull_case':[], 'bear_case':[], 'principal_risks':[],
 'watch_items':[], 'change_since_previous_analysis':[],
 'validated_role_artifact_hashes':hashes}
prompt='This is a non-personal Gemini Gateway JSON contract test, not a market forecast. Return EXACTLY this JSON object without markdown or other text: '+json.dumps(sample,ensure_ascii=False,separators=(',',':'))
if len(prompt.encode('utf-8'))>8192: raise RuntimeError('canary_prompt_exceeds_limit')
# A separate minimal input byte-size check is not a substitute for a full Fact Pack.
route=routing.ProviderRouter.from_environment({}, bounded_manual=True)
if route.routing['effective_providers'] != ['gemini'] or route.routing.get('execution_policy')!='omniagent_gateway_gemini_lite_only':
    raise RuntimeError('gateway_route_not_enabled')
provider=route.providers['gemini']
provider.bind_context(owner_id=str(UUID('00000000-0000-4000-8000-000000000001')),request_id=str(uuid4()))
original=routing._prompt
try:
    routing._prompt=lambda *args:prompt
    result=route.invoke('ceo',{'validated_role_artifact_hashes':hashes})
finally:
    routing._prompt=original
if result.status!='succeeded' or not isinstance(result.output,dict):
    # Do not leak raw provider text/prompt or fabricate success.
    reason=result.reason if result.reason in {'invalid_structured_output','gateway_contract_mismatch',
      'gateway_identity_unavailable','gateway_endpoint_unapproved','gateway_prompt_too_large',
      'provider_unavailable','quota','timeout','unsupported_parameter'} else 'model_reply_not_validated'
    raise RuntimeError('ceo_gateway_live_canary_'+reason)
if result.output.get('validated_role_artifact_hashes')!=hashes or result.output.get('role')!='ceo':
    raise RuntimeError('ceo_gateway_live_canary_hashes_invalid')
print(json.dumps({'kind':'janus_ceo_gateway_synthetic_json_canary','status':'PASS',
                  'schema':'ceo.v1','model':result.model,'transport':result.transport,
                  'model_calls':1,'database_writes':0,'canonical_publication':False}))
"""

def run_once():
    path=f"{ROOT}/jobs/{JOB}"
    job=cloud(path)
    task=job["template"]["template"]
    if job.get("reconciling") or task["serviceAccount"] != f"intelligence-mart@{PROJECT}.iam.gserviceaccount.com":
        raise RuntimeError("not_approved_existing_ceo_job")
    if job.get("labels",{}).get("janus-git-sha")!="b63bf350213fa7c3933724fa38006d8ab7b8033f":
        raise RuntimeError("ceo_image_not_pinned_to_tested_sha")
    if task.get("maxRetries",0)!=0:
        raise RuntimeError("job_retry_policy_unapproved")
    env={e["name"]:e.get("value") for e in task["containers"][0].get("env",[]) if "value" in e}
    if env.get("MART_CEO_GEMINI_VIA_OMNIAGENT")!="true" or env.get("MART_CEO_GEMINI_ONLY")!="true":
        raise RuntimeError("gateway_route_not_deployed")
    if env.get("MART_OMNI_GATEWAY_URL")!="https://gemini-p0v-b03e5f55---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app":
        raise RuntimeError("gateway_candidate_changed")
    execution_fence()
    operation=cloud(path+":run",{
        "overrides":{"taskCount":1,"timeout":"120s",
                     "containerOverrides":[{"name":"ceo","args":["-c",TEST_CODE]}]}
    },"POST")
    name=operation.get("name","")
    if not name.startswith(ROOT+"/operations/"):
        raise RuntimeError("model_canary_operation_missing_no_retry")
    deadline=time.monotonic()+280
    while time.monotonic()<deadline:
        op=cloud(name)
        if op.get("done"):
            if op.get("error"):
                raise RuntimeError("model_canary_execution_failed_no_retry")
            execution=op.get("response",{}).get("name","")
            if not execution.startswith(path+"/executions/"):
                raise RuntimeError("model_canary_execution_unknown")
            result=cloud(execution)
            if not terminal(result) or result.get("succeededCount")!=1 or result.get("failedCount",0):
                raise RuntimeError("model_canary_not_pass_no_retry")
            return {"status":"PASS","execution":execution,"job_sha":job["labels"]["janus-git-sha"],
                    "model_calls":1,"database_writes":0,"persisted_ceo_report":False,"traffic_changes":False}
        time.sleep(3)
    raise RuntimeError("model_canary_terminal_unknown_no_retry")

if __name__=="__main__":
    print(json.dumps(run_once(),sort_keys=True))
