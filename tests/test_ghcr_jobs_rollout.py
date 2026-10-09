from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_jobs_rollout as rollout


def sample():
    return {"template": {"template": {"containers": [{"image": "ghcr.io/example@sha256:" + "a" * 64,
            "env": [{"name": "SECRET_REFERENCE", "value": "never-export"}],
            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}}}], "serviceAccount": "existing"}},
            "labels": {"app": "janus"}, "annotations": {}}


def test_fingerprint_ignores_only_image_and_client_metadata():
    before = sample()
    changed = deepcopy(before)
    changed["template"]["template"]["containers"][0]["image"] = "different"
    changed["annotations"]["run.googleapis.com/client-name"] = "gcloud"
    assert rollout.fingerprint(before) == rollout.fingerprint(changed)
    changed["template"]["template"]["containers"][0]["env"][0]["value"] = "altered"
    assert rollout.fingerprint(before) != rollout.fingerprint(changed)


@pytest.mark.parametrize("state,running,reconciling,reason,expected", [
    ("CONDITION_SUCCEEDED", 0, False, None, True),
    ("CONDITION_FAILED", 0, False, None, True),
    ("CONDITION_PENDING", 0, False, None, False),
    ("CONDITION_SUCCEEDED", 1, False, None, False),
    ("CONDITION_SUCCEEDED", 0, True, None, False),
    ("CONDITION_FAILED", 0, False, "CANCELLING", False),
])
def test_execution_fence_never_treats_unknown_or_running_as_terminal(state, running, reconciling, reason, expected):
    assert rollout.terminal({"runningCount": running, "reconciling": reconciling,
                            "conditions": [{"type": "Completed", "state": state, "executionReason": reason}]}) is expected


def test_fence_checks_every_page_and_all_jobs():
    complete = {"conditions": [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]}
    pages = [{"executions": [complete], "nextPageToken": "next"},
             {"executions": [{"runningCount": 1}]}]
    with patch.object(rollout, "cloud", side_effect=pages) as cloud:
        with pytest.raises(ValueError, match="execution_not_terminal"):
            rollout.fence()
    assert "pageToken=next" in cloud.call_args.args[0]


def test_pending_legacy_cloud_build_blocks_jobs_rollout():
    commands = []

    def fake_command(args):
        commands.append(args)
        if args[:3] == ["gcloud", "builds", "triggers"]:
            return '[{"disabled": true}]'
        if args[:3] == ["gcloud", "builds", "list"]:
            return '[{"id": "queued-or-pending-build"}]'
        raise AssertionError("Unexpected command after a blocked writer")

    with patch.object(rollout, "command", side_effect=fake_command):
        with pytest.raises(ValueError, match="legacy_writer_unfenced"):
            rollout.writers()
    assert "--filter=status=QUEUED OR status=WORKING OR status=PENDING" in commands[1]


def test_job_rollout_preflight_requires_update_and_run_with_overrides_on_every_job():
    targets = {name for name, _ in rollout.JOB_COMPONENT}
    seen = []

    def check_permissions(path, body=None, method=None):
        seen.append((path, body, method))
        return {"permissions": body["permissions"]}

    with patch.object(rollout, "cloud", side_effect=check_permissions):
        rollout.job_update_permissions()
    assert len(seen) == len(rollout.REQUIRED_JOBS)
    for path, body, method in seen:
        assert path.endswith(":testIamPermissions")
        name = path.rsplit("/", 1)[-1].removesuffix(":testIamPermissions")
        expected = {"run.jobs.get"}
        if name in targets:
            expected |= {"run.jobs.update", "run.jobs.run", "run.jobs.runWithOverrides"}
        assert set(body["permissions"]) == expected
        assert method == "POST"


def test_missing_canary_override_permission_blocks_before_mutation():
    no_override = {"permissions": ["run.jobs.get", "run.jobs.update", "run.jobs.run"]}
    with (
        patch.object(rollout, "cloud", return_value=no_override),
        patch.object(rollout, "set_scheduler") as scheduler,
        patch.object(rollout, "update") as update,
    ):
        with pytest.raises(ValueError, match="job_rollout_iam_missing"):
            rollout.job_update_permissions()
    scheduler.assert_not_called()
    update.assert_not_called()


