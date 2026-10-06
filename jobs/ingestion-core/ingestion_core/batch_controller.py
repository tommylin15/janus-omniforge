"""Hourly dev controller; never wait for or cancel child jobs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
import re
from uuid import NAMESPACE_URL, uuid5
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from packages.mobile_ledger_queue import MobileLedgerQueueError, probe_mobile_ledger_queue

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
API = "https://run.googleapis.com/v2/"


@dataclass(frozen=True)
class Batch:
    name: str
    job: str
    hours: tuple[int, ...]
    weekdays: tuple[int, ...] = tuple(range(7))
    dependencies: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    exclusive_jobs: tuple[str, ...] = ()
    minute: int = 30
    month_days: tuple[int, ...] = ()
    catch_up: bool = True


BATCHES = (
    Batch("ingestion", "janus-ingestion-core", (7,), env=(("QUEUE_CONSUMER", "false"), ("MART_JOB", ""), ("ICEBERG_MAINTENANCE_MODE", ""))),
    Batch("data-supplement", "janus-ingestion-core", (8,), dependencies=("ingestion",),
          env=(("JANUS_DATA_SUPPLEMENT_MODE", "daily"), ("JANUS_DATA_SUPPLEMENT_SYMBOLS", ""),
               ("QUEUE_CONSUMER", "false"), ("MART_JOB", ""), ("ICEBERG_MAINTENANCE_MODE", ""))),
    Batch("mart", "janus-intelligence-mart", (9,), tuple(range(5)), ("ingestion", "data-supplement"), (("MART_OPERATION", "queue"), ("MART_AI_ENABLED", "false")), minute=0),
    Batch("specialist-retrain", "janus-intelligence-mart", (10,), dependencies=("ingestion", "data-supplement"),
          env=(("MART_OPERATION", "specialist-retrain"), ("MART_OOS_EVALUATION", "true"), ("MART_AI_ENABLED", "false")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart"), month_days=(1,)),
    Batch("data-quality", "janus-ingestion-core", (12,), (5,),
          env=(("JANUS_DATA_SUPPLEMENT_MODE", "quality"), ("QUEUE_CONSUMER", "false"), ("MART_JOB", ""),
               ("ICEBERG_MAINTENANCE_MODE", "")), exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart")),
    Batch("private", "janus-private-pipeline", (21,), tuple(range(5)), ("ingestion",)),
    Batch("mobile-ledger", "janus-private-pipeline", tuple(range(24)), catch_up=False),
    Batch("core-cleanup", "janus-ingestion-core", (23,), dependencies=("mart-cleanup",),
          env=(("ICEBERG_MAINTENANCE_MODE", "retention-apply"), ("QUEUE_CONSUMER", "false"), ("MART_JOB", "")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")),
    Batch("mart-cleanup", "janus-intelligence-mart", (23,), dependencies=("ingestion",),
          env=(("MART_OPERATION", "retention"), ("MART_RETENTION_MODE", "apply"), ("MART_AI_ENABLED", "false")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")),
)


def due_batches(now: datetime, batches=BATCHES):
    """Catch up elapsed slots today. Each hour has a separate occurrence identity."""
    if now.tzinfo is None:
        raise ValueError("controller clock must include a timezone")
    local = now.astimezone(ZoneInfo("Asia/Taipei"))
    by_name = {batch.name: batch for batch in batches}
    if len(by_name) != len(batches):
        raise ValueError("duplicate batch names")
    result = []
    for batch in batches:
        if not batch.hours or any(hour not in range(24) for hour in batch.hours) or len(set(batch.hours)) != len(batch.hours):
            raise ValueError("invalid batch hours")
        if any(day not in range(7) for day in batch.weekdays):
            raise ValueError("invalid batch weekdays")
        if batch.minute not in range(60):
            raise ValueError("invalid batch minute")
        if any(day not in range(1, 32) for day in batch.month_days):
            raise ValueError("invalid batch month day")
        if batch.month_days and local.day not in batch.month_days:
            continue
        if local.weekday() not in batch.weekdays:
            continue
        for hour in sorted(batch.hours):
            if not batch.catch_up and hour != local.hour:
                continue
            slot = local.replace(hour=hour, minute=batch.minute, second=0, microsecond=0)
            if slot > local:
                continue
            dependencies = []
            for name in batch.dependencies:
                dependency = by_name[name]
                preceding = [value for value in dependency.hours if value < hour or (value == hour and dependency.minute <= batch.minute)]
                if local.weekday() not in dependency.weekdays or not preceding:
                    raise ValueError("dependency has no preceding slot on this weekday")
                dependencies.append(f"{name}/{local.date().isoformat()}/{max(preceding):02d}")
            result.append((f"{batch.name}/{local.date().isoformat()}/{hour:02d}", batch, slot, dependencies))
    return sorted(result, key=lambda item: (item[2], item[0]))


def scheduled_batches(now: datetime, mobile_pending: bool) -> list[tuple[str, Batch, datetime, list[str]]]:
    rows = due_batches(now)
    private_slots = {slot for _, batch, slot, _ in rows if batch.name == "private"}
    return [
        row for row in rows
        if row[1].name != "mobile-ledger" or (mobile_pending and row[2] not in private_slots)
    ]


def resource(job):
    if job not in {batch.job for batch in BATCHES}:
        raise ValueError("job is outside the dev allowlist")
    return f"projects/{PROJECT}/locations/{REGION}/jobs/{job}"


def _read(session, path):
    response = session.get(API + path, timeout=15)
    if response.status_code != 200:
        raise RuntimeError("Cloud Run read failed")
    return response.json()


def _identity(name, kind, job=None):
    prefixes = [f"projects/{project}/locations/{REGION}/" for project in (PROJECT, "131494961796")]
    suffix = f"jobs/{job}/executions/" if kind == "execution" else "operations/"
    if not isinstance(name, str) or not any(name.startswith(prefix + suffix) for prefix in prefixes):
        raise ValueError("unexpected Cloud Run identity")
    tail = name.split(suffix, 1)[-1]
    if not tail or "/" in tail or "?" in tail or "#" in tail:
        raise ValueError("invalid Cloud Run identity suffix")
    return name


def execution_finished(execution):
    return bool(execution.get("completionTime")) or any(
        condition.get("type") == "Completed" and condition.get("state") in {"CONDITION_SUCCEEDED", "CONDITION_FAILED"}
        for condition in execution.get("conditions", []))


def poll_job(session, state):
    """Read once per tick; ambiguous dispatch requires manual reconciliation."""
    if state["status"] == "ambiguous":
        return state
    if not state.get("operation") and not state.get("execution"):
        return {**state, "status": "ambiguous", "reason": "dispatch_response_missing"}
    if state.get("execution"):
        execution = _read(session, _identity(state["execution"], "execution", state["job"]))
    else:
        operation = _read(session, _identity(state["operation"], "operation"))
        if not operation.get("done"):
            return {**state, "status": "running"}
        if operation.get("error"):
            return {**state, "status": "failed", "reason": "cloud_run_operation_failed"}
        execution = operation.get("response", {})
        state = {**state, "execution": _identity(execution.get("name"), "execution", state["job"])}
    if not execution_finished(execution):
        return {**state, "status": "running"}
    failed_condition = any(condition.get("type") == "Completed" and condition.get("state") == "CONDITION_FAILED"
                           for condition in execution.get("conditions", []))
    succeeded = execution.get("succeededCount") == 1 and not execution.get("failedCount") and not execution.get("cancelledCount") and not failed_condition
    return {**state, "status": "succeeded" if succeeded else "failed", "completion_time": execution.get("completionTime")}


def job_active(session, job):
    # ponytail: inspect up to 2,000 executions; beyond this, block and review the cap.
    query, seen = {"pageSize": 100}, set()
    for _ in range(20):
        response = _read(session, resource(job) + "/executions?" + urlencode(query))
        if any(not execution_finished(item) for item in response.get("executions", [])):
            return True
        token = response.get("nextPageToken")
        if not token:
            return False
        if token in seen:
            return True
        seen.add(token)
        query["pageToken"] = token
    return True


def dispatch_job(session, batch):
    """Caller must commit dispatch intent first; never automatically retry this POST."""
    response = session.post(API + resource(batch.job) + ":run", json={"overrides": {
        "taskCount": 1, "containerOverrides": [{"env": [{"name": name, "value": value} for name, value in batch.env]}]}}, timeout=15)
    if response.status_code != 200:
        raise RuntimeError("dispatch response unavailable; reconcile before retry")
    return _identity(response.json().get("name"), "operation")


def record(connection, tick, key, state, action, *, update=True):
    from hashlib import sha256
    state_hash = sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    event_id = str(uuid5(NAMESPACE_URL, f"janus-batch-v1/{tick}/{key}/{action}/{state_hash}"))
    payload = {"schema_version": "batch-event-v1", "tick": tick, "occurrence_id": key, "action": action,
               "controller_execution": os.environ.get("CLOUD_RUN_EXECUTION", ""), **state}
    with connection.transaction(), connection.cursor() as cursor:
        if update:
            cursor.execute("UPDATE control.batch_occurrences SET state=%s::jsonb,updated_at=now() WHERE occurrence_id=%s", (json.dumps(state), key))
        cursor.execute("INSERT INTO control.batch_event_outbox(event_id,payload) VALUES (%s,%s::jsonb) ON CONFLICT DO NOTHING", (event_id, json.dumps(payload)))


def export_events(connection, core):
    """Acknowledge the outbox only after an idempotent Iceberg commit and readback."""
    import pyarrow as pa
    from pyiceberg.schema import Schema
    from pyiceberg.types import NestedField, StringType, TimestamptzType
    from pyiceberg.expressions import In
    identifier = "ops.batch_events_v1"
    core.catalog.create_namespace_if_not_exists("ops")
    if not core.catalog.table_exists(identifier):
        core.catalog.create_table(identifier, schema=Schema(
            NestedField(1, "event_id", StringType(), required=True),
            NestedField(2, "recorded_at", TimestamptzType(), required=True),
            NestedField(3, "payload_json", StringType(), required=True), identifier_field_ids=[1]),
            location=core.warehouse + "/batch_events_v1")
    with connection.cursor() as cursor:
        cursor.execute("SELECT event_id,created_at,payload FROM control.batch_event_outbox WHERE exported_at IS NULL ORDER BY created_at,event_id LIMIT 200")
        pending = cursor.fetchall()
    if not pending:
        return 0
    schema = pa.schema([pa.field("event_id", pa.string(), nullable=False), pa.field("recorded_at", pa.timestamp("us", tz="UTC"), nullable=False), pa.field("payload_json", pa.string(), nullable=False)])
    rows = [{"event_id": str(key), "recorded_at": created, "payload_json": json.dumps(payload, sort_keys=True)} for key, created, payload in pending]
    table = core.catalog.load_table(identifier)
    table.upsert(pa.Table.from_pylist(rows, schema=schema), join_cols=["event_id"])
    readback = table.scan(row_filter=In("event_id", [row["event_id"] for row in rows])).to_arrow().to_pylist()
    if {row["event_id"]: row["payload_json"] for row in readback} != {row["event_id"]: row["payload_json"] for row in rows}:
        raise RuntimeError("Iceberg batch log readback mismatch")
    with connection.transaction(), connection.cursor() as cursor:
        cursor.executemany("UPDATE control.batch_event_outbox SET exported_at=now() WHERE event_id=%s", [(key,) for key, _, _ in pending])
    return len(pending)


def manual_retrain_dependencies(connection, now: datetime, batch=None):
    """Use the newest dependency date and wait until that day's full pair succeeds."""
    batch = batch or next(batch for batch in BATCHES if batch.name == "specialist-retrain")
    cutoff = now - timedelta(days=7)
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT scheduled_at
                 FROM control.batch_occurrences
                WHERE state->>'batch'=ANY(%s)
                  AND scheduled_at >= %s
                  AND scheduled_at <= %s
                ORDER BY scheduled_at DESC
                LIMIT 32""",
            (list(batch.dependencies), cutoff, now),
        )
        rows = cursor.fetchall()
    if not rows:
        raise RuntimeError("manual retrain requires recent dependency occurrences")
    local_dates = []
    for row in rows:
        scheduled_at = row[0]
        if scheduled_at.tzinfo is None:
            raise RuntimeError("dependency occurrence timestamp is naive")
        local_dates.append(scheduled_at.astimezone(ZoneInfo("Asia/Taipei")).date())
    dependency_date = max(local_dates)
    by_name = {item.name: item for item in BATCHES}
    dependencies = []
    for name in batch.dependencies:
        dependency = by_name[name]
        if dependency_date.weekday() not in dependency.weekdays:
            raise RuntimeError("manual retrain dependency is not scheduled on selected date")
        preceding = [value for value in dependency.hours
                     if value < batch.hours[0] or (value == batch.hours[0] and dependency.minute <= batch.minute)]
        if not preceding:
            raise RuntimeError("manual retrain dependency has no preceding slot")
        dependencies.append(f"{name}/{dependency_date.isoformat()}/{max(preceding):02d}")
    return dependencies


def insert_manual_retrain(connection, now: datetime, request_id: str):
    """Persist one idempotent manual retrain occurrence behind controller dependency fences."""
    batch = next(batch for batch in BATCHES if batch.name == "specialist-retrain")
    key = f"{batch.name}/manual/{request_id}"
    with connection.cursor() as cursor:
        cursor.execute("SELECT state FROM control.batch_occurrences WHERE occurrence_id=%s", (key,))
        existing = cursor.fetchone()
    if existing is not None:
        state = existing[0]
        if state.get("batch") != batch.name or state.get("origin") != "manual" or state.get("request_id") != request_id:
            raise RuntimeError("manual occurrence identity conflict")
        return key
    dependencies = manual_retrain_dependencies(connection, now, batch)
    state = {
        "job": batch.job,
        "batch": batch.name,
        "status": "pending",
        "dependencies": dependencies,
        "scheduled_at": now.isoformat(),
        "origin": "manual",
        "request_id": request_id,
    }
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
            (key, now, json.dumps(state)),
        )
    return key


def run(*, now=None, session=None, control=None, core=None):
    from datetime import timezone
    from .__main__ import _control_plane, _iceberg_core
    if os.environ.get("GCP_PROJECT_ID") != PROJECT:
        raise ValueError("batch controller is restricted to the existing dev project")
    now = now or datetime.now(timezone.utc)
    mode = os.environ.get("BATCH_CONTROLLER_MODE", "observe")
    if mode not in {"observe", "active", "seed", "manual", "mobile-probe"}:
        raise ValueError("unsupported controller mode")
    if mode == "mobile-probe":
        try:
            result = probe_mobile_ledger_queue(write=False)
        except MobileLedgerQueueError as error:
            print(json.dumps({"mobile_ledger_probe": "failed", "error_code": str(error)}, sort_keys=True))
            raise
        return {"status": result["status"], "mobile_ledger_pending": bool(result["pending"])}
    manual_request_id = ""
    if mode == "manual":
        manual_request_id = os.environ.get("BATCH_CONTROLLER_MANUAL_REQUEST_ID", "")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", manual_request_id) is None:
            raise ValueError("invalid manual request id")
    not_before = None
    if mode == "active":
        not_before = datetime.fromisoformat(os.environ["BATCH_CONTROLLER_NOT_BEFORE"].replace("Z", "+00:00"))
        if not_before.tzinfo is None:
            raise ValueError("controller activation must include a timezone")
    if now.tzinfo is None:
        raise ValueError("controller clock must include a timezone")
    utc = now.astimezone(timezone.utc)
    tick = utc.replace(minute=utc.minute // 10 * 10, second=0, microsecond=0).isoformat()
    owns_control, owns_core = control is None, core is None
    control = control or _control_plane()
    connection = control.connection
    locked = False
    try:
        locked = connection.execute("SELECT pg_try_advisory_lock(1835102836,3)").fetchone()[0]
        if not locked:
            return {"status": "controller_busy"}
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
            session = AuthorizedSession(credentials)
        if mode == "observe":
            record(connection, tick, "controller", {"status": "observe", "model_calls": 0}, "tick", update=False)
            core = core or _iceberg_core(PROJECT + "-dev-core")
            return {"status": "observe", "tick": tick, "exported_events": export_events(connection, core), "model_calls": 0}
        if mode == "seed":
            seeds = json.loads(os.environ["BATCH_CONTROLLER_SEED_EXECUTIONS"])
            if not isinstance(seeds, list) or not 1 <= len(seeds) <= 3:
                raise ValueError("seed requires 1..3 verified existing executions")
            due = {batch.name: (key, batch, slot, dependencies) for key, batch, slot, dependencies in due_batches(now)
                   if batch.name in {"ingestion", "mart", "private"}}
            for seed in seeds:
                key, batch, slot, dependencies = due[seed["batch"]]
                name = _identity(seed["execution"], "execution", batch.job)
                execution = _read(session, name)
                created = datetime.fromisoformat(execution["createTime"].replace("Z", "+00:00"))
                if not 0 <= (created - slot).total_seconds() <= 900:
                    raise ValueError("seed execution does not match the scheduled slot")
                state = poll_job(session, {"job": batch.job, "batch": batch.name, "status": "running", "execution": name,
                                          "dependencies": dependencies, "scheduled_at": slot.isoformat(), "origin": "previous_scheduler"})
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute("INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (key, slot, json.dumps(state)))
                record(connection, tick, key, state, "adopt_previous_scheduler", update=False)
            core = core or _iceberg_core(PROJECT + "-dev-core")
            return {"status": "seeded", "exported_events": export_events(connection, core), "model_calls": 0}
        with connection.cursor() as cursor:
            cursor.execute("SELECT occurrence_id,state FROM control.batch_occurrences WHERE state->>'status' IN ('dispatching','running','ambiguous') ORDER BY scheduled_at LIMIT 101")
            active = cursor.fetchall()
        if len(active) > 100:
            raise RuntimeError("active occurrence limit exceeded; dispatch blocked")
        for key, state in active:
            try:
                updated = poll_job(session, state)
                record(connection, tick, key, updated, "reconcile")
            except Exception:
                # A read failure must never release the running-job fence.
                record(connection, tick, key, state, "cloud_status_unavailable", update=False)
        manual_key = None
        mobile_pending: bool | None = False
        if mode == "manual":
            manual_key = insert_manual_retrain(connection, now, manual_request_id)
        else:
            try:
                mobile_pending = bool(probe_mobile_ledger_queue(write=False)["pending"])
            except MobileLedgerQueueError:
                mobile_pending = None
                record(connection, tick, "mobile-ledger", {"status": "unavailable"}, "mobile_queue_unavailable", update=False)
            for key, batch, slot, dependencies in scheduled_batches(now, mobile_pending is True):
                if slot < not_before:
                    continue
                state = {"job": batch.job, "batch": batch.name, "status": "pending", "dependencies": dependencies,
                         "scheduled_at": slot.isoformat()}
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute("INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (key, slot, json.dumps(state)))
        # Persisted pending slots survive midnight and controller restarts.
        with connection.cursor() as cursor:
            if mode == "manual":
                cursor.execute("SELECT occurrence_id,state FROM control.batch_occurrences WHERE occurrence_id=%s AND state->>'status'='pending' LIMIT 1", (manual_key,))
            else:
                cursor.execute("SELECT occurrence_id,state FROM control.batch_occurrences WHERE state->>'status'='pending' ORDER BY scheduled_at,occurrence_id LIMIT 101")
            pending = cursor.fetchall()
        if len(pending) > 100:
            raise RuntimeError("pending occurrence limit exceeded; dispatch blocked")
        batches = {batch.name: batch for batch in BATCHES}
        for key, state in pending:
            batch = batches[state["batch"]]
            if batch.name == "mobile-ledger":
                if mobile_pending is None:
                    record(connection, tick, key, state, "mobile_queue_unavailable", update=False)
                    continue
                if mobile_pending is False:
                    state = {**state, "status": "skipped", "reason": "queue_empty"}
                    record(connection, tick, key, state, "mobile_queue_empty")
                    continue
            dependencies = state["dependencies"]
            if state.get("origin") == "manual":
                dependencies = manual_retrain_dependencies(connection, now, batch)
                if dependencies != state["dependencies"]:
                    state = {**state, "dependencies": dependencies}
                    record(connection, tick, key, state, "manual_dependency_updated")
            else:
                # Reconcile scheduled pending slots created before a dependency-policy change.
                dependencies = next(row[3] for row in due_batches(datetime.fromisoformat(state["scheduled_at"])) if row[0] == key)
                if dependencies != state["dependencies"]:
                    state = {**state, "dependencies": dependencies}
                    record(connection, tick, key, state, "dependency_policy_updated")
            with connection.cursor() as cursor:
                statuses = {}
                if dependencies:
                    cursor.execute("SELECT occurrence_id,state->>'status' FROM control.batch_occurrences WHERE occurrence_id=ANY(%s)", (dependencies,))
                    statuses = dict(cursor.fetchall())
                cursor.execute("SELECT 1 FROM control.batch_occurrences WHERE state->>'job'=%s AND state->>'status' IN ('dispatching','running','ambiguous') LIMIT 1", (batch.job,))
                busy = cursor.fetchone() is not None
            if any(statuses.get(dependency) != "succeeded" for dependency in dependencies):
                record(connection, tick, key, state, "waiting_dependency", update=False)
                continue
            if busy or any(job_active(session, job) for job in (batch.exclusive_jobs or (batch.job,))):
                record(connection, tick, key, state, "job_busy", update=False)
                continue
            state = {**state, "status": "dispatching"}
            record(connection, tick, key, state, "dispatch_intent")
            try:
                operation = dispatch_job(session, batch)
                state = {**state, "status": "running", "operation": operation}
            except Exception:
                state = {**state, "status": "ambiguous", "reason": "inspect_cloud_execution_before_manual_recovery"}
            record(connection, tick, key, state, "dispatch_result")
        core = core or _iceberg_core(PROJECT + "-dev-core")
        record(connection, tick, "controller", {"status": "tick_completed", "model_calls": 0,
               "execution": os.environ.get("CLOUD_RUN_EXECUTION", "")}, "tick", update=False)
        return {"status": "tick_completed", "tick": tick, "exported_events": export_events(connection, core), "model_calls": 0}
    finally:
        if locked:
            connection.execute("SELECT pg_advisory_unlock(1835102836,3)")
        if owns_core and core is not None:
            core.close()
        if owns_control:
            control.close()


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except Exception as error:
        print(json.dumps({"status": "failed", "error_code": type(error).__name__.upper()}))
        raise SystemExit(1) from None
