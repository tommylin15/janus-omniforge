"""Small Cloud Run-compatible WSGI boundary for Core and Admin services."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from packages.observability import redact
try:
    from ingestion_core.control import ControlPlaneError, StockInUseError
except ImportError:  # pragma: no cover - web-only deployments include this package
    ControlPlaneError = RuntimeError
    StockInUseError = RuntimeError


STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 64 * 1024
LOGGER = logging.getLogger(__name__)


class WebApplication:
    def __init__(self, *, core: Any | None = None, admin: Any | None = None) -> None:
        self.core = core
        self.admin = admin

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        path = urlsplit(environ.get("PATH_INFO", "/")).path.rstrip("/") or "/"
        query = parse_qs(environ.get("QUERY_STRING", ""))
        trace_id = redact(environ.get("HTTP_X_TRACE_ID") or str(uuid4()))
        try:
            method = environ.get("REQUEST_METHOD", "GET").upper()
            request_body = self._request_body(environ)
            authenticated_actor = str(environ.get("JANUS_AUTH_EMAIL", "")).strip().lower() or None
            body, status, content_type = self._dispatch(
                path, query, method, request_body, authenticated_actor=authenticated_actor,
            )
        except (ValueError, KeyError) as error:
            body, status, content_type = {"error": redact(error)}, "400 Bad Request", "application/json; charset=utf-8"
        except StockInUseError as error:
            body, status, content_type = {"error": redact(error)}, "409 Conflict", "application/json; charset=utf-8"
        except ControlPlaneError as error:
            body, status, content_type = {"error": redact(error)}, "409 Conflict", "application/json; charset=utf-8"
        except Exception as error:
            LOGGER.warning("web request failed: %s", type(error).__name__)
            body, status, content_type = {"error": "service unavailable"}, "503 Service Unavailable", "application/json; charset=utf-8"
        payload = body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(payload))), ("X-Content-Type-Options", "nosniff"), ("X-Trace-ID", trace_id)])
        return [payload]

    @staticmethod
    def _request_body(environ: dict[str, Any]) -> dict[str, Any]:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body is too large")
        if not length:
            return {}
        stream = environ.get("wsgi.input")
        if stream is None:
            raise ValueError("request body is unavailable")
        body = json.loads(stream.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        return body

    def _dispatch(
        self,
        path: str,
        query: dict[str, list[str]],
        method: str = "GET",
        request_body: dict[str, Any] | None = None,
        *,
        authenticated_actor: str | None = None,
    ) -> tuple[Any, str, str]:
        request_body = request_body or {}
        json_type = "application/json; charset=utf-8"
        if path == "/health":
            return {"status": "ok", "revision": os.environ.get("K_REVISION", "local")}, "200 OK", json_type
        if method == "GET" and path in {"/admin", "/admin/stocks"}:
            return (STATIC_DIR / "admin.html").read_text(encoding="utf-8"), "200 OK", "text/html; charset=utf-8"
        if method == "GET" and path == "/private-journal-acceptance.html":
            return (STATIC_DIR / "private-journal-acceptance.html").read_text(encoding="utf-8"), "200 OK", "text/html; charset=utf-8"
        if method == "GET" and path == "/assets/admin.css":
            return (STATIC_DIR / "admin.css").read_text(encoding="utf-8"), "200 OK", "text/css; charset=utf-8"
        if method == "GET" and path == "/assets/admin.js":
            return (STATIC_DIR / "admin.js").read_text(encoding="utf-8"), "200 OK", "text/javascript; charset=utf-8"
        if method == "GET" and path.startswith("/api/v1/core/"):
            if self.core is None:
                return {"error": "core query unavailable"}, "503 Service Unavailable", json_type
            parts = path.split("/")
            if len(parts) == 6 and parts[5] == "summary":
                return self.core.summary(unquote(parts[4])), "200 OK", json_type
            if len(parts) == 7 and parts[5] == "datasets":
                limit = int(query.get("limit", ["50"])[0]); offset = int(query.get("offset", ["0"])[0])
                page = self.core.page(unquote(parts[6]), unquote(parts[4]), limit=limit, offset=offset)
                return {"dataset_id": page.dataset_id, "symbol": page.symbol, "rows": page.rows, "limit": page.limit, "offset": page.offset}, "200 OK", json_type
        if path.startswith("/api/v1/admin/") and self.admin is None:
            return {"error": "admin unavailable"}, "503 Service Unavailable", json_type
        if method == "GET" and path == "/api/v1/admin/stocks":
            if "offset" in query:
                raise ValueError("offset is not supported; use cursor")
            enabled = query.get("enabled", [None])[0]
            if enabled is not None and enabled.lower() not in {"true", "false"}:
                raise ValueError("enabled must be true or false")
            enabled_value = None if enabled is None else enabled.lower() == "true"
            limit = int(query.get("limit", ["10"])[0])
            if not 1 <= limit <= 100:
                raise ValueError("limit is invalid")
            items = self.admin.stocks(query.get("q", [""])[0], enabled=enabled_value, limit=limit + 1, cursor=query.get("cursor", [None])[0])
            page = items[:limit]
            return {"items": page, "limit": limit, "next_cursor": page[-1]["symbol"] if len(items) > limit else None}, "200 OK", json_type
        if method in {"POST", "PUT"} and path in {"/api/v1/admin/stocks", "/api/v1/admin/stocks/"}:
            return self.admin.upsert_stock(request_body), "200 OK", json_type
        if method == "PATCH" and path.startswith("/api/v1/admin/stocks/") and path.endswith("/enabled"):
            symbol = unquote(path.split("/")[5])
            if not isinstance(request_body.get("enabled"), bool):
                raise ValueError("enabled must be a boolean")
            self.admin.set_stock_enabled(symbol, request_body["enabled"])
            return {"symbol": symbol, "enabled": request_body["enabled"]}, "200 OK", json_type
        if method == "DELETE" and path.startswith("/api/v1/admin/stocks/"):
            symbol = unquote(path.split("/")[5])
            self.admin.delete_stock(symbol)
            return {"symbol": symbol, "deleted": True}, "200 OK", json_type
        if method == "GET" and path == "/api/v1/admin/executions":
            limit = int(query.get("limit", ["10"])[0])
            if not 1 <= limit <= 50:
                raise ValueError("limit is invalid")
            items = self.admin.executions(limit=limit + 1, cursor=query.get("cursor", [None])[0])
            page = items[:limit]
            next_cursor = f'{page[-1]["requested_at"]},{page[-1]["execution_id"]}' if len(items) > limit else None
            return {"items": page, "limit": limit, "next_cursor": next_cursor}, "200 OK", json_type
        if method == "GET" and path.startswith("/api/v1/admin/executions/"):
            return self.admin.execution_details(unquote(path.split("/")[5])), "200 OK", json_type
        if method == "POST" and path in {"/api/v1/admin/executions/collection", "/api/v1/admin/executions/analysis"}:
            config_id = self._required_text(request_body, "config_id")
            symbols = self._symbols(request_body.get("symbols"))
            enqueue = self.admin.enqueue_collection if path.endswith("/collection") else self.admin.enqueue_analysis
            options = request_body.get("options") if path.endswith("/collection") else None
            if options is None:
                return enqueue(config_id, symbols), "202 Accepted", json_type
            return enqueue(config_id, symbols, request_options=options), "202 Accepted", json_type
        if method == "GET" and path == "/api/v1/admin/source-health":
            return {"items": self.admin.source_health(limit=int(query.get("limit", ["200"])[0]))}, "200 OK", json_type
        if method == "GET" and path == "/api/v1/admin/source-catalog":
            return {"items": self.admin.collection_configs(limit=int(query.get("limit", ["200"])[0]))}, "200 OK", json_type
        if method in {"POST", "PUT"} and path == "/api/v1/admin/source-catalog":
            actor = authenticated_actor or self._required_text(request_body, "actor")
            return self.admin.save_collection_config(request_body, actor=actor), "200 OK", json_type
        if path.startswith("/api/v1/admin/source-reviews/"):
            adapter_id = unquote(path.split("/")[5])
            if method == "GET":
                return self.admin.source_review(adapter_id), "200 OK", json_type
            if method in {"POST", "PUT"}:
                actor = authenticated_actor or self._required_text(request_body, "actor")
                expected = request_body.get("expected_version")
                if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
                    raise ValueError("expected_version is required")
                return self.admin.save_source_review(adapter_id, request_body.get("value"), actor=actor, expected_version=expected), "200 OK", json_type
        if method == "GET" and path.startswith("/api/v1/admin/stocks/") and path.endswith("/status"):
            symbol = unquote(path.split("/")[5])
            return self.admin.stock_status(symbol), "200 OK", json_type
        if path.startswith("/api/v1/admin/settings/"):
            key = unquote(path.split("/")[5])
            if method == "GET":
                return self.admin.setting(key), "200 OK", json_type
            if method in {"POST", "PUT"}:
                actor = authenticated_actor or self._required_text(request_body, "actor")
                expected = request_body.get("expected_version")
                if expected is not None and (not isinstance(expected, int) or expected < 0):
                    raise ValueError("expected_version must be a non-negative integer")
                return self.admin.save_setting(key, request_body.get("value"), actor=actor, expected_version=expected), "200 OK", json_type
        if method == "GET" and path == "/api/v1/admin/audit":
            return {"items": self.admin.audit(limit=int(query.get("limit", ["50"])[0]))}, "200 OK", json_type
        if path.startswith("/api/v1/admin/memberships/"):
            tier = unquote(path.split("/")[5])
            if method == "GET":
                return self.admin.membership_snapshot(tier), "200 OK", json_type
            if method == "PUT":
                effective_from = self._required_text(request_body, "effective_from")
                expected = request_body.get("expected_version")
                if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
                    raise ValueError("expected_version is required")
                result = self.admin.set_membership(
                    tier,
                    self._symbols(request_body.get("symbols")) or (),
                    effective_from=self.admin.parse_datetime(effective_from),
                    reason=self._required_text(request_body, "reason"),
                    owner=authenticated_actor or self._required_text(request_body, "owner"),
                    expected_version=expected,
                )
                return result, "200 OK", json_type
        return {"error": "not found"}, "404 Not Found", json_type

    @staticmethod
    def _required_text(body: dict[str, Any], field: str) -> str:
        value = body.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
        return value.strip()

    @staticmethod
    def _symbols(value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("symbols must be an array of strings")
        return tuple(dict.fromkeys(item.strip().upper() for item in value if item.strip()))


def application() -> Callable[..., Any]:
    """Build the dev/prod runtime when its Secret Manager settings exist."""
    try:
        from .runtime import build_runtime
        runtime = build_runtime()
    except Exception as error:
        # Keep /health and static diagnostics available without exposing
        # credentials, SQL, upstream errors, or tracebacks.
        LOGGER.warning("web runtime unavailable: %s", redact(error))
        app = WebApplication()
    else:
        app = WebApplication(core=runtime.core, admin=runtime.admin)
    from .auth import protect_with_google
    return protect_with_google(app)


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    make_server("0.0.0.0", int(os.environ.get("PORT", "8080")), application()).serve_forever()
