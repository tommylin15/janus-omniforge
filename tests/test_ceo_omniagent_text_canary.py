"""Bounded single-call live canary contract; no mocked result can prove live Gemini."""
import importlib.util
from pathlib import Path
import sys
import pytest

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"scripts/gcp"))
spec=importlib.util.spec_from_file_location("ceo_omniagent_text_canary",root/"scripts/gcp/ceo_omniagent_text_canary.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_real_canary_compiles_single_model_call_and_no_ledger_access():
    code=mod.TEST_CODE
    compile(code,"ceo_gateway_synthetic_live_test","exec")
    assert code.count("route.invoke(")==1
    assert "ProviderRouter.from_environment" in code
    assert "validated_role_artifact_hashes" in code
    assert "ceo.v1" in code and "insufficient_data" in code
    assert "psycopg" not in code and "INSERT INTO" not in code
    assert "retry" not in code.lower().split("route.invoke(")[1].split("print(")[0]
    assert "Authorization" not in code
    assert "canonical_publication':False" in code

def test_runner_only_dispatches_once_with_pinned_image(monkeypatch):
    path=f"{mod.ROOT}/jobs/{mod.JOB}"
    calls=[]
    j={"labels":{"janus-git-sha":"b63bf350213fa7c3933724fa38006d8ab7b8033f"},
       "template":{"template":{"serviceAccount":f"intelligence-mart@{mod.PROJECT}.iam.gserviceaccount.com",
                               "maxRetries":0,"containers":[{"name":"ceo","env":[
                                   {"name":"MART_CEO_GEMINI_VIA_OMNIAGENT","value":"true"},
                                   {"name":"MART_CEO_GEMINI_ONLY","value":"true"},
                                   {"name":"MART_OMNI_GATEWAY_URL","value":"https://gemini-p0v-b03e5f55---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app"}]}]}}}
    def cloud(target,body=None,method=None):
        calls.append((target,body,method))
        if target==path:return j
        if target.endswith(":run"):return {"name":mod.ROOT+"/operations/canary"}
        if target.endswith("/operations/canary"):return {"done":True,"response":{"name":path+"/executions/canary"}}
        return {"succeededCount":1,"failedCount":0}
    monkeypatch.setattr(mod,"cloud",cloud)
    monkeypatch.setattr(mod,"execution_fence",lambda:None)
    monkeypatch.setattr(mod,"terminal",lambda _:True)
    result=mod.run_once()
    assert result["status"]=="PASS" and result["model_calls"]==1
    assert result["persisted_ceo_report"] is False
    ops=[body for t,body,m in calls if t.endswith(":run")]
    assert len(ops)==1 and ops[0]["overrides"]["containerOverrides"]==[{"name":"ceo","args":["-c",mod.TEST_CODE]}]
    assert "image" not in str(ops[0]).lower()

def test_drift_refuses_any_provider_call(monkeypatch):
    calls=[]
    monkeypatch.setattr(mod,"cloud",lambda path,body=None,method=None:(
        calls.append((path,method)) or {"labels":{"janus-git-sha":"bad"},
          "template":{"template":{"serviceAccount":f"intelligence-mart@{mod.PROJECT}.iam.gserviceaccount.com",
                                  "containers":[]}}}))
    with pytest.raises(RuntimeError,match="not_pinned"):
        mod.run_once()
    assert not any(t.endswith(":run") for t,_ in calls)
