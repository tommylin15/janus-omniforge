"""Bounded live acceptance helper for owner-scoped Private Mart recalculation.

This module runs inside janus-ingestion-core because that existing runtime already
has the approved PostgreSQL network path. It never emits owner identity, symbols,
trades, or holdings.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4


ACTIVE = ("QUEUED", "RUNNING", "CANCEL_REQUESTED")
TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED")


def _request_uuid(value: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("private recalculation acceptance request id must be a UUID") from error
    if str(parsed) != str(value).lower():
        raise ValueError("private recalculation acceptance request id must be canonical")
    return parsed


class _PostgresAcceptanceStore:
    def __init__(self, control: Any, private: Any) -> None:
        self.control = control
        self.private = private

    def _workers(self) -> int:
        with self.control.connection.cursor() as cursor:
            cursor.execute(
                """SELECT value_json->>'workers'
                   FROM control.admin_settings
                   WHERE setting_key='private_recalc_workers'"""
            )
            row = cursor.fetchone()
        if not row:
            raise RuntimeError("private recalculation worker setting is unavailable")
        workers = int(row[0])
        if not 2 <= workers <= 8:
            raise RuntimeError("private recalculation worker setting is outside 2..8")
        return workers

    def seed(self, request_id: UUID) -> dict[str, Any]:
        workers = self._workers()
        with self.control.connection.cursor() as cursor:
            cursor.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM control.schema_migrations
                       WHERE version='048_private_recalculation_queue'
                   )"""
            )
            row = cursor.fetchone()
            if not row or not bool(row[0]):
                raise RuntimeError("private recalculation queue migration is unavailable")

        with self.private.transaction(), self.private.cursor() as cursor:
            cursor.execute(
                """SELECT count(*)
                   FROM private.recalculation_requests
                   WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')"""
            )
            if int(cursor.fetchone()[0]) != 0:
                raise RuntimeError("private recalculation queue is not idle")

            cursor.execute(
                """SELECT user_id,ledger_version
                   FROM private.users
                   ORDER BY ledger_version DESC,user_id
                   LIMIT 1"""
            )
            owner = cursor.fetchone()
            if not owner:
                raise RuntimeError("private recalculation acceptance requires an existing owner")
            user_id, ledger_version = owner[0], int(owner[1])

            cursor.execute(
                """INSERT INTO private.recalculation_requests(
                       request_id,user_id,requested_ledger_version,status,trigger_source,safe_message
                   ) VALUES(%s,%s,%s,'QUEUED','manual',%s)""",
                (
                    request_id,
                    user_id,
                    ledger_version,
                    "系統驗收：owner-scoped queue 2-task canary",
                ),
            )

            # Prove the live partial-unique owner fence without leaving a second row.
            duplicate_id = uuid4()
            cursor.execute("SAVEPOINT duplicate_owner_guard")
            duplicate_blocked = False
            try:
                cursor.execute(
                    """INSERT INTO private.recalculation_requests(
                           request_id,user_id,requested_ledger_version,status,trigger_source
                       ) VALUES(%s,%s,%s,'QUEUED','manual')""",
                    (duplicate_id, user_id, ledger_version),
                )
            except Exception as error:
                cursor.execute("ROLLBACK TO SAVEPOINT duplicate_owner_guard")
                if str(getattr(error, "sqlstate", "")) != "23505":
                    raise
                duplicate_blocked = True
            else:
                cursor.execute("ROLLBACK TO SAVEPOINT duplicate_owner_guard")
            finally:
                cursor.execute("RELEASE SAVEPOINT duplicate_owner_guard")
            if not duplicate_blocked:
                raise RuntimeError("same-owner active recalculation was not rejected")

            cursor.execute(
                """UPDATE private.recalculation_dispatch
                   SET active=true,generation=generation+1,updated_at=now()
                   WHERE singleton=true AND active=false
                   RETURNING generation"""
            )
            dispatch = cursor.fetchone()
            if not dispatch:
                raise RuntimeError("private recalculation dispatch fence is already active")

        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_seed",
            "request_id": str(request_id),
            "requested_ledger_version": ledger_version,
            "workers": workers,
            "duplicate_owner_guard": "passed",
        }

    def verify(self, request_id: UUID, expected_execution: str) -> dict[str, Any]:
        if not expected_execution or len(expected_execution) > 253:
            raise ValueError("expected private recalculation execution is required")
        with self.private.transaction(), self.private.cursor() as cursor:
            cursor.execute(
                """SELECT r.status,r.attempt_count,r.worker_task_index,r.worker_execution,
                          r.requested_ledger_version,u.ledger_version
                   FROM private.recalculation_requests r
                   JOIN private.users u ON u.user_id=r.user_id
                   WHERE r.request_id=%s""",
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("private recalculation acceptance request is missing")
            status, attempts, task_index, execution, requested_version, current_version = row
            if status != "SUCCEEDED":
                raise RuntimeError("private recalculation acceptance request did not succeed")
            if int(attempts) != 1:
                raise RuntimeError("private recalculation acceptance attempt count drift")
            if task_index not in (0, 1):
                raise RuntimeError("private recalculation acceptance worker index drift")
            if str(execution or "") != expected_execution:
                raise RuntimeError("private recalculation acceptance execution mismatch")
            if int(requested_version) != int(current_version):
                raise RuntimeError("private recalculation result did not catch current ledger version")

            cursor.execute(
                """SELECT count(*)
                   FROM private.recalculation_requests
                   WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')"""
            )
            if int(cursor.fetchone()[0]) != 0:
                raise RuntimeError("private recalculation queue remains active after canary")
            cursor.execute(
                "SELECT active FROM private.recalculation_dispatch WHERE singleton=true"
            )
            dispatch = cursor.fetchone()
            if not dispatch or bool(dispatch[0]):
                raise RuntimeError("private recalculation dispatch fence remains active")

            cursor.execute(
                """UPDATE private.recalculation_requests
                   SET safe_message='系統驗收通過：owner-scoped queue 2-task canary',
                       updated_at=now()
                   WHERE request_id=%s AND status='SUCCEEDED'""",
                (request_id,),
            )

        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_verify",
            "request_id": str(request_id),
            "requested_ledger_version": int(requested_version),
            "attempt_count": int(attempts),
            "worker_task_index": int(task_index),
            "worker_execution": expected_execution,
        }

    def cleanup(self, request_id: UUID) -> dict[str, Any]:
        with self.private.transaction(), self.private.cursor() as cursor:
            cursor.execute(
                """UPDATE private.recalculation_requests
                   SET status='FAILED',error_code='LIVE_ACCEPTANCE_FAILED',
                       safe_message='系統驗收失敗，未影響交易資料，可重新嘗試',
                       finished_at=now(),updated_at=now()
                   WHERE request_id=%s
                     AND status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                   RETURNING status""",
                (request_id,),
            )
            changed = cursor.fetchone() is not None
            cursor.execute(
                """UPDATE private.recalculation_dispatch
                   SET active=false,updated_at=now()
                   WHERE singleton=true
                     AND NOT EXISTS (
                       SELECT 1 FROM private.recalculation_requests
                       WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                     )"""
            )
        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_cleanup",
            "request_id": str(request_id),
            "active_request_failed": changed,
        }


