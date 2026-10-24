from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ingestion_core.batch_controller import Batch, PROJECT, REGION, due_batches, scheduled_batches, poll_job, job_active, occurrence_env


def test_multiple_daily_and_weekend_slots_have_distinct_identities():
    batches = (Batch("weekend", "unused", (7, 12), (5, 6)),)
    saturday = datetime(2026, 10, 3, 5, tzinfo=timezone.utc)
    assert [row[0] for row in due_batches(saturday, batches)] == ["weekend/2026-10-03/07", "weekend/2026-10-03/12"]
    assert due_batches(saturday.replace(day=2), batches) == []
    assert due_batches(saturday.replace(hour=0, minute=29), batches) == [due_batches(saturday, batches)[0]]
    with pytest.raises(ValueError):
        due_batches(datetime(2026, 10, 3), batches)


def test_weekly_maintenance_uses_only_saturday_chain_and_keeps_daily_core_work(monkeypatch):
    from ingestion_core.batch_controller import effective_batches
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "true")
    assert [batch.name for batch in effective_batches() if batch.weekdays == (5,) and batch.name in
            {"iceberg-compaction", "mart-cleanup", "core-cleanup"}] == [
                "iceberg-compaction", "core-cleanup", "mart-cleanup"]
    before = datetime(2026, 10, 17, 15, 29, tzinfo=timezone.utc)  # Saturday 23:29 Taipei
    due = before.replace(minute=30)
    weekly = {"iceberg-compaction", "mart-cleanup", "core-cleanup"}
    assert not weekly.intersection(row[1].name for row in due_batches(before))
    rows = {row[1].name: row for row in due_batches(due) if row[1].name in weekly}
    assert set(rows) == weekly
    assert rows["iceberg-compaction"][3] == []  # Cross-day EOD attestation happens before dispatch.
    assert rows["mart-cleanup"][3] == ["iceberg-compaction/2026-10-17/23"]
    assert rows["core-cleanup"][3] == ["mart-cleanup/2026-10-17/23"]
    assert {row[1].name for row in due_batches(datetime(2026, 10, 18, 15, 30, tzinfo=timezone.utc))}.isdisjoint(weekly)
    assert any(row[1].name == "ingestion" for row in due_batches(due))
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "invalid")
    with pytest.raises(ValueError, match="FINOPS_WEEKLY_MAINTENANCE"):
        due_batches(due)


def test_stage_cleanup_runs_daily_independent_of_weekly_iceberg(monkeypatch):
    from ingestion_core.batch_controller import effective_batches
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "true")
    batch = next(x for x in effective_batches() if x.name == "stage-cleanup")
    assert batch.weekdays == tuple(range(7))
    assert batch.dependencies == ()
    assert dict(batch.env)["ICEBERG_MAINTENANCE_MODE"] == "stage-only-apply"
    assert dict(batch.env)["JANUS_DATA_SUPPLEMENT_MODE"] == ""
    before = datetime(2026, 10, 19, 10, 29, tzinfo=timezone.utc)
    due = before.replace(minute=30)  # 18:30 Taipei
    assert not [r for r in due_batches(before) if r[1].name == "stage-cleanup"]
    assert [r[0] for r in due_batches(due) if r[1].name == "stage-cleanup"] == [
        "stage-cleanup/2026-10-19/18"]
    assert [r[0] for r in due_batches(due.replace(day=20)) if r[1].name == "stage-cleanup"] == [
        "stage-cleanup/2026-10-20/18"]


def test_weekly_eod_core_requires_successful_trading_slot_and_immutable_receipt():
    from unittest.mock import MagicMock
    from ingestion_core.batch_controller import weekly_eod_core_evidence
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    friday = datetime(2026, 10, 16, 6, 30, tzinfo=timezone.utc)  # 14:30 Taipei
    slot = datetime(2026, 10, 17, 15, 30, tzinfo=timezone.utc)
    ready = ("sha256:" + "a" * 64,
             "gs://janus-dev-core/executions/eod-1/core-snapshot.json", "2026-10-16")
    cursor.fetchall.side_effect = [
        [("ingestion/2026-10-16/14", friday)],
        [ready],
    ]
    evidence = weekly_eod_core_evidence(db, slot)
    assert evidence == {
        "source_occurrence": "ingestion/2026-10-16/14", "source_date": "2026-10-16",
        "core_snapshot_id": ready[0], "core_snapshot_uri": ready[1]}
    assert cursor.execute.call_count == 2
    cursor.reset_mock()
    cursor.fetchall.side_effect = [
        [("ingestion/2026-10-16/14", friday)],
        [("sha256:invalid", ready[1], ready[2])],
    ]
    assert weekly_eod_core_evidence(db, slot) is None
    cursor.fetchall.side_effect = [[], []]
    assert weekly_eod_core_evidence(db, slot) is None


