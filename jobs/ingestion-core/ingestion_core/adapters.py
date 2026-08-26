"""Common source adapter contract and safe error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
import asyncio
import inspect
from typing import Any, Awaitable, Callable, Mapping, Protocol
from urllib.parse import urlsplit


class ErrorCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION = "authentication"
    SCHEMA_DRIFT = "schema_drift"
    EMPTY_RESPONSE = "empty_response"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class IngestionError(Exception):
    code: ErrorCode
    safe_message: str
    retryable: bool = False
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        if "\n" in self.safe_message or len(self.safe_message) > 200:
            raise ValueError("safe_message must be a short single-line message")
        Exception.__init__(self, self.safe_message)


@dataclass(frozen=True)
class CollectionRequest:
    execution_id: str
    trace_id: str
    source_id: str
    dataset_id: str
    market: str
    symbols: tuple[str, ...]
    window_start: date | None
    window_end: date
    timeout_seconds: float


@dataclass(frozen=True)
class SourceResponse:
    rows: tuple[Mapping[str, Any], ...] = ()
    schema_version: str = "1.0.0"
    fields: frozenset[str] = frozenset()
    observed_at: datetime | None = None
    is_partial: bool = False
    is_fallback: bool = False
    stale_as_of: datetime | None = None
    raw_payload: bytes | None = None
    source_url: str | None = None
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.fields and self.rows:
            object.__setattr__(self, "fields", frozenset(self.rows[0].keys()))
        if self.observed_at and self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.stale_as_of and self.stale_as_of.tzinfo is None:
            raise ValueError("stale_as_of must be timezone-aware")


class SourceAdapter(Protocol):
    source_id: str

    def fetch(self, request: CollectionRequest) -> SourceResponse | Awaitable[SourceResponse]: ...


@dataclass(frozen=True)
class CallableAdapter:
    """Adapter helper for sync or async functions used by real connectors/tests."""

    source_id: str
    handler: Callable[[CollectionRequest], SourceResponse | Awaitable[SourceResponse]]

    async def fetch(self, request: CollectionRequest) -> SourceResponse:
        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(request)
        return await asyncio.to_thread(self.handler, request)


def classify_exception(error: BaseException) -> IngestionError:
    """Map implementation exceptions to a bounded, non-sensitive taxonomy."""
    if isinstance(error, IngestionError):
        return error
    if isinstance(error, (TimeoutError,)):
        return IngestionError(ErrorCode.TIMEOUT, "source request timed out", True)
    if isinstance(error, PermissionError):
        return IngestionError(ErrorCode.AUTHENTICATION, "source authentication failed", False)
    if isinstance(error, (ConnectionError, OSError)):
        return IngestionError(ErrorCode.TRANSIENT, "source connection failed", True)
    return IngestionError(ErrorCode.UNAVAILABLE, "source is unavailable", True)


def validate_source_url(value: str) -> str:
    """Validate URLs at adapter configuration time; never persist credentials/query."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("source URL must be an absolute HTTP(S) URL without credentials or query parameters")
    return value


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
