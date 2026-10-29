import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
sys.path.insert(0, str(Path("scripts/gcp").resolve()))
import three_pipeline_compensation_acceptance as compensation


def test_positive_queue_duplicate_and_empty_use_controller_without_ledger_changes(monkeypatch, tmp_path):
    acceptance = compensation.acceptance
    jobs = acceptance.jobs
    monkeypatch.setattr(acceptance, "source_gate", lambda *args: "a" * 40)
    state = {"value": "ENABLED"}
    monkeypatch.setattr(jobs, "scheduler", lambda: {"state": state["value"]})
    monkeypatch.setattr(jobs, "set_scheduler", lambda op, value: state.update(value=value))
    monkeypatch.setattr(jobs, "scheduler_fingerprint", lambda data: "unchanged")
    monkeypatch.setattr(jobs, "existing_jobs", lambda: {"janus-private-pipeline": {}})
    monkeypatch.setattr(jobs, "image", lambda data: "pinned")
    monkeypatch.setattr(jobs, "fingerprint", lambda data: "fingerprint")
    for name in ("legacy_writers", "wait_for_terminal_executions", "checked_image", "command"):
        monkeypatch.setattr(jobs, name, Mock())
    monkeypatch.setattr(compensation, "executions", Mock(side_effect=[{"old"}, {"old", "worker"}, {"old", "worker"}]))
    calls = []
    monkeypatch.setattr(acceptance, "invoke", lambda name, env, *args: calls.append((name, env)))
    path = tmp_path / "receipt.json"
    compensation.run(SimpleNamespace(receipt=path, release_run="1", jobs_run="2", source_date="2026-10-28"))
    receipt = json.loads(path.read_text())
    assert receipt["phase"] == "PASS" and receipt["no_ledger_mutation"]
    assert [env.get("JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE") for _, env in calls] == ["seed", None, "verify", None, "cleanup"]
    assert [name for name, _ in calls].count("janus-batch-controller") == 2
    assert all(name != "janus-private-pipeline" for name, _ in calls)
    assert state["value"] == "ENABLED"


def test_invalid_date_cannot_acquire_lease_or_seed_queue(monkeypatch, tmp_path):
    command = Mock()
    monkeypatch.setattr(compensation.acceptance.jobs, "command", command)
    with pytest.raises(ValueError):
        compensation.run(SimpleNamespace(receipt=tmp_path / "receipt.json", release_run="1", jobs_run="2", source_date="invalid"))
    command.assert_not_called()
