from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from packages.web_api import CoreQueryService
from services.api.app import create_app


def test_market_home_keeps_core_sections_when_brief_is_missing():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    def query(identifier, sql, parameters):
        if identifier == "core.benchmark_v1":
            return [{"benchmark_id": "TAIEX", "trade_date": today, "close": "25000", "source_id": "taiex"}]
        if identifier == "core.market_activity_v1":
            return [{"trade_date": today, "row_count": 10, "covered_symbols": 4,
                     "day_trade_shares": 1200, "source_ids": ["twse", "tpex"],
                     "provenance_ids": ["p1", "p2"], "execution_ids": ["e1"]}]
        return []

    core = CoreQueryService(query)
    api = TestClient(create_app(object(), object(), query_core=core), raise_server_exceptions=False)
    result = api.get("/api/v1/public/market-home")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "partial"
    assert body["sections"]["taiex"]["data"]["close"] == "25000"
    assert body["sections"]["market-activity"]["coverage"]["received_symbols"] == 4
    assert body["sections"]["market-activity"]["data"]["day_trade_shares"] == 1200
    assert body["sections"]["market-activity"]["status"] == "partial"
    assert body["sections"]["market-activity"]["provenance"]["source_ids"] == ["twse", "tpex"]
    assert body["sections"]["institutional"]["status"] == "missing"
    assert body["as_of"] is None
    assert "secret" not in str(body)


def test_market_home_is_public_and_independent_of_admin_auth():
    core = CoreQueryService(lambda _identifier, _sql, _parameters: [])
    api = TestClient(create_app(object(), object(), query_core=core), raise_server_exceptions=False)
    assert api.get("/api/v1/public/market-home").status_code == 200
    assert api.get("/api/v1/admin/executions").status_code in {401, 503}


def test_market_home_keeps_dates_separate_and_does_not_invent_missing_metrics():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()

    def query(identifier, sql, parameters):
        if identifier == "core.benchmark_v1":
            return [{"benchmark_id": "TAIEX", "trade_date": today, "close": "25000"}]
        if identifier == "core.market_activity_v1":
            return [{"trade_date": today, "row_count": 1, "covered_symbols": 1,
                     "day_trade_shares": None, "day_trade_buy_twd": None,
                     "day_trade_sell_twd": None}]
        return [{"trade_date": today - timedelta(days=1), "row_count": 3, "covered_symbols": 1,
                 "foreign_net_shares": 100, "investment_trust_net_shares": 20,
                 "dealer_net_shares": -5}]

    body = TestClient(create_app(object(), object(), query_core=CoreQueryService(query))).get(
        "/api/v1/public/market-home").json()
    assert body["as_of"] is None
    assert body["sections"]["market-activity"]["status"] == "missing"
    assert body["sections"]["market-activity"]["data"] == {}
    assert body["sections"]["institutional"]["as_of"] == (today - timedelta(days=1)).isoformat()
    assert body["sections"]["institutional"]["data"]["foreign_net_shares"] == 100


def test_market_home_dataset_failure_only_affects_that_section():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()

    def query(identifier, sql, parameters):
        if identifier == "core.market_activity_v1":
            raise RuntimeError("private backend detail")
        if identifier == "core.benchmark_v1":
            return [{"benchmark_id": "TAIEX", "trade_date": today, "close": "25000"}]
        return []

    body = TestClient(create_app(object(), object(), query_core=CoreQueryService(query))).get(
        "/api/v1/public/market-home").json()
    assert body["status"] == "partial"
    assert body["sections"]["taiex"]["status"] == "available"
    assert body["sections"]["market-activity"]["status"] == "unavailable"
    assert "private backend detail" not in str(body)
