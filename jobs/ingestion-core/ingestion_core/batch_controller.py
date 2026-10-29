"""Two-hour dev controller with bounded, lock-free waits between chain steps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
import re
from uuid import NAMESPACE_URL, uuid5
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from time import monotonic, sleep

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
    # Explicit per-slot waiver, not a global bypass of data-readiness guards.
    independent_hours: tuple[int, ...] = ()
    manual_only: bool = False


BATCHES = (
    Batch("ledger-backup", "janus-batch-controller", (0,)),
    Batch("ingestion", "janus-ingestion-core", (18,), tuple(range(5)), env=(("JANUS_UNIFIED_COLLECTION", "true"), ("INGESTION_DATASETS", ""), ("INGESTION_DATE", ""), ("JANUS_DATA_SUPPLEMENT_MODE", ""), ("QUEUE_CONSUMER", "false"), ("MART_JOB", ""), ("ICEBERG_MAINTENANCE_MODE", ""))),
    Batch("market-screening", "janus-intelligence-mart", (18,), tuple(range(5)), ("ingestion",),
          (("MART_OPERATION", "market-cycle"), ("QUEUE_EXECUTION_ID", ""), ("MART_OOS_EVALUATION", "false"),
           ("MART_AI_ENABLED", "false"), ("MART_RISK_SHADOW_ENABLED", "false")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart")),
    Batch("private", "janus-private-pipeline", (18,), tuple(range(5)),
          ("market-screening",)),
    Batch("serving-prune", "janus-ingestion-core", (18,), tuple(range(5)), ("private",),
          (("JANUS_SERVING_PRUNE", "true"),)),
    Batch("postgres-maintenance", "janus-batch-controller", (22,), (5,), ("core-cleanup",)),
    # Independent daily 48h Stage TTL: reuse existing ingestion Job, not weekly Iceberg scans.
    Batch("stage-cleanup", "janus-ingestion-core", (22,),
          env=(("ICEBERG_MAINTENANCE_MODE", "stage-only-apply"),
               ("QUEUE_CONSUMER", "false"), ("MART_JOB", ""),
               ("JANUS_DATA_SUPPLEMENT_MODE", ""), ("JANUS_CONTROL_MIGRATION", ""),
               ("JANUS_SERVING_SCHEMA_MIGRATION", "")),
          exclusive_jobs=("janus-ingestion-core",)),
    Batch("mobile-ledger", "janus-private-pipeline", tuple(range(0, 24, 2)),
          env=(("MOBILE_LEDGER_ONLY", "true"),), catch_up=False),
    # This is an execution override of the existing ingestion Job, not another Scheduler or Cloud Run Job.
    # Serial ordering avoids compaction racing with Mart/Core retention at the same 22:30 slot.
    Batch("iceberg-compaction", "janus-ingestion-core", (22,), (5,),
          env=(("ICEBERG_MAINTENANCE_MODE", "compact-nightly"), ("QUEUE_CONSUMER", "false"),
               ("MART_JOB", ""), ("JANUS_DATA_SUPPLEMENT_MODE", ""), ("JANUS_CONTROL_MIGRATION", ""),
               ("JANUS_SERVING_SCHEMA_MIGRATION", "")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")),
    Batch("core-cleanup", "janus-ingestion-core", (22,), (5,), dependencies=("mart-cleanup",),
          env=(("ICEBERG_MAINTENANCE_MODE", "retention-apply"), ("QUEUE_CONSUMER", "false"), ("MART_JOB", "")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")),
    Batch("mart-cleanup", "janus-intelligence-mart", (22,), (5,), dependencies=("iceberg-compaction",),
          env=(("MART_OPERATION", "retention"), ("MART_RETENTION_MODE", "apply"), ("MART_AI_ENABLED", "false")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")),
    Batch("collection-queue", "janus-ingestion-core", (0,), manual_only=True,
          env=(("QUEUE_CONSUMER", "true"), ("MART_JOB", ""),
               ("JANUS_DATA_SUPPLEMENT_MODE", ""), ("ICEBERG_MAINTENANCE_MODE", "")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart")),
    Batch("analysis-queue", "janus-intelligence-mart", (0,), manual_only=True,
          env=(("MART_OPERATION", "queue"), ("MART_AI_ENABLED", "false")),
          exclusive_jobs=("janus-ingestion-core", "janus-intelligence-mart")),
)


MAINTENANCE_NAMES = frozenset({"iceberg-compaction", "mart-cleanup", "core-cleanup", "postgres-maintenance"})


def weekly_maintenance_enabled() -> bool:
    if os.environ.get("FINOPS_WEEKLY_MAINTENANCE", "true").strip().lower() != "true":
        raise ValueError("FINOPS_WEEKLY_MAINTENANCE must follow the new weekly schedule")
    return True


def effective_batches():
    weekly_maintenance_enabled()
    return BATCHES


def weekly_eod_core_evidence(connection, scheduled_at: datetime, observed_at=None):
    """Require a recent immutable Core receipt from a completed EOD ingestion.

    Only the new 18:30 EOD collection can attest the maintenance input.
    Missing receipts fail closed without deleting any current Iceberg files.
    """
    local_day = scheduled_at.astimezone(ZoneInfo("Asia/Taipei")).date()
    evidence_at = observed_at or scheduled_at
    evidence_day = evidence_at.astimezone(ZoneInfo("Asia/Taipei")).date()
    first_day = evidence_day - timedelta(days=8)
    if local_day.weekday() != 5:
        raise ValueError("weekly maintenance requires Saturday occurrence")
    lower = datetime.combine(first_day, datetime.min.time(), tzinfo=ZoneInfo("Asia/Taipei"))
    if os.environ.get("BATCH_CONTROLLER_NOT_BEFORE"):
        lower = max(lower, datetime.fromisoformat(os.environ["BATCH_CONTROLLER_NOT_BEFORE"].replace("Z", "+00:00")))
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT occurrence_id,scheduled_at
                 FROM control.batch_occurrences
                WHERE state->>'batch'='ingestion'
                  AND state->>'status'='succeeded'
                  AND scheduled_at >= %s AND scheduled_at <= %s
                ORDER BY scheduled_at DESC LIMIT 32""",
            (lower, evidence_at),
        )
        ingestions = cursor.fetchall()
    for key, slot in ingestions:
        if slot.tzinfo is None:
            raise RuntimeError("weekly EOD timestamp lacks timezone")
        day = (date.fromisoformat(key.split("/")[2]) if key.startswith("controlled/")
               else slot.astimezone(ZoneInfo("Asia/Taipei")).date())
        if key.removeprefix("controlled/") != f"ingestion/{day.isoformat()}/18":
            continue
        # Match a real receipt written after this scheduled collection began,
        # rather than guessing that analysisAsOf equals the calendar day.
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload->>'coreSnapshotId',payload->>'coreSnapshotUri',payload->>'analysisAsOf'
                     FROM control.core_ready_events
                    WHERE created_at >= %s AND created_at <= %s
                      AND payload->>'analysisAsOf' <= %s
                    ORDER BY created_at DESC LIMIT 32""",
                (slot, evidence_at, day.isoformat()),
            )
            receipts = cursor.fetchall()
        for snapshot_id, uri, as_of in receipts:
            try:
                source_day = date.fromisoformat(as_of)
            except (TypeError, ValueError):
                continue
            if not (0 <= (day - source_day).days <= 8):
                continue
            if (isinstance(snapshot_id, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot_id)
                    and isinstance(uri, str) and re.fullmatch(
                        r"gs://[a-z0-9][a-z0-9._-]{2,220}/executions/[A-Za-z0-9._-]+/core-snapshot[.]json", uri)):
                return {"source_occurrence": key, "source_date": source_day.isoformat(),
                        "core_snapshot_id": snapshot_id, "core_snapshot_uri": uri}
    return None


def due_batches(now: datetime, batches=None):
    """Catch up elapsed slots today. Each hour has a separate occurrence identity."""
    if now.tzinfo is None:
        raise ValueError("controller clock must include a timezone")
    local = now.astimezone(ZoneInfo("Asia/Taipei"))
    batches = effective_batches() if batches is None else batches
    by_name = {batch.name: batch for batch in batches}
    if len(by_name) != len(batches):
        raise ValueError("duplicate batch names")
    result = []
    for batch in batches:
        if batch.manual_only:
            continue
        if not batch.hours or any(hour not in range(24) for hour in batch.hours) or len(set(batch.hours)) != len(batch.hours):
            raise ValueError("invalid batch hours")
        if any(day not in range(7) for day in batch.weekdays):
            raise ValueError("invalid batch weekdays")
        if batch.minute not in range(60):
            raise ValueError("invalid batch minute")
        if any(day not in range(1, 32) for day in batch.month_days):
            raise ValueError("invalid batch month day")
        if (len(set(batch.independent_hours)) != len(batch.independent_hours)
                or any(hour not in batch.hours for hour in batch.independent_hours)
                or (batch.independent_hours and not batch.dependencies)):
            raise ValueError("invalid independent batch slot")
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
            for name in (() if hour in batch.independent_hours else batch.dependencies):
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
            metadata = operation.get("metadata") or {}
            if metadata.get("name"):
                state = {**state, "execution": _identity(metadata["name"], "execution", state["job"]),
                         **({"start_time": metadata["startTime"]} if metadata.get("startTime") else {})}
            return {**state, "status": "running"}
        if operation.get("error"):
            return {**state, "status": "failed", "reason": "cloud_run_operation_failed"}
        execution = operation.get("response", {})
        state = {**state, "execution": _identity(execution.get("name"), "execution", state["job"])}
    if execution.get('startTime'):
        state = {**state, 'start_time': execution['startTime']}
    if execution.get('startTime') and execution.get('completionTime'):
        try:
            duration = (datetime.fromisoformat(execution['completionTime'].replace('Z','+00:00'))
                        - datetime.fromisoformat(execution['startTime'].replace('Z','+00:00'))).total_seconds()
            if duration >= 0:
                state = {**state, 'duration_seconds': round(duration,3)}
        except ValueError:
            pass
    if not execution_finished(execution):
        return {**state, "status": "running"}
    failed_condition = any(condition.get("type") == "Completed" and condition.get("state") == "CONDITION_FAILED"
                           for condition in execution.get("conditions", []))
    succeeded = execution.get("succeededCount") == 1 and not execution.get("failedCount") and not execution.get("cancelledCount") and not failed_condition
    return {**state, "status": "succeeded" if succeeded else "failed", "completion_time": execution.get("completionTime"),
            **({"reason": "admin_stopped"} if execution.get("cancelledCount") and state.get("admin_stop_requested") else {})}


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


def occurrence_env(batch, slot: datetime) -> tuple[tuple[str, str], ...]:
    """Resolve non-secret execution overrides once and persist them with the occurrence."""
    values = dict(batch.env)
    if batch.job == "janus-ingestion-core":
        values.setdefault("JANUS_UNIFIED_COLLECTION", "false")
        values.setdefault("JANUS_SERVING_PRUNE", "false")
    if batch.name == "market-screening":
        values["SCREENING_DATE"] = slot.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
    if batch.name == "private":
        values["VALUATION_DATE"] = slot.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
        values["MOBILE_LEDGER_ONLY"] = "false"
        values["PRIVATE_RECALC_QUEUE_MODE"] = "false"
    if batch.name == "ingestion":
        values["INGESTION_DATE"] = slot.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
    return tuple(sorted(values.items()))


def dispatch_job(session, batch, env=None):
    """Caller must commit dispatch intent first; never automatically retry this POST."""
    overrides = tuple(env) if env is not None else batch.env
    response = session.post(API + resource(batch.job) + ":run", json={"overrides": {
        "taskCount": 1, "containerOverrides": [{"env": [{"name": name, "value": value} for name, value in overrides]}]}}, timeout=15)
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


def run(*, now=None, session=None, control=None, controlled=None):
    from datetime import timezone
    from .__main__ import _control_plane
    if os.environ.get("GCP_PROJECT_ID") != PROJECT:
        raise ValueError("batch controller is restricted to the existing dev project")
    now = now or datetime.now(timezone.utc)
    mode = os.environ.get("BATCH_CONTROLLER_MODE", "observe")
    if mode not in {"observe", "active", "retire-legacy", "mobile-probe"}:
        raise ValueError("unsupported controller mode")
    if mode == "mobile-probe":
        try:
            result = probe_mobile_ledger_queue(write=False)
        except MobileLedgerQueueError as error:
            print(json.dumps({"mobile_ledger_probe": "failed", "error_code": str(error)}, sort_keys=True))
            raise
        return {"status": result["status"], "mobile_ledger_pending": bool(result["pending"])}
    not_before = None
    if mode in {"active", "retire-legacy"}:
        not_before = datetime.fromisoformat(os.environ["BATCH_CONTROLLER_NOT_BEFORE"].replace("Z", "+00:00"))
        if not_before.tzinfo is None:
            raise ValueError("controller activation must include a timezone")
    if now.tzinfo is None:
        raise ValueError("controller clock must include a timezone")
    utc = now.astimezone(timezone.utc)
    tick = utc.replace(minute=utc.minute // 10 * 10, second=0, microsecond=0).isoformat()
    owns_control = control is None
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
            return {"status": "observe", "tick": tick, "exported_events": 0,
                    "iceberg_audit_disabled": True, "model_calls": 0}
        if mode == "retire-legacy":
            if any(job_active(session, name) for name in
                   ("janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")):
                raise RuntimeError("retirement requires terminal workers")
            return retire_legacy(connection, not_before, now)
        with connection.cursor() as cursor:
            cursor.execute("SELECT occurrence_id,state FROM control.batch_occurrences WHERE state->>'status' IN ('dispatching','running','ambiguous') ORDER BY scheduled_at LIMIT 101")
            active = cursor.fetchall()
        if len(active) > 100:
            raise RuntimeError("active occurrence limit exceeded; dispatch blocked")
        for key, state in active:
            try:
                if state.get('batch') == 'ledger-backup':
                    from .ledger_backup import poll_backup
                    updated = poll_backup(connection, state)
                elif state.get("batch") == "postgres-maintenance":
                    continue  # Existing VM executor persists its own terminal state.
                else:
                    updated = poll_job(session, state)
                if updated.get("reason") == "admin_stopped" and updated.get("queued_execution_id"):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute("""UPDATE control.executions SET status='failed',error_code='ADMIN_STOPPED',
                            finished_at=now(),claimed_by=NULL,claimed_until=NULL WHERE execution_id=%s
                            AND status IN ('running','retrying')""", (updated["queued_execution_id"],))
                record(connection, tick, key, updated, "reconcile")
            except Exception:
                # A read failure must never release the running-job fence.
                record(connection, tick, key, state, "cloud_status_unavailable", update=False)
        from .admin_batches import consume_requests, publish_runtime, enqueue_manual_queues
        definitions = effective_batches()
        paused = consume_requests(control, definitions, now, not_before, due_batches, occurrence_env, record, tick,
                                  session, _identity, API)
        enqueue_manual_queues(connection, definitions, paused, now, occurrence_env)
        mobile_pending: bool | None = False
        try:
            mobile_pending = bool(probe_mobile_ledger_queue(write=False)["pending"])
        except MobileLedgerQueueError:
            mobile_pending = None
            record(connection, tick, "mobile-ledger", {"status": "unavailable"}, "mobile_queue_unavailable", update=False)
        private_pending = bool(connection.execute(
            "SELECT EXISTS (SELECT 1 FROM private.recalculation_requests WHERE status='QUEUED')").fetchone()[0])
        if private_pending:
            mobile_pending = True
        rows = controlled_rows(now, *controlled) if controlled else scheduled_batches(now, mobile_pending is True)
        for key, batch, slot, dependencies in rows:
            if (not controlled and slot < not_before) or batch.name in paused:
                continue
            state = {"job": batch.job, "batch": batch.name, "status": "pending", "dependencies": dependencies,
                     "scheduled_at": (now if controlled else slot).isoformat(), "env": list(occurrence_env(batch, slot)),
                     **({"origin": "controlled", "source_slot": slot.isoformat(),
                         "policy_key": key.removeprefix("controlled/")} if controlled else {})}
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (key, slot, json.dumps(state)))
        # Persisted pending slots survive midnight and controller restarts.
        with connection.cursor() as cursor:
            cursor.execute("SELECT occurrence_id,state FROM control.batch_occurrences WHERE state->>'status'='pending' ORDER BY scheduled_at,occurrence_id LIMIT 101")
            pending = cursor.fetchall()
        if len(pending) > 100:
            raise RuntimeError("pending occurrence limit exceeded; dispatch blocked")
        batches = {batch.name: batch for batch in effective_batches()}
        for key, state in pending:
            # Already-persisted rows for removed schedules must never dispatch.
            if state.get("batch") not in batches:
                record(connection, tick, key, {**state, "status": "skipped", "reason": "schedule_superseded"}, "schedule_superseded")
                continue
            batch = batches[state["batch"]]
            if datetime.fromisoformat(state["scheduled_at"]) < not_before:
                record(connection, tick, key, {**state, "status": "skipped",
                    "reason": "retired_before_new_schedule"}, "retired_before_new_schedule")
                continue
            # A pending queue occurrence can outlive the selection window.
            # Recheck at dispatch; never send >5-day or missing references
            # to a worker, even for an admin-triggered pending occurrence.
            if batch.name in {"analysis-queue", "collection-queue"}:
                from .admin_batches import queued_execution_is_fresh
                trigger = "analysis" if batch.name == "analysis-queue" else "collection"
                if not queued_execution_is_fresh(
                        connection, state.get("queued_execution_id"), trigger):
                    record(connection, tick, key,
                           {**state, "status": "skipped",
                            "reason": "queue_execution_outside_five_day_window"},
                           "queue_request_excluded")
                    continue
            if batch.name in paused and state.get("origin") != "admin":
                record(connection, tick, key, state, "admin_paused", update=False)
                continue
            if batch.name in {"ingestion", "market-screening"}:
                setting = control.get_admin_setting("schedule")
                if not setting or not isinstance(setting[0], dict):
                    record(connection, tick, key, state, "market_calendar_unavailable", update=False)
                    continue
                day = datetime.fromisoformat(state.get("source_slot", state["scheduled_at"])).astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
                if day in setting[0].get("holiday_overrides", ()):
                    record(connection, tick, key, {**state, "status": "skipped", "reason": "market_holiday"}, "market_holiday")
                    continue
            if batch.name == "mobile-ledger":
                if mobile_pending is None:
                    record(connection, tick, key, state, "mobile_queue_unavailable", update=False)
                    continue
                if mobile_pending is False:
                    state = {**state, "status": "skipped", "reason": "queue_empty"}
                    record(connection, tick, key, state, "mobile_queue_empty")
                    continue
            dependencies = state["dependencies"]
            # Reconcile scheduled pending slots created before a dependency-policy change.
            policy_time = state.get("source_slot") if state.get("origin") in {"admin", "controlled"} else state["scheduled_at"]
            policy_key = state.get("policy_key") if state.get("origin") in {"admin", "controlled"} else key
            due_row = ((key, batch, datetime.fromisoformat(policy_time), []) if batch.manual_only else
                       next((row for row in due_batches(datetime.fromisoformat(policy_time)) if row[0] == policy_key), None))
            if due_row is None:
                record(connection, tick, key, {**state, "status": "skipped", "reason": "schedule_superseded"},
                       "schedule_superseded")
                continue
            dependencies = (["controlled/" + dep for dep in due_row[3]]
                            if state.get("origin") == "controlled" else due_row[3])
            expected_env = list(occurrence_env(batch, due_row[2]))
            if batch.manual_only and state.get("queued_execution_id"):
                expected_env.append(("QUEUE_EXECUTION_ID", state["queued_execution_id"]))
            if dependencies != state["dependencies"] or state.get("env") != expected_env:
                state = {**state, "dependencies": dependencies, "env": expected_env}
                record(connection, tick, key, state, "dependency_policy_updated")
            with connection.cursor() as cursor:
                statuses = {}
                if dependencies:
                    cursor.execute("SELECT occurrence_id,state->>'status' FROM control.batch_occurrences WHERE occurrence_id=ANY(%s)", (dependencies,))
                    statuses = dict(cursor.fetchall())
                cursor.execute("SELECT 1 FROM control.batch_occurrences WHERE state->>'job'=%s AND state->>'status' IN ('dispatching','running','ambiguous') LIMIT 1", (batch.job,))
                busy = cursor.fetchone() is not None
            # Failed or holiday-skipped upstream work must not strand dependent rows.
            if batch.dependencies and state.get("status") == "pending" and any(
                    statuses.get(dependency) in {"failed", "skipped"} for dependency in dependencies):
                reason = ("upstream_market_skipped" if any(statuses.get(dep) == "skipped" for dep in dependencies)
                          else "upstream_ingestion_failed")
                record(connection, tick, key,
                       {**state, "status": "skipped", "reason": reason},
                       "private_upstream_failed" if batch.name == "private" else "upstream_failed")
                continue
            if any(statuses.get(dependency) != "succeeded" for dependency in dependencies):
                record(connection, tick, key, state, "waiting_dependency", update=False)
                continue
            weekly_evidence = None
            if batch.name == "iceberg-compaction" and weekly_maintenance_enabled():
                weekly_evidence = weekly_eod_core_evidence(
                    connection, datetime.fromisoformat(state.get("source_slot", state["scheduled_at"])),
                    observed_at=now if state.get("origin") == "controlled" else None)
                if weekly_evidence is None:
                    record(connection, tick, key, state, "weekly_eod_core_not_verified", update=False)
                    continue
                record(connection, tick, key, {**state, "core_eod_evidence": weekly_evidence},
                       "weekly_eod_core_attested", update=False)
            if batch.name == "postgres-maintenance":
                record(connection, tick, key, {**state, "status": "running",
                       "executor": "existing_postgres_vm"}, "postgres_maintenance_request")
                continue
            if batch.name == 'ledger-backup':
                from .ledger_backup import request_backup
                record(connection, tick, key, request_backup(connection, state), 'backup_request')
                continue
            if busy or any(job_active(session, job) for job in (batch.exclusive_jobs or (batch.job,))):
                record(connection, tick, key, state, "job_busy", update=False)
                continue
            state = {**state, "status": "dispatching"}
            record(connection, tick, key, state, "dispatch_intent")
            try:
                dispatch_env = list(state.get("env") or batch.env)
                if weekly_evidence is not None:
                    dispatch_env.extend([
                        ["FINOPS_SOURCE_CORE_SNAPSHOT_ID", weekly_evidence["core_snapshot_id"]],
                        ["FINOPS_SOURCE_CORE_SNAPSHOT_URI", weekly_evidence["core_snapshot_uri"]],
                        ["FINOPS_SOURCE_EOD_DATE", weekly_evidence["source_date"]],
                    ])
                operation = dispatch_job(session, batch, dispatch_env)
                state = {**state, "status": "running", "operation": operation}
                try:
                    state = poll_job(session, state)
                except Exception:
                    # Retain the durable operation fence when immediate metadata is unavailable.
                    pass
            except Exception:
                state = {**state, "status": "ambiguous", "reason": "inspect_cloud_execution_before_manual_recovery"}
            record(connection, tick, key, state, "dispatch_result")
        record(connection, tick, "controller", {"status": "tick_completed", "model_calls": 0,
               "execution": os.environ.get("CLOUD_RUN_EXECUTION", "")}, "tick", update=False)
        publish_runtime(connection, now, mode, not_before, definitions)
        return {"status": "tick_completed", "tick": tick, "exported_events": 0,
                "chain_keys": [key for key, batch, _, _ in rows if controlled or batch.name != "mobile-ledger"],
                "compensation_pending": mobile_pending,
                "iceberg_audit_disabled": True, "model_calls": 0}
    finally:
        if locked:
            connection.execute("SELECT pg_advisory_unlock(1835102836,3)")
        if owns_control:
            control.close()


def retire_legacy(connection, cutoff, now):
    """Drop old operational buffers; current Owner/canonical data never enters this scope."""
    if cutoff.tzinfo is None or not timedelta(0) <= now-cutoff <= timedelta(minutes=15):
        raise ValueError("retirement cutoff must be the current activation time")
    statements = {
        "batch_buffers": ("DELETE FROM control.batch_occurrences WHERE scheduled_at<%s AND (state->>'status' IN ('pending','dispatching','running','ambiguous') OR state->>'origin'='controlled')", (cutoff,)),
        "queued_executions": ("UPDATE control.executions SET status='failed',error_code='RETIRED_BY_NEW_SCHEDULE',finished_at=now(),claimed_by=NULL,claimed_until=NULL WHERE requested_at<%s AND finished_at IS NULL AND status IN ('queued','retrying','running') AND (claimed_until IS NULL OR claimed_until<=now())", (cutoff,)),
        "backup_buffers": ("DELETE FROM control.ledger_backup_requests WHERE requested_at<%s AND status='queued'", (cutoff,)),
        "demand_buffers": ("DELETE FROM control.stock_supplement_requests WHERE updated_at<%s", (cutoff,)),
        "private_queue_buffers": ("DELETE FROM private.recalculation_requests WHERE requested_at<%s AND updated_at<%s AND status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')", (cutoff, cutoff)),
        "old_batch_controls": ("DELETE FROM control.admin_settings WHERE setting_key LIKE 'batch_control:%%' AND updated_at<%s", (cutoff,)),
    }
    counts = {}
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout='60000ms'")
        cursor.execute("SET LOCAL lock_timeout='5000ms'")
        cursor.execute("SELECT pg_advisory_xact_lock(1835102836,7)")
        cursor.execute("""INSERT INTO control.admin_settings(setting_key,value_json,version,updated_at,updated_by)
            VALUES ('batch_schedule_epoch',jsonb_build_object('not_before',%s::text),1,now(),'batch-controller')
            ON CONFLICT(setting_key) DO UPDATE SET value_json=EXCLUDED.value_json,
              version=control.admin_settings.version+1,updated_at=now(),updated_by='batch-controller'""",
            (cutoff.isoformat(),))
        for key, (statement, params) in statements.items():
            where = statement.split(" WHERE ", 1)[1]
            table = statement.split(" FROM ", 1)[1].split(" WHERE ", 1)[0] if statement.startswith("DELETE") else "control.executions"
            cursor.execute("SELECT count(*) FROM " + table + " WHERE " + where, params)
            if cursor.fetchone()[0] > 10000:
                raise RuntimeError("legacy buffer retirement exceeds bounded scope")
            cursor.execute(statement, params)
            if cursor.rowcount > 10000:
                raise RuntimeError("legacy buffer retirement exceeded bounded scope")
            counts[key] = cursor.rowcount
        cursor.execute("""UPDATE private.recalculation_dispatch SET active=false,updated_at=now()
            WHERE singleton AND NOT EXISTS (SELECT 1 FROM private.recalculation_requests
              WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED'))""")
        cursor.execute("SELECT control.sync_stock_supplement_demand()")
    return {"status": "retired", "cutoff": cutoff.isoformat(), "retired": counts,
            "current_demand_rebuilt": True, "ledger_writes": 0}


def controlled_rows(now, group, source_day):
    """Stable identities exercise the same schedule/dependencies without moving the clock."""
    day = date.fromisoformat(source_day)
    local = now.astimezone(ZoneInfo("Asia/Taipei"))
    if not 0 <= (local.date() - day).days <= 8:
        raise ValueError("controlled run requires a recent completed source day")
    if group == "compensation":
        batch = next(b for b in effective_batches() if b.name == "mobile-ledger")
        slot = local.replace(year=day.year, month=day.month, day=day.day,
                             hour=0, minute=30, second=0, microsecond=0)
        if slot > local:
            raise ValueError("controlled compensation slot has not elapsed")
        return [(f"controlled/mobile-ledger/{day.isoformat()}/00", batch, slot, [])]
    if group == "eod" and day == local.date() and local.hour < 19:
        raise ValueError("controlled run requires a completed source day")
    names = {"eod": {"ingestion", "market-screening", "private", "serving-prune"},
             "maintenance": MAINTENANCE_NAMES | {"stage-cleanup"},
             "backup": {"ledger-backup"}}.get(group)
    if names is None:
        raise ValueError("unsupported controlled pipeline")
    point = local.replace(year=day.year, month=day.month, day=day.day, hour=23, minute=59)
    rows = [("controlled/" + key, batch, slot, ["controlled/" + dep for dep in deps])
            for key, batch, slot, deps in due_batches(point) if batch.name in names]
    if {batch.name for _, batch, _, _ in rows} != names:
        raise ValueError("source day does not match pipeline schedule")
    return rows


def run_chain(*, controlled=None, deadline_seconds=3000):
    """Wait only while chain work exists; every tick releases the shared writer lock."""
    from .__main__ import _control_plane
    if not 1 <= deadline_seconds <= 3000:
        raise ValueError("invalid chain deadline")
    end = monotonic() + deadline_seconds
    while True:
        result = run(controlled=controlled)
        if result["status"] == "controller_busy":
            if monotonic() >= end:
                raise RuntimeError("controller writer lock deadline reached")
            sleep(15)
            continue
        if result["status"] != "tick_completed":
            return result
        with _control_plane() as control:
            with control.connection.cursor() as cursor:
                cursor.execute("""SELECT occurrence_id,state->>'status' FROM control.batch_occurrences
                    WHERE occurrence_id=ANY(%s) ORDER BY scheduled_at LIMIT 101""",
                    (result.get("chain_keys", []),))
                rows = cursor.fetchall()
        if controlled:
            expected = {row[0] for row in controlled_rows(datetime.now(ZoneInfo("Asia/Taipei")), *controlled)}
            rows = [(key, status) for key, status in rows if key in expected]
            if {key for key, _ in rows} != expected:
                raise RuntimeError("controlled pipeline occurrences missing or paused")
            if controlled[0] == "eod" and any(status == "skipped" for _, status in rows):
                raise RuntimeError("controlled EOD skipped; no completed market chain")
        statuses = [status for _, status in rows]
        if "ambiguous" in statuses or "failed" in statuses:
            raise RuntimeError("pipeline failed or dispatch is ambiguous; inspect persisted state")
        if not any(status in {"pending", "dispatching", "running"} for status in statuses):
            return {**result, "chain_status": "settled"}
        if monotonic() >= end:
            raise RuntimeError("pipeline deadline reached; persisted work retained")
        sleep(15)


if __name__ == "__main__":
    try:
        controlled = ((os.environ["BATCH_ACCEPTANCE_GROUP"], os.environ["BATCH_ACCEPTANCE_DATE"])
                      if os.environ.get("BATCH_ACCEPTANCE_GROUP") else None)
        print(json.dumps(run_chain(controlled=controlled), sort_keys=True))
    except Exception as error:
        print(json.dumps({"status": "failed", "error_code": type(error).__name__.upper()}))
        raise SystemExit(1) from None
