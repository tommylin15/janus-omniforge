import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_reversible_baseline as baseline


def _service(ready="True", observed=5):
    return {"metadata": {"generation": 5}, "status": {
        "observedGeneration": observed,
        "latestReadyRevisionName": "janus-api-00451-cuw",
        "conditions": [{"type": "Ready", "status": ready},
                       {"type": "RoutesReady", "status": ready}]}}


def test_ready_requires_reconciled_service_and_revision():
    revision = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    baseline.ready(_service(), revision, "janus-api-00451-cuw")
    with pytest.raises(ValueError):
        baseline.ready(_service(observed=4), revision, "janus-api-00451-cuw")
    with pytest.raises(ValueError):
        baseline.ready(_service(ready="False"), revision, "janus-api-00451-cuw")
    with pytest.raises(ValueError):
        baseline.ready(_service(), {"status": {"conditions":[]}}, "janus-api-00451-cuw")


def test_no_gcp_or_scheduling_writes_when_lease_is_present(tmp_path):
    p=tmp_path/"receipt.json"
    with (patch.object(baseline,"validated_request",return_value={"source_sha": "a"*40}),
          patch.object(baseline,"command",return_value=json.dumps({"status": "PRESENT"})) as cmd,
          patch.object(baseline.jobs,"set_scheduler") as schedule,
          patch.object(baseline.jobs,"update") as update):
        assert baseline.inspect(p)==78
    assert json.loads(p.read_text())["gcp_writes"] == 0
    assert cmd.call_count == 1
    schedule.assert_not_called()
    update.assert_not_called()


def test_readonly_workflow_never_has_deploy_write_or_scheduler_ops():
    text = (ROOT/".github/workflows/ghcr-reversible-baseline-dev.yml").read_text()
    assert "ghcr_reversible_baseline.py" in text
    assert "ghcr-reversible-baseline-request.json" in text
    for forbidden in ("gcloud run deploy", "gcloud run jobs update",
                      "scheduler jobs pause", "scheduler jobs resume"):
        assert forbidden not in text
