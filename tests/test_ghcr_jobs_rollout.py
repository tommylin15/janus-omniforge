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


@pytest.mark.parametrize('operation,names', [
    ('release', ['release-tests', 'release-flutter', 'release-verify'] +
     [f'release-publish ({part})' for part in ('api', 'ingestion-core', 'intelligence-mart', 'private-pipeline')]),
    ('auth-boundary', ['auth-boundary']),
    ('candidate', ['candidate']),
    ('jobs-rollout', ['jobs-rollout']),
])
def test_unified_provenance_requires_real_operation_jobs(monkeypatch, operation, names):
    metadata = dict(status='completed', conclusion='success',
                    workflowName='Janus GHCR operations', headSha='a'*40)
    identity = dict(path='.github/workflows/ghcr-dev.yml', head_sha='a'*40, head_branch='main')
    jobs = [dict(name=name, status='completed', conclusion='success') for name in names]
    monkeypatch.setattr(rollout, 'command', lambda args: json.dumps(identity if args[1] == 'api' else {'jobs': jobs}))
    assert rollout.successful_operation(metadata, '123', 'legacy', operation)
    jobs[-1]['conclusion'] = 'skipped'
    assert not rollout.successful_operation(metadata, '123', 'legacy', operation)
    jobs[-1]['conclusion'] = 'success'
    identity['path'] = '.github/workflows/unrelated.yml'
    assert not rollout.successful_operation(metadata, '123', 'legacy', operation)
    identity['path'] = '.github/workflows/ghcr-dev.yml'
    identity['head_sha'] = 'b'*40
    assert not rollout.successful_operation(metadata, '123', 'legacy', operation)


def test_verify_success_cannot_be_used_as_a_full_release(monkeypatch):
    metadata = dict(status='completed', conclusion='success',
                    workflowName='Janus GHCR operations', headSha='a'*40)
    identity = dict(path='.github/workflows/ghcr-dev.yml', head_sha='a'*40, head_branch='main')
    jobs = [dict(name=name, status='completed', conclusion='success')
            for name in ('release-tests', 'release-flutter')]
    monkeypatch.setattr(rollout, 'command', lambda args: json.dumps(identity if args[1] == 'api' else {'jobs': jobs}))
    assert not rollout.successful_operation(metadata, '123', 'legacy', 'release')




def test_transient_control_get_retries_but_dispatch_does_not(monkeypatch):
    from urllib.error import HTTPError
    import io
    from contextlib import closing
    seen=[]
    sleeps=[]
    monkeypatch.setattr(rollout,'command',lambda args:'token')
    monkeypatch.setattr(rollout.time,'sleep',sleeps.append)
    def read(req,timeout):
        seen.append(req.get_method())
        if len(seen)==1: raise HTTPError(req.full_url,500,'transient',None,None)
        return closing(io.BytesIO(b'{"done":true}'))
    monkeypatch.setattr(rollout,'urlopen',read)
    assert rollout.cloud('projects/p/operations/o')=={'done':True}
    assert seen==['GET','GET'] and sleeps==[2]
    def failed(req,timeout):
        seen.append(req.get_method())
        raise HTTPError(req.full_url,500,'ambiguous',None,None)
    seen.clear();sleeps.clear()
    monkeypatch.setattr(rollout,'urlopen',failed)
    with pytest.raises(RuntimeError,match='cloud_control_http_500'):
        rollout.cloud('projects/p/jobs/j:run',{},'POST')
    assert seen==['POST'] and sleeps==[]
    seen.clear()
    with pytest.raises(RuntimeError):rollout.cloud('projects/p/operations/o')
    assert seen==['GET','GET','GET'] and sleeps==[2,4]


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
            return '[{"name": "janus-dev-v2", "disabled": true}]'
        if args[:3] == ["gcloud", "builds", "list"]:
            return '[{"id": "queued-or-pending-build"}]'
        raise AssertionError("Unexpected command after a blocked writer")

    with patch.object(rollout, "command", side_effect=fake_command):
        with pytest.raises(ValueError, match="legacy_writer_unfenced"):
            rollout.writers()
    assert "--filter=status=QUEUED OR status=WORKING OR status=PENDING" in commands[1]


