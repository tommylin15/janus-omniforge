"""GCP v2 reconciliation is a strict, secret-free execution safety signal."""
import runpy
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/"scripts/gcp/ghcr_execution_v2_readback.py"))
classify=m["classify"]
EXEC="janus-private-pipeline-7rkz7"
NAME=f"projects/gen-lang-client-0593591102/locations/us-central1/jobs/janus-private-pipeline/executions/{EXEC}"


def row(**kwargs):
    return {"name":NAME,**{"reconciling":False,"conditions":[{"type":"Completed","state":"CONDITION_FAILED"}]},**kwargs}


def test_proto_json_omitted_default_false_is_readable_but_not_terminal():
    # Cloud Run REST v2 omits false boolean properties in JSON by default.
    payload=row()
    del payload["reconciling"]
    result=classify(EXEC,payload)
    assert result["v2_readback"]=="READABLE"
    assert result["reconciling"] is False
    assert result["terminal_confirmed"] is False


def test_v2_missing_completion_is_not_terminal_regardless_of_no_tasks():
    r=classify(EXEC,row(runningCount=0,taskCount=1))
    assert r["v2_readback"]=="READABLE"
    assert r["start_observed"] is False
    assert r["completion_observed"] is False
    assert r["terminal_confirmed"] is False
    assert r["running_count"]==0


def test_v2_completed_failed_execution_is_terminal_but_not_called_success():
    r=classify(EXEC,row(completionTime="2026-09-25T00:00:00Z",runningCount=0))
    assert r["terminal_confirmed"] is True
    assert r["condition_states"]==[{"type":"Completed","state":"CONDITION_FAILED"}]
    assert "successful" not in r


def test_v2_completion_while_reconciling_cannot_be_accepted():
    r=classify(EXEC,row(completionTime="2026-09-25T00:00:00Z",reconciling=True))
    assert r["terminal_confirmed"] is False


@pytest.mark.parametrize("change",[
    {"name":"projects/foreign/locations/us-central1/jobs/janus-private-pipeline/executions/janus-private-pipeline-7rkz7"},
    {"job":"janus-private-pipeline-other"},
    {"reconciling":None},
    {"conditions":None},
    {"runningCount":True},
    {"conditions":[{"type":"Completed","state":"not a valid enum!"}]},
])
def test_mismatched_schema_blocks_without_leaking_payload(change):
    d=row(**{"annotations":{"owner_email":"private@example.invalid"},
             "template":{"env":[{"value":"SECRET"}]}})
    d.update(change)
    r=classify(EXEC,d)
    assert r["v2_readback"]=="UNKNOWN_OR_BLOCKED"
    assert r["terminal_confirmed"] is False
    assert "SECRET" not in str(r)
    assert "private@example.invalid" not in str(r)


def test_wrong_job_execution_is_not_accepted():
    r=classify("janus-other-7rkz7",row(completionTime="2026-10-08T00:00:00Z"))
    assert r["v2_readback"]=="UNKNOWN_OR_BLOCKED"


def test_workflow_never_cancels_or_deletes_and_runs_v2_readback():
    s=(ROOT/".github/workflows/ghcr-stale-executions-audit.yml").read_text()
    assert "ghcr_execution_v2_readback.py" in s
    assert "tests/test_ghcr_execution_v2_readback.py" in s
    assert '"authorize_job_promotion": False' in (ROOT/"scripts/gcp/ghcr_execution_v2_readback.py").read_text()
    assert "gcloud run jobs executions cancel" not in s
    assert "gcloud run jobs executions delete" not in s
    assert "gcloud run jobs execute" not in s
    assert "ghcr_release_lease.py release" not in s
