from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from packages.web_api import CoreQueryService
from services.api.app import create_app


def test_public_home_warm_read_does_not_wait_for_broker_refresh(monkeypatch):
    import services.api.app as app_module
    from services.api.quote_router import QuoteRouter

    calls = []
    def resolve(self, identities, *, refresh=False, force=False, now=None):
        calls.append(bool(refresh))
        if refresh:
            raise AssertionError("public quote refresh must not block first paint")
        return {}, {"status": "cached"}

    monkeypatch.setattr(QuoteRouter, "resolve", resolve)
    monkeypatch.setenv("JANUS_MIS_QUOTES_ENABLED", "false")
    core = CoreQueryService(lambda *_: [])
    api = TestClient(create_app(object(), object(), query_core=core))
    assert api.get("/api/v1/public/market-home").status_code == 200
    assert calls == [False]


def test_public_market_home_cache_expires_without_changing_dates(monkeypatch):
    import services.api.app as app_module

    clock = [0.0]
    monkeypatch.setattr(app_module, "monotonic", lambda: clock[0])
    calls = []
    core = CoreQueryService(lambda *args: calls.append(args) or [])
    api = TestClient(create_app(object(), object(), query_core=core))
    first = api.get("/api/v1/public/market-home").json()
    count = len(calls)
    assert count == 3
    clock[0] = 59
    assert api.get("/api/v1/public/market-home").json() == first
    assert len(calls) == count
    clock[0] = 60
    assert api.get("/api/v1/public/market-home").status_code == 200
    assert len(calls) == 2 * count


def test_market_home_keeps_core_sections_when_brief_is_missing():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    def query(identifier, sql, parameters):
        if identifier == "core.benchmark_v1":
            return [{"benchmark_id": "TAIEX", "trade_date": today, "close": "25000", "source_id": "taiex"}]
        if identifier == "core.market_activity_v1":
            return [{"trade_date": today, "row_count": 10, "covered_symbols": 4,
                     "day_trade_shares": 1200, "source_ids": ["twse"],
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
    assert body["sections"]["market-activity"]["provenance"]["source_ids"] == ["twse"]
    assert body["sections"]["institutional"]["status"] == "missing"
    assert body["as_of"] is None
    assert "secret" not in str(body)


def test_market_home_includes_quote_previous_close_and_tick_timestamp(monkeypatch):
    """An authenticated exchange quote's reference must travel with its index value."""
    from services.api.quote_router import QuoteRouter

    now = datetime.now(ZoneInfo("Asia/Taipei"))
    today = now.date()
    previous = today - timedelta(days=1)

    def query(identifier, _sql, _parameters):
        if identifier == "core.benchmark_v1":
            return [{"benchmark_id": "TAIEX", "trade_date": previous,
                     "close": "25000", "source_id": "official",
                     "provenance_id": "benchmark-published"}]
        return []

    quote = {
        "price": "25125.5", "previous_close": "25000",
        "price_date": today.isoformat(), "quote_at": now.isoformat(),
        "source": "twse_mis", "state": "intraday",
    }
    monkeypatch.setattr(QuoteRouter, "resolve",
                        lambda self, *args, **kwargs: ({"TAIEX": quote}, {"status": "fresh"}))
    client = TestClient(create_app(object(), object(),
                            query_core=CoreQueryService(query)))
    response = client.get("/api/v1/public/market-home")
    assert response.status_code == 200
    section = response.json()["sections"]["taiex"]
    assert section["as_of"] == today.isoformat()
    assert section["data"]["close"] == "25125.5"
    assert section["data"]["quote_previous_close"] == "25000"
    assert section["data"]["quote_at"] == now.isoformat()
    assert section["data"]["quote_state"] == "intraday"
    assert section["data"]["quote_source"] == "twse_mis"
    # Official Core history remains separate from the non-final MIS tick.
    assert section["data"]["history_points"][0]["value"] == "25000"


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


def test_index_quote_is_lightweight_same_request_and_no_store(monkeypatch):
    from services.api.quote_router import QuoteRouter
    import services.api.app as app_module

    now = datetime.now(ZoneInfo("Asia/Taipei"))
    calls = []
    class Core:
        def market_home(self):
            raise AssertionError("lightweight endpoint must not query market-home")
    def resolve(self, identities, *, refresh=False, force=False, now=None):
        calls.append((identities, refresh, force))
        return {"TAIEX": {"price": "25125.5", "previous_close": "25000",
                           "price_date": now.date().isoformat(), "quote_at": now.isoformat(),
                           "source": "shioaji", "state": "intraday"}}, {"status": "updated"}
    monkeypatch.setattr(QuoteRouter, "resolve", resolve)
    monkeypatch.setenv("JANUS_MIS_QUOTES_ENABLED", "true")
    monkeypatch.setattr(app_module, "market_phase", lambda _: "regular")
    client = TestClient(create_app(object(), object(), query_core=Core()))
    response = client.get("/api/v1/public/market-index-quote?force=true")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["schema_version"] == "market-index-quote.v1"
    assert body["refresh_status"] == "updated"
    assert body["section"]["data"]["close"] == "25125.5"
    assert body["section"]["data"]["quote_previous_close"] == "25000"
    assert body["section"]["data"]["quote_source"] == "shioaji"
    assert calls == [({"TAIEX": {"market": "TWSE_INDEX", "enabled": True}}, True, True)]


def test_index_quote_off_session_only_manual_refresh_and_missing_is_explicit(monkeypatch):
    from services.api.quote_router import QuoteRouter
    import services.api.app as app_module
    calls = []
    def resolve(self, identities, *, refresh=False, force=False, now=None):
        calls.append((refresh, force))
        return {}, {"status": "unavailable" if refresh else "idle"}
    monkeypatch.setattr(QuoteRouter, "resolve", resolve)
    monkeypatch.setattr(app_module, "market_phase", lambda _: "closed")
    monkeypatch.setenv("JANUS_MIS_QUOTES_ENABLED", "true")
    client = TestClient(create_app(object(), object(), query_core=object()))
    body = client.get("/api/v1/public/market-index-quote").json()
    assert body["section"] is None and body["session"] == "closed"
    assert client.get("/api/v1/public/market-index-quote?force=true").json()["refresh_status"] == "unavailable"
    assert calls == [(False, False), (True, True)]
    monkeypatch.setenv("JANUS_MIS_QUOTES_ENABLED", "false")
    assert client.get("/api/v1/public/market-index-quote?force=true").json()["refresh_status"] == "blocked"
    assert calls[-1] == (False, True)