def test_private_pipeline_effective_schedule_is_controller_owned():
    from ingestion_core.batch_controller import BATCHES
    private = next(batch for batch in BATCHES if batch.name == "private")
    assert private.job == "janus-private-pipeline"
    assert private.hours == (15, 21)
    assert private.minute == 30
    assert private.weekdays == tuple(range(5))
    assert private.dependencies == ("ingestion",)

    before = datetime(2026, 10, 2, 7, 29, tzinfo=timezone.utc)  # 15:29 Asia/Taipei
    after = datetime(2026, 10, 2, 13, 30, tzinfo=timezone.utc)   # 21:30 Asia/Taipei
    assert not any(row[1].name == "private" for row in due_batches(before))
    private_rows = [row for row in due_batches(after) if row[1].name == "private"]
    assert [row[0] for row in private_rows] == ["private/2026-10-02/15", "private/2026-10-02/21"]
    assert private_rows[0][3] == ["ingestion/2026-10-02/14"]
    assert private_rows[1][3] == []  # Nightly PIT-safe fallback must be dispatchable independently.


def test_ingestion_has_same_controller_eod_slot_with_same_day_price_scope():
    from ingestion_core.batch_controller import BATCHES
    ingestion = next(batch for batch in BATCHES if batch.name == "ingestion")
    assert ingestion.hours == (7, 14)
    now = datetime(2026, 10, 6, 6, 30, tzinfo=timezone.utc)  # 14:30 Asia/Taipei
    rows = [row for row in due_batches(now) if row[1].name == "ingestion"]
    assert [row[0] for row in rows] == [
        "ingestion/2026-10-06/07",
        "ingestion/2026-10-06/14",
    ]
    eod = rows[-1]
    env = dict(occurrence_env(eod[1], eod[2]))
    assert env["INGESTION_DATE"] == "2026-10-06"
    assert env["INGESTION_DATASETS"] == "twse-market-volume,tpex-market-volume,taiex"
    assert "INGESTION_DATE" not in dict(occurrence_env(rows[0][1], rows[0][2]))


def test_afternoon_private_requires_ingestion_but_nightly_does_not():
    rows = due_batches(datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc))  # 21:30 Asia/Taipei
    private = [row for row in rows if row[1].name == "private"]
    assert len(private) == 2
    assert private[0][3] == ["ingestion/2026-10-06/14"]
    assert private[1][3] == []




def test_private_independent_hour_configuration_rejects_invalid_slots():
    # Waiving one dependency is explicit and limited to a configured daily slot.
    with pytest.raises(ValueError, match="independent batch slot"):
        due_batches(datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc),
                    (Batch("bad", "unused", (15,), dependencies=("ingestion",),
                           independent_hours=(21,)),))
    with pytest.raises(ValueError, match="independent batch slot"):
        due_batches(datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc),
                    (Batch("bad", "unused", (21,), independent_hours=(21,)),))


def test_nightly_private_precedes_older_unrunnable_afternoon_slot():
    from ingestion_core.batch_controller import prioritize_nightly_private
    now = datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc)
    rows = [("private/2026-10-15/15", {"status": "pending"}),
            ("ingestion/2026-10-15/14", {"status": "failed"}),
            ("private/2026-10-15/21", {"status": "pending"})]
    assert prioritize_nightly_private(rows, now)[0][0] == "private/2026-10-15/21"
    assert len(prioritize_nightly_private(rows, now)) == len(rows)