@pytest.mark.parametrize('triggers,builds,allowed', [
    ([], [], True),
    ([{'name': 'janus-dev-v2', 'disabled': True}], [], True),
    ([], [{'id': 'active'}], False),
    ([{'name': 'janus-dev-v2', 'disabled': False}], [], False),
    ([{'name': 'unknown-writer', 'disabled': True}], [], False),
    ([{'name': 'janus-dev-v2', 'disabled': 'true'}], [], False),
])
def test_legacy_writer_fence_accepts_confirmed_absence_but_rejects_unknown_writers(triggers, builds, allowed):
    with patch.object(rollout, 'command', side_effect=[json.dumps(triggers), json.dumps(builds)]):
        if allowed:
            rollout.legacy_writers()
        else:
            with pytest.raises(ValueError, match='legacy_writer_unfenced'):
                rollout.legacy_writers()


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
    # Recovery uses the bounded waiter, not a one-shot fence that can strand
    # Scheduler while a failed canary is still terminating.


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
               "auth_boundary_run": "321",
               "rollback_mode": "user_authorized_forward_only",
               "accept_no_old_image_rollback": False}

    def load(path, *args, **kwargs):
        if str(path).endswith("ghcr-candidate-request.json"):
            return json.dumps({"sha": sha})
        return json.dumps(request)

    with patch.object(rollout.Path, "read_text", load), patch.object(rollout, "command") as command:
        with pytest.raises(ValueError, match="forward_only_waiver_not_valid_for_new_source"):
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
         patch.object(rollout, "legacy_writers"), \
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


def test_automatic_oauth_gate_requires_same_source_successful_live_boundary():
    source = "a" * 40
    request_head = "b" * 40
    observed = []
    metadata = {"status": "completed", "conclusion": "success",
                "workflowName": "GHCR candidate OAuth and private-boundary probe",
                "headSha": request_head}
    request = {"intent": "verify-ghcr-candidate-boundary", "scope": "read-only",
               "no_gcp_mutation": True, "sha": source}
    def command(args):
        observed.append(args)
        if args[:3] == ["gh", "run", "view"]:
            return json.dumps(metadata)
        if args[:2] == ["git", "show"]:
            return json.dumps(request)
        if args[:3] == ["git", "merge-base", "--is-ancestor"]:
            return ""
        raise AssertionError("unexpected command")
    with patch.object(rollout.Path, "read_text", return_value=json.dumps(request)), \
         patch.object(rollout, "command", side_effect=command):
        receipt = rollout.automated_oauth_acceptance(source, "12345")
        assert receipt["status"] == "AUTOMATED_OAUTH_NEGATIVE_AND_METADATA_PASS"
        assert receipt["human_google_login"] == "NOT_REQUIRED_NOT_VERIFIED"
        assert ["git", "show", request_head + ":ops/ghcr-candidate-boundary-request.json"] in observed
        for changed in ({"conclusion": "failure"}, {"status": "in_progress"},
                        {"workflowName": "wrong-workflow"}, {"headSha": "not-a-sha"}):
            with patch.object(rollout, "command", side_effect=lambda args: json.dumps({**metadata, **changed})):
                with pytest.raises(ValueError, match="automated_oauth_boundary_not_verified"):
                    rollout.automated_oauth_acceptance(source, "12345")
        with patch.object(rollout, "command",
                          side_effect=lambda args: json.dumps({**request, "sha": "c" * 40})
                          if args[:2] == ["git", "show"] else json.dumps(metadata)):
            with pytest.raises(ValueError, match="automated_oauth_run_source_mismatch"):
                rollout.automated_oauth_acceptance(source, "12345")

    with patch.object(rollout, "command") as run:
        with pytest.raises(ValueError, match="automated_oauth_run_required"):
            rollout.automated_oauth_acceptance(source, "")
    run.assert_not_called()
    with patch.object(rollout.Path, "read_text",
                      return_value=json.dumps({**request, "sha": "c" * 40})), \
         patch.object(rollout, "command") as run:
        with pytest.raises(ValueError, match="automated_oauth_candidate_sha_mismatch"):
            rollout.automated_oauth_acceptance(source, "12345")
    run.assert_not_called()


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
    source = (ROOT / ".github/workflows/archive/ghcr-jobs-rollout-dev.yml").read_text()
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
        "rollback_config_hashes": {
            name: rollout.fingerprint(sample()) for name, _ in rollout.JOB_COMPONENT
        },
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
    without_hash = deepcopy(request)
    without_hash.pop("rollback_config_hashes")
    with pytest.raises(ValueError, match="reversible_ghcr_config_fingerprints_missing"):
        rollout.release_rollback_mode(without_hash, "b" * 40)
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


