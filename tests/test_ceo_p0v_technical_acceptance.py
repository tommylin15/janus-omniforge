"""Synthetic technical P0-V contract requires zero owner/canonical writes."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/gcp"))
sys.path.insert(0,str(ROOT/"jobs/intelligence-mart"))
sys.path.insert(0,str(ROOT/"tests"))
spec=importlib.util.spec_from_file_location("ceo_p0v_technical_acceptance",ROOT/"scripts/gcp/ceo_p0v_technical_acceptance.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_live_acceptance_script_compiles_and_is_isolated():
    code=mod.PROBE_CODE
    compile(code,"ceo_p0v_live_contract","exec")
    assert "execute_ceo(request,Router(output))" in code
    assert "('hash','evidence','numeric','missing')" in code
    assert "CREATE TEMP TABLE" in code and "ON COMMIT DROP" in code
    assert "UPDATE private.ceo_requests" not in code
    assert "INSERT INTO private.ceo_requests" not in code
    assert "p0v-ceo-technical" in code
    assert "acceptance/p0v-ceo-technical/" in code
    assert "store.delete(name)" in code
    assert "GEMINI_API_KEY" not in code
    assert "CEO_REQUEST_ID" not in code
    assert "INSERT INTO private." not in code
    assert "'llm_calls':0" in code


def test_canary_job_only_args_override_and_source_sha(monkeypatch):
    path=f"{mod.ROOT}/jobs/{mod.JOB}"
    calls=[]
    def fake_cloud(target,body=None,method=None):
        calls.append((target,body,method))
        if target==path:return {
            "labels":{"janus-git-sha":mod.RELEASE_SHA},
            "template":{"template":{"serviceAccount":
                "intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com",
                "maxRetries":0}}}
        if target.endswith(":run"):return {"name":mod.ROOT+"/operations/check"}
        if target.endswith("/operations/check"):
            return {"done":True,"response":{"name":path+"/executions/check"}}
        return {"succeededCount":1,"failedCount":0}
    monkeypatch.setattr(mod,"cloud",fake_cloud)
    monkeypatch.setattr(mod,"execution_fence",lambda:None)
    monkeypatch.setattr(mod,"terminal",lambda v:True)
    value=mod.run_once()
    assert value["status"]=="PASS" and value["canonical_write"] is False
    run=[body for name,body,method in calls if name.endswith(":run")]
    assert len(run)==1 and run[0]=={"overrides":{"taskCount":1,"timeout":"240s",
      "containerOverrides":[{"name":"ceo","args":["-c",mod.PROBE_CODE]}]}}
    assert "image" not in str(run[0]).lower()


def test_wrong_job_image_never_triggers_execution(monkeypatch):
    calls=[]
    def cloud(target,body=None,method=None):
        calls.append(target)
        if target.endswith(":run"):pytest.fail("unverified CEO job must not run")
        return {"labels":{"janus-git-sha":"bad"},"template":{"template":{}}}
    monkeypatch.setattr(mod,"cloud",cloud)
    with pytest.raises(RuntimeError,match="ceo_release_not_pinned"):
        mod.run_once()
    assert not any(s.endswith(":run") for s in calls)


def test_gateway_bounded_full_synthetic_factpack_does_not_mint_when_too_big(monkeypatch):
    """Measure actual _prompt expansion, not just a toy text canary."""
    from intelligence_mart import provider_routing as routing
    from packages.analysis_product import numeric_facts
    import test_analysis_product
    baseline=routing.json.loads(routing.json.dumps(
        __import__("packages.analysis_product",fromlist=["baseline_projection"]).baseline_projection(
            *test_analysis_product.product_inputs())))
    payload={
      "fact_pack":baseline, "validated_specialists":baseline["specialists"],
      "validated_role_artifact_hashes":[x["output_hash"] for x in baseline["specialists"]],
      "canonical_numbers_are_read_only":True,"numeric_facts":numeric_facts(baseline),
      "numeric_claim_policy":"Only supplied fact key=value bindings",
      "previous_analysis":None,
    }
    prompt=routing._prompt("ceo",payload)
    count=len(prompt.encode("utf-8"))
    print(f"p0v_representative_factpack_prompt_bytes={count};gateway_limit=8192")
    monkeypatch.setenv("MART_CEO_GEMINI_ONLY","true")
    monkeypatch.setenv("MART_CEO_GEMINI_VIA_OMNIAGENT","true")
    if count>8192:
        provider=routing.OmniGatewayGeminiProvider(
          gateway_url="https://gemini-p0v-b03e5f55---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app",
          opener=lambda *a,**k: pytest.fail("oversized input must not reach gateway"),
          token_provider=lambda: pytest.fail("oversized input must not mint credentials"))
        provider.bind_context(owner_id="00000000-0000-4000-8000-000000000001",
                              request_id="00000000-0000-4000-8000-000000000002")
        result=provider.invoke("ceo",payload)
        assert result.reason=="gateway_prompt_too_large"
        assert result.output is None and result.status=="failed"
    else:
        assert count<=8192
