"""Non-billable regression for the narrow CEO runtime IAM canary."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
spec = importlib.util.spec_from_file_location("ceo_omniagent_iam_probe", ROOT / "scripts/gcp/ceo_omniagent_iam_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_probe_is_no_llm_and_no_database_path():
    code = probe.PROBE_CODE
    assert "data=b'{}'" in code
    assert "'invalid_request'" in code
    assert "target_audience=audience, include_email=True" in code
    assert "omniagent-codex-market-client@" in code
    assert "gemini-p0v-b03e5f55---" in code
    assert "generateContent" not in code
    assert "GEMINI_API_KEY" not in code
    assert "CEO_REQUEST_ID" not in code
    assert "psycopg" not in code


def test_real_job_probe_overrides_only_args_no_image_or_secrets(monkeypatch):
    calls = []
    path = f"{probe.ROOT}/jobs/{probe.JOB}"
    values = {
        path: {"template": {"template": {"serviceAccount": probe.SOURCE, "maxRetries": 0}},
               "reconciling": False},
        probe.ROOT + "/operations/probe": {"done": True, "response": {"name": path + "/executions/probe"}},
        path + "/executions/probe": {"succeededCount": 1},
    }
    def cloud(target, body=None, method=None):
        calls.append((target, body, method))
        if target.endswith(":run"):
            return {"name": probe.ROOT + "/operations/probe"}
        return values[target]
    monkeypatch.setattr(probe, "cloud", cloud)
    monkeypatch.setattr(probe, "execution_fence", lambda: None)
    monkeypatch.setattr(probe, "terminal", lambda result: True)
    result = probe.execute_once()
    assert result["status"] == "PASS" and result["model_calls"] == 0
    assert result["job_updated"] is False and result["database_writes"] == 0
    runs = [(body, method) for target, body, method in calls if target.endswith(":run")]
    assert len(runs) == 1 and runs[0][1] == "POST"
    body = runs[0][0]
    assert list(body) == ["overrides"]
    assert body["overrides"]["containerOverrides"] == [{"name":"ceo","args":["-c",probe.PROBE_CODE]}]
    assert "image" not in str(body).lower()
    assert "env" not in body["overrides"]["containerOverrides"][0]


def test_probe_refuses_unexpected_identity_and_wont_issue_job(monkeypatch):
    def cloud(target, body=None, method=None):
        if target.endswith(":run"):
            pytest.fail("runtime with wrong identity must never execute")
        return {"template": {"template": {"serviceAccount":"unexpected", "maxRetries":0}}}
    monkeypatch.setattr(probe,"cloud",cloud)
    with pytest.raises(RuntimeError,match="unexpected_ceo_runtime_identity"):
        probe.execute_once()


def test_probe_ambiguous_terminal_fails_closed(monkeypatch):
    path = f"{probe.ROOT}/jobs/{probe.JOB}"
    def cloud(target, body=None, method=None):
        if target == path:
            return {"template":{"template":{"serviceAccount":probe.SOURCE,"maxRetries":0}}}
        if target.endswith(":run"):
            return {"name":probe.ROOT+"/operations/probe"}
        if target.endswith("/operations/probe"):
            return {"done":True,"response":{"name":path+"/executions/probe"}}
        return {"succeededCount":0,"failedCount":1}
    monkeypatch.setattr(probe,"cloud",cloud)
    monkeypatch.setattr(probe,"execution_fence",lambda:None)
    monkeypatch.setattr(probe,"terminal",lambda result:True)
    with pytest.raises(RuntimeError,match="iam_probe_worker_not_pass"):
        probe.execute_once()
