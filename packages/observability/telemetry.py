"""Bounded telemetry and safe error mapping.

Telemetry contains aggregate metadata only.  It must never carry upstream
payloads, credentials, query strings, or tracebacks to an API response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Callable, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionContext:
    execution_id: str
    trace_id: str

    @classmethod
    def create(cls, execution_id: str | None = None, trace_id: str | None = None) -> "ExecutionContext":
        return cls(execution_id or str(uuid4()), trace_id or str(uuid4()))


@dataclass(frozen=True)
class SourceHealthRecord:
    source_id: str
    dataset_id: str
    coverage_tier: str
    expected_symbols: int
    received_symbols: int
    success_rate: float
    average_latency_ms: float
    last_fetched_at: datetime | None
    latest_observation_at: datetime | None
    cache_age_seconds: float | None
    fallback_count: int
    schema_drift_count: int
    last_state: str | None


class SafeError(RuntimeError):
    """An error whose message is safe to expose at the API boundary."""

    def __init__(self, message: str, *, code: str = "service_unavailable") -> None:
        super().__init__(message)
        self.code = code


_SECRET = re.compile(r"(?i)(password|passwd|secret|token|api[-_]?key|authorization)\s*[=:]\s*[^\s,;]+")
_URL_QUERY = re.compile(r"([?&](?:key|token|secret|password|signature|sig)=[^&\s]+)", re.I)


def redact(value: Any) -> str:
    """Return a short, non-sensitive diagnostic string."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = _SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _URL_QUERY.sub(lambda match: match.group(1).split("=", 1)[0] + "=<redacted>", text)
    return text[:240]


def safe_error_message(error: BaseException) -> str:
    return redact(error) or "service unavailable"


class PostgresHealthCollector:
    """Collect bounded PostgreSQL operational aggregates through an injected query."""

    def __init__(self, query: Callable[[str, tuple[Any, ...]], Any]) -> None:
        self._query = query

    def snapshot(self, *, observed_at: datetime | None = None) -> dict[str, Any]:
        now = observed_at or datetime.now(timezone.utc)
        # These are fixed read-only queries; no caller supplied SQL is accepted.
        activity = self._one("SELECT count(*) AS connection_count FROM pg_stat_activity", ())
        database = self._one(
            "SELECT COALESCE(sum(deadlocks),0) AS deadlocks, "
            "COALESCE(sum(temp_bytes),0) AS temp_bytes FROM pg_stat_database", ())
        disk = self._one("SELECT pg_database_size(current_database()) AS disk_bytes", ())
        slow = self._one(
            "SELECT COALESCE(sum(calls) FILTER (WHERE mean_exec_time >= %s),0) AS slow_query_count "
            "FROM pg_stat_statements", (1000,))
        return {
            "observed_at": now.isoformat(),
            "connection_count": int(activity.get("connection_count", 0)),
            "disk_bytes": int(disk.get("disk_bytes", 0)),
            "deadlocks": int(database.get("deadlocks", 0)),
            "temp_bytes": int(database.get("temp_bytes", 0)),
            "slow_query_count": int(slow.get("slow_query_count", 0)),
            "retention": self.retention(),
        }

    def retention(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for name in ("response_cache", "executions", "source_health", "audit_events"):
            row = self._one(f"SELECT count(*) AS row_count FROM control.{name}", ())
            result[name] = int(row.get("row_count", 0))
        return result

    def _one(self, sql: str, parameters: tuple[Any, ...]) -> Mapping[str, Any]:
        try:
            row = self._query(sql, parameters)
            return dict(row or {})
        except Exception:
            # Optional pg_stat_statements and audit tables may not exist in dev.
            return {}
