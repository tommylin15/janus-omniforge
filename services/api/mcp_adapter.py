"""Stateless MCP surface for bounded Janus reads and explicit owner-scoped ledger writes."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Mapping
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .context_sources import ContextSourceError, ContextSourceService, MAX_CONTEXT_BYTES
from .models import ContextSelector, LedgerEventIn


PROTOCOL_VERSION = "2025-06-18"
MARKET_RESOURCES = ("ohlcv", "valuation", "institutional", "financials", "events", "market-activity", "benchmark")
PRIVATE_RESOURCES = ("positions", "annual-pnl", "exposure", "performance", "stress-tests", "investment-profile", "watchlist", "trades")
TOOL_SCOPES = {
    "janus_sources":"janus.sources.read",
    "janus_market_context":"janus.market.read",
    "janus_private_context":"janus.private.read",
    "janus_private_ledger_append":"janus.private.write",
}


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


class LedgerAppendArgs(LedgerEventIn):
    idempotency_key: str = Field(min_length=8, max_length=128)


def _tool(name: str, title: str, description: str, model: type[BaseModel],
          *, read_only: bool = True) -> dict[str, Any]:
    return {"name":name, "title":title, "description":description,
            "inputSchema":model.model_json_schema(),
            "annotations":{"readOnlyHint":read_only,"destructiveHint":False,"openWorldHint":False},
            "securitySchemes":[{"type":"oauth2","scopes":[TOOL_SCOPES[name],"offline_access"]}]}


TOOLS = (
    _tool("janus_sources", "List Janus sources",
          "List the bounded Janus market and owner-scoped private sources available to this user; returns metadata only.", SourcesArgs),
    _tool("janus_market_context", "Read Janus market context",
          "Read bounded published Janus market records for one allowlisted symbol and resource.", MarketArgs),
    _tool("janus_private_context", "Read private Janus context",
          "Read bounded owner-scoped Janus portfolio or ledger records after explicit OAuth authorization.", PrivateArgs),
    _tool("janus_private_ledger_append", "Record private Janus ledger event",
          "Append one owner-scoped Janus BUY, SELL, cash-dividend, or stock-dividend ledger fact after explicit OAuth authorization. This records Janus data only; it never places a broker order or moves funds. Use exact user-provided values and a stable idempotency_key; do not infer missing transaction values.",
          LedgerAppendArgs, read_only=False),
)


class McpAdapter:
    def __init__(self, contexts: ContextSourceService, oauth: Any, repository: Any | None = None) -> None:
        self.contexts, self.oauth, self.repository = contexts, oauth, repository

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
                "serverInfo":{"name":"janus-private","version":"1.1.0"},
                "instructions":"Bounded Janus market/private reads plus explicit owner-scoped ledger recording. Ledger writes never place broker orders or move funds."}), 200, {}
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
            message = ("The ledger event is invalid, conflicts with current holdings, or is unavailable."
                       if name == "janus_private_ledger_append"
                       else "The bounded selector is invalid or unavailable.")
            return self._result(request_id, {"isError":True,"content":[{"type":"text","text":message}]}), 200, {}
        if name == "janus_sources":
            text = "Listed Janus source metadata."
        elif name == "janus_private_ledger_append":
            text = ("Persisted the owner-scoped Janus ledger event. This records Janus data only; "
                    "no broker order was placed and no funds were moved.")
        else:
            text = f"Returned {result['bounds']['returned']} bounded {result['resource']} record(s); status={result['status']}."
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
        if name == "janus_private_ledger_append":
            if self.repository is None:
                raise ValueError("repository unavailable")
            args = LedgerAppendArgs.model_validate(arguments)
            event = LedgerEventIn.model_validate(args.model_dump(exclude={"idempotency_key"}))
            row = self.repository.add_ledger(owner_id, event, args.idempotency_key)
            return self._ledger_write_result(row)
        if name == "janus_market_context":
            args = MarketArgs.model_validate(arguments)
            selector = ContextSelector(source_id="janus-core", **args.model_dump())
        else:
            args = PrivateArgs.model_validate(arguments)
            source_id = "janus-private-core" if args.resource in {"watchlist","trades"} else "janus-private-mart"
            selector = ContextSelector(source_id=source_id, **args.model_dump())
        return self.contexts.read(owner_id, selector)

    @staticmethod
    def _ledger_write_result(row: Mapping[str, Any]) -> dict[str, Any]:
        fields = ("event_id","ledger_version","event_action","event_type","trade_date","symbol",
                  "shares","price","cash_amount","fee","tax","currency","memo","record_version")
        return {
            "schema_version":"janus.mcp.v1",
            "status":"persisted",
            "resource":"trades",
            "record":{key:row[key] for key in fields if key in row},
            "effects":{"broker_order_placed":False,"funds_moved":False},
            "disclosure":"This tool records an owner-scoped Janus ledger fact only; it does not place orders or move funds.",
        }

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
