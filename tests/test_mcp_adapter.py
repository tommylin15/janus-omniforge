from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.api.app import create_app


OWNER = UUID("00000000-0000-0000-0000-000000000001")


class OAuth:
    settings = SimpleNamespace(issuer="https://janus.example")

    def verify_access_token(self, token, scope):
        if token != "valid" or scope not in {"janus.sources.read","janus.market.read","janus.private.read"}:
            raise HTTPException(401, "invalid token")
        return {"sub":str(OWNER),"scope":scope}


class Repository:
    def watchlist(self, owner_id): return [{"user_id":owner_id,"symbol":"2330","active":True}]
    def ledger_history(self, owner_id, symbol, year, limit=200):
        return [{"user_id":owner_id,"symbol":symbol or "2330","trade_date":f"{year or 2026}-01-02","ledger_version":4}]
    def investment_profile(self, owner_id):
        return {"user_id":owner_id,"risk_tolerance":"moderate","ai_context_opt_in":True,"version":2}


class Store:
    def mart(self, table, owner_id, **filters):
        return [{"user_id":owner_id,"symbol":filters.get("symbol","2330"),"year":filters.get("year"),
                 "valuation_date":"2026-09-17","ledger_version":4,"artifact_ref":"private/hidden",
                 "secret":"hidden","table":table}]


class Core:
    def page(self, resource, symbol, limit):
        return [{"symbol":symbol,"trade_date":"2026-09-17","close":"100","source_id":"twse",
                 "provenance_id":"prov-1","gcs_uri":"gs://hidden"}]


def client():
    return TestClient(create_app(repository=Repository(), store=Store(), core=Core(), oauth_facade=OAuth()))


def rpc(api, method, params=None, *, token=None, request_id=1):
    headers={"Authorization":f"Bearer {token}"} if token else {}
    body={"jsonrpc":"2.0","id":request_id,"method":method}
    if params is not None: body["params"]=params
    return api.post("/mcp",headers=headers,json=body)


def test_mcp_initialization_and_tool_contract_are_read_only_and_explicitly_secured():
    api=client()
    initialized=rpc(api,"initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1"}})
    assert initialized.status_code==200
    assert initialized.json()["result"]["protocolVersion"]=="2025-06-18"
    tools=rpc(api,"tools/list").json()["result"]["tools"]
    assert {tool["name"] for tool in tools}=={"janus_sources","janus_market_context","janus_private_context"}
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    assert all(tool["annotations"]=={"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False} for tool in tools)
    assert all(tool["securitySchemes"][0]["type"]=="oauth2" for tool in tools)


def test_mcp_tool_calls_require_oauth_and_return_bounded_sanitized_records():
    api=client()
    params={"name":"janus_market_context","arguments":{"symbol":"2330","resource":"ohlcv","limit":1}}
    denied=rpc(api,"tools/call",params)
    assert denied.status_code==401
    assert "resource_metadata=" in denied.headers["www-authenticate"]
    assert "mcp/www_authenticate" in denied.json()["result"]["_meta"]

    response=rpc(api,"tools/call",params,token="valid")
    assert response.status_code==200
    result=response.json()["result"]["structuredContent"]
    assert result["schema_version"]=="janus.mcp.v1"
    assert result["bounds"]=={"limit":1,"returned":1,"truncated":False,"max_output_bytes":32768}
    assert result["records"]==[{"symbol":"2330","trade_date":"2026-09-17","close":"100",
                                "source_id":"twse","provenance_id":"prov-1"}]
    assert "gcs_uri" not in str(result) and str(OWNER) not in str(result)


def test_mcp_private_selectors_are_owner_bound_and_reject_extra_or_invalid_combinations():
    api=client()
    valid=rpc(api,"tools/call",{"name":"janus_private_context","arguments":{
        "resource":"trades","symbol":"2330","year":2026,"limit":2}},token="valid")
    result=valid.json()["result"]["structuredContent"]
    assert result["resource"]=="trades" and result["records"][0]["symbol"]=="2330"
    assert str(OWNER) not in str(result)

    for arguments in ({"resource":"positions","owner_id":str(OWNER)},
                      {"resource":"annual-pnl"},
                      {"resource":"stress-tests","symbol":"2330"},
                      {"resource":"notes"}):
        response=rpc(api,"tools/call",{"name":"janus_private_context","arguments":arguments},token="valid")
        assert response.status_code==200 and response.json()["result"]["isError"] is True

