from datetime import datetime, timedelta, timezone

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs" / "ingestion-core"))

from packages.admin_api.batch_dashboard import dashboard
from packages.admin_api.service import AdminService, AdminConflictError, AdminValidationError

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def runtime():
    return {"mode": "active", "observed_at": NOW.isoformat(),
            "not_before": (NOW - timedelta(days=20)).isoformat(),
            "definitions": [{"name": name, "hours": [7], "minute": 30,
                "weekdays": days, "month_days": [], "dependencies": []}
                for name, days in [("ingestion", list(range(7))),
                                   ("data-quality", [5])]]}


def test_latest_seven_days_and_sort_do_not_hide_job_definitions():
    latest = {"ingestion": {"scheduled_at": NOW - timedelta(days=8), "status": "succeeded"},
              "data-quality": {"scheduled_at": NOW - timedelta(days=6), "status": "failed"}}
    result = dashboard(runtime(), latest, {}, NOW)
    assert result["items"][0]["name"] == "data-quality"
    ingestion = next(row for row in result["items"] if row["name"] == "ingestion")
    assert ingestion["latest"] is None and ingestion["overdue"] is True
    assert result["items"][-1]["cadence"] == "monthly"
    assert result["items"][-1]["can_start"] is False


def test_stale_schedule_and_paused_or_conditional_work_never_claim_overdue():
    stale = runtime()
    stale["observed_at"] = (NOW - timedelta(hours=3)).isoformat()
    assert all(row.get("overdue") is None for row in dashboard(stale, {}, {}, NOW)["items"])
    result = dashboard(runtime(), {}, {"ingestion": ({"paused": True}, 2)}, NOW)
    row = next(row for row in result["items"] if row["name"] == "ingestion")
    assert row["paused"] and row["overdue"] is None


def test_half_open_missing_start_and_weekend_are_not_success():
    fresh = runtime()
    fresh["not_before"] = NOW.isoformat()
    rows = dashboard(fresh, {}, {}, NOW)["items"]
    weekly = next(row for row in rows if row["name"] == "data-quality")
    assert weekly["cadence"] == "weekly" and weekly["overdue"] is None
    assert weekly["latest"] is None


class Control:
    def __init__(self):
        self.settings = {}
        self.writes = []

    def get_admin_setting(self, key):
        return self.settings.get(key)

    def put_admin_setting(self, *args, **kwargs):
        self.writes.append((args, kwargs))
        return 1


def test_actions_are_allowlisted_versioned_and_cannot_stop_running_work():
    control = Control()
    service = AdminService(control)
    service.batch_dashboard = lambda: {"items": [{"name": "ingestion", "control_version": 0,
        "can_start": True, "can_stop": False, "latest": {"status": "running"}}]}
    with pytest.raises(AdminValidationError):
        service.batch_action("arbitrary-job", "start", 0, actor="admin")
    with pytest.raises(AdminConflictError):
        service.batch_action("ingestion", "start", 1, actor="admin")
    with pytest.raises(AdminConflictError):
        service.batch_action("ingestion", "stop", 0, actor="admin", occurrence_id="wrong")
    assert control.writes == []
    service.batch_action("ingestion", "start", 0, actor="admin")
    assert control.writes[0][1]["expected_version"] == 0
    assert control.writes[0][1]["audit_resource"] == "batch_control"
    with pytest.raises(AdminValidationError):
        service.save_setting("batch_controller_runtime", {}, actor="admin")


def test_stop_targets_exact_execution_and_keeps_running_until_verified():
    from unittest.mock import MagicMock, Mock
    from ingestion_core.admin_batches import consume_requests
    from ingestion_core.batch_controller import Batch, _identity, API, PROJECT, REGION
    batch = Batch("ingestion", "janus-ingestion-core", (7,))
    execution = f"projects/{PROJECT}/locations/{REGION}/jobs/{batch.job}/executions/specific-run"
    state = {"status": "running", "job": batch.job, "execution": execution}
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (state,)
    control = Mock(connection=connection)
    control.get_admin_setting.return_value = ({"action": "stop", "occurrence_id": "selected"}, 1)
    session = Mock()
    session.post.return_value.status_code = 200
    consume_requests(control, [batch], NOW, NOW - timedelta(days=2), Mock(), Mock(), Mock(),
                     "tick", session, _identity, API)
    session.post.assert_called_once_with(API + execution + ":cancel", json={}, timeout=15)
    assert state["status"] == "running" and state["admin_stop_requested"] is True
    session.reset_mock()
    state["job"] = "janus-private-pipeline"
    consume_requests(control, [batch], NOW, NOW - timedelta(days=2), Mock(), Mock(), Mock(),
                     "tick", session, _identity, API)
    session.post.assert_not_called()


