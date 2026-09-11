"""Bounded PostgreSQL connectivity checks for the Mart Cloud Run Job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from ipaddress import ip_interface
import os
from typing import Any, Callable


_DATABASES = {
    "catalog": ("CATALOG_DB", "catalog", "catalog.iceberg_tables"),
    "publication": ("PUBLICATION_DB", "publication", None),
}


@dataclass(frozen=True)
class AnalysisExecution:
    execution_id: str
    config_id: str
    requested_symbols: tuple[str, ...]
    retry_count: int
    request_options: dict[str, object]

    def validate_input(self) -> None:
        required = (
            "core_execution_id", "analysis_as_of", "core_snapshot_id", "schema_version",
            "feature_version", "model_version", "governance_snapshot_version",
        )
        missing = [name for name in required if not str(self.request_options.get(name, "")).strip()]
        if missing:
            raise ValueError(f"analysis execution is missing immutable input: {','.join(missing)}")
        date.fromisoformat(str(self.request_options["analysis_as_of"]))

    @property
    def core_snapshot_id(self) -> str:
        return str(self.request_options["core_snapshot_id"]).strip()


class PostgreSQLAnalysisQueue:
    """Lease one persisted analysis execution without broad control-plane access."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def claim(self, worker_id: str, *, lease_seconds: int = 300) -> AnalysisExecution | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_id and a positive lease are required")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM control.claim_mart_analysis(%s,%s)",
                (worker_id.strip(), lease_seconds),
            )
            row = cursor.fetchone()
        return AnalysisExecution(row[0], row[1], tuple(row[2]), row[3], row[4]) if row else None

    def transition(self, execution_id: str, worker_id: str, status: str, *,
                   retry_count: int, error_code: str | None = None) -> None:
        if status not in {"succeeded", "retrying", "failed"}:
            raise ValueError("invalid analysis terminal status")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT control.transition_mart_analysis(%s,%s,%s,%s,%s)",
                (execution_id, worker_id, status, retry_count, error_code),
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError("analysis execution lease is no longer owned by this worker")


def consume_queued_analysis(queue: PostgreSQLAnalysisQueue, processor: Callable[[AnalysisExecution], dict[str, object]],
                            *, worker_id: str, max_retries: int = 1) -> dict[str, object]:
    """Process one leased execution; claiming alone can never mark analysis complete."""
    execution = queue.claim(worker_id)
    if execution is None:
        return {"component": "intelligence-mart", "status": "idle", "claimed": False}
    try:
        execution.validate_input()
        result = processor(execution)
        artifact_uri = str(result.get("artifact_uri", ""))
        if not artifact_uri.startswith("gs://") or result.get("core_snapshot_id") != execution.core_snapshot_id:
            raise ValueError("analysis processor must persist an artifact for the claimed Core snapshot")
        queue.transition(execution.execution_id, worker_id, "succeeded", retry_count=execution.retry_count)
        return {"component": "intelligence-mart", "status": "succeeded", "claimed": True,
                "execution_id": execution.execution_id, "artifact_uri": artifact_uri}
    except Exception as error:
        retry_count = execution.retry_count + 1
        status = "retrying" if retry_count <= max_retries else "failed"
        queue.transition(execution.execution_id, worker_id, status, retry_count=retry_count,
                         error_code=type(error).__name__.upper()[:64])
        raise


def run_queued_validation() -> dict[str, object]:
    """Run the queue fence against one dev execution; no artifact is fabricated."""
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "PUBLICATION_DB_PASSWORD": "publication_password",
    })
    settings = _settings("PUBLICATION_DB")
    import psycopg

    with psycopg.connect(
        host=settings["host"], dbname=settings["name"], user=settings["user"], password=settings["password"],
        sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
        options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
    ) as connection:
        return consume_queued_analysis(
            PostgreSQLAnalysisQueue(connection), lambda _: {},
            worker_id=os.environ.get("QUEUE_WORKER_ID", "intelligence-mart").strip(),
            max_retries=int(os.environ.get("QUEUE_MAX_RETRIES", "1")),
        )


def _settings(prefix: str) -> dict[str, str]:
    names = ("HOST", "NAME", "USER", "PASSWORD")
    values = {name.lower(): os.environ.get(f"{prefix}_{name}", "").strip() for name in names}
    missing = [f"{prefix}_{name}" for name in names if not values[name.lower()]]
    if missing:
        raise ValueError(f"missing database settings: {','.join(missing)}")
    return values


def _is_private(address: str) -> bool:
    parsed = ip_interface(address).ip
    return parsed.is_private and not (parsed.is_loopback or parsed.is_link_local)


def postgres_smoke(connect: Callable[..., Any] | None = None) -> dict[str, object]:
    """Verify both Mart identities reach PostgreSQL privately with bounded grants."""
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": "catalog_password",
        "PUBLICATION_DB_PASSWORD": "publication_password",
    })
    if connect is None:
        import psycopg

        connect = psycopg.connect

    results: dict[str, object] = {}
    for label, (prefix, schema, writable_table) in _DATABASES.items():
        settings = _settings(prefix)
        with connect(
            host=settings["host"],
            dbname=settings["name"],
            user=settings["user"],
            password=settings["password"],
            sslmode=os.environ.get(f"{prefix}_SSLMODE", "require"),
            connect_timeout=5,
            options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_user, inet_server_addr()::text, "
                    "has_schema_privilege(current_user, %s, 'USAGE')",
                    (schema,),
                )
                role, server_address, schema_usage = cursor.fetchone()
                writable = True
                if writable_table:
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, 'SELECT,INSERT,UPDATE,DELETE')",
                        (writable_table,),
                    )
                    writable = bool(cursor.fetchone()[0])

        if role != settings["user"]:
            raise RuntimeError(f"{label} role mismatch")
        if not _is_private(server_address):
            raise RuntimeError(f"{label} database did not resolve to a private server address")
        if not schema_usage or not writable:
            raise RuntimeError(f"{label} role is missing its bounded schema privileges")
        results[label] = {"role": role, "server_address": server_address, "private": True, "privileges": "ok"}

    return {"component": "intelligence-mart", "status": "ok", "databases": results}
