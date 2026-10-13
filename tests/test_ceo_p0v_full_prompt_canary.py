"""P0-V 32KiB full CEO prompt canary is non-canonical, one-shot and SHA-fenced."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/gcp"))
spec=importlib.util.spec_from_file_location("ceo_p0v_full_prompt_canary",ROOT/"scripts/gcp/ceo_p0v_full_prompt_canary.py")
canary=importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)


def test_full_synthetic_ceo_uses_production_prompt_and_validator():
    c=canary.CODE
    compile(c,"janus_p0v_complete_ceo_smoke","exec")
    assert "_prompt('ceo',role_input)" in c
    assert "execute_ceo(request,router)" in c
    assert c.count("execute_ceo(request,router)") == 1
    assert "29500 <= prompt_bytes <= OMNI_MARKET_PROMPT_MAX_BYTES" in c
    assert "len(baseline['specialists'])==5" in c
    assert "report_persisted':False" in c or "report_persisted':False" in canary.__dict__.__repr__() or "report_persisted':False" in Path(canary.__file__).read_text()
    assert "CEO_REQUEST_ID" not in c and "INSERT INTO" not in c
    assert "psycopg" not in c and "raw_text" not in c
    assert "routing._prompt=" not in c and "_prompt=lambda" not in c
    assert "test_analysis_product" not in c


def test_full_prompt_run_dispatches_once_only_for_source_pinned_job(monkeypatch):
    path=f"{canary.ROOT}/jobs/{canary.JOB}"
    digest="a"*40
    calls=[]
    values={
      path:{"labels":{"janus-git-sha":digest},"reconciling":False,
        "template":{"template":{"maxRetries":0,"serviceAccount":canary.SOURCE,
            "containers":[{"env":[
              {"name":"MART_OMNI_GATEWAY_URL","value":canary.MARKET_URL},
              {"name":"MART_CEO_GEMINI_ONLY","value":"true"},
              {"name":"MART_CEO_GEMINI_VIA_OMNIAGENT","value":"true"}]}]}}},
      canary.ROOT+"/operations/check":{"done":True,"response":{"name":path+"/executions/check"}},
      path+"/executions/check":{"succeededCount":1,"failedCount":0}
    }
    def cloud(url,body=None,method=None):
        calls.append((url,body,method))
        return {"name":canary.ROOT+"/operations/check"} if url.endswith(":run") else values[url]
    monkeypatch.setattr(canary,"cloud",cloud)
    monkeypatch.setattr(canary,"execution_fence",lambda:None)
    monkeypatch.setattr(canary,"terminal",lambda x:True)
    result=canary.run_once(digest)
    assert result["status"]=="PASS" and result["report_persisted"] is False
    dispatched=[b for u,b,m in calls if u.endswith(":run")]
    assert len(dispatched)==1
    assert dispatched[0]=={"overrides":{"taskCount":1,"timeout":"180s",
                                "containerOverrides":[{"name":"ceo","args":["-c",canary.CODE]}]}}


def test_full_prompt_unknown_sha_or_candidate_mismatch_never_dispatches(monkeypatch):
    with pytest.raises(ValueError,match="SHA"):
        canary.run_once("bad")
    called=[]
    def cloud(path,body=None,method=None):
        called.append(path)
        if path.endswith(":run"):pytest.fail("unexpected model call")
        return {"labels":{"janus-git-sha":"b"*40},
                "template":{"template":{"serviceAccount":canary.SOURCE,
                    "containers":[{"env":[]}],"maxRetries":0}}}
    monkeypatch.setattr(canary,"cloud",cloud)
    with pytest.raises(RuntimeError,match="ceo_job_sha_mismatch"):
        canary.run_once("a"*40)
    assert not any(x.endswith(":run") for x in called)
