from datetime import datetime
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
                     "day_trade_shares": 1200, "source_id": "twse", "provenance_id": "p1", "execution_id": "e1"}]
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
    assert body["sections"]["institutional"]["status"] == "missing"
    assert "secret" not in str(body)


def test_market_home_is_public_and_independent_of_admin_auth():
    core = CoreQueryService(lambda _identifier, _sql, _parameters: [])
    api = TestClient(create_app(object(), object(), query_core=core), raise_server_exceptions=False)
    assert api.get("/api/v1/public/market-home").status_code == 200
    assert api.get("/api/v1/admin/executions").status_code in {401, 503}