def test_live_tick_dispatches_nightly_private_when_afternoon_upstream_failed(monkeypatch):
    from unittest.mock import MagicMock, Mock, call
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-01T00:00:00Z")
    monkeypatch.setattr(controller, "probe_mobile_ledger_queue",
                        lambda **kwargs: {"pending": False})
    day = "private/2026-10-15/15"
    night = "private/2026-10-15/21"
    morning = {"batch": "private", "job": "janus-private-pipeline",
               "status": "pending", "dependencies": ["ingestion/2026-10-15/14"],
               "scheduled_at": "2026-10-15T15:30:00+08:00", "env": []}
    evening = {"batch": "private", "job": "janus-private-pipeline",
               "status": "pending", "dependencies": [],
               "scheduled_at": "2026-10-15T21:30:00+08:00", "env": []}
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = (True,)
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(day, morning), (night, evening)],
                                   [("ingestion/2026-10-15/14", "failed")]]
    cursor.fetchone.return_value = None
    session = Mock()
    session.get.return_value = SimpleNamespace(status_code=200, json=lambda: {"executions": []})
    session.post.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"name": f"projects/{PROJECT}/locations/{REGION}/operations/nightly-123"})
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    result = controller.run(now=datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=db, get_admin_setting=lambda key: None), session=session)
    assert result["status"] == "tick_completed"
    assert session.post.call_count == 1
    assert session.post.call_args.args[0].endswith("/jobs/janus-private-pipeline:run")
    transitions = [(args.args[2], args.args[4]) for args in record.call_args_list]
    assert (night, "dispatch_intent") in transitions
    assert (night, "dispatch_result") in transitions
    assert (day, "private_upstream_failed") in transitions
    skipped = next(args.args[3] for args in record.call_args_list
                   if args.args[2] == day and args.args[4] == "private_upstream_failed")
    assert skipped["status"] == "skipped" and skipped["reason"] == "upstream_ingestion_failed"
    assert transitions.index((night, "dispatch_intent")) < transitions.index((day, "private_upstream_failed"))

def test_dependency_uses_latest_preceding_slot_and_original_private_time():
    batches = (Batch("source", "unused", (7, 12)), Batch("mart", "unused", (9, 13), dependencies=("source",)))
    rows = due_batches(datetime(2026, 10, 2, 6, tzinfo=timezone.utc), batches)
    assert [row[3] for row in rows if row[1].name == "mart"] == [["source/2026-10-02/07"], ["source/2026-10-02/12"]]
    assert not any(row[1].name == "private" for row in due_batches(datetime(2026, 10, 2, 7, 29, tzinfo=timezone.utc)))


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


def test_busy_controller_never_polls_or_dispatches(monkeypatch):
    from unittest.mock import Mock
    from ingestion_core.batch_controller import run
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (False,)
    control = SimpleNamespace(connection=connection, get_admin_setting=lambda key: None)
    session = Mock()
    assert run(control=control, session=session)["status"] == "controller_busy"
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


@pytest.mark.parametrize("hour", [5, 11, 14, 15, 17, 23])
def test_observe_mode_never_opens_iceberg(monkeypatch, hour):
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "observe")
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (True,)
    monkeypatch.setattr(controller, "record", Mock())
    result = controller.run(now=datetime(2026, 10, 15, hour, 30, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=conn), session=Mock())
    assert result["status"] == "observe"
    assert result["exported_events"] == 0 and result["iceberg_audit_disabled"] is True
    assert not hasattr(controller, "export_events")


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
    session = Mock()
    result = controller.run(now=datetime(2026, 10, 15, 15, 30, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=connection, get_admin_setting=lambda key: None), session=session)
    assert result["exported_events"] == 0
    assert result["iceberg_audit_disabled"] is True
    assert record.call_args.args[3]["execution"] == "idle-execution"
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_supplement_daily_precedes_mart_and_saturday_quality_is_independent():
    from ingestion_core.batch_controller import BATCHES
    batches = {batch.name: batch for batch in BATCHES}
    assert dict(batches["data-supplement"].env)["JANUS_DATA_SUPPLEMENT_MODE"] == "daily"
    assert "data-supplement" in batches["mart"].dependencies
    assert batches["data-quality"].weekdays == (5,)
    assert batches["data-quality"].dependencies == ()
    saturday = due_batches(datetime(2026, 10, 3, 5, tzinfo=timezone.utc))
    assert any(row[1].name == "data-quality" for row in saturday)
    friday = due_batches(datetime(2026, 10, 2, 5, tzinfo=timezone.utc))
    assert not any(row[1].name == "data-quality" for row in friday)


def test_mart_retention_precedes_core_retention_on_weekdays_and_weekends():
    for day in (2, 3):
        due = {batch.name: dependencies for _, batch, _, dependencies in
               due_batches(datetime(2026, 10, day, 15, 45, tzinfo=timezone.utc))}
        assert due["iceberg-compaction"] == [f"ingestion/2026-10-{day:02d}/14"]
        assert due["mart-cleanup"] == [f"iceberg-compaction/2026-10-{day:02d}/23"]
        assert due["core-cleanup"] == [f"mart-cleanup/2026-10-{day:02d}/23"]


