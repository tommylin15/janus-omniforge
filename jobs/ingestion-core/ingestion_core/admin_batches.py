"""Admin requests consumed only under the existing controller writer lock."""
from dataclasses import asdict
from datetime import timedelta
import json
import os
import re
from zoneinfo import ZoneInfo


def publish_runtime(connection, now, mode, not_before, batches):
    logs = connection.execute("""SELECT DISTINCT ON (payload->>'batch')
        payload->>'batch',created_at,payload->>'occurrence_id',payload->>'action',
        payload->>'status',payload->>'reason'
        FROM control.batch_event_outbox WHERE created_at >= %s
        AND payload->>'batch' IS NOT NULL
        ORDER BY payload->>'batch',created_at DESC LIMIT 32""",
        (now - timedelta(days=7),)).fetchall()
    value = {"observed_at": now.isoformat(), "mode": mode,
             "not_before": not_before.isoformat(),
             "latest_logs": {row[0]: {"at": row[1].isoformat(), "occurrence_id": row[2],
                 "action": row[3], "status": row[4], "reason": row[5]} for row in logs},
             "definitions": [{key: asdict(batch)[key] for key in
                ("name", "hours", "minute", "weekdays", "month_days", "dependencies", "manual_only")}
                for batch in batches]}
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("""INSERT INTO control.admin_settings
            (setting_key,value_json,version,updated_at,updated_by)
            VALUES ('batch_controller_runtime',%s::jsonb,1,now(),'batch-controller')
            ON CONFLICT(setting_key) DO UPDATE SET value_json=EXCLUDED.value_json,
              updated_at=now(),version=control.admin_settings.version+1,
              updated_by='batch-controller'""", (json.dumps(value),))


def consume_requests(control, batches, now, not_before, due, occurrence_env, record, tick, session, execution_identity, api):
    """No arbitrary Job/env; cancellation is limited to the selected occurrence."""
    connection = control.connection
    paused = set()
    for batch in batches:
        entry = control.get_admin_setting("batch_control:" + batch.name)
        if not entry:
            continue
        value, version = entry
        if value.get("paused"):
            paused.add(batch.name)
        if value.get("processed_version") == version:
            continue
        action = value.get("action")
        outcome = "applied"
        if action == "start":
            if batch.manual_only:
                outcome = enqueue_queued_worker(connection, batch, now, occurrence_env, origin="admin", request_version=version)
            else:
                slots = []
                for offset in range(32):
                    point = now if offset == 0 else (now - timedelta(days=offset)).astimezone(
                        ZoneInfo("Asia/Taipei")).replace(hour=23, minute=59, second=59)
                    slots = [row for row in due(point) if row[1].name == batch.name]
                    slots = [row for row in slots if row[2] >= not_before]
                    if slots:
                        break
                if not slots:
                    outcome = "no_eligible_slot"
                else:
                    policy_key, _, slot, dependencies = slots[-1]
                    key = f"admin/{batch.name}/{version}"
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute("""SELECT 1 FROM control.batch_occurrences
                            WHERE state->>'job'=%s AND state->>'status' IN
                            ('pending','dispatching','running','ambiguous') LIMIT 1""", (batch.job,))
                        busy = cursor.fetchone() is not None
                        state = {"job": batch.job, "batch": batch.name,
                            "status": "skipped" if busy else "pending", "origin": "admin",
                            "policy_key": policy_key, "source_slot": slot.isoformat(),
                            "scheduled_at": now.isoformat(), "dependencies": dependencies,
                            "env": list(occurrence_env(batch, slot)),
                            **({"reason": "duplicate_active_work"} if busy else {})}
                        cursor.execute("""INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state)
                            VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING""", (key, now, json.dumps(state)))
                    outcome = "duplicate_active_work" if busy else "queued"
        elif action == "stop":
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("""SELECT state FROM control.batch_occurrences
                    WHERE occurrence_id=%s AND state->>'batch'=%s FOR UPDATE""",
                    (value.get("occurrence_id"), batch.name))
                selected = cursor.fetchone()
                state = selected[0] if selected else {}
                if state.get("status") == "pending":
                    state.update(status="skipped", reason="admin_stopped_before_dispatch")
                    outcome = "stopped"
                    if state.get("queued_execution_id"):
                        cursor.execute("""UPDATE control.executions SET status='failed',error_code='ADMIN_STOPPED',
                            finished_at=now(),claimed_by=NULL,claimed_until=NULL WHERE execution_id=%s AND status IN ('queued','retrying')""",
                            (state["queued_execution_id"],))
                elif (state.get("status") in {"running", "dispatching"}
                      and state.get("execution") and state.get("job") == batch.job
                      and batch.name != "ledger-backup"):
                    identity = execution_identity(state["execution"], "execution", batch.job)
                    try:
                        response = session.post(api + identity + ":cancel", json={}, timeout=15)
                        if 200 <= response.status_code < 300:
                            state["admin_stop_requested"] = True
                            outcome = "stop_requested"
                        else:
                            outcome = "stop_not_confirmed"
                    except Exception:
                        outcome = "stop_not_confirmed"
                else:
                    outcome = "cannot_safely_stop"
                if selected:
                    cursor.execute("UPDATE control.batch_occurrences SET state=%s::jsonb,updated_at=now() WHERE occurrence_id=%s",
                        (json.dumps(state), value["occurrence_id"]))
            if selected:
                record(connection, tick, value["occurrence_id"], {**state, "batch": batch.name},
                       "admin_stop_request", update=False)
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute("""UPDATE control.admin_settings SET
                value_json=value_json || %s::jsonb WHERE setting_key=%s AND version=%s""",
                (json.dumps({"processed_version": version, "outcome": outcome}),
                 "batch_control:" + batch.name, version))
        record(connection, tick, batch.name,
               {"status": "admin_request_processed", "request_version": version,
                "action": action, "outcome": outcome}, "admin_control", update=False)
    return paused