def test_pending_control_is_not_overwritten_and_wakeup_is_never_replayed():
    control = Control()
    service = AdminService(control, batch_wake=lambda: (_ for _ in ()).throw(TimeoutError()))
    service.batch_dashboard = lambda: {"items": [{"name": "ingestion", "control_version": 0,
        "can_start": True, "can_stop": False}]}
    result = service.batch_action("ingestion", "start", 0, actor="admin")
    assert result["status"] == "requested" and result["wake_status"] == "unconfirmed"
    assert len(control.writes) == 1
    control.settings["batch_control:ingestion"] = ({"action": "start"}, 0)
    with pytest.raises(AdminConflictError):
        service.batch_action("ingestion", "pause", 0, actor="admin")


def test_log_is_not_borrowed_from_another_occurrence():
    evidence = runtime()
    evidence["latest_logs"] = {"ingestion": {"occurrence_id": "other", "status": "succeeded"}}
    row = next(row for row in dashboard(evidence, {"ingestion": {
        "occurrence_id": "current", "scheduled_at": NOW, "status": "failed"}}, {}, NOW)["items"]
        if row["name"] == "ingestion")
    assert row["latest"]["status"] == "failed" and row["latest_log"] is None


def test_batch_routes_reject_user_tokens_and_never_accept_arbitrary_job_or_env():
    from unittest.mock import Mock
    from fastapi.testclient import TestClient
    from services.api.app import create_app
    service = Mock()
    service.batch_dashboard.return_value = {"items": []}
    claims = {"iss": "https://accounts.google.com", "aud": "admin-client", "sub": "admin",
              "email": "admin@example.com", "email_verified": True, "exp": 1900000000}
    api = TestClient(create_app(repository=Mock(), store=Mock(), core=Mock(), query_core=Mock(),
        public=Mock(), private_recalculator=Mock(), admin_service=service,
        admin_audience="admin-client", admin_emails=frozenset({"admin@example.com"}),
        admin_verifier=lambda token, audience: claims if token == "admin" else {**claims, "aud": "user-client"}))
    url = "/api/v1/admin/batches/ingestion/actions"
    assert api.get("/api/v1/admin/batch-dashboard").status_code == 401
    assert api.post(url, json={"action": "start", "expected_version": 0},
                    headers={"Authorization": "Bearer user"}).status_code == 401
    service.batch_action.assert_not_called()
    headers = {"Authorization": "Bearer admin"}
    assert api.get("/api/v1/admin/batch-dashboard", headers=headers).status_code == 200
    assert api.post(url, json={"action": "start", "expected_version": 0,
                              "job": "arbitrary", "env": {"unsafe": "value"}}, headers=headers).status_code == 422
    service.batch_action.assert_not_called()


def test_active_sources_omit_retired_collection_configs():
    from ingestion_core import SQLiteControlPlane, CollectionConfig, DataState
    control = SQLiteControlPlane()
    try:
        control.put_collection_config(CollectionConfig("live", "ohlcv", ("twse",), frozenset({"symbol"})))
        control.put_collection_config(CollectionConfig("old", "ohlcv", ("old-provider",), frozenset({"symbol"}), enabled=False))
        for source in ("twse", "old-provider"):
            control.record_health(source, "ohlcv", state=DataState.UNAVAILABLE, latency_ms=1, fetched_at=NOW)
        assert [row["source_id"] for row in AdminService(control).source_health(active_only=True)] == ["twse"]
    finally:
        control.close()


