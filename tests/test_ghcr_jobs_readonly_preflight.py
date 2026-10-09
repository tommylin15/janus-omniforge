from unittest.mock import patch
import pytest

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_jobs_readonly_preflight as preflight


def test_no_mutations_and_all_live_gates_present():
    with patch.object(preflight.rollout, "legacy_writers") as writer, \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "ENABLED"}), \
         patch.object(preflight.rollout, "job") as job, \
         patch.object(preflight.rollout, "fence") as fence, \
         patch.object(preflight.rollout, "job_update_permissions") as iam, \
         patch.object(preflight, "rollback_images_readable") as rollback_images, \
         patch.object(preflight, "runtime_identity_permissions") as identities, \
         patch.object(preflight.rollout, "set_scheduler") as set_sched, \
         patch.object(preflight.rollout, "update") as update:
        evidence = preflight.scan()
    assert evidence["status"] == "READONLY_PREFLIGHT_PASS"
    assert evidence["gcp_writes"] == 0
    assert all(v["status"] == "PASS" for v in evidence["gates"].values())
    assert job.call_count == len(preflight.rollout.REQUIRED_JOBS)
    writer.assert_called_once()
    fence.assert_called_once()
    iam.assert_called_once()
    rollback_images.assert_called_once()
    identities.assert_called_once()
    set_sched.assert_not_called()
    update.assert_not_called()


def test_unknown_cloud_run_or_iam_is_blocked_not_misreported_pass():
    with patch.object(preflight.rollout, "legacy_writers", side_effect=RuntimeError("token-secret")), \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "ENABLED"}), \
         patch.object(preflight.rollout, "job"), \
         patch.object(preflight.rollout, "fence"), \
         patch.object(preflight.rollout, "job_update_permissions", side_effect=ValueError("missing")), \
         patch.object(preflight, "rollback_images_readable"), \
         patch.object(preflight, "runtime_identity_permissions"):
        evidence = preflight.scan()
    assert evidence["status"] == "BLOCKED"
    assert evidence["gates"]["legacy_cloud_build_not_competing"]["status"] == "BLOCKED"
    assert evidence["gates"]["jobs_update_and_canary_iam"]["status"] == "BLOCKED"
    assert "token-secret" not in str(evidence)
    assert "missing" not in str(evidence)


def test_unexpected_scheduler_state_blocks_readonly_preflight():
    with patch.object(preflight.rollout, "legacy_writers"), \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(preflight.rollout, "job"), \
         patch.object(preflight.rollout, "fence"), \
         patch.object(preflight.rollout, "job_update_permissions"), \
         patch.object(preflight, "rollback_images_readable"), \
         patch.object(preflight, "runtime_identity_permissions"):
        evidence = preflight.scan()
    assert evidence["status"] == "BLOCKED"
    assert evidence["gates"]["scheduler_expected_enabled_baseline"]["status"] == "BLOCKED"


def test_workflow_is_explicit_preflight_and_has_no_mutating_release_step():
    source = (ROOT / ".github/workflows/ghcr-jobs-readonly-preflight.yml").read_text()
    assert "workflow_dispatch:" in source
    assert "'ops/ghcr-jobs-preflight-request.json'" in source
    assert "ghcr_jobs_readonly_preflight.py" in source
    assert "ghcr_jobs_rollout.py --release-run" not in source
    assert "id-token: write" in source


def test_rollback_image_diagnostics_never_expose_registry_error_or_secret():
    from types import SimpleNamespace
    original = preflight.rollout.REQUIRED_JOBS
    with patch.object(preflight.rollout, "REQUIRED_JOBS", original[:1]), \
         patch.object(preflight.rollout, "job", return_value={"template": {"template": {"containers": [
             {"image": "us-central1-docker.pkg.dev/example/repo/image@sha256:" + "a" * 64}]}}}), \
         patch.object(preflight.subprocess, "run", return_value=SimpleNamespace(
             returncode=1, stdout="", stderr="PERMISSION_DENIED token=do-not-disclose")) as cli:
        outcome = {}
        preflight.check("rollback", preflight.rollback_images_readable, outcome)
    assert outcome["rollback"]["reason_code"] == "ROLLBACK_IMAGE_READ_IAM"
    assert outcome["rollback"]["job"] == original[0]
    assert "do-not-disclose" not in str(outcome)
    assert cli.call_args.args[0][0:4] == ["gcloud", "artifacts", "docker", "images"]


def test_all_rollback_images_require_nonempty_registry_digest_readback():
    from types import SimpleNamespace
    only = preflight.rollout.REQUIRED_JOBS[:1]
    with patch.object(preflight.rollout, "REQUIRED_JOBS", only), \
         patch.object(preflight.rollout, "job", return_value={"template": {"template": {"containers": [
             {"image": "ghcr.io/test/image@sha256:" + "a" * 64}]}}}), \
         patch.object(preflight.subprocess, "run", return_value=SimpleNamespace(
             returncode=0, stdout="", stderr="")):
        with pytest.raises(preflight.RollbackImageBlocked, match="ROLLBACK_IMAGE_NO_DIGEST_READBACK"):
            preflight.rollback_images_readable()


def test_runtime_identity_actas_probe_reports_only_job_names_not_identity_or_token():
    from types import SimpleNamespace
    import io
    one = preflight.rollout.JOB_COMPONENT[:1]
    job = {"template": {"template": {"serviceAccount": "some-identity@a.iam.gserviceaccount.com"}}}
    class FakeResponse:
        def __enter__(self): return io.BytesIO(b'{"permissions":[]}')
        def __exit__(self, *_): return False
    with patch.object(preflight.rollout, "JOB_COMPONENT", one), \
         patch.object(preflight.rollout, "job", return_value=job), \
         patch.object(preflight.rollout, "command", return_value="secret-token"), \
         patch.object(preflight, "urlopen", return_value=FakeResponse()):
        outcome = {}
        preflight.check("identities", preflight.runtime_identity_permissions, outcome)
    assert outcome["identities"]["reason_code"] == "runtime_identity_actas_missing_or_unknown"
    assert outcome["identities"]["jobs"] == [one[0][0]]
    assert "some-identity" not in str(outcome) and "secret-token" not in str(outcome)