def test_reversible_ghcr_config_drift_blocks_even_when_registry_digest_matches():
    request = _reversible_request()
    previous = {}
    for name, ref in request["rollback_images"].items():
        old = sample()
        old["template"]["template"]["containers"][0]["image"] = ref
        previous[name] = old
    previous["janus-private-pipeline"]["template"]["template"]["containers"][0]["env"][0]["value"] = "drift"
    with patch.object(rollout, "command") as cmd:
        with pytest.raises(ValueError, match="rollback_baseline_config_drift"):
            rollout.verify_reversible_baseline(request, previous)
    cmd.assert_not_called()


def test_nonterminal_execution_does_not_strand_unchanged_original_jobs(monkeypatch):
    original = sample()
    originals = {
        name: {"image": rollout.image(original), "configuration_hash": rollout.fingerprint(original)}
        for name in rollout.REQUIRED_JOBS
    }
    schedule = {"state": "PAUSED", "schedule": "30 * * * *", "timeZone": "Asia/Taipei"}
    journal = {
        "phase": "RECOVERY_REQUIRED", "snapshots": originals,
        "scheduler_hash": rollout.scheduler_fingerprint(schedule),
    }
    saves = []
    with patch.object(rollout, "command"), patch.object(rollout, "legacy_writers"), \
         patch.object(rollout, "job", return_value=original), \
         patch.object(rollout, "scheduler", return_value=schedule), \
         patch.object(rollout, "fence", side_effect=ValueError("execution_not_terminal")) as fence, \
         patch.object(rollout, "set_scheduler") as resume, patch.object(rollout, "update") as update:
        rollout.recover(journal, lambda: saves.append(journal["phase"]))
    fence.assert_not_called()
    update.assert_not_called()
    resume.assert_called_once_with("resume", "ENABLED")
    assert journal["phase"] == "RESTORED_NO_MUTATION" and saves == ["RESTORED_NO_MUTATION"]


def test_partial_image_change_cannot_bypass_terminal_execution_fence():
    original = sample()
    changed = deepcopy(original)
    changed["template"]["template"]["containers"][0]["image"] = "ghcr.io/other@sha256:" + "b" * 64
    journal = {
        "snapshots": {
            name: {"image": rollout.image(original), "configuration_hash": rollout.fingerprint(original)}
            for name in rollout.REQUIRED_JOBS
        },
        "scheduler_hash": rollout.scheduler_fingerprint({"state": "PAUSED"}),
    }
    with patch.object(rollout, "command"), patch.object(rollout, "job", return_value=changed), \
         patch.object(rollout, "wait_for_terminal_executions",
                      side_effect=ValueError("execution_not_terminal")) as bounded_wait, \
         patch.object(rollout, "set_scheduler") as resume:
        with pytest.raises(ValueError, match="execution_not_terminal"):
            rollout.recover(journal, lambda: None)
    bounded_wait.assert_called_once()
    resume.assert_not_called()


