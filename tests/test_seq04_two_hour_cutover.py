"""Bounded SEQ-04 Scheduler cutover and rollback contracts; no GCP calls."""
from copy import deepcopy
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/gcp"))
import seq04_two_hour_cutover as cutover


def sample_scheduler(cron=cutover.OLD):
    return {
        "name": "projects/gen-lang-client-0593591102/locations/us-central1/jobs/janus-ingestion-daily",
        "schedule": cron,
        "timeZone": "Asia/Taipei",
        "state": "ENABLED",
        "httpTarget": {
            "uri": "https://run.googleapis.com/v2/projects/gen-lang-client-0593591102/locations/us-central1/jobs/janus-batch-controller:run",
            "httpMethod": "POST",
            "oauthToken": {"serviceAccountEmail": "existing-controller@example.invalid"},
        },
        "retryConfig": {"retryCount": 0},
        "attemptDeadline": "180s",
    }


def test_schedule_invariant_rejects_identity_and_time_zone_drift():
    before = sample_scheduler()
    after = deepcopy(before)
    after["schedule"] = cutover.NEW
    assert cutover.invariant(before, after)
    after["httpTarget"]["uri"] += "/other"
    assert not cutover.invariant(before, after)
    after = deepcopy(before)
    after["timeZone"] = "UTC"
    assert not cutover.invariant(before, after)


def _fake_live(monkeypatch, current):
    source = "032871a38b1dffd11c7bf0cc833563c0c3091841"
    images = {
        "janus-batch-controller": "ghcr.io/tommylin15/janus-ingestion-core@sha256:" + "a" * 64,
        "janus-ingestion-core": "ghcr.io/tommylin15/janus-ingestion-core@sha256:" + "a" * 64,
        "janus-intelligence-mart": "ghcr.io/tommylin15/janus-intelligence-mart@sha256:" + "b" * 64,
        "janus-private-pipeline": "ghcr.io/tommylin15/janus-private-pipeline@sha256:" + "c" * 64,
    }
    monkeypatch.setattr(cutover, "checked_request", lambda: {"source_sha": source, "job_images": images})
    monkeypatch.setattr(cutover.api, "describe", lambda: {
        "status": {"traffic": [{"revisionName": "new-revision", "percent": 100},
                              {"revisionName": "new-revision", "tag": "ghcr-" + source[:12], "percent": 0}]}
    })
    monkeypatch.setattr(cutover.api, "health", lambda sha: None)
    monkeypatch.setattr(cutover.jobs, "legacy_writers", lambda: None)
    monkeypatch.setattr(cutover.jobs, "job", lambda name: {"image": images[name]})
    monkeypatch.setattr(cutover.jobs, "image", lambda value: value["image"])
    monkeypatch.setattr(cutover.jobs, "scheduler", lambda: deepcopy(current))
    monkeypatch.setattr(cutover.jobs, "wait_for_terminal_executions", lambda timeout=900: None)
    monkeypatch.setattr(cutover.jobs, "set_scheduler", lambda operation, expected: current.update(
        {"state": "PAUSED" if operation == "pause" else "ENABLED"}))
    commands = []
    monkeypatch.setattr(cutover.jobs, "command", lambda args: commands.append(args) or "")
    return commands


def test_two_hour_cutover_uses_one_existing_scheduler_and_releases_lease(monkeypatch, tmp_path):
    current = sample_scheduler()
    commands = _fake_live(monkeypatch, current)
    original = cutover.change_schedule
    monkeypatch.setattr(cutover, "change_schedule", lambda cron: current.update({"schedule": cron}))
    receipt = tmp_path / "receipt.json"
    assert cutover.run(receipt) == 0
    assert json.loads(receipt.read_text())["phase"] == "PASS"
    assert current["schedule"] == cutover.NEW and current["state"] == "ENABLED"
    assert any(cmd[-1] == "acquire" for cmd in commands)
    assert any(cmd[-2:] == ["release", "--safe-to-release"] for cmd in commands)
    assert not any("create" in cmd for cmd in commands)
    monkeypatch.setattr(cutover, "change_schedule", original)


def test_failed_schedule_update_restores_old_cron_and_keeps_no_double_scheduler(monkeypatch, tmp_path):
    current = sample_scheduler()
    commands = _fake_live(monkeypatch, current)
    def failed_change(cron):
        current["schedule"] = cron
        if cron == cutover.NEW:
            raise ValueError("simulated_update_response_lost")
    monkeypatch.setattr(cutover, "change_schedule", failed_change)
    receipt = tmp_path / "receipt.json"
    assert cutover.run(receipt) == 78
    assert json.loads(receipt.read_text())["phase"] == "ROLLED_BACK"
    assert current["schedule"] == cutover.OLD and current["state"] == "ENABLED"
    assert any(cmd[-2:] == ["release", "--safe-to-release"] for cmd in commands)


def test_workflow_is_explicit_and_has_single_global_mutex():
    text = (Path(__file__).parents[1] /
            ".github/workflows/seq04-two-hour-controller-dev.yml").read_text()
    assert "janus-dev-runtime-writers" in text
    assert "cancel-in-progress: false" in text
    assert "ops/seq04-two-hour-cutover-request.json" in text
    assert "seq04_two_hour_cutover.py --receipt" in text
    assert "actions/upload-artifact@v4" in text
