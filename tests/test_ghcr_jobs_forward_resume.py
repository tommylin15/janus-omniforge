from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_jobs_forward_resume as resume


def sample():
    return {"template": {"taskCount": 1, "parallelism": 1, "template": {
        "serviceAccount": "job@example.iam.gserviceaccount.com",
        "maxRetries": 0, "containers": [{
            "name": "worker", "image": "ghcr.io/image@sha256:" + "a" * 64,
            "env": [{"name": "SECRET", "valueSource": {"secretKeyRef": {"secret": "real"}}}],
            "command": ["python"]}]}}}


def test_runtime_contract_excludes_only_image_not_secret_config():
    a = sample()
    b = deepcopy(a)
    b["template"]["template"]["containers"][0]["image"] = "ghcr.io/other@sha256:" + "b"*64
    resume.assert_contract(a, b)
    b["template"]["template"]["containers"][0]["env"][0]["valueSource"]["secretKeyRef"]["secret"] = "changed"
    with pytest.raises(ValueError, match="runtime_contract_drift"):
        resume.assert_contract(a, b)


def test_request_rejects_unapproved_resumption():
    with patch.object(Path, "read_text", return_value='{"approved": false}'):
        with pytest.raises(ValueError, match="recovery_request_invalid"):
            resume.request_data()


def test_lease_recovery_checks_original_owner_is_finished():
    req = {"failed_run": "37913564122", "failed_attempt": 1,
           "failed_run_sha": "2b4607481e41e2789a6c05aee0e085272e244a5e"}
    active = {"headSha":req["failed_run_sha"], "status":"in_progress",
              "conclusion":None, "workflowName":"Janus GHCR controlled Jobs rollout"}
    with patch.object(resume.rollout, "command", return_value=json.dumps(active)) as call:
        with pytest.raises(ValueError, match="original_lease_owner_not_finished"):
            resume.owner_lease(req)
    call.assert_called_once()


def test_failed_lease_guard_never_resumes_scheduler(tmp_path):
    report=tmp_path/"receipt.json"
    with (patch.object(resume, "request_data", return_value={}),
          patch.object(resume.rollout, "acceptance"),
          patch.object(resume, "owner_lease", side_effect=ValueError("lease_busy")),
          patch.object(resume.rollout, "set_scheduler") as sched):
        assert resume.run(report)==78
    assert json.loads(report.read_text())["phase"]=="RECOVERY_REQUIRED"
    sched.assert_not_called()


def test_one_time_recovery_workflow_scope_and_fence():
    src=(ROOT/".github/workflows/ghcr-jobs-forward-resume.yml").read_text()
    assert "'ops/ghcr-jobs-forward-resume-request.json'" in src
    assert "group: janus-dev-runtime-writers" in src
    assert "cancel-in-progress: false" in src
    assert "ghcr_jobs_forward_resume.py" in src
    assert "id-token: write" in src
