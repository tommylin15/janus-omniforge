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
    before = datetime(2026, 10, 17, 14, 29, tzinfo=timezone.utc)  # Saturday 23:29 Taipei
    due = before.replace(minute=30)
    weekly = {"iceberg-compaction", "mart-cleanup", "core-cleanup"}
    assert not weekly.intersection(row[1].name for row in due_batches(before))
    rows = {row[1].name: row for row in due_batches(due) if row[1].name in weekly}
    assert set(rows) == weekly
    assert rows["iceberg-compaction"][3] == []  # Cross-day EOD attestation happens before dispatch.
    assert rows["mart-cleanup"][3] == ["iceberg-compaction/2026-10-17/22"]
    assert rows["core-cleanup"][3] == ["mart-cleanup/2026-10-17/22"]
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
    before = datetime(2026, 10, 19, 14, 29, tzinfo=timezone.utc)
    due = before.replace(minute=30)  # 18:30 Taipei
    assert not [r for r in due_batches(before) if r[1].name == "stage-cleanup"]
    assert [r[0] for r in due_batches(due) if r[1].name == "stage-cleanup"] == [
        "stage-cleanup/2026-10-19/22"]
    assert [r[0] for r in due_batches(due.replace(day=20)) if r[1].name == "stage-cleanup"] == [
        "stage-cleanup/2026-10-20/22"]


def test_weekly_eod_core_requires_successful_preopen_ingestion_receipt():
    from unittest.mock import MagicMock
    from ingestion_core.batch_controller import weekly_eod_core_evidence
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    saturday_preopen = datetime(2026, 10, 16, 18, 30, tzinfo=timezone.utc)  # Saturday 02:30
    slot = datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc)  # Saturday 22:30
    ready = ("sha256:" + "a" * 64,
             "gs://janus-dev-core/executions/eod-1/core-snapshot.json", "2026-10-16")
    cursor.fetchall.side_effect = [
        [("ingestion/2026-10-17/02", saturday_preopen)], [ready]]
    evidence = weekly_eod_core_evidence(db, slot)
    assert evidence == {
        "source_occurrence": "ingestion/2026-10-17/02", "source_date": "2026-10-16",
        "core_snapshot_id": ready[0], "core_snapshot_uri": ready[1]}
    assert cursor.execute.call_count == 2
    assert "created_at >= %s" in cursor.execute.call_args.args[0]
    cursor.reset_mock()
    cursor.fetchall.side_effect = [
        [("ingestion/2026-10-17/02", saturday_preopen)],
        [("sha256:invalid", ready[1], ready[2])]]
    assert weekly_eod_core_evidence(db, slot) is None
    cursor.fetchall.side_effect = [[], []]
    assert weekly_eod_core_evidence(db, slot) is None
    cursor.fetchall.side_effect = [
        [("ingestion/2026-10-17/14", saturday_preopen)], [ready]]
    assert weekly_eod_core_evidence(db, slot) is None




def test_private_pipeline_effective_schedule_is_controller_owned():
    from ingestion_core.batch_controller import BATCHES
    private = next(b for b in BATCHES if b.name == "private")
    assert private.hours == (6,)
    assert private.dependencies == ("market-screening",)
    assert private.independent_hours == ()
    rows = [r for r in due_batches(datetime(2026, 10, 1, 22, 30, tzinfo=timezone.utc))
            if r[1].name == "private"]
    assert [r[3] for r in rows] == [["market-screening/2026-10-02/04"]]