def test_unknown_canary_keeps_scheduler_paused_and_images_fenced():
    journal = {"snapshots": {}, "phase": "RECOVERY_REQUIRED"}
    with patch.object(rollout, "command"), patch.object(rollout, "fence", side_effect=ValueError("unknown")), \
         patch.object(rollout, "set_scheduler") as scheduler, patch.object(rollout, "update") as update:
        with pytest.raises(ValueError):
            rollout.recover(journal, lambda: None)
    scheduler.assert_not_called()
    update.assert_not_called()


def test_recovery_restores_reverse_order_and_verifies_before_resuming():
    names = [name for name, _ in rollout.JOB_COMPONENT]
    journal = {"snapshots": {name: {"image": "old", "configuration_hash": "hash"} for name in names},
               "scheduler_hash": rollout.scheduler_fingerprint({"state": "PAUSED"})}
    events = []
    with patch.object(rollout, "command"), patch.object(rollout, "fence"), \
         patch.object(rollout, "job", return_value={}), patch.object(rollout, "image", return_value="new"), \
         patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "update", side_effect=lambda name, *_: events.append(("restore", name))), \
         patch.object(rollout, "checked_image", side_effect=lambda name, *_: events.append(("verify", name))), \
         patch.object(rollout, "set_scheduler", side_effect=lambda *_: events.append(("resume", None))):
        rollout.recover(journal, lambda: None)
    assert [name for action, name in events if action == "restore"] == list(reversed(names))
    assert events[-1] == ("resume", None)
    assert journal["phase"] == "RESTORED"


def test_non_mutating_preflight_failure_is_not_recovered_twice():
    assert "PREFLIGHT_BLOCKED_NO_MUTATION" in (
        ROOT / "scripts/gcp/ghcr_jobs_rollout.py").read_text()
    journal = {"phase": "PREFLIGHT_BLOCKED_NO_MUTATION"}
    assert journal["phase"] in {"PASS", "RESTORED", "PREFLIGHT_BLOCKED_NO_MUTATION"}


def test_pending_owner_acceptance_blocks_before_any_mutation():
    with patch.object(rollout.Path, "read_text", return_value=json.dumps({"result": "PENDING"})), \
         patch.object(rollout, "command") as command:
        with pytest.raises(ValueError, match="owner_acceptance_not_verified"):
            rollout.acceptance("a" * 40)
    command.assert_not_called()


def test_canary_preserves_entrypoint_and_limits_execution_without_private_output():
    data = sample()
    data["etag"] = "etag"
    operation = {"name": rollout.ROOT + "/operations/test", "done": True,
                 "response": {"name": "execution", "succeededCount": 1,
                              "conditions": [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]}}
    with patch.object(rollout, "checked_image", return_value=data), patch.object(rollout, "writers"), \
         patch.object(rollout, "fence"), patch.object(rollout, "cloud", return_value=operation) as cloud:
        journal = {"operations": [], "canaries": []}
        rollout.canary("janus-intelligence-mart", "image", "hash", journal, lambda: None)
    payload = cloud.call_args.args[1]
    assert payload["overrides"]["taskCount"] == 1
    assert payload["overrides"]["timeout"] == "300s"
    assert payload["overrides"]["containerOverrides"][0]["args"] == ["python", "-m", "intelligence_mart.__main__"]
    assert "never-export" not in json.dumps(journal)


def test_workflow_is_manual_shared_lease_and_has_failure_recovery():
    source = (ROOT / ".github/workflows/ghcr-jobs-rollout-dev.yml").read_text()
    assert "workflow_dispatch:" in source and "push:" in source
    assert "'ops/ghcr-jobs-rollout-request.json'" in source
    assert '.intent == "approved-dev-ghcr-jobs-rollout"' in source
    assert '.approved == true' in source and '.sha == $sha' in source
    assert 'branches: [main]' in source
    assert "RELEASE_RUN=" in source and "GITHUB_ENV" in source
    assert "group: janus-dev-runtime-writers" in source and "cancel-in-progress: false" in source
    assert "--recover" in source and "failure() || cancelled()" in source
    assert "/tmp/ghcr-jobs-rollout.json" in source
    assert "ghcr-full-job-snapshots" not in source
