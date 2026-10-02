from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ingestion_core.batch_controller import Batch, PROJECT, REGION, due_batches, poll_job, job_active


def test_multiple_daily_and_weekend_slots_have_distinct_identities():
    batches = (Batch("weekend", "unused", (7, 12), (5, 6)),)
    saturday = datetime(2026, 10, 3, 5, tzinfo=timezone.utc)
    assert [row[0] for row in due_batches(saturday, batches)] == ["weekend/2026-10-03/07", "weekend/2026-10-03/12"]
    assert due_batches(saturday.replace(day=2), batches) == []
    assert due_batches(saturday.replace(hour=0, minute=29), batches) == [due_batches(saturday, batches)[0]]
    with pytest.raises(ValueError):
        due_batches(datetime(2026, 10, 3), batches)


def test_dependency_uses_latest_preceding_slot_and_original_private_time():
    batches = (Batch("source", "unused", (7, 12)), Batch("mart", "unused", (9, 13), dependencies=("source",)))
    rows = due_batches(datetime(2026, 10, 2, 6, tzinfo=timezone.utc), batches)
    assert [row[3] for row in rows if row[1].name == "mart"] == [["source/2026-10-02/07"], ["source/2026-10-02/12"]]
    assert not any(row[1].name == "private" for row in due_batches(datetime(2026, 10, 2, 13, 29, tzinfo=timezone.utc)))


def test_running_jobs_are_polled_once_without_mutation_or_wait():
    calls = []
    path = f"projects/{PROJECT}/locations/{REGION}/jobs/janus-ingestion-core/executions/test"
    session = SimpleNamespace(get=lambda url, timeout: calls.append(url) or SimpleNamespace(status_code=200, json=lambda: {"name": path}))
    state = {"status": "running", "job": "janus-ingestion-core", "execution": path}
    assert poll_job(session, state) == state
    assert len(calls) == 1
    assert poll_job(session, {**state, "status": "ambiguous"})["status"] == "ambiguous"
    assert len(calls) == 1


def test_operation_and_execution_failure_and_listing_fail_closed():
    path = f"projects/{PROJECT}/locations/{REGION}/operations/test"
    session = SimpleNamespace(get=lambda url, timeout: SimpleNamespace(status_code=200, json=lambda: {"done": True, "error": {"message": "never copy raw error"}}))
    result = poll_job(session, {"status": "running", "job": "janus-ingestion-core", "operation": path})
    assert result["status"] == "failed"
    assert "never copy" not in str(result)
    session.get = lambda url, timeout: SimpleNamespace(status_code=200, json=lambda: {"nextPageToken": "more", "executions": []})
    assert job_active(session, "janus-ingestion-core")
    with pytest.raises(ValueError):
        poll_job(session, {"status": "running", "job": "janus-ingestion-core", "execution": "projects/prod/locations/us-central1/jobs/other/executions/test"})


@pytest.mark.parametrize("later_running", [False, True])
def test_execution_listing_checks_later_pages_and_ignores_terminal_startup_failures(later_running):
    from unittest.mock import Mock
    first = {"nextPageToken": "next/page", "executions": [{"completionTime": "done"}]}
    failed = {"succeededCount": 1, "conditions": [{"type": "Completed", "state": "CONDITION_FAILED"}]}
    second = {"executions": [failed, {}] if later_running else [failed]}
    session = Mock()
    session.get.side_effect = [SimpleNamespace(status_code=200, json=lambda: first),
                               SimpleNamespace(status_code=200, json=lambda: second)]
    assert job_active(session, "janus-ingestion-core") is later_running
    assert session.get.call_count == 2
    assert "pageToken=next%2Fpage" in session.get.call_args.args[0]
    path = f"projects/{PROJECT}/locations/{REGION}/jobs/janus-ingestion-core/executions/failed"
    session.get.side_effect = None
    session.get.return_value = SimpleNamespace(status_code=200, json=lambda: failed)
    result = poll_job(session, {"job": "janus-ingestion-core", "status": "running", "execution": path})
    assert result["status"] == "failed" and result["completion_time"] is None


