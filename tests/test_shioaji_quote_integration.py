"""Shioaji simulation quote integration: auth boundary, source mapping, singleflight."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

from services.api.shioaji_quotes import ShioajiQuotes
from services.api.quote_router import QuoteRouter

TZ = timezone(timedelta(hours=8))


def test_proxy_transport_normalizes_authorized_quote(monkeypatch):
    now = datetime.now(TZ)
    payload = {
        "status": "success",
        "quotes": {"2330": {
            "symbol": "2330", "close": 100.5, "previous_close": 100,
            "source": "shioaji", "exchange": "TSE",
            "trade_time": (now - timedelta(seconds=2)).isoformat(),
            "received_at": now.isoformat(),
        }, "9999": {"symbol": "9999", "close": 1}},
    }
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): return json.dumps(payload).encode()
    requests = []
    def fake_urlopen(request, timeout):
        requests.append(request)
        return Response()
    monkeypatch.setattr("services.api.shioaji_quotes._identity_token", lambda _: "token")
    monkeypatch.setattr("services.api.shioaji_quotes.urlopen", fake_urlopen)
    rows = ShioajiQuotes().prices({"2330": {"market": "TWSE", "enabled": True}})
    assert rows["2330"]["price"] == "100.5"
    assert rows["2330"]["source"] == "shioaji"
    assert list(rows) == ["2330"]
    assert len(requests) == 1
    assert requests[0].get_header("Authorization") == "Bearer token"


def test_proxy_rejects_wrong_exchange_and_future_timestamp(monkeypatch):
    now = datetime.now(TZ)
    data = {"status": "success", "quotes": {"00719B": {
        "symbol": "00719B", "close": 35, "exchange": "TSE",
        "source": "shioaji", "trade_time": now.isoformat(),
        "received_at": now.isoformat(),
    }}}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): return json.dumps(data).encode()
    monkeypatch.setattr("services.api.shioaji_quotes._identity_token", lambda _: "token")
    monkeypatch.setattr("services.api.shioaji_quotes.urlopen", lambda *_args, **_kwargs: Response())
    assert ShioajiQuotes().prices({"00719B": {"market": "TPEX", "enabled": True}}) == {}


class SharedRepo:
    def __init__(self):
        self.in_flight = False
        self.saved = {}
    def last_quotes(self, identities):
        return {s: self.saved[s] for s in identities if s in self.saved}
    def eod_quotes(self, identities):
        return {}
    def save_last_quotes(self, quotes):
        self.saved.update(quotes)
    @contextmanager
    def quote_refresh_guard(self):
        if self.in_flight:
            yield False
            return
        self.in_flight = True
        try:
            yield True
        finally:
            self.in_flight = False


def test_distributed_singleflight_reuses_last_success():
    now = datetime.now(TZ)
    class Source:
        calls = 0
        def prices(self, _):
            self.calls += 1
            return {"2330": {
                "price": "102", "quote_at": now.isoformat(),
                "received_at": now.isoformat(), "source": "shioaji",
            }}
    source, repo = Source(), SharedRepo()
    router = QuoteRouter(repo, source)
    identities = {"2330": {"market": "TWSE", "enabled": True}}
    assert router.refresh(identities, now=now)["updated"] == 1
    assert router.refresh(identities, now=now)["status"] == "fresh"
    assert source.calls == 1
    repo.in_flight = True
    assert router.refresh(identities, force=True, now=now)["status"] == "in_flight"
    assert source.calls == 1
    assert router.read(identities, now=now)["2330"]["source"] == "shioaji"
