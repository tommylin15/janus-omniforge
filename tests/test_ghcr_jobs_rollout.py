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


@pytest.mark.parametrize("message,code", [
    ("PERMISSION_DENIED: blocked", "job_update_permission_denied"),
    ("Not Found in registry", "job_update_image_or_job_not_found"),
    ("Failed to import image manifest", "job_update_registry_import_failed"),
    ("Invalid container configuration", "job_update_invalid_configuration"),
    ("opaque failure", "job_update_unknown_rejection"),
])
def test_job_update_failure_is_classified_without_gcloud_sensitive_output(message, code):
    from types import SimpleNamespace
    data = sample()
    target = "ghcr.io/tommylin15/new@sha256:" + "b" * 64
    with patch.object(rollout, "writers"), patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "fence"), patch.object(rollout, "job", return_value=data), \
         patch.object(rollout, "subprocess") as sub, \
         patch.object(rollout, "checked_image") as readback:
        sub.run.return_value = SimpleNamespace(returncode=1, stderr=message+" private=secret", stdout="")
        with pytest.raises(RuntimeError, match=code) as exc:
            rollout.update("janus-private-pipeline", target, rollout.fingerprint(data))
    assert "private=secret" not in str(exc.value)
    readback.assert_not_called()


def test_forward_only_authorization_must_be_explicit_before_release_commands():
    sha = "a" * 40
    request = {"intent": "approved-dev-ghcr-jobs-rollout", "approved": True,
               "scope": "existing-dev-four-jobs", "sha": sha, "release_run": "123",
               "rollback_mode": "user_authorized_forward_only",
               "accept_no_old_image_rollback": False}

    def load(path, *args, **kwargs):
        if str(path).endswith("ghcr-candidate-request.json"):
            return json.dumps({"sha": sha})
        return json.dumps(request)

    with patch.object(rollout.Path, "read_text", load), patch.object(rollout, "command") as command:
        with pytest.raises(ValueError, match="forward_only_user_authorization_missing"):
            rollout.run("123", Path("/tmp/test-rollout-receipt.json"))
    command.assert_not_called()


def test_forward_only_preflight_no_mutation_restores_scheduler_without_old_image_read():
    old = "us-central1-docker.pkg.dev/test/image@sha256:" + "b" * 64
    names = rollout.REQUIRED_JOBS
    snapshots = {name: {"image": old, "configuration_hash": rollout.fingerprint(sample())}
                 for name in names}
    original = sample()
    original["template"]["template"]["containers"][0]["image"] = old
    snapshots = {name: {"image": old, "configuration_hash": rollout.fingerprint(original)}
                 for name in names}
    journal = {"rollback_mode": "user_authorized_forward_only", "scheduler_hash": "f",
               "snapshots": snapshots,
               "targets": {name: "ghcr.io/tommylin15/latest@sha256:" + "c" * 64
                           for name, _ in rollout.JOB_COMPONENT}, "canaries": []}
    with patch.object(rollout, "command"), patch.object(rollout, "fence"), \
         patch.object(rollout, "job", return_value=original), \
         patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "scheduler_fingerprint", return_value="f"), \
         patch.object(rollout, "set_scheduler") as resume, \
         patch.object(rollout, "update") as update:
        rollout.recover(journal, lambda: None)
    assert journal["phase"] == "RESTORED_NO_MUTATION"
    resume.assert_called_once_with("resume", "ENABLED")
    update.assert_not_called()


def test_partial_forward_only_change_keeps_scheduler_fenced():
    names = [name for name, _ in rollout.JOB_COMPONENT]
    old = "us-central1-docker.pkg.dev/test/image@sha256:" + "a" * 64
    new = "ghcr.io/tommylin15/new@sha256:" + "b" * 64
    original = sample()
    original["template"]["template"]["containers"][0]["image"] = old
    changed = deepcopy(original)
    changed["template"]["template"]["containers"][0]["image"] = new
    current = {name: deepcopy(original) for name in rollout.REQUIRED_JOBS}
    current[names[0]] = changed
    journal = {"rollback_mode": "user_authorized_forward_only", "scheduler_hash": "f",
               "snapshots": {name: {"image": old, "configuration_hash": rollout.fingerprint(original)}
                             for name in rollout.REQUIRED_JOBS},
               "targets": {name: new for name in names}, "canaries": []}
    def check(name, ref, h):
        if rollout.image(current[name]) != ref:
            raise ValueError("image_or_configuration_drift")

    with patch.object(rollout, "command"), patch.object(rollout, "fence"), \
         patch.object(rollout, "job", side_effect=lambda name: current[name]), \
         patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "scheduler_fingerprint", return_value="f"), \
         patch.object(rollout, "checked_image", side_effect=check), \
         patch.object(rollout, "set_scheduler") as resume, \
         patch.object(rollout, "update") as update:
        with pytest.raises(ValueError, match="image_or_configuration_drift"):
            rollout.recover(journal, lambda: None)
    resume.assert_not_called()
    update.assert_not_called()