def test_manual_start_before_first_slot_uses_previous_evening_and_cannot_duplicate():
    import json
    from unittest.mock import MagicMock, Mock
    from ingestion_core.admin_batches import consume_requests
    from ingestion_core.batch_controller import Batch, due_batches, occurrence_env, _identity, API
    now = datetime(2026, 10, 23, 22, tzinfo=timezone.utc)  # Saturday 06:00 Taipei.
    batch = Batch("ingestion", "janus-ingestion-core", (7, 23))
    control = Mock(connection=MagicMock())
    control.get_admin_setting.return_value = ({"action": "start"}, 1)
    cursor = control.connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    def invoke():
        consume_requests(control, [batch], now, now - timedelta(days=4),
            lambda point: due_batches(point, [batch]), occurrence_env, Mock(), "tick", Mock(), _identity, API)
    invoke()
    inserted = next(call.args[1] for call in cursor.execute.call_args_list
                    if "INSERT INTO control.batch_occurrences" in call.args[0])
    state = json.loads(inserted[2])
    assert state["source_slot"] == "2026-10-23T23:30:00+08:00"
    assert state["status"] == "pending" and state["job"] == batch.job
    cursor.reset_mock()
    cursor.fetchone.return_value = (1,)
    invoke()
    inserted = next(call.args[1] for call in cursor.execute.call_args_list
                    if "INSERT INTO control.batch_occurrences" in call.args[0])
    assert json.loads(inserted[2])["reason"] == "duplicate_active_work"


def test_monthly_completion_proof_is_used_without_displaying_old_logs():
    evidence = runtime()
    evidence["definitions"][0]["month_days"] = [1]
    evidence["not_before"] = (NOW - timedelta(days=30)).isoformat()
    completed = datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc)  # October 1, 07:30 Taipei.
    row = next(row for row in dashboard(evidence, {"ingestion": {
        "scheduled_at": completed, "status": "succeeded"}}, {}, NOW)["items"] if row["name"] == "ingestion")
    assert row["cadence"] == "monthly" and row["latest"] is None
    assert row["overdue"] is False


def test_running_operation_metadata_exposes_only_verified_execution_identity():
    from types import SimpleNamespace
    from ingestion_core.batch_controller import poll_job, PROJECT, REGION
    execution = f"projects/{PROJECT}/locations/{REGION}/jobs/janus-ingestion-core/executions/specific-run"
    operation = f"projects/{PROJECT}/locations/{REGION}/operations/operation-one"
    body = {"done": False, "metadata": {"name": execution, "startTime": "2026-10-23T12:00:00Z"}}
    session = SimpleNamespace(get=lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: body))
    result = poll_job(session, {"status": "running", "job": "janus-ingestion-core", "operation": operation})
    assert result["execution"] == execution and result["status"] == "running"
    body["metadata"]["name"] = execution.replace("janus-ingestion-core", "janus-private-pipeline")
    with pytest.raises(ValueError):
        poll_job(session, {"status": "running", "job": "janus-ingestion-core", "operation": operation})


def test_scoped_collection_claim_cannot_take_an_older_unrelated_request():
    from ingestion_core import SQLiteControlPlane, CollectionConfig, Stock, TriggerType
    control = SQLiteControlPlane()
    try:
        control.upsert_stock(Stock("2330", "台積電", "TWSE"))
        control.put_collection_config(CollectionConfig("ohlcv", "ohlcv", ("twse",), frozenset({"symbol"})), ("2330",))
        older = control.enqueue_collection("ohlcv", ("2330",))
        selected = control.enqueue_collection("ohlcv", ("2330",))
        claimed = control.claim_execution("worker", trigger_type=TriggerType.COLLECTION,
                                          execution_id=selected.execution_id)
        assert claimed.execution_id == selected.execution_id
        assert control.get_execution(older.execution_id).status.value == "queued"
    finally:
        control.close()


def test_manual_queue_env_is_bound_to_the_selected_request_and_has_no_schedule_slot():
    import json
    from uuid import uuid4
    from unittest.mock import MagicMock
    from ingestion_core.admin_batches import enqueue_queued_worker
    from ingestion_core.batch_controller import Batch, due_batches, occurrence_env
    selected = uuid4()
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(selected, 0), None, ("inserted",)]
    batch = Batch("collection-queue", "janus-ingestion-core", (0,), manual_only=True,
                  env=(("QUEUE_CONSUMER", "true"),))
    assert due_batches(NOW, [batch]) == []
    assert enqueue_queued_worker(connection, batch, NOW, occurrence_env) == "queued"
    inserted = next(call.args[1] for call in cursor.execute.call_args_list
                    if "INSERT INTO control.batch_occurrences" in call.args[0])
    state = json.loads(inserted[2])
    assert dict(state["env"])["QUEUE_EXECUTION_ID"] == str(selected)
    assert state["queued_execution_id"] == str(selected)