def test_unchanged_jobs_do_not_override_drifted_scheduler_config():
    original = sample()
    journal = {
        "snapshots": {
            name: {"image": rollout.image(original), "configuration_hash": rollout.fingerprint(original)}
            for name in rollout.REQUIRED_JOBS
        },
        "scheduler_hash": "wrong-fingerprint",
    }
    with patch.object(rollout, "command"), patch.object(rollout, "job", return_value=original), \
         patch.object(rollout, "legacy_writers"), \
         patch.object(rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(rollout, "set_scheduler") as resume:
        with pytest.raises(ValueError, match="scheduler_configuration_drift"):
            rollout.recover(journal, lambda: None)
    resume.assert_not_called()


def test_failed_preflight_active_execution_does_not_strand_unchanged_scheduler():
    journal = {"phase":"RECOVERY_REQUIRED", "scheduler_hash":"baseline",
               "snapshots":{"janus-ingestion-core":{"image":"original", "configuration_hash":"sha"}}}
    saved=[]
    with patch.object(rollout, "scheduler", return_value={"state":"ENABLED"}), \
         patch.object(rollout, "scheduler_fingerprint", return_value="baseline"), \
         patch.object(rollout, "checked_image") as image, \
         patch.object(rollout, "fence", side_effect=ValueError("execution_not_terminal")) as fence:
        rollout.restore_unmodified_preflight(journal, lambda: saved.append(journal["phase"]))
    fence.assert_not_called()
    image.assert_called_once_with("janus-ingestion-core","original","sha")
    assert journal["phase"] == "PREFLIGHT_BLOCKED_NO_MUTATION" and saved == ["PREFLIGHT_BLOCKED_NO_MUTATION"]


def test_preflight_blocked_if_scheduler_drifted_even_without_job_mutation():
    journal={"scheduler_hash":"original","snapshots":{}}
    with patch.object(rollout,"scheduler",return_value={"state":"ENABLED"}), \
         patch.object(rollout,"scheduler_fingerprint",return_value="different"):
        with pytest.raises(RuntimeError,match="preflight_scheduler_configuration_drift"):
            rollout.restore_unmodified_preflight(journal,lambda:None)
    assert journal.get("phase") is None



def test_bounded_drain_waits_for_active_execution_without_weakening_fence():
    with patch.object(rollout, 'fence', side_effect=[ValueError('execution_not_terminal'), None]) as fence, \
         patch.object(rollout.time, 'sleep') as sleep:
        rollout.wait_for_terminal_executions()
    assert fence.call_count == 2
    sleep.assert_called_once_with(15)
    with patch.object(rollout, 'fence', side_effect=ValueError('execution_not_terminal')):
        with pytest.raises(ValueError, match='execution_not_terminal'):
            rollout.wait_for_terminal_executions(timeout=0)
    with patch.object(rollout, 'fence', side_effect=ValueError('execution_pagination_loop')), \
         patch.object(rollout.time, 'sleep') as sleep:
        with pytest.raises(ValueError, match='execution_pagination_loop'):
            rollout.wait_for_terminal_executions()
        sleep.assert_not_called()


@pytest.mark.parametrize("argv,category", [
    (["gh","run","view","123"],"gh_run"),
    (["gh","api","repos/a/b/actions/runs/1"],"gh_api"),
    (["skopeo","inspect","--no-creds","docker://ghcr.io/demo:sha-test"],"registry_by_tag"),
    (["skopeo","inspect","--no-creds","docker://ghcr.io/demo@sha256:abc"],"registry_by_digest"),
    (["git","show","head:path"],"git_provenance"),
    (["gcloud","scheduler","jobs","list"],"gcloud_readback"),
])
def test_rollout_external_command_failures_are_phase_only_and_do_not_expose_args(argv, category):
    with patch.object(rollout, "_redacted_command", side_effect=RuntimeError("bounded_command_failed")):
        with pytest.raises(RuntimeError, match="^bounded_command_failed_" + category + "$") as exc:
            rollout.command(argv)
    assert all(str(arg) not in str(exc.value) for arg in argv[2:] if len(str(arg)) > 10)


def test_global_lease_diagnostic_is_bounded_redacted_and_never_retries(monkeypatch):
    """Lease acquisition must not be replayed just to disclose a safe reason."""
    from types import SimpleNamespace
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=78, stdout="",
                               stderr='{"status":"BLOCKED","reason":"lease_busy"}')
    monkeypatch.setattr(rollout.subprocess, "run", execute)
    with pytest.raises(RuntimeError, match="^bounded_release_lease_lease_busy$"):
        rollout.command(rollout.LEASE + ["acquire"])
    assert calls == [rollout.LEASE + ["acquire"]]

def test_global_lease_diagnostic_never_reveals_untrusted_stderr(monkeypatch):
    from types import SimpleNamespace
    secret = "private-token-never-log"
    monkeypatch.setattr(rollout.subprocess, "run", lambda *a, **kw:
        SimpleNamespace(returncode=78, stdout="",
                        stderr=secret + ' {"status":"BLOCKED","reason":"invalid@secret"}'))
    with pytest.raises(RuntimeError, match="^bounded_release_lease_unknown$") as exc:
        rollout.command(rollout.LEASE + ["acquire"])
    assert secret not in str(exc.value)


def test_retired_research_execution_fence_requires_both_cloud_run_404s():
    missing = "janus-research-big-move-500"
    seen = []
    def api(path, *args, **kwargs):
        seen.append(path)
        if "/jobs/" + missing in path:
            raise RuntimeError("cloud_control_http_404")
        return {"executions":[]}
    with patch.object(rollout, "cloud", side_effect=api):
        rollout.fence()
    assert seen[-2:] == [
        f"{rollout.ROOT}/jobs/{missing}/executions?pageSize=100",
        f"{rollout.ROOT}/jobs/{missing}",
    ]


def test_retired_research_fence_rejects_inconsistent_presence():
    missing = "janus-research-big-move-500"
    def api(path, *args, **kwargs):
        if path == f"{rollout.ROOT}/jobs/{missing}/executions?pageSize=100":
            raise RuntimeError("cloud_control_http_404")
        if path == f"{rollout.ROOT}/jobs/{missing}":
            return {"name":path}
        return {"executions":[]}
    with patch.object(rollout, "cloud", side_effect=api):
        with pytest.raises(ValueError, match="research_job_execution_listing_drift"):
            rollout.fence()


