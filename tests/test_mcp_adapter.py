from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.api.app import create_app
from services.api.context_sources import CoreContextReader


OWNER = UUID("00000000-0000-0000-0000-000000000001")


class OAuth:
    settings = SimpleNamespace(issuer="https://janus.example")

    def verify_access_token(self, token, scope):
        if token != "valid" or scope not in {"janus.sources.read","janus.market.read","janus.private.read","janus.private.write"}:
            raise HTTPException(401, "invalid token")
        return {"sub":str(OWNER),"scope":scope}


class Repository:
    def __init__(self):
        self.added = []

    def latest_ledger_version(self, owner_id): return 4
    def watchlist(self, owner_id): return [{"user_id":owner_id,"symbol":"2330","active":True}]
    def ledger_history(self, owner_id, symbol, year, limit=200):
        return [{"user_id":owner_id,"symbol":symbol or "2330","trade_date":f"{year or 2026}-01-02","ledger_version":4}]
    def investment_profile(self, owner_id):
        return {"user_id":owner_id,"risk_tolerance":"moderate","ai_context_opt_in":True,"version":2}
    def add_ledger(self, owner_id, value, key):
        self.added.append((owner_id, value, key))
        return {
            "event_id":"11111111-1111-1111-1111-111111111111",
            "user_id":owner_id,
            "ledger_version":5,
            "event_action":"ORIGINAL",
            "event_type":value.event_type,
            "trade_date":value.trade_date,
            "symbol":value.symbol,
            "shares":value.shares,
            "price":value.price,
            "cash_amount":value.cash_amount,
            "fee":value.fee,
            "tax":value.tax,
            "currency":value.currency,
            "memo":value.memo,
            "record_version":1,
            "idempotency_key":key,
        }


class Store:
    def mart(self, table, owner_id, **filters):
        return [{"user_id":owner_id,"symbol":filters.get("symbol","2330"),"year":filters.get("year"),
                 "valuation_date":"2026-09-17","ledger_version":4,"artifact_ref":"private/hidden",
                 "secret":"hidden","table":table}]


class Core:
    def page(self, resource, symbol, limit):
        if resource == "financials":
            return [{"symbol":symbol,"fiscal_year":2026,"fiscal_quarter":2,
                     "availability_at":"2026-09-25T06:00:00+00:00",
                     "published_at":"2026-09-30T00:00:00+00:00",
                     "publication_time_authoritative":False,
                     "observed_at":"2026-06-30T00:00:00+00:00",
                     "metric":"Revenue","value":"100","source_id":"mops",
                     "provenance_id":"prov-financial","gcs_uri":"gs://hidden"}]
        return [{"symbol":symbol,"trade_date":"2026-09-17","close":"100","source_id":"twse",
                 "provenance_id":"prov-1","gcs_uri":"gs://hidden"}]


def test_core_context_reader_uses_public_query_runtime(monkeypatch):
    expected=[{"symbol":"2330","trade_date":"2026-09-17","close":"100"}]
    class Query:
        def page(self, dataset_id, symbol, *, limit, offset):
            assert (dataset_id,symbol,limit,offset)==("ohlcv","2330",200,0)
            return SimpleNamespace(rows=expected)
    monkeypatch.setattr("services.api.public_runtime.build_core_service",lambda:Query())
    assert CoreContextReader.from_env().page("ohlcv","2330",200)==expected


def client(repository=None):
    return TestClient(create_app(repository=repository or Repository(), store=Store(), core=Core(), oauth_facade=OAuth()))


def rpc(api, method, params=None, *, token=None, request_id=1):
    headers={"Authorization":f"Bearer {token}"} if token else {}
    body={"jsonrpc":"2.0","id":request_id,"method":method}
    if params is not None: body["params"]=params
    return api.post("/mcp",headers=headers,json=body)


