"""Stateless, read-only MCP surface for ChatGPT."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Mapping
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .context_sources import ContextSourceError, ContextSourceService, MAX_CONTEXT_BYTES
from .models import ContextSelector


PROTOCOL_VERSION = "2025-06-18"
MARKET_RESOURCES = ("ohlcv", "valuation", "institutional", "financials", "events", "market-activity", "benchmark")
PRIVATE_RESOURCES = ("positions", "annual-pnl", "exposure", "performance", "stress-tests", "investment-profile", "watchlist", "trades")
TOOL_SCOPES = {"janus_sources":"janus.sources.read", "janus_market_context":"janus.market.read",
               "janus_private_context":"janus.private.read"}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourcesArgs(_Args):
    pass


class MarketArgs(_Args):
    symbol: str = Field(pattern=r"^[0-9A-Z._-]{1,20}$")
    resource: Literal["ohlcv", "valuation", "institutional", "financials", "events", "market-activity", "benchmark"]
    start_date: date | None = None
    end_date: date | None = None
    limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def dates_are_bounded(self) -> "MarketArgs":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date and self.end_date and (self.start_date > self.end_date or
                                                   (self.end_date-self.start_date).days > 366):
            raise ValueError("date range must be ordered and no longer than 366 days")
        return self


class PrivateArgs(_Args):
    resource: Literal["positions", "annual-pnl", "exposure", "performance", "stress-tests", "investment-profile", "watchlist", "trades"]
    symbol: str | None = Field(default=None, pattern=r"^[0-9A-Z._-]{1,20}$")
    year: int | None = Field(default=None, ge=1900, le=9999)
    limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def selector_matches_resource(self) -> "PrivateArgs":
        if self.symbol and self.resource not in {"positions", "watchlist", "trades"}:
            raise ValueError("symbol is not allowed for this resource")
        if self.resource in {"annual-pnl", "performance"} and self.year is None:
            raise ValueError("year is required for this resource")
        if self.year is not None and self.resource not in {"annual-pnl", "performance", "trades"}:
            raise ValueError("year is not allowed for this resource")
        return self


def _tool(name: str, title: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    return {"name":name, "title":title, "description":description,
            "inputSchema":model.model_json_schema(),
            "annotations":{"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False},
            "securitySchemes":[{"type":"oauth2","scopes":[TOOL_SCOPES[name]]}]}


TOOLS = (
    _tool("janus_sources", "List Janus sources",
          "List the bounded Janus market and owner-scoped private sources available to this user; returns metadata only.", SourcesArgs),
    _tool("janus_market_context", "Read Janus market context",
          "Read bounded published Janus market records for one allowlisted symbol and resource.", MarketArgs),
    _tool("janus_private_context", "Read private Janus context",
          "Read bounded owner-scoped Janus portfolio or ledger records after explicit OAuth authorization.", PrivateArgs),
)


class McpAdapter:
    def __init__(self, contexts: ContextSourceService, oauth: Any) -> None:
        self.contexts, self.oauth = contexts, oauth

    def handle(self, value: Any, authorization: str = "") -> tuple[dict[str, Any] | None, int, dict[str, str]]:
        if not isinstance(value, Mapping) or value.get("jsonrpc") != "2.0" or isinstance(value.get("id"), bool):
            return self._error(value.get("id") if isinstance(value, Mapping) else None, -32600, "Invalid Request"), 400, {}
        request_id, method = value.get("id"), value.get("method")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request"), 400, {}
        if method in {"notifications/initialized", "notifications/cancelled"}:
            return None, 202, {}
        if request_id is None:
            return None, 202, {}
        if method == "initialize":
            return self._result(request_id, {"protocolVersion":PROTOCOL_VERSION,
                "capabilities":{"tools":{"listChanged":False}},
                "serverInfo":{"name":"janus-read-only","version":"1.0.0"},
                "instructions":"Read-only bounded Janus market and owner-scoped private context."}), 200, {}
        if method == "ping": return self._result(request_id, {}), 200, {}
        if method == "tools/list": return self._result(request_id, {"tools":list(TOOLS)}), 200, {}
        if method != "tools/call": return self._error(request_id, -32601, "Method not found"), 200, {}
        params = value.get("params")
        if not isinstance(params, Mapping) or not isinstance(params.get("name"), str) or not isinstance(params.get("arguments", {}), Mapping):
            return self._error(request_id, -32602, "Invalid params"), 200, {}
        name, arguments = params["name"], params.get("arguments", {})
        scope = TOOL_SCOPES.get(name)
        if not scope: return self._error(request_id, -32602, "Unknown tool"), 200, {}
        claims = self._authenticate(authorization, scope)
        if claims is None:
            return self._auth_required(request_id, scope)
        try:
            result = self._call(name, arguments, UUID(str(claims["sub"])))
        except (ValidationError, ValueError, ContextSourceError):
            return self._result(request_id, {"isError":True,"content":[{"type":"text","text":"The bounded selector is invalid or unavailable."}]}), 200, {}
        text = "Listed Janus source metadata." if name == "janus_sources" else (
            f"Returned {result['bounds']['returned']} bounded {result['resource']} record(s); status={result['status']}.")
        return self._result(request_id, {"structuredContent":result,"content":[{"type":"text","text":text}]}), 200, {}

    def _call(self, name: str, arguments: Mapping[str, Any], owner_id: UUID) -> dict[str, Any]:
        if name == "janus_sources":
            SourcesArgs.model_validate(arguments)
            return {"schema_version":"janus.mcp.v1", "items":[
                {"source_id":"janus-core","owner_scope":"public","resources":list(MARKET_RESOURCES),
                 "freshness":"published daily data","status":"available","bounds":self._bounds(),
                 "disclosure":"Published Janus market data shared with an external AI service."},
                {"source_id":"janus-private-core","owner_scope":"owner","resources":["watchlist","trades"],
                 "freshness":"latest owner snapshot","status":"available","bounds":self._bounds(),
                 "disclosure":"Private owner data shared with an external AI service."},
                {"source_id":"janus-private-mart","owner_scope":"owner","resources":list(PRIVATE_RESOURCES[:6]),
                 "freshness":"latest completed valuation","status":"available","bounds":self._bounds(),
                 "disclosure":"Private owner calculations shared with an external AI service."},
            ]}
        if name == "janus_market_context":
            args = MarketArgs.model_validate(arguments)
            selector = ContextSelector(source_id="janus-core", **args.model_dump())
        else:
            args = PrivateArgs.model_validate(arguments)
            source_id = "janus-private-core" if args.resource in {"watchlist","trades"} else "janus-private-mart"
            selector = ContextSelector(source_id=source_id, **args.model_dump())
        return self.contexts.read(owner_id, selector)

    def _authenticate(self, authorization: str, scope: str) -> Mapping[str, Any] | None:
        if not authorization.lower().startswith("bearer ") or not authorization[7:].strip(): return None
        try:
            claims = self.oauth.verify_access_token(authorization[7:].strip(), scope)
            UUID(str(claims.get("sub", "")))
            return claims
        except (AttributeError, HTTPException, ValueError): return None

    def _auth_required(self, request_id: Any, scope: str) -> tuple[dict[str, Any], int, dict[str, str]]:
        challenge = (f'Bearer resource_metadata="{self.oauth.settings.issuer}/.well-known/oauth-protected-resource", '
                     f'scope="{scope}", error="invalid_token", error_description="A valid Janus MCP token is required"')
        body = self._result(request_id, {"isError":True,
            "content":[{"type":"text","text":"Authentication is required for this Janus tool."}],
            "_meta":{"mcp/www_authenticate":[challenge]}})
        return body, 401, {"WWW-Authenticate":challenge}

    @staticmethod
    def _bounds() -> dict[str, int]:
        return {"max_records":20,"max_range_days":366,"max_output_bytes":MAX_CONTEXT_BYTES}

    @staticmethod
    def _result(request_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
        return {"jsonrpc":"2.0","id":request_id,"result":dict(result)}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc":"2.0","id":request_id,"error":{"code":code,"message":message}}
