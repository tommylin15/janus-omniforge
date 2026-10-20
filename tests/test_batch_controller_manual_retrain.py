"""Regression tests for immediate retirement of the old cloud retraining route."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ingestion_core import batch_controller as controller


def test_retired_cloud_training_is_not_in_controller_schedule(monkeypatch):
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "true")
    assert "specialist-retrain" not in {batch.name for batch in controller.effective_batches()}
    first_saturday = datetime(2026, 11, 7, 2, 30, tzinfo=timezone.utc)
    assert all(batch.name != "specialist-retrain" for _, batch, _, _ in controller.due_batches(first_saturday))


def test_retired_manual_mode_rejected_before_db(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", controller.PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "manual")
    control = Mock()
    with pytest.raises(ValueError, match="unsupported controller mode"):
        controller.run(control=control, session=Mock())
    control.connection.execute.assert_not_called()


def test_retired_legacy_workflow_has_been_removed():
    from pathlib import Path
    assert not Path(".github/workflows/run-dev-specialist-retrain.yml").exists()
    assert not Path("ops/dev-specialist-retrain-request.json").exists()
