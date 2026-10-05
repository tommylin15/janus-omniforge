from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from ingestion_core import batch_controller as controller
from ingestion_core.batch_controller import PROJECT, REGION, insert_manual_retrain, manual_retrain_dependencies


def test_manual_retrain_uses_newest_dependency_date_even_if_pair_is_incomplete():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc),),  # 10/05 07:30 Taipei ingestion
        (datetime(2026, 10, 4, 0, 30, tzinfo=timezone.utc),),   # prior-day supplement
    ]
    assert manual_retrain_dependencies(connection, datetime(2026, 10, 5, tzinfo=timezone.utc)) == [
        "ingestion/2026-10-05/07", "data-supplement/2026-10-05/08"
    ]


def test_manual_retrain_occurrence_is_idempotent_and_fails_closed_without_recent_dependencies():
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = [
        (datetime(2026, 10, 4, 0, 30, tzinfo=timezone.utc),),
        (datetime(2026, 10, 3, 23, 30, tzinfo=timezone.utc),),
    ]
    key = insert_manual_retrain(connection, now, "wbs5-oos-20261005")
    assert key == "specialist-retrain/manual/wbs5-oos-20261005"

    existing = MagicMock()
    existing_cursor = existing.cursor.return_value.__enter__.return_value
    existing_cursor.fetchone.return_value = ({
        "batch": "specialist-retrain", "origin": "manual",
        "request_id": "wbs5-oos-20261005", "status": "succeeded",
    },)
    assert insert_manual_retrain(existing, now, "wbs5-oos-20261005") == key
    existing.transaction.assert_not_called()

    missing = MagicMock()
    missing_cursor = missing.cursor.return_value.__enter__.return_value
    missing_cursor.fetchone.return_value = None
    missing_cursor.fetchall.return_value = []
    with pytest.raises(RuntimeError, match="recent dependency occurrences"):
        insert_manual_retrain(missing, now, "missing")
    missing.transaction.assert_not_called()


def test_manual_retrain_occurrence_identity_conflict_fails_closed():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ({"batch": "mart", "origin": "manual", "request_id": "same-id"},)
    with pytest.raises(RuntimeError, match="identity conflict"):
        insert_manual_retrain(connection, datetime(2026, 10, 5, tzinfo=timezone.utc), "same-id")


def test_manual_controller_dispatches_only_the_persisted_manual_occurrence(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "manual")
    monkeypatch.setenv("BATCH_CONTROLLER_MANUAL_REQUEST_ID", "wbs5-oos-20261005")
    key = "specialist-retrain/manual/wbs5-oos-20261005"
    state = {
        "job": "janus-intelligence-mart", "batch": "specialist-retrain", "status": "pending",
        "dependencies": ["ingestion/2026-10-04/07", "data-supplement/2026-10-04/08"],
        "scheduled_at": "2026-10-05T00:00:00+00:00", "origin": "manual", "request_id": "wbs5-oos-20261005",
    }
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(key, state)], [(state["dependencies"][0], "succeeded"), (state["dependencies"][1], "succeeded")]]
    cursor.fetchone.return_value = None
    monkeypatch.setattr(controller, "record", Mock())
    monkeypatch.setattr(controller, "export_events", lambda *_: 0)
    monkeypatch.setattr(controller, "insert_manual_retrain", lambda *_: key)
    monkeypatch.setattr(controller, "manual_retrain_dependencies", lambda *_: state["dependencies"])
    due = Mock(side_effect=AssertionError("manual mode must not create scheduled occurrences"))
    monkeypatch.setattr(controller, "due_batches", due)
    monkeypatch.setattr(controller, "job_active", lambda *_: False)
    dispatch = Mock(return_value=f"projects/{PROJECT}/locations/{REGION}/operations/manual")
    monkeypatch.setattr(controller, "dispatch_job", dispatch)

    result = controller.run(now=datetime(2026, 10, 5, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=connection), session=Mock(), core=Mock())
    assert result["status"] == "tick_completed"
    due.assert_not_called()
    dispatch.assert_called_once()
    assert dispatch.call_args.args[1].name == "specialist-retrain"


def test_manual_pending_rebinds_to_newer_dependency_date_before_dispatch(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "manual")
    monkeypatch.setenv("BATCH_CONTROLLER_MANUAL_REQUEST_ID", "cross-day")
    key = "specialist-retrain/manual/cross-day"
    old = ["ingestion/2026-10-04/07", "data-supplement/2026-10-04/08"]
    new = ["ingestion/2026-10-05/07", "data-supplement/2026-10-05/08"]
    state = {"job": "janus-intelligence-mart", "batch": "specialist-retrain", "status": "pending",
             "dependencies": old, "scheduled_at": "2026-10-04T22:50:00+00:00", "origin": "manual", "request_id": "cross-day"}
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(key, state)], [(new[0], "succeeded")]]
    cursor.fetchone.return_value = None
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    monkeypatch.setattr(controller, "export_events", lambda *_: 0)
    monkeypatch.setattr(controller, "insert_manual_retrain", lambda *_: key)
    monkeypatch.setattr(controller, "manual_retrain_dependencies", lambda *_: new)
    monkeypatch.setattr(controller, "job_active", lambda *_: False)
    dispatch = Mock()
    monkeypatch.setattr(controller, "dispatch_job", dispatch)

    controller.run(now=datetime(2026, 10, 5, 0, 10, tzinfo=timezone.utc),
                   control=SimpleNamespace(connection=connection), session=Mock(), core=Mock())
    updates = [call.args for call in record.call_args_list if call.args[2] == key]
    assert [args[4] for args in updates] == ["manual_dependency_updated", "waiting_dependency"]
    assert updates[0][3]["dependencies"] == new
    dispatch.assert_not_called()


@pytest.mark.parametrize("request_id", ["", "has space", "../escape", "x" * 81])
def test_manual_controller_rejects_invalid_request_id_before_db(monkeypatch, request_id):
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "manual")
    monkeypatch.setenv("BATCH_CONTROLLER_MANUAL_REQUEST_ID", request_id)
    control = Mock()
    with pytest.raises(ValueError, match="invalid manual request id"):
        controller.run(control=control, session=Mock(), core=Mock())
    control.connection.execute.assert_not_called()


def test_manual_retrain_workflow_routes_through_controller_only():
    workflow = Path(".github/workflows/run-dev-specialist-retrain.yml").read_text()
    assert "gcloud run jobs execute janus-batch-controller" in workflow
    assert "BATCH_CONTROLLER_MODE=manual" in workflow
    assert "BATCH_CONTROLLER_MANUAL_REQUEST_ID=${REQUEST_ID}" in workflow
    assert "gcloud run jobs execute janus-intelligence-mart" not in workflow