def test_execution_page_limit_and_unknown_conditions_fail_closed():
    from unittest.mock import Mock
    session = Mock()
    session.get.side_effect = [SimpleNamespace(status_code=200, json=lambda i=i: {"nextPageToken": str(i)}) for i in range(20)]
    assert job_active(session, "janus-ingestion-core")
    assert session.get.call_count == 20
    session.get.side_effect = None
    session.get.return_value = SimpleNamespace(status_code=200, json=lambda: {"executions": [{"conditions": [{"type": "Completed", "state": "CONDITION_PENDING"}]}]})
    assert job_active(session, "janus-ingestion-core")


def test_iceberg_outbox_replay_is_idempotent_and_readback_precedes_ack():
    from contextlib import nullcontext
    from uuid import uuid4
    from unittest.mock import Mock
    from pathlib import Path
    import shutil
    from pyiceberg.catalog import load_catalog
    from ingestion_core.batch_controller import export_events
    root = Path(".tmp") / ("batch-log-" + str(uuid4()))
    root.mkdir(parents=True)
    warehouse = (root / "warehouse").as_posix()
    catalog = load_catalog("unit", type="sql", uri="sqlite:///" + (root.resolve() / "catalog.db").as_posix(), warehouse=warehouse)
    core = SimpleNamespace(catalog=catalog, warehouse=warehouse)
    key = uuid4()
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchall.return_value = [(key, datetime(2026, 10, 2, tzinfo=timezone.utc), {"action": "job_busy"})]
    connection = SimpleNamespace(cursor=lambda: cursor, transaction=nullcontext)
    try:
        assert export_events(connection, core) == 1
        assert export_events(connection, core) == 1
        assert catalog.load_table("ops.batch_events_v1").scan().to_arrow().num_rows == 1
        assert cursor.executemany.call_count == 2
        # A failed commit must leave the outbox unacknowledged.
        cursor.executemany.reset_mock()
        original = catalog.load_table
        catalog.load_table = lambda identifier: SimpleNamespace(upsert=Mock(side_effect=RuntimeError("write failed")))
        with pytest.raises(RuntimeError):
            export_events(connection, core)
        assert cursor.executemany.call_count == 0
        catalog.load_table = original
    finally:
        catalog.engine.dispose()
        shutil.rmtree(root)


def test_busy_controller_never_polls_or_dispatches(monkeypatch):
    from unittest.mock import Mock
    from ingestion_core.batch_controller import run
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (False,)
    control = SimpleNamespace(connection=connection)
    session = Mock()
    assert run(control=control, session=session, core=Mock())["status"] == "controller_busy"
    session.get.assert_not_called()
    session.post.assert_not_called()
    assert connection.execute.call_count == 1


def test_lost_dispatch_response_is_not_automatically_retried():
    from unittest.mock import Mock
    from ingestion_core.batch_controller import dispatch_job, BATCHES
    session = Mock()
    session.post.side_effect = TimeoutError("uncertain response")
    with pytest.raises(TimeoutError):
        dispatch_job(session, BATCHES[0])
    assert session.post.call_count == 1
    session.get.assert_not_called()


def test_idle_active_tick_is_recorded_without_dispatch(monkeypatch):
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-02T00:00:00Z")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "idle-execution")
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    connection.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    monkeypatch.setattr(controller, "due_batches", lambda _: [])
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    monkeypatch.setattr(controller, "export_events", lambda *_: 1)
    session = Mock()
    result = controller.run(control=SimpleNamespace(connection=connection), session=session, core=Mock())
    assert result["exported_events"] == 1
    assert record.call_args.args[3]["execution"] == "idle-execution"
    session.get.assert_not_called()
    session.post.assert_not_called()