def test_nightly_compaction_reuses_ingestion_job_with_isolated_execution_overrides():
    from ingestion_core.batch_controller import BATCHES
    batches = {batch.name: batch for batch in BATCHES}
    compaction = batches["iceberg-compaction"]
    assert compaction.job == "janus-ingestion-core"
    assert compaction.hours == (23,) and compaction.minute == 30
    assert compaction.dependencies == ("ingestion",)
    assert set(compaction.exclusive_jobs) == {
        "janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline"
    }
    overrides = dict(occurrence_env(compaction, datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc)))
    assert overrides["ICEBERG_MAINTENANCE_MODE"] == "compact-nightly"
    assert overrides["QUEUE_CONSUMER"] == "false"
    assert overrides["MART_JOB"] == ""
    assert overrides["JANUS_DATA_SUPPLEMENT_MODE"] == ""
    assert overrides["JANUS_CONTROL_MIGRATION"] == ""
    assert overrides["JANUS_SERVING_SCHEMA_MIGRATION"] == ""
    assert "ICEBERG_MAINTENANCE_MODE" not in dict(batches["core-cleanup"].env) or dict(batches["core-cleanup"].env)["ICEBERG_MAINTENANCE_MODE"] == "retention-apply"
    before = datetime(2026, 10, 15, 15, 29, tzinfo=timezone.utc)  # 23:29 Taipei
    due = datetime(2026, 10, 15, 15, 30, tzinfo=timezone.utc)  # 23:30 Taipei
    assert not any(row[1].name == "iceberg-compaction" for row in due_batches(before))
    assert [key for key, batch, _, _ in due_batches(due) if batch.name == "iceberg-compaction"] == [
        "iceberg-compaction/2026-10-15/23"
    ]


def test_old_pending_core_cleanup_waits_for_new_mart_dependency(monkeypatch):
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-01T00:00:00Z")
    key = "core-cleanup/2026-10-02/23"
    state = {"job": "janus-ingestion-core", "batch": "core-cleanup", "status": "pending",
             "dependencies": ["ingestion/2026-10-02/07"], "scheduled_at": "2026-10-02T23:30:00+08:00"}
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(key, state)], [("mart-cleanup/2026-10-02/23", "failed")]]
    cursor.fetchone.return_value = None
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    session = Mock()
    controller.run(now=datetime(2026, 10, 2, 16, tzinfo=timezone.utc),
                   control=SimpleNamespace(connection=connection, get_admin_setting=lambda key: None), session=session)
    updates = [call.args for call in record.call_args_list if call.args[2] == key]
    assert [args[4] for args in updates] == ["dependency_policy_updated", "waiting_dependency"]
    assert updates[0][3]["dependencies"] == ["mart-cleanup/2026-10-02/23"]
    session.post.assert_not_called()


def test_mobile_ledger_slot_is_current_hour_only_and_conditionally_dispatched():
    # 12:35 Taipei: no historical mobile catch-up slots are created.
    now = datetime(2026, 10, 6, 4, 35, tzinfo=timezone.utc)
    mobile = [row for row in due_batches(now) if row[1].name == "mobile-ledger"]
    assert len(mobile) == 1
    assert mobile[0][0] == "mobile-ledger/2026-10-06/12"
    assert mobile[0][2].hour == 12 and mobile[0][2].minute == 30

    assert not [row for row in scheduled_batches(now, False) if row[1].name == "mobile-ledger"]
    assert len([row for row in scheduled_batches(now, True) if row[1].name == "mobile-ledger"]) == 1


def test_regular_private_slot_suppresses_same_hour_mobile_trigger():
    # Tuesday 21:30 Taipei has the canonical Private Pipeline slot.
    now = datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc)
    rows = scheduled_batches(now, True)
    assert len([row for row in rows if row[1].name == "private"]) == 2
    assert not [row for row in rows if row[1].name == "mobile-ledger"]


def test_mobile_probe_does_not_open_control_database(monkeypatch):
    from unittest.mock import Mock
    from ingestion_core import batch_controller as controller

    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "mobile-probe")
    monkeypatch.setattr(controller, "probe_mobile_ledger_queue",
                        lambda **kwargs: {"status": "available", "pending": True, "writable": False})
    control = Mock()
    result = controller.run(control=control)
    assert result == {"status": "available", "mobile_ledger_pending": True}
    control.connection.execute.assert_not_called()


def test_disabled_mirror_still_records_postgres_event_atomically():
    from unittest.mock import MagicMock
    from ingestion_core.batch_controller import record
    connection = MagicMock()
    record(connection, "tick", "occurrence", {"status": "failed"}, "reconcile")
    statements = connection.cursor.return_value.__enter__.return_value.execute.call_args_list
    assert len(statements) == 2
    assert "UPDATE control.batch_occurrences" in statements[0].args[0]
    assert "INSERT INTO control.batch_event_outbox" in statements[1].args[0]
    connection.transaction.assert_called_once()


