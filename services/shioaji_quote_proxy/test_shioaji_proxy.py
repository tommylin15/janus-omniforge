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
