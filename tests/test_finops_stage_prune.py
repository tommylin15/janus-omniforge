"""Regression for stale control status bypass in the legacy bounded Stage pruner."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest


def load_pruner():
    file = Path(__file__).resolve().parents[1] / "scripts/gcp/finops_stage_prune.py"
    spec = importlib.util.spec_from_file_location("stage_pruner_lease_test", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeControl:
    def __init__(self):
        self.connection = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return nullcontext(object())


class FakeStage:
    bucket = "gen-lang-client-0593591102-dev-stage"

    def __init__(self):
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        self.items = [{"name": "executions/stale/stage/manifest.json",
                       "generation": "71", "size": "123", "updated": old}]
        self.deleted = []

    def objects(self, prefix):
        assert prefix == ""
        return list(self.items)

    def delete(self, name, *, generation):
        self.deleted.append((name, generation))
        self.items = [item for item in self.items
                      if (item["name"], item["generation"]) != (name, generation)]


@pytest.mark.parametrize("apply", [False, True])
def test_expired_unleased_execution_is_not_protected_by_stale_status(monkeypatch, apply):
    module, store = load_pruner(), FakeStage()
    monkeypatch.setattr(module, "GcsObjectStore", lambda bucket: store)
    monkeypatch.setattr(module, "_control_plane", FakeControl)
    monkeypatch.setattr(module, "_stage_live_execution_ids",
                        lambda cursor, now: frozenset())
    monkeypatch.setenv("JANUS_STAGE_PRUNE_MODE", "apply" if apply else "dry-run")
    monkeypatch.setenv("JANUS_APPROVED_STAGE_PRUNE", "true")
    monkeypatch.setenv("STAGE_BUCKET", store.bucket)
    result = module.run()
    assert result["planned_objects"] == 1
    assert result["held_active_objects"] == 0
    assert result["deleted_objects"] == (1 if apply else 0)
    assert store.deleted == ([("executions/stale/stage/manifest.json", "71")] if apply else [])


def test_new_lease_before_apply_fails_closed_without_deleting(monkeypatch):
    module, store = load_pruner(), FakeStage()
    claims = iter([frozenset(), frozenset({"stale"})])
    monkeypatch.setattr(module, "GcsObjectStore", lambda bucket: store)
    monkeypatch.setattr(module, "_control_plane", FakeControl)
    monkeypatch.setattr(module, "_stage_live_execution_ids",
                        lambda cursor, now: next(claims))
    monkeypatch.setenv("JANUS_STAGE_PRUNE_MODE", "apply")
    monkeypatch.setenv("JANUS_APPROVED_STAGE_PRUNE", "true")
    monkeypatch.setenv("STAGE_BUCKET", store.bucket)
    with pytest.raises(RuntimeError, match="stage_prune_live_lease_drift"):
        module.run()
    assert not store.deleted
