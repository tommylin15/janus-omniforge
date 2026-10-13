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
              {"name":"MART_OMNI_GATEWAY_URL","value":canary.PREVIOUS_URL},
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
                                "containerOverrides":[{"name":"ceo","args":["-c",canary.CODE],
                                  "env":[{"name":"MART_OMNI_GATEWAY_URL","value":canary.MARKET_URL}]}]}}
    assert canary.MARKET_URL != canary.PREVIOUS_URL
    assert result["job_updated"] is False and result["one_execution_gateway_override"] is True


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


def test_full_fixture_offline_executes_real_prompt_and_ceo_validator():
    """Runs the real 32KiB fixture and CEO/PIT guards before any model is called."""
    from types import SimpleNamespace
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))
    # Stop immediately before network/identity-capable provider construction.
    assert canary.CODE.count("router=ProviderRouter.from_environment") == 1
    offline = canary.CODE.split("router=ProviderRouter.from_environment")[0]
    context = {}
    exec(compile(offline, "p0v_full_prompt_offline", "exec"), context)
    baseline = context["baseline"]
    request = context["request"]
    hashes = context["hashes"]
    prompt_bytes = context["prompt_bytes"]
    assert len(baseline["specialists"]) == 5
    assert all(isinstance(role["metrics"], dict) for role in baseline["specialists"])
    assert 29500 <= prompt_bytes <= 32768
    assert request["baseline_hash"] == baseline["content_hash"]

    class NoNetworkRouter:
        def invoke(self, role, fact_pack):
            assert role == "ceo"
            assert fact_pack["numeric_facts"] == {}
            assert len(fact_pack["validated_specialists"]) == 5
            assert fact_pack["validated_role_artifact_hashes"] == hashes
            from intelligence_mart.provider_routing import _prompt
            assert len(_prompt(role, fact_pack).encode("utf-8")) == prompt_bytes
            output = {
                "schema_version": "1.0.0", "role": "ceo",
                "stance": "insufficient_data", "thesis": None,
                "missing_information": ["測試來源不足"],
                "confidence": 0.0, "evidence_ids": [],
                "supporting_roles": [], "opposing_roles": [],
                "contradictions": [], "bull_case": [], "bear_case": [],
                "principal_risks": [], "watch_items": [],
                "change_since_previous_analysis": [],
                "validated_role_artifact_hashes": hashes,
            }
            return SimpleNamespace(
                status="succeeded", output=output, attempts=[],
                routing={"routing_hash": "local-only",
                         "execution_providers": ["gemini"],
                         "providers": ["gemini"],
                         "execution_policy": "omniagent_gateway_gemini_lite_only"},
                provider="gemini", model="gemini-3.5-flash-lite")

    state, report, audit, reason = context["execute_ceo"](request, NoNetworkRouter())
    assert state == "PARTIAL" and reason is None
    assert report["output"]["validated_role_artifact_hashes"] == hashes
    assert audit["route"] == ["gemini"]
    assert report["publication_authority"] is False


def test_full_prompt_gateway_override_is_one_request_only():
    import ast
    c = canary.CODE
    assert "MART_OMNI_GATEWAY_URL" not in c
    assert "INSERT INTO" not in c
    assert "run_ceo_request" not in c
    assert "POST" not in c
    assert canary.MARKET_URL.startswith("https://p0v-market2048-227a0bdc---")
    assert canary.PREVIOUS_URL.startswith("https://ghcr-965b05542a35---")
    ast.parse(c)