def test_preopen_ingestion_and_screening_use_real_data_date():
    from ingestion_core.batch_controller import BATCHES
    batches = {b.name: b for b in BATCHES}
    assert batches["ledger-backup"].hours == (0,)
    assert batches["ingestion"].hours == (2,)
    assert batches["market-screening"].hours == (4,)
    assert batches["private"].hours == (6,)
    at_private = datetime(2026, 10, 1, 22, 30, tzinfo=timezone.utc)  # Friday 06:30 Taipei
    rows = {row[0]: row for row in due_batches(at_private)}
    assert rows["market-screening/2026-10-02/04"][3] == ["ingestion/2026-10-02/02"]
    assert rows["private/2026-10-02/06"][3] == ["market-screening/2026-10-02/04"]
    ingestion = rows["ingestion/2026-10-02/02"]
    assert dict(occurrence_env(ingestion[1], ingestion[2]))["INGESTION_DATE"] == ""
    screening = rows["market-screening/2026-10-02/04"]
    assert dict(occurrence_env(screening[1], screening[2]))["SCREENING_DATE"] == "latest"
    assert dict(occurrence_env(ingestion[1], ingestion[2]))["JANUS_UNIFIED_COLLECTION"] == "true"


def test_weekend_ingestion_and_backup_but_no_market_or_private():
    saturday = datetime(2026, 10, 16, 22, 30, tzinfo=timezone.utc)  # Saturday 06:30 Taipei
    rows = {batch.name for _, batch, _, _ in due_batches(saturday)}
    assert {"ingestion", "ledger-backup"} <= rows
    assert "market-screening" not in rows and "private" not in rows



def test_private_independent_hour_configuration_rejects_invalid_slots():
    # Waiving one dependency is explicit and limited to a configured daily slot.
    with pytest.raises(ValueError, match="independent batch slot"):
        due_batches(datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc),
                    (Batch("bad", "unused", (15,), dependencies=("ingestion",),
                           independent_hours=(21,)),))
    with pytest.raises(ValueError, match="independent batch slot"):
        due_batches(datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc),
                    (Batch("bad", "unused", (21,), independent_hours=(21,)),))


def test_current_private_slot_prioritized_over_retired_pending():
    from ingestion_core.batch_controller import prioritize_nightly_private
    now = datetime(2026, 10, 14, 22, 30, tzinfo=timezone.utc)
    rows = [("private/2026-10-15/18", {"status": "pending"}),
            ("private/2026-10-15/06", {"status": "pending"})]
    assert prioritize_nightly_private(rows, now)[0][0] == "private/2026-10-15/06"


def test_live_tick_closes_private_when_early_market_failed(monkeypatch):
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-01T00:00:00Z")
    monkeypatch.setattr(controller, "probe_mobile_ledger_queue",
                        lambda **kwargs: {"pending": False})
    day = "private/2026-10-15/06"
    state = {"batch": "private", "job": "janus-private-pipeline",
             "status": "pending", "dependencies": ["market-screening/2026-10-15/04"],
             "scheduled_at": "2026-10-15T06:30:00+08:00", "env": []}
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = (True,)
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(day, state)],
                                   [("market-screening/2026-10-15/04", "failed")]]
    cursor.fetchone.return_value = None
    session = Mock()
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    result = controller.run(now=datetime(2026, 10, 14, 22, 30, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=db, get_admin_setting=lambda key: None),
                            session=session)
    assert result["status"] == "tick_completed"
    session.post.assert_not_called()
    skipped = next(call.args[3] for call in record.call_args_list
                   if call.args[2] == day and call.args[4] == "private_upstream_failed")
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "upstream_ingestion_failed"




def test_dependency_uses_latest_preceding_slot_and_original_private_time():
    batches = (Batch("source", "unused", (7, 12)), Batch("mart", "unused", (9, 13), dependencies=("source",)))
    rows = due_batches(datetime(2026, 10, 2, 6, tzinfo=timezone.utc), batches)
    assert [row[3] for row in rows if row[1].name == "mart"] == [["source/2026-10-02/07"], ["source/2026-10-02/12"]]
    assert not any(row[1].name == "private" for row in due_batches(datetime(2026, 10, 1, 22, 29, tzinfo=timezone.utc)))


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
    result = controller.run(now=datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc),
                            control=SimpleNamespace(connection=connection, get_admin_setting=lambda key: None), session=session)
    assert result["exported_events"] == 0
    assert result["iceberg_audit_disabled"] is True
    assert record.call_args.args[3]["execution"] == "idle-execution"
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_supplement_daily_precedes_mart_and_quality_audit_is_retired():
    from ingestion_core.batch_controller import BATCHES
    batches = {b.name: b for b in BATCHES}
    assert {"data-supplement", "mart", "data-quality"}.isdisjoint(batches)
    assert dict(batches["ingestion"].env)["JANUS_UNIFIED_COLLECTION"] == "true"
    assert batches["market-screening"].dependencies == ("ingestion",)
    assert dict(batches["market-screening"].env)["MART_OPERATION"] == "market-cycle"