def test_admin_duration_uses_actual_execution_not_scheduled_slot():
    from unittest.mock import Mock
    path=f"projects/{PROJECT}/locations/{REGION}/jobs/janus-ingestion-core/executions/test"
    session=Mock()
    session.get.return_value=SimpleNamespace(status_code=200,json=lambda:{
        'startTime':'2026-10-18T01:00:00Z','completionTime':'2026-10-18T01:02:03Z','succeededCount':1})
    value=poll_job(session,{'job':'janus-ingestion-core','status':'running','execution':path})
    assert value['status']=='succeeded' and value['duration_seconds']==123
    assert value['start_time']=='2026-10-18T01:00:00Z'


def test_five_day_queue_policy_limits_selection_and_disables_old_override(monkeypatch):
    from unittest.mock import MagicMock
    from ingestion_core.admin_batches import enqueue_queued_worker, enqueue_manual_queues
    batch = SimpleNamespace(name="analysis-queue", job="janus-ingestion-core", manual_only=True)
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [("fresh-execution", 0), None, ("inserted",)]
    now = datetime(2026, 10, 24, 1, tzinfo=timezone.utc)
    result = enqueue_queued_worker(connection, batch, now, lambda *_: ())
    assert result == "queued"
    sql = cursor.execute.call_args_list[0].args[0]
    assert "requested_at >= now() - interval '5 days'" in sql
    assert "interval '7 days'" not in sql
    assert "interval '30 days'" not in sql
    assert "OR %s" not in sql
    assert cursor.execute.call_args_list[0].args[1] == ("analysis",)
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_queued_worker(connection, batch, now, lambda *_: (),
                              historical_recovery=True,
                              target_execution_ref="a" * 32)
    monkeypatch.setenv("JANUS_P02_ANALYSIS_RECOVERY", "one-shot")
    monkeypatch.setenv("JANUS_P02_ANALYSIS_EXECUTION_REF", "a" * 32)
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_manual_queues(connection, [batch], set(), now, lambda *_: ())


def test_persisted_queue_dispatch_requires_current_matching_execution():
    from unittest.mock import MagicMock
    from ingestion_core.admin_batches import queued_execution_is_fresh
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(1,), None]
    assert queued_execution_is_fresh(connection, "uuid", "analysis")
    assert not queued_execution_is_fresh(connection, "uuid", "collection")
    assert not queued_execution_is_fresh(connection, None, "analysis")
    assert not queued_execution_is_fresh(connection, "uuid", "other")
    assert cursor.execute.call_count == 2
    for call in cursor.execute.call_args_list:
        sql, params = call.args
        assert "requested_at >= now() - interval '5 days'" in sql
        assert "finished_at IS NULL" in sql
        assert "SELECT 1" in sql
        assert params[0] == "uuid"
    assert cursor.execute.call_args_list[0].args[1][1] == "analysis"
    assert cursor.execute.call_args_list[1].args[1][1] == "collection"


def test_active_controller_skips_old_pending_queue_without_job_dispatch(monkeypatch):
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    from ingestion_core import admin_batches
    monkeypatch.delenv("JANUS_P02_ANALYSIS_RECOVERY", raising=False)
    monkeypatch.delenv("JANUS_P02_ANALYSIS_EXECUTION_REF", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-01T00:00:00Z")
    monkeypatch.setattr(controller, "due_batches", lambda *_: [])
    monkeypatch.setattr(controller, "scheduled_batches", lambda *_: [])
    monkeypatch.setattr(controller, "probe_mobile_ledger_queue",
                        lambda **_: {"pending": False})
    monkeypatch.setattr(admin_batches, "queued_execution_is_fresh", lambda *_: False)
    state = {"batch": "analysis-queue", "job": "janus-intelligence-mart",
             "status": "pending", "origin": "queue",
             "queued_execution_id": "stale-id", "dependencies": [],
             "scheduled_at": "2026-10-15T00:00:00+00:00", "env": []}
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [("queue/analysis/stale-id/0", state)]]
    cursor.fetchone.return_value = None
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    session = Mock()
    result = controller.run(now=datetime(2026, 10, 24, 1, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=connection,
                                get_admin_setting=lambda *_: None), session=session)
    assert result["status"] == "tick_completed"
    excluded = [c for c in record.call_args_list if c.args[4] == "queue_request_excluded"]
    assert len(excluded) == 1
    assert excluded[0].args[3]["status"] == "skipped"
    assert excluded[0].args[3]["reason"] == "queue_execution_outside_five_day_window"
    session.post.assert_not_called()
