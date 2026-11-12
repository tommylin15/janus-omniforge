"""Unit tests for Shioaji Quote Proxy."""

import json
import os
import pytest
from fastapi.testclient import TestClient

from services.shioaji_quote_proxy.main import app, resolve_credentials, ShioajiManager


def test_resolve_credentials_from_bundle(monkeypatch):
    test_bundle = {
        "shioaji_api_key": "test_key_123",
        "shioaji_secret_key": "test_secret_456",
        "shioaji_person_id": "A123456789",
        "shioaji_password": "test_password",
    }
    monkeypatch.setenv("JANUS_RUNTIME_BUNDLE", json.dumps(test_bundle))
    monkeypatch.delenv("SHIOAJI_API_KEY", raising=False)
    monkeypatch.delenv("SHIOAJI_SECRET_KEY", raising=False)

    api_key, secret_key, person_id, password = resolve_credentials()
    assert api_key == "test_key_123"
    assert secret_key == "test_secret_456"
    assert person_id == "A123456789"
    assert password == "test_password"


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "janus-shioaji-quote-proxy"
        assert data["region"] == "asia-east1"
        assert "shioaji" in data


def test_quotes_endpoint_validation():
    with TestClient(app) as client:
        # Empty symbols
        resp = client.get("/quotes?symbols=")
        assert resp.status_code == 400

        # Valid symbols structure
        resp = client.get("/quotes?symbols=2382,2327")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "quotes" in data


def test_simulation_login_never_attempts_production(monkeypatch):
    import sys
    from types import SimpleNamespace
    modes = []
    class FakeClient:
        def __init__(self, simulation):
            modes.append(simulation)
        def login(self, **kwargs):
            return []
        def fetch_contracts(self, **kwargs):
            return None
    monkeypatch.setitem(sys.modules, "shioaji", SimpleNamespace(Shioaji=FakeClient))
    manager = ShioajiManager(api_key="fake", secret_key="fake")
    assert manager.initialize()
    assert modes == [True]