def enqueue_manual_queues(connection, batches, paused, now, occurrence_env):
    # Only an explicit, single-Job *override* may consider historical (>7-day)
    # analysis work. Normal Scheduler ticks remain bounded to fresh requests.
    mode = os.environ.get("JANUS_P02_ANALYSIS_RECOVERY", "")
    target_ref = os.environ.get("JANUS_P02_ANALYSIS_EXECUTION_REF", "")
    if bool(mode) != bool(target_ref) or (mode and mode != "one-shot"):
        raise ValueError("historical analysis recovery requires one verified target")
    for batch in batches:
        if batch.manual_only and batch.name not in paused:
            allow = batch.name == "analysis-queue" and mode == "one-shot"
            enqueue_queued_worker(connection, batch, now, occurrence_env,
                historical_recovery=allow,
                target_execution_ref=target_ref if allow else None)


def enqueue_queued_worker(connection, batch, now, occurrence_env, origin="queue", request_version=None,
                          *, historical_recovery=False, target_execution_ref=None):
    """Enqueue one worker only after a durable, bounded lease/recovery decision.

    Historical >7-day analysis work requires a separately verified recovery
    gate. Never automatically replay legacy 'running' rows with a NULL lease:
    they may contain 14 partially produced collection artifacts.
    """
    trigger = {"collection-queue": "collection", "analysis-queue": "analysis"}[batch.name]
    if historical_recovery and trigger != "analysis":
        raise ValueError("historical collection recovery requires artifact-level review")
    if historical_recovery and (
        not isinstance(target_execution_ref, str)
        or re.fullmatch(r"[0-9a-f]{32}", target_execution_ref) is None):
        raise ValueError("historical recovery requires one pseudonymous execution ref")
    if target_execution_ref and not historical_recovery:
        raise ValueError("historical target without enabled recovery")
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("""SELECT e.execution_id,e.retry_count FROM control.executions e
            WHERE e.trigger_type=%s AND e.finished_at IS NULL
              AND e.requested_at >= now() - interval '30 days'
              AND (e.requested_at >= now() - interval '7 days' OR %s)
              AND (%s::text IS NULL OR md5(e.execution_id::text)=%s)
              AND (NOT %s OR
                    (e.trigger_type='analysis' AND e.status='queued'
                      AND e.started_at IS NULL))
              AND EXISTS (SELECT 1 FROM control.collection_configs cfg
                          WHERE cfg.config_id=e.config_id AND cfg.enabled
                            AND (e.trigger_type='collection' OR cfg.analysis_enabled))
              AND (
                e.status IN ('queued','retrying')
                OR (e.status='running' AND e.claimed_until IS NOT NULL
                    AND e.claimed_until < now())
                OR (e.status='running' AND e.claimed_until IS NULL
                    AND e.started_at IS NULL
                    AND NOT EXISTS (SELECT 1 FROM control.execution_items i
                        WHERE i.execution_id=e.execution_id))
              )
              AND (e.trigger_type='collection' OR EXISTS (
                   SELECT 1 FROM control.core_ready_events r
                   WHERE r.analysis_execution_id=e.execution_id
                     AND r.payload->>'coreSnapshotUri' =
                         e.request_options->>'core_snapshot_uri'
                     AND r.payload->>'coreSnapshotHash' =
                         e.request_options->>'core_snapshot_hash'
                     AND r.payload->>'coreSnapshotId' =
                         e.request_options->>'core_snapshot_id'))
              AND NOT EXISTS (
                   SELECT 1 FROM control.batch_occurrences b
                   WHERE b.state->>'queued_execution_id'=e.execution_id::text
                     AND b.state->>'status' IN ('pending','dispatching','running','ambiguous'))
            ORDER BY e.requested_at,e.execution_id LIMIT 1""",
                       (trigger, historical_recovery,
                        target_execution_ref, target_execution_ref,
                        historical_recovery))
        queued = cursor.fetchone()
        if not queued:
            return "queue_empty"
        cursor.execute("""SELECT 1 FROM control.batch_occurrences
            WHERE state->>'job'=%s AND state->>'status' IN
            ('pending','dispatching','running','ambiguous') LIMIT 1""", (batch.job,))
        if cursor.fetchone():
            return "duplicate_active_work"
        key = f"queue/{trigger}/{queued[0]}/{queued[1]}" + (f"/admin/{request_version}" if request_version is not None else "")
        state = {"batch": batch.name, "job": batch.job, "status": "pending", "origin": origin,
                 "queued_execution_id": str(queued[0]),
                 "source_slot": now.isoformat(), "scheduled_at": now.isoformat(), "dependencies": [],
                 "env": [*occurrence_env(batch, now), ("QUEUE_EXECUTION_ID", str(queued[0]))]}
        cursor.execute("""INSERT INTO control.batch_occurrences(occurrence_id,scheduled_at,state)
            VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING occurrence_id""", (key, now, json.dumps(state)))
        return "queued" if cursor.fetchone() else "already_queued"