def test_mcp_initialization_and_tool_contract_are_explicitly_secured():
    api=client()
    initialized=rpc(api,"initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1"}})
    assert initialized.status_code==200
    assert initialized.json()["result"]["protocolVersion"]=="2025-06-18"
    tools=rpc(api,"tools/list").json()["result"]["tools"]
    by_name={tool["name"]:tool for tool in tools}
    assert set(by_name)=={"janus_sources","janus_market_context","janus_private_context"}
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    for name in ("janus_sources","janus_market_context","janus_private_context"):
        assert by_name[name]["annotations"]=={"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False}
    assert all(tool["securitySchemes"][0]["type"]=="oauth2" and
               "offline_access" in tool["securitySchemes"][0]["scopes"] for tool in tools)


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


def test_retired_mcp_ledger_write_is_rejected_even_with_existing_write_authorization():
    repository=Repository()
    api=client(repository)
    for event_type in ("BUY", "SELL", "CASH_DIV", "STOCK_DIV"):
        for token in (None, "valid"):
            response=rpc(api,"tools/call",{"name":"janus_private_ledger_append","arguments":{
                "event_type":event_type,"trade_date":"2026-01-01","symbol":"1101",
                "shares":"1","price":"1","idempotency_key":"retired-write-test",
            }},token=token)
            assert response.status_code==200
            assert response.json()["error"]=={"code":-32602,"message":"Unknown tool"}
    assert repository.added==[]


def test_mcp_financial_context_uses_availability_fence_for_date_bounds_and_as_of():
    api=client()
    params={"name":"janus_market_context","arguments":{
        "symbol":"2330","resource":"financials","start_date":"2026-09-25",
        "end_date":"2026-09-25","limit":1}}
    response=rpc(api,"tools/call",params,token="valid")
    assert response.status_code==200
    result=response.json()["result"]["structuredContent"]
    assert result["status"]=="available"
    assert result["as_of"]=="2026-09-25T06:00:00+00:00"
    assert result["records"][0]["availability_at"]=="2026-09-25T06:00:00+00:00"
    assert result["records"][0]["published_at"]=="2026-09-30T00:00:00+00:00"
    assert result["records"][0]["publication_time_authoritative"] is False
    assert "gcs_uri" not in str(result)


def test_mcp_private_selectors_are_owner_bound_and_reject_extra_or_invalid_combinations():
    api=client()
    valid=rpc(api,"tools/call",{"name":"janus_private_context","arguments":{
        "resource":"trades","symbol":"2330","year":2026,"limit":2}},token="valid")
    result=valid.json()["result"]["structuredContent"]
    assert result["resource"]=="trades" and result["records"][0]["symbol"]=="2330"
    assert str(OWNER) not in str(result)

    for resource,extra in (("positions",{}),("annual-pnl",{"year":2026}),
                           ("exposure",{}),("performance",{"year":2026})):
        response=rpc(api,"tools/call",{"name":"janus_private_context","arguments":{
            "resource":resource,"limit":2,**extra}},token="valid")
        value=response.json()["result"]["structuredContent"]
        assert response.status_code==200 and value["resource"]==resource
        assert value["bounds"]["returned"]==1 and str(OWNER) not in str(value)

    for arguments in ({"resource":"positions","owner_id":str(OWNER)},
                      {"resource":"annual-pnl"},
                      {"resource":"stress-tests","symbol":"2330"},
                      {"resource":"notes"}):
        response=rpc(api,"tools/call",{"name":"janus_private_context","arguments":arguments},token="valid")
        assert response.status_code==200 and response.json()["result"]["isError"] is True


def test_private_mart_withholds_stale_records_before_date_and_limit_filtering():
    from services.api.context_sources import ContextSourceService
    from services.api.models import ContextSelector
    repository = Repository()
    repository.latest_ledger_version = lambda owner_id: 24
    service = ContextSourceService(repository, Store(), Core())
    for resource in ("positions", "annual-pnl", "performance", "exposure", "stress-tests"):
        result = service.read(OWNER, ContextSelector(source_id="janus-private-mart", resource=resource))
        assert result["status"] == "pending"
        assert result["records"] == []
        assert result["as_of"] is None
        assert result["ledger_version"] == 24
        assert result["missing_reason"] == "private_mart_stale"
    assert service.read(OWNER, ContextSelector(source_id="janus-private-core", resource="trades"))["records"]
