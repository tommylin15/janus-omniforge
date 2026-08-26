"""Bounded Trino statement client for job workloads.

The caller owns the polling loop. This is intentional: a job keeps waiting for
the coordinator instead of losing a query when its HTTP request returns early.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class QueryError(RuntimeError):
    """A safe, classified Trino client error (never includes SQL or secrets)."""


@dataclass(frozen=True)
class QueryHandle:
    query_id: str
    next_uri: str | None


@dataclass(frozen=True)
class QueryPage:
    query_id: str
    columns: tuple[dict[str, Any], ...]
    rows: tuple[tuple[Any, ...], ...]
    next_uri: str | None
    finished: bool
    stats: dict[str, Any]
    error: dict[str, Any] | None = None


class QueryClient:
    def __init__(self, endpoint: str, *, user: str = "janus-job", timeout: float = 30.0,
                 poll_interval: float = 2.0, max_poll_seconds: float = 900.0) -> None:
        parsed = urlparse(endpoint.rstrip("/") + "/")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        self.endpoint = endpoint.rstrip("/")
        self._origin = (parsed.scheme, parsed.netloc)
        self.user = user
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_seconds = max_poll_seconds

    def submit(self, sql: str, *, catalog: str = "iceberg", schema: str = "core") -> QueryHandle:
        if not sql.strip():
            raise ValueError("sql must not be empty")
        payload = self._request("POST", f"{self.endpoint}/v1/statement", body=sql.encode(),
                                headers={"Content-Type": "text/plain; charset=utf-8",
                                         "X-Trino-User": self.user, "X-Trino-Catalog": catalog,
                                         "X-Trino-Schema": schema})
        query_id = payload.get("id")
        if not query_id:
            raise QueryError("invalid Trino response")
        return QueryHandle(str(query_id), self._safe_next(payload.get("nextUri")))

    def poll(self, handle: QueryHandle) -> QueryPage:
        payload = self._request("GET", handle.next_uri) if handle.next_uri else {"id": handle.query_id}
        error = payload.get("error")
        rows = tuple(tuple(row) for row in payload.get("data", ()))
        next_uri = self._safe_next(payload.get("nextUri"))
        finished = next_uri is None and not payload.get("queued", False) and not payload.get("started", True)
        # Trino commonly omits started/queued on terminal responses.
        if next_uri is None and (payload.get("stats", {}).get("state") in {"FINISHED", "FAILED", "CANCELED"} or error):
            finished = True
        return QueryPage(str(payload.get("id", handle.query_id)), tuple(payload.get("columns", ())), rows,
                         next_uri, finished, dict(payload.get("stats", {})), error)

    def wait(self, handle: QueryHandle) -> list[tuple[Any, ...]]:
        rows: list[tuple[Any, ...]] = []
        deadline = time.monotonic() + self.max_poll_seconds
        current = handle
        while True:
            page = self.poll(current)
            rows.extend(page.rows)
            if page.error:
                raise QueryError("Trino query failed")
            if page.finished:
                return rows
            if time.monotonic() >= deadline:
                self.cancel(current)
                raise QueryError("Trino query polling timed out")
            current = QueryHandle(page.query_id, page.next_uri)
            time.sleep(self.poll_interval)

    def cancel(self, handle: QueryHandle) -> None:
        target = handle.next_uri or f"{self.endpoint}/v1/query/{handle.query_id}"
        self._request("DELETE", target, expect_json=False)

    def _safe_next(self, value: Any) -> str | None:
        if not value:
            return None
        target = urljoin(self.endpoint + "/", str(value))
        parsed = urlparse(target)
        if (parsed.scheme, parsed.netloc) != self._origin:
            raise QueryError("Trino returned an unsafe polling URL")
        return target

    def _request(self, method: str, url: str | None, *, body: bytes | None = None,
                 headers: dict[str, str] | None = None, expect_json: bool = True) -> Any:
        if not url:
            raise QueryError("Trino response has no polling URL")
        try:
            with urlopen(Request(url, data=body, headers=headers or {}, method=method), timeout=self.timeout) as response:
                if not expect_json:
                    return None
                return json.load(response)
        except HTTPError as exc:
            raise QueryError(f"Trino HTTP {exc.code}") from exc
        except URLError as exc:
            raise QueryError("Trino connection failed") from exc