def run_private_recalc_acceptance(
    mode: str,
    request_id: str,
    *,
    expected_execution: str = "",
    store: Any | None = None,
) -> dict[str, Any]:
    normalized = str(mode or "").strip().lower()
    if normalized not in {"seed", "verify", "cleanup"}:
        raise ValueError("unsupported private recalculation acceptance mode")
    parsed = _request_uuid(request_id)

    owned_control = owned_private = None
    if store is None:
        from .__main__ import _control_plane
        from .serving_schema_migration import _private_api_connection

        owned_control = _control_plane()
        owned_private = _private_api_connection()
        store = _PostgresAcceptanceStore(owned_control, owned_private)

    try:
        if normalized == "seed":
            return store.seed(parsed)
        if normalized == "verify":
            return store.verify(parsed, expected_execution)
        return store.cleanup(parsed)
    finally:
        if owned_private is not None:
            owned_private.close()
        if owned_control is not None:
            owned_control.close()


def run_from_env() -> dict[str, Any]:
    return run_private_recalc_acceptance(
        os.environ.get("JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE", ""),
        os.environ.get("JANUS_PRIVATE_RECALC_ACCEPTANCE_REQUEST_ID", ""),
        expected_execution=os.environ.get(
            "JANUS_PRIVATE_RECALC_ACCEPTANCE_EXECUTION", ""
        ).strip(),
    )