def test_mart_retention_precedes_core_retention_on_weekdays_and_weekends(monkeypatch):
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "true")
    friday = due_batches(datetime(2026, 10, 2, 14, 45, tzinfo=timezone.utc))
    assert not any(b.name == "core-cleanup" for _, b, _, _ in friday)
    saturday = {b.name: deps for _, b, _, deps in
                due_batches(datetime(2026, 10, 3, 14, 45, tzinfo=timezone.utc))}
    assert saturday["mart-cleanup"] == ["iceberg-compaction/2026-10-03/22"]
    assert saturday["core-cleanup"] == ["mart-cleanup/2026-10-03/22"]

def test_nightly_compaction_reuses_ingestion_job_with_isolated_execution_overrides(monkeypatch):
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "false")
    from ingestion_core.batch_controller import BATCHES
    batches = {batch.name: batch for batch in BATCHES}
    compaction = batches["iceberg-compaction"]
    assert compaction.job == "janus-ingestion-core"
    assert compaction.hours == (22,) and compaction.minute == 30
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
    before = datetime(2026, 10, 15, 14, 29, tzinfo=timezone.utc)  # 23:29 Taipei
    due = datetime(2026, 10, 15, 15, 30, tzinfo=timezone.utc)  # 23:30 Taipei
    assert not any(row[1].name == "iceberg-compaction" for row in due_batches(before))
    assert [key for key, batch, _, _ in due_batches(due) if batch.name == "iceberg-compaction"] == [
        "iceberg-compaction/2026-10-15/22"
    ]


def test_old_pending_core_cleanup_waits_for_new_mart_dependency(monkeypatch):
    monkeypatch.setenv("FINOPS_WEEKLY_MAINTENANCE", "false")
    from unittest.mock import MagicMock, Mock
    from ingestion_core import batch_controller as controller
    monkeypatch.setenv("GCP_PROJECT_ID", PROJECT)
    monkeypatch.setenv("BATCH_CONTROLLER_MODE", "active")
    monkeypatch.setenv("BATCH_CONTROLLER_NOT_BEFORE", "2026-10-01T00:00:00Z")
    key = "core-cleanup/2026-10-02/22"
    state = {"job": "janus-ingestion-core", "batch": "core-cleanup", "status": "pending",
             "dependencies": ["ingestion/2026-10-02/07"], "scheduled_at": "2026-10-02T22:30:00+08:00"}
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (True,)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[], [(key, state)], [("mart-cleanup/2026-10-02/22", "failed")]]
    cursor.fetchone.return_value = None
    record = Mock()
    monkeypatch.setattr(controller, "record", record)
    session = Mock()
    controller.run(now=datetime(2026, 10, 2, 16, tzinfo=timezone.utc),
                   control=SimpleNamespace(connection=connection, get_admin_setting=lambda key: None), session=session)
    updates = [call.args for call in record.call_args_list if call.args[2] == key]
    assert [args[4] for args in updates] == ["dependency_policy_updated", "waiting_dependency"]
    assert updates[0][3]["dependencies"] == ["mart-cleanup/2026-10-02/22"]
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
    rows = scheduled_batches(datetime(2026, 10, 5, 22, 30, tzinfo=timezone.utc), True)
    assert len([r for r in rows if r[1].name == "private"]) == 1
    assert not [r for r in rows if r[1].name == "mobile-ledger"]

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