def test_required_active_job_404_cannot_be_waived():
    def api(path, *args, **kwargs):
        if "/jobs/janus-ingestion-core/executions?" in path:
            raise RuntimeError("cloud_control_http_404")
        return {"executions":[]}
    with patch.object(rollout, "cloud", side_effect=api):
        with pytest.raises(RuntimeError, match="cloud_control_http_404"):
            rollout.fence()


def test_retired_research_is_omitted_from_config_snapshots_and_recovery():
    original=sample()
    def read(name):
        if name=='janus-research-big-move-500':
            raise RuntimeError('cloud_control_http_404')
        return original
    schedule={'state':'PAUSED'}
    with patch.object(rollout,'job',side_effect=read), patch.object(rollout,'cloud',side_effect=RuntimeError('cloud_control_http_404')):
        jobs=rollout.existing_jobs()
        assert set(jobs)=={name for name,_ in rollout.JOB_COMPONENT}
        journal={'snapshots':{name:{'image':rollout.image(data),'configuration_hash':rollout.fingerprint(data)} for name,data in jobs.items()},'scheduler_hash':rollout.scheduler_fingerprint(schedule)}
        with patch.object(rollout,'command'), patch.object(rollout,'legacy_writers'), patch.object(rollout,'scheduler',return_value=schedule), patch.object(rollout,'set_scheduler') as resume:
            rollout.recover(journal,lambda:None)
        resume.assert_called_once_with('resume','ENABLED')
        assert journal['phase']=='RESTORED_NO_MUTATION'
    with patch.object(rollout,'job',side_effect=read), patch.object(rollout,'cloud',return_value={'executions':[{'runningCount':1}]}):
        with pytest.raises(ValueError,match='research_job_execution_listing_drift'):
            rollout.existing_jobs()
    with patch.object(rollout,'job',side_effect=RuntimeError('cloud_control_http_404')):
        with pytest.raises(RuntimeError,match='cloud_control_http_404'):
            rollout.existing_jobs()


def test_retired_research_get_404_and_exact_empty_list_is_safe():
    def read(name):
        if name=='janus-research-big-move-500':
            raise RuntimeError('cloud_control_http_404')
        return sample()
    with patch.object(rollout,'job',side_effect=read), patch.object(rollout,'cloud',return_value={}):
        assert set(rollout.existing_jobs())=={name for name,_ in rollout.JOB_COMPONENT}
    with patch.object(rollout,'job',side_effect=read), patch.object(rollout,'cloud',return_value={'nextPageToken':'next'}):
        with pytest.raises(ValueError,match='research_job_execution_listing_drift'):
            rollout.existing_jobs()


def test_mixed_four_job_rollback_sources_keep_per_job_registry_identity():
    request = _reversible_request()
    request.pop("baseline_source_sha")
    names = [name for name, _ in rollout.JOB_COMPONENT]
    request["rollback_source_shas"] = {name: ("a" if i % 2 == 0 else "d") * 40
                                       for i, name in enumerate(names)}
    assert rollout.release_rollback_mode(request, "b" * 40) == "reversible_ghcr"
    previous = {}
    responses = []
    for name in names:
        old = sample()
        ref = request["rollback_images"][name]
        old["template"]["template"]["containers"][0]["image"] = ref
        previous[name] = old
        responses.append(json.dumps({"Digest": ref.rsplit("@", 1)[-1],
                          "Labels": {"org.opencontainers.image.revision":
                                     request["rollback_source_shas"][name]}}))
    with patch.object(rollout, "command", side_effect=responses):
        rollout.verify_reversible_baseline(request, previous)
    invalid = deepcopy(request)
    invalid["rollback_source_shas"].pop(names[0])
    with pytest.raises(ValueError, match="reversible_ghcr_baseline_invalid"):
        rollout.release_rollback_mode(invalid, "b" * 40)
    invalid = deepcopy(request)
    invalid["rollback_source_shas"][names[0]] = "b" * 40
    with pytest.raises(ValueError, match="reversible_ghcr_baseline_invalid"):
        rollout.release_rollback_mode(invalid, "b" * 40)
    invalid = deepcopy(request)
    invalid["rollback_source_shas"][names[0]] = "e" * 40
    with patch.object(rollout, "command", side_effect=responses):
        with pytest.raises(ValueError, match="rollback_baseline_registry_unverified"):
            rollout.verify_reversible_baseline(invalid, previous)