def test_forward_only_recovers_only_after_eight_real_canaries():
    names = [name for name, _ in rollout.JOB_COMPONENT]
    old = "us-central1-docker.pkg.dev/test/image@sha256:" + "a" * 64
    new = "ghcr.io/tommylin15/new@sha256:" + "b" * 64
    original = sample()
    original["template"]["template"]["containers"][0]["image"] = old
    updated = deepcopy(original)
    updated["template"]["template"]["containers"][0]["image"] = new
    current = {name: updated for name in names}
    current["janus-research-big-move-500"] = original
    journal = {"rollback_mode": "user_authorized_forward_only", "scheduler_hash": "f",
               "snapshots": {name: {"image": old, "configuration_hash": rollout.fingerprint(original)}
                             for name in rollout.REQUIRED_JOBS},
               "targets": {name: new for name in names},
               "canaries": [{"job": name, "result": "PASS", "execution": name + str(i)}
                            for name in names for i in range(2)]}
    with patch.object(rollout, "command"), patch.object(rollout, "fence"), \
         patch.object(rollout, "job", side_effect=lambda name: current[name]), \
         patch.object(rollout, "checked_image") as checked, \
         patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "scheduler_fingerprint", return_value="f"), \
         patch.object(rollout, "set_scheduler") as resume, \
         patch.object(rollout, "update") as update:
        rollout.recover(journal, lambda: None)
    assert checked.call_count == 4
    assert journal["phase"] == "RESTORED_FORWARD_ONLY"
    resume.assert_called_once_with("resume", "ENABLED")
    update.assert_not_called()


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


def _reversible_request(sha="b" * 40, prior="a" * 40):
    return {
        "rollback_mode": "reversible_ghcr",
        "accept_no_old_image_rollback": False,
        "baseline_source_sha": prior,
        "rollback_images": {
            name: f"ghcr.io/tommylin15/janus-{component}@sha256:" + "c" * 64
            for name, component in rollout.JOB_COMPONENT
        },
    }


def test_reversible_ghcr_baseline_accepts_only_explicit_four_immutable_refs():
    request = _reversible_request()
    assert rollout.release_rollback_mode(request, "b" * 40) == "reversible_ghcr"
    for patch_data in (
        {"accept_no_old_image_rollback": True},
        {"baseline_source_sha": "bad"},
        {"baseline_source_sha": "b" * 40},
        {"rollback_mode": "auto"},
    ):
        with pytest.raises(ValueError):
            rollout.release_rollback_mode({**request, **patch_data}, "b" * 40)
    missing = deepcopy(request)
    missing["rollback_images"].pop(next(iter(missing["rollback_images"])))
    with pytest.raises(ValueError):
        rollout.release_rollback_mode(missing, "b" * 40)
    wrong_component = deepcopy(request)
    name = next(iter(wrong_component["rollback_images"]))
    wrong_component["rollback_images"][name] = "ghcr.io/other/image@sha256:" + "c" * 64
    with pytest.raises(ValueError):
        rollout.release_rollback_mode(wrong_component, "b" * 40)


def test_old_forward_only_waiver_cannot_be_reused_for_new_release():
    request = {"rollback_mode": "user_authorized_forward_only",
               "accept_no_old_image_rollback": True}
    previous = "fbcc5f58a2fa31f2f36dc4c82702fb62910c7361"
    assert rollout.release_rollback_mode(request, previous) == "user_authorized_forward_only"
    with pytest.raises(ValueError, match="forward_only_waiver_not_valid_for_new_source"):
        rollout.release_rollback_mode(request, "b" * 40)


def test_reversible_baseline_checks_actual_current_images_and_registry():
    request = _reversible_request()
    previous = {}
    for name, ref in request["rollback_images"].items():
        old = sample()
        old["template"]["template"]["containers"][0]["image"] = ref
        previous[name] = old
    responses = [
        json.dumps({"Digest": ref.rsplit("@", 1)[-1],
                    "Labels": {"org.opencontainers.image.revision": request["baseline_source_sha"]}})
        for ref in request["rollback_images"].values()
    ]
    with patch.object(rollout, "command", side_effect=responses) as command:
        rollout.verify_reversible_baseline(request, previous)
    assert command.call_count == len(rollout.JOB_COMPONENT)
    assert all("--no-creds" in call.args[0] for call in command.call_args_list)
    previous["janus-private-pipeline"]["template"]["template"]["containers"][0]["image"] = "wrong"
    with patch.object(rollout, "command") as command:
        with pytest.raises(ValueError, match="rollback_baseline_runtime_drift"):
            rollout.verify_reversible_baseline(request, previous)
    command.assert_not_called()


def test_missing_public_rollback_digest_never_satisfies_gate():
    request = _reversible_request()
    previous = {}
    for name, ref in request["rollback_images"].items():
        old = sample()
        old["template"]["template"]["containers"][0]["image"] = ref
        previous[name] = old
    with patch.object(rollout, "command", return_value='{"Digest": "sha256:wrong", "Labels": {}}'):
        with pytest.raises(ValueError, match="rollback_baseline_registry_unverified"):
            rollout.verify_reversible_baseline(request, previous)
