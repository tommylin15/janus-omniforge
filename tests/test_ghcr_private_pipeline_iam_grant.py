from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_private_pipeline_iam_grant as grant


def request():
    return {"intent": "grant-existing-private-pipeline-runtime-actas", "approved": True,
            "scope": "runtime-service-account-only", "project": grant.EXPECTED_PROJECT,
            "job": grant.TARGET_JOB, "role": grant.ROLE}


def test_rejects_unauthorized_scope():
    with patch.object(Path, "read_text", return_value=json.dumps(
            {**request(), "scope": "project-wide"})):
        with pytest.raises(ValueError, match="iam_grant_request_invalid"):
            grant.require_request()


def test_actual_target_is_derived_from_live_job_not_request():
    runtime = "private@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    ci = "ci@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    with patch.object(grant.rollout, "job", return_value={
            "template": {"template": {"serviceAccount": runtime}}}), \
         patch.dict(grant.os.environ, {"GCP_CI_SERVICE_ACCOUNT": ci}):
        assert grant.identity() == (runtime, ci)


def test_rejects_cross_project_target():
    with patch.object(grant.rollout, "job", return_value={
            "template": {"template": {"serviceAccount": "outside@other.iam.gserviceaccount.com"}}}), \
         patch.dict(grant.os.environ, {
             "GCP_CI_SERVICE_ACCOUNT": "ci@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"}):
        with pytest.raises(ValueError, match="runtime_service_account_outside_project"):
            grant.identity()


def test_scoped_policy_command_never_updates_project_policy():
    runtime = "private@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    ci = "ci@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    with patch.object(grant.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        grant.apply(runtime, ci)
    argv = run.call_args.args[0]
    assert argv[:4] == ["gcloud", "iam", "service-accounts", "add-iam-policy-binding"]
    assert argv[4] == runtime
    assert "--member=serviceAccount:" + ci in argv
    assert "--role=roles/iam.serviceAccountUser" in argv
    assert "--condition=None" in argv
    assert "projects add-iam-policy-binding" not in " ".join(argv)


def test_denied_policy_editor_never_mutates(tmp_path):
    output = tmp_path / "receipt.json"
    runtime = "private@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    ci = "ci@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    with patch.object(grant, "require_request"), \
         patch.object(grant, "identity", return_value=(runtime, ci)), \
         patch.object(grant, "permissions", side_effect=[set(), set()]), \
         patch.object(grant, "apply") as apply:
        code = grant.run(output)
    assert code == 78
    assert json.loads(output.read_text())["reason"] == "policy_editor_permission_missing"
    apply.assert_not_called()


def test_success_write_and_live_actas_readback(tmp_path):
    output = tmp_path / "receipt.json"
    runtime = "private@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    ci = "ci@" + grant.EXPECTED_PROJECT + ".iam.gserviceaccount.com"
    with patch.object(grant, "require_request"), \
         patch.object(grant, "identity", return_value=(runtime, ci)), \
         patch.object(grant, "permissions", side_effect=[
             set(), {"iam.serviceAccounts.getIamPolicy", "iam.serviceAccounts.setIamPolicy"},
             {"iam.serviceAccounts.actAs"}]), \
         patch.object(grant, "apply") as apply:
        code = grant.run(output)
    assert code == 0
    apply.assert_called_once_with(runtime, ci)
    assert json.loads(output.read_text())["result"] == "PASS"


def test_workflow_trigger_is_a_single_explicit_request():
    source = (ROOT / ".github/workflows/ghcr-private-pipeline-iam-grant.yml").read_text()
    assert "'ops/ghcr-private-pipeline-iam-grant-request.json'" in source
    assert "group: janus-dev-runtime-writers" in source
    assert "google-github-actions/auth@v2" in source
    assert "workflow_dispatch:" not in source