def test_scoped_mart_claim_uses_only_the_target_uuid_without_broad_table_access():
    import sys
    from uuid import uuid4
    from unittest.mock import MagicMock
    sys.path.insert(0, str(Path(__file__).parents[1] / "jobs" / "intelligence-mart"))
    from intelligence_mart.runtime import PostgreSQLAnalysisQueue
    selected = str(uuid4())
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (selected, "ohlcv", ["2330"], 0, {}, "queued")
    claimed = PostgreSQLAnalysisQueue(connection, execution_id=selected).claim("worker")
    assert claimed.execution_id == selected
    query, params = cursor.execute.call_args_list[0].args
    assert "execution_id=%s::uuid" in query and "trigger_type='analysis'" in query
    assert "SELECT *" not in query and params == (selected,)
    with pytest.raises(ValueError):
        PostgreSQLAnalysisQueue(connection, execution_id="arbitrary-sql")


def test_p02_dispatch_five_day_boundary_preserves_safe_lease_checks():
    from unittest.mock import MagicMock
    import pytest
    from ingestion_core.admin_batches import enqueue_queued_worker
    from ingestion_core.batch_controller import Batch, occurrence_env

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    analysis = Batch("analysis-queue", "janus-intelligence-mart", (0,), manual_only=True)
    assert enqueue_queued_worker(connection, analysis, NOW, occurrence_env) == "queue_empty"
    sql, params = cursor.execute.call_args_list[0].args
    assert "e.requested_at >= now() - interval '5 days'" in sql
    assert "interval '7 days'" not in sql and "interval '30 days'" not in sql
    assert "e.claimed_until IS NULL" in sql
    assert "e.started_at IS NULL" in sql
    assert "NOT EXISTS (SELECT 1 FROM control.execution_items" in sql
    assert "control.core_ready_events" in sql
    assert "r.analysis_execution_id=e.execution_id" in sql
    assert "AND e.finished_at IS NULL" in sql
    assert "control.batch_occurrences" in sql
    assert params == ("analysis",)

    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_queued_worker(connection, analysis, NOW, occurrence_env,
                              historical_recovery=True, target_execution_ref="e" * 32)
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_queued_worker(connection, analysis, NOW, occurrence_env,
                              historical_recovery=True)
    collection = Batch("collection-queue", "janus-ingestion-core", (0,), manual_only=True)
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_queued_worker(connection, collection, NOW, occurrence_env,
                              historical_recovery=True)


def test_p02_controller_historical_override_is_rejected(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    from ingestion_core.admin_batches import enqueue_manual_queues
    from ingestion_core.batch_controller import Batch, occurrence_env

    analysis = Batch("analysis-queue", "janus-intelligence-mart", (0,), manual_only=True)
    collection = Batch("collection-queue", "janus-ingestion-core", (0,), manual_only=True)
    connection = MagicMock()
    cur = connection.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = None
    monkeypatch.setenv("JANUS_P02_ANALYSIS_RECOVERY", "one-shot")
    monkeypatch.setenv("JANUS_P02_ANALYSIS_EXECUTION_REF", "f" * 32)
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_manual_queues(connection, [collection, analysis], set(), NOW, occurrence_env)
    cur.execute.assert_not_called()

    monkeypatch.setenv("JANUS_P02_ANALYSIS_EXECUTION_REF", "")
    with pytest.raises(ValueError, match="historical recovery disabled"):
        enqueue_manual_queues(connection, [analysis], set(), NOW, occurrence_env)
    monkeypatch.delenv("JANUS_P02_ANALYSIS_RECOVERY")
    enqueue_manual_queues(connection, [collection, analysis], set(), NOW, occurrence_env)
    selectors = [call.args[1] for call in cur.execute.call_args_list
                 if call.args and "SELECT e.execution_id,e.retry_count" in call.args[0]]
    assert selectors == [("collection",), ("analysis",)]