def test_no_snapshot_polling_and_shared_subscription(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    import sys
    from services.shioaji_quote_proxy.streaming import StreamCache

    count = []
    class Client:
        def __init__(self):
            self.contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, fn):
            self.stock_callback = fn
        def set_on_quote_idx_v1_callback(self, fn):
            self.index_callback = fn
        def subscribe(self, contract, *, quote_type):
            count.append(contract)
        def unsubscribe(self, contract, *, quote_type):
            pass
        def snapshots(self, contracts):
            raise AssertionError("must never poll snapshots")
    monkeypatch.setitem(sys.modules, "shioaji",
                        SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote")))
    client = Client()
    cache = StreamCache(client)
    now = datetime.now(timezone(timedelta(hours=8)))
    quote = SimpleNamespace(code="2330", datetime=now, close=100,
                            price_chg=2, open=98, high=101, low=97,
                            total_volume=1000, simtrade=False)
    client.stock_callback(SimpleNamespace(value="TSE"), quote)
    assert cache.read(["2330"])["2330"]["close"] == 100
    assert cache.read(["2330"])["2330"]["previous_close"] == 98
    assert count == ["2330"]


def test_simulation_callback_with_old_trade_time_is_not_live_even_if_just_received(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    import sys
    from services.shioaji_quote_proxy import streaming
    from services.shioaji_quote_proxy.streaming import StreamCache

    class Client:
        contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, fn): self.cb = fn
        def set_on_quote_idx_v1_callback(self, fn): pass
        def subscribe(self, *_, **__): pass
        def unsubscribe(self, *_, **__): pass

    monkeypatch.setitem(sys.modules, "shioaji",
                        SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote")))
    monkeypatch.setattr(streaming, "sleep", lambda _: None)
    cache = StreamCache(Client())
    now = datetime.now(timezone(timedelta(hours=8)))
    # A simulation source may replay a 5-minute-old trade right now.
    stale = SimpleNamespace(code="2330", datetime=now - timedelta(minutes=5),
                            close=100, reference=99, total_volume=1, simtrade=False)
    cache.on_stock(SimpleNamespace(value="TSE"), stale)
    assert cache.latest["2330"]["received_at"].startswith(now.date().isoformat())
    assert cache.read(["2330"]) == {}
    # A real fresh trade becomes usable without inventing a timestamp.
    fresh = SimpleNamespace(code="2330", datetime=datetime.now(timezone(timedelta(hours=8))),
                            close=101, reference=99, total_volume=2, simtrade=False)
    cache.on_stock(SimpleNamespace(value="TSE"), fresh)
    assert cache.read(["2330"])["2330"]["close"] == 101


def test_stock_etf_reference_is_retained_when_price_chg_missing(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from services.shioaji_quote_proxy.streaming import StreamCache
    class Client:
        contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, fn): self.cb = fn
        def set_on_quote_idx_v1_callback(self, fn): pass
        def subscribe(self, *_, **__): pass
        def unsubscribe(self, *_, **__): pass
    monkeypatch.setitem(__import__("sys").modules, "shioaji",
                        SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote")))
    cache = StreamCache(Client())
    event = SimpleNamespace(code="0050", datetime=datetime.now(timezone(timedelta(hours=8))),
                            close=98.1, reference=97.5, open=97.8, high=98.5, low=97.6,
                            total_volume=1000, simtrade=False)
    cache.on_stock(SimpleNamespace(value="TSE"), event)
    assert cache.read(["0050"])["0050"]["previous_close"] == 97.5


def test_index_subscription_maps_to_taiex(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    import sys
    from services.shioaji_quote_proxy.streaming import StreamCache
    called = []
    class Client:
        contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, fn): pass
        def set_on_quote_idx_v1_callback(self, fn): self.cb = fn
        def subscribe(self, contract, *, quote_type): called.append(contract)
        def unsubscribe(self, contract, *, quote_type): pass
    monkeypatch.setitem(sys.modules, "shioaji",
                        SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote")))
    client = Client()
    cache = StreamCache(client)
    client.cb(SimpleNamespace(code="IX0001",
               datetime=datetime.now(timezone(timedelta(hours=8))),
               close=43227.63, reference=43100, open=43000,
               high=43400, low=42900, vol_sum=20000))
    assert cache.read(["TAIEX"])["TAIEX"]["source"] == "shioaji"
    assert called == ["IX0001"]


def test_mis_no_last_close_fake_quote(monkeypatch):
    from services.shioaji_quote_proxy.main import fetch_twse_mis
    class Response:
        status_code = 200
        def json(self):
            return {"msgArray": [{"ex":"tse", "c":"2330", "z":"-",
                                   "y":"100", "d":"20261104", "t":"10:00:00"}]}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr("services.shioaji_quote_proxy.main.httpx.Client", Client)
    assert fetch_twse_mis(["2330"]) == {}


def test_standalone_cloud_run_main_imports_streaming(monkeypatch):
    """uvicorn main:app loads a flat module, not services.shioaji_quote_proxy."""
    from pathlib import Path
    import importlib.util
    import sys
    from types import SimpleNamespace

    folder = Path(__file__).resolve().parent
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location("shioaji_proxy_flat_main", folder / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__package__ == ""

    class Client:
        contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, callback): self.stock_callback = callback
        def set_on_quote_idx_v1_callback(self, callback): self.index_callback = callback
        def subscribe(self, contract, *, quote_type): pass
        def unsubscribe(self, contract, *, quote_type): pass

    monkeypatch.setitem(sys.modules, "shioaji",
                        SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote")))
    manager = module.ShioajiManager()
    manager.logged_in = True
    manager.api = Client()
    monkeypatch.setattr(module, "fetch_twse_mis", lambda symbols: {})
    assert manager.get_quotes(["2330"]) == {}
    assert hasattr(manager, "_stream_cache")


def test_stream_failure_falls_back_without_500(monkeypatch):
    from types import SimpleNamespace

    class UnsupportedClient:
        def set_on_quote_stk_v1_callback(self, callback):
            raise RuntimeError("mock client subscription broken")

    manager = ShioajiManager()
    manager.logged_in = True
    manager.api = UnsupportedClient()
    calls = []
    expected = {"2330": {"symbol": "2330", "source": "twse_mis", "close": 101}}
    def mis(symbols):
        calls.append(symbols)
        return expected
    monkeypatch.setattr("services.shioaji_quote_proxy.main.fetch_twse_mis", mis)
    assert manager.get_quotes(["2330"]) == expected
    assert calls == [["2330"]]


def test_missing_etf_prior_close_uses_same_day_mis_trade_without_mixing_sources(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from services.shioaji_quote_proxy.main import TAIWAN_TZ
    manager = ShioajiManager()
    manager.logged_in = True
    class Stream:
        def read(self, symbols):
            at = datetime.now(TAIWAN_TZ)
            return {"0050": {"symbol": "0050", "exchange": "TSE",
                             "close": 98.1, "previous_close": None,
                             "trade_time": at.isoformat(), "source": "shioaji"}}
    manager._stream_cache = Stream()
    now = datetime.now(TAIWAN_TZ)
    monkeypatch.setattr("services.shioaji_quote_proxy.main.fetch_twse_mis",
                        lambda symbols: {"0050": {
                            "symbol": "0050", "exchange": "TSE", "close": 98.0,
                            "previous_close": 97.5, "trade_time": now.isoformat(),
                            "source": "twse_mis"}})
    quotes = manager.get_quotes(["0050"])
    assert quotes["0050"]["source"] == "twse_mis"
    assert quotes["0050"]["close"] == 98.0
    assert quotes["0050"]["previous_close"] == 97.5


def test_stale_mis_cannot_replace_today_etf_quote(monkeypatch):
    from datetime import datetime, timedelta
    from services.shioaji_quote_proxy.main import TAIWAN_TZ
    manager = ShioajiManager()
    manager.logged_in = True
    now = datetime.now(TAIWAN_TZ)
    class Stream:
        def read(self, symbols):
            return {"0050": {"symbol": "0050", "exchange": "TSE",
                             "close": 98.1, "previous_close": None,
                             "trade_time": now.isoformat(), "source": "shioaji"}}
    manager._stream_cache = Stream()
    monkeypatch.setattr("services.shioaji_quote_proxy.main.fetch_twse_mis",
                        lambda symbols: {"0050": {
                            "symbol": "0050", "exchange": "TSE", "close": 97.0,
                            "previous_close": 96.5,
                            "trade_time": (now - timedelta(minutes=5)).isoformat(),
                            "source": "twse_mis"}})
    quotes = manager.get_quotes(["0050"])
    assert quotes["0050"]["source"] == "shioaji"
    assert quotes["0050"]["previous_close"] is None


def test_mis_trade_time_preserves_dated_timestamp_for_janus(monkeypatch):
    """Janus refuses undated HH:MM:SS timestamps; Proxy must send ISO 8601."""
    from datetime import datetime, timedelta, timezone
    from services.shioaji_quote_proxy.main import fetch_twse_mis
    today = datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)
    class Response:
        status_code = 200
        def json(self):
            return {"msgArray": [{
                "ex": "tse", "c": "2330", "z": "101.5", "y": "100",
                "d": today.strftime("%Y%m%d"), "t": "10:01:30",
            }, {
                "ex": "tse", "c": "t00", "z": "23456.78", "y": "23000",
                "d": today.strftime("%Y%m%d"), "t": "10:02:30",
            }]}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr("services.shioaji_quote_proxy.main.httpx.Client", Client)
    quotes = fetch_twse_mis(["2330", "TAIEX"])
    assert set(quotes) == {"2330", "TAIEX"}
    for symbol in quotes:
        row = quotes[symbol]
        observed = datetime.fromisoformat(row["trade_time"])
        assert observed.tzinfo is not None
        assert observed.date() == today.date()
        assert row["received_at"] and row["exchange"] == "TSE"
    assert quotes["TAIEX"]["close"] == 23456.78



def test_broker_kbars_use_taipei_wall_clock_and_right_label_not_utc_plus_eight():
    """Provider nanosecond timestamps must display 09:00, not 17:00."""
    from datetime import date, datetime, timezone, timedelta
    from types import SimpleNamespace
    from services.shioaji_quote_proxy.kbars import session_kbars
    tw = timezone(timedelta(hours=8))
    # Exchange timestamp 09:01 closes the 09:00 minute.
    raw_ns = int(datetime(2026, 11, 5, 9, 1, tzinfo=timezone.utc).timestamp()) * 10**9
    second_ns = raw_ns + 60 * 10**9
    future_ns = raw_ns + 240 * 60 * 10**9
    class SDK:
        contracts = {"2330": SimpleNamespace(code="2330")}
        calls = 0
        def kbars(self, **kwargs):
            self.calls += 1
            assert kwargs["start"] == kwargs["end"] == "2026-11-05"
            assert kwargs["timeout"] == 6000
            return SimpleNamespace(ts=[raw_ns, second_ns, future_ns],
                                   Close=[100.5, 101.5, 990.0])
    sdk = SDK()
    result = session_kbars(sdk, "2330", date(2026, 11, 5),
                           now=datetime(2026, 11, 5, 11, 49, tzinfo=tw))
    assert sdk.calls == 1
    assert result["status"] == "available"
    assert [x["date"][11:16] for x in result["points"]] == ["09:00", "09:01"]
    assert [x["value"] for x in result["points"]] == ["100.5", "101.5"]
    assert all(x["date"].endswith("+08:00") for x in result["points"])
    assert result["bar_semantics"] == "one-minute-right-labelled-close"


def test_kbars_refuse_future_wrong_day_invalid_price_and_no_contract():
    from datetime import date, datetime, timezone, timedelta
    from types import SimpleNamespace
    from services.shioaji_quote_proxy.kbars import session_kbars
    tw = timezone(timedelta(hours=8))
    today = date(2026, 11, 5)
    sdk = SimpleNamespace(contracts={}, kbars=lambda **_: 1)
    assert session_kbars(sdk, "2330", today,
                         now=datetime(2026, 11, 5, 12, tzinfo=tw))["status"] == "unavailable"
    try:
        session_kbars(sdk, "2330", date(2026, 11, 4),
                      now=datetime(2026, 11, 5, 12, tzinfo=tw))
        assert False, "wrong-day historical request must be rejected"
    except ValueError:
        pass


def test_private_proxy_historical_endpoint_is_one_day_and_simulation_manager_only(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from fastapi.testclient import TestClient
    from services.shioaji_quote_proxy import main as proxy
    tw = timezone(timedelta(hours=8))
    today = datetime.now(tw).date().isoformat()
    calls = []
    class Fake:
        def historical_minutes(self, symbol, trade_day):
            calls.append((symbol, trade_day))
            return {"status": "missing", "source": "shioaji_kbars",
                    "symbol": symbol, "date": trade_day.isoformat(), "points": []}
    monkeypatch.setattr(proxy, "CLIENT", Fake())
    # No lifespan startup here: never start a real broker session in tests.
    client = TestClient(proxy.app)
    assert client.get("/kbars", params={"symbol": "../../foo", "day": today}).status_code == 400
    assert client.get("/kbars", params={"symbol": "2330", "day": "2020-01-01"}).status_code == 400
    response = client.get("/kbars", params={"symbol": "2330", "day": today})
    assert response.status_code == 200
    assert response.json()["source"] == "shioaji_kbars"
    assert calls == [("2330", datetime.now(tw).date())]


def test_fetch_endpoint_allowlist_validation():
    from fastapi.testclient import TestClient
    from services.shioaji_quote_proxy import main as proxy
    client = TestClient(proxy.app)
    assert client.post("/fetch", json={"url": "https://evil.example.com/test"}).status_code == 400
    assert client.post("/fetch", json={"url": "http://blave.org/studio"}).status_code == 400



def test_bidask_five_levels_shared_and_unsubscribed_without_snapshot(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    import sys
    from services.shioaji_quote_proxy.streaming import StreamCache
    from services.shioaji_quote_proxy import streaming
    events = []
    class Client:
        contracts = SimpleNamespace(get=lambda code: code)
        def set_on_quote_stk_v1_callback(self, fn): self.quote = fn
        def set_on_quote_idx_v1_callback(self, fn): self.index = fn
        def set_on_bidask_stk_v1_callback(self, fn): self.bidask = fn
        def subscribe(self, contract, *, quote_type): events.append(("on", contract, quote_type))
        def unsubscribe(self, contract, *, quote_type): events.append(("off", contract, quote_type))
        def snapshots(self, *_): raise AssertionError("SDK snapshots forbidden")
    monkeypatch.setitem(sys.modules, "shioaji", SimpleNamespace(
        QuoteType=SimpleNamespace(Quote="quote", BidAsk="bidask")))
    monkeypatch.setattr(streaming, "sleep", lambda _: None)
    client = Client()
    cache = StreamCache(client)
    now = datetime.now(timezone(timedelta(hours=8)))
    book = SimpleNamespace(code="2330", datetime=now, simtrade=False, intraday_odd=False,
                           bid_price=[100, 99.5, 99, 98.5, 98],
                           ask_price=[100.5, 101, 101.5, 102, 102.5],
                           bid_volume=[12, 20, 18, 10, 9],
                           ask_volume=[5, 8, 12, 15, 19])
    assert cache.read_book("2330") is None
    client.bidask(SimpleNamespace(value="TSE"), book)
    assert len(cache.read_book("2330")["bid"]) == 5
    assert cache.read_book("2330")["ask"][0]["volume"] == 5
    assert events == [("on", "2330", "bidask")]
    book.simtrade = True
    book.bid_volume[0] = 999
    client.bidask(SimpleNamespace(value="TSE"), book)
    assert cache.read_book("2330")["bid"][0]["volume"] == 12
    cache.book_demand["2330"] = -1
    cache._unsubscribe_expired(0)
    assert ("off", "2330", "bidask") in events
    assert cache.read_book("2330") is None


def test_proxy_order_book_returns_missing_not_fabricated_levels(monkeypatch):
    from services.shioaji_quote_proxy import main
    with TestClient(app) as client:
        assert client.get("/order-book/$$").status_code == 400
        monkeypatch.setattr(main.CLIENT, "get_order_book", lambda symbol: None)
        result = client.get("/order-book/2330")
        assert result.status_code == 200
        assert result.json()["status"] == "missing"
        assert result.json()["data"] is None


def test_taiex_mis_fallback_15_seconds_shared_cache_and_equities_60(monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    import services.shioaji_quote_proxy.main as proxy

    manager = ShioajiManager()
    manager.logged_in = True
    manager._stream_cache = SimpleNamespace(read=lambda symbols: {})
    clock = [100.0]
    tick = datetime.now(proxy.TAIWAN_TZ) - timedelta(seconds=75)
    calls = []
    def fetch(symbols):
        calls.append(tuple(symbols))
        at = (tick + timedelta(seconds=clock[0] - 100)).isoformat()
        return {s: {"symbol": s, "trade_time": at, "received_at": at,
                    "source": "twse_mis", "close": 100, "previous_close": 99}
                for s in symbols}
    monkeypatch.setattr(proxy, "monotonic", lambda: clock[0])
    monkeypatch.setattr(proxy, "fetch_twse_mis", fetch)
    first = manager.get_quotes(["TAIEX", "2330"])
    assert set(first) == {"TAIEX", "2330"}
    clock[0] = 105
    cached = manager.get_quotes(["TAIEX", "2330"])
    assert cached == {"TAIEX": first["TAIEX"]}
    assert calls == [("TAIEX", "2330")]
    clock[0] = 115
    updated = manager.get_quotes(["TAIEX", "2330"])
    assert updated["TAIEX"]["trade_time"] != first["TAIEX"]["trade_time"]
    assert "2330" not in updated
    assert calls[-1] == ("TAIEX",)
    clock[0] = 159
    manager.get_quotes(["TAIEX", "2330"])
    assert calls[-1] == ("TAIEX",)
    clock[0] = 160
    manager.get_quotes(["TAIEX", "2330"])
    assert calls[-1] == ("2330",)
    assert len(calls) == 4


def test_taiex_mis_cache_never_changes_original_time_on_failure(monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    import services.shioaji_quote_proxy.main as proxy

    manager = ShioajiManager()
    manager.logged_in = True
    manager._stream_cache = SimpleNamespace(read=lambda symbols: {})
    clock = [100.0]
    tick = (datetime.now(proxy.TAIWAN_TZ) - timedelta(seconds=10)).isoformat()
    row = {"symbol": "TAIEX", "trade_time": tick, "received_at": tick,
           "source": "twse_mis", "close": 100, "previous_close": 99}
    monkeypatch.setattr(proxy, "monotonic", lambda: clock[0])
    monkeypatch.setattr(proxy, "fetch_twse_mis", lambda _: {"TAIEX": row})
    assert manager.get_quotes(["TAIEX"])["TAIEX"] == row
    clock[0] = 115
    monkeypatch.setattr(proxy, "fetch_twse_mis", lambda _: {})
    assert manager.get_quotes(["TAIEX"])["TAIEX"] == row
    # Shioaji takes precedence when its own real tick has a reference.
    stream = {**row, "source": "shioaji", "close": 101}
    manager._stream_cache = SimpleNamespace(read=lambda symbols: {"TAIEX": stream})
    assert manager.get_quotes(["TAIEX"])["TAIEX"] == stream
