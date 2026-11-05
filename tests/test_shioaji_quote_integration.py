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



def test_resolve_freshness_uses_elapsed_io_time_not_pre_refresh_clock(monkeypatch):
    """A valid tick arriving while the request runs must not become STALE."""
    now = datetime(2026, 11, 5, 10, 0, tzinfo=TZ)
    observed = now + timedelta(seconds=2)
    repo = SharedRepo()
    repo.saved["2330"] = {
        "price": "102", "quote_at": observed.isoformat(),
        "received_at": observed.isoformat(), "source": "shioaji",
    }
    router = QuoteRouter(repo, object())
    seen = []

    def refresh(_identities, force=False, now=None):
        seen.append(now)
        return {"status": "updated", "requested": 1, "updated": 1}

    monkeypatch.setattr(router, "refresh", refresh)
    clock = iter([100.0, 103.0])
    monkeypatch.setattr("services.api.quote_router.monotonic", lambda: next(clock))
    prices, result = router.resolve(
        {"2330": {"market": "TWSE", "enabled": True}},
        refresh=True, now=now,
    )
    assert seen == [now]
    assert result["status"] == "updated"
    assert prices["2330"]["state"] == "intraday"


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


def test_shioaji_is_an_authorized_source_for_owner_reference_valuation():
    from services.api.intraday_quotes import value_holdings
    now = datetime(2026, 11, 4, 10, 15, tzinfo=TZ)
    rows = [{"symbol": "2330", "currency": "TWD", "shares": "10",
             "average_cost": "100"}]
    quotes = {"2330": {
        "price": "105", "source": "shioaji", "state": "intraday",
        "quote_at": now.isoformat(), "received_at": now.isoformat(),
        "price_date": now.date().isoformat(), "is_final": False
    }}
    result = value_holdings(rows, quotes, now=now)
    row = result["positions"][0]
    assert row["reference_eligible"] is True
    assert row["market_price"] == "105"
    assert row["unrealized_pnl"] == "50"
    assert row["price_source"] == "shioaji"
    assert row["price_status"] == "available"
    assert result["items"][0]["aggregate_status"] == "available"


def test_pg_session_advisory_guard_reads_dict_row_by_name(monkeypatch):
    """Psycopg Repository uses dict_row, never positional fetchone()[0]."""
    from contextlib import contextmanager
    from services.api.repository import PostgresWorkspaceRepository
    seen = []
    class FakeConn:
        def execute(self, query, params):
            seen.append((query, params))
            return self
        def fetchone(self):
            return {"acquired": True}
    @contextmanager
    def fake_connection():
        yield FakeConn()
    repo = PostgresWorkspaceRepository("postgresql://example.invalid/test")
    monkeypatch.setattr(repo, "_connection", fake_connection)
    with repo.quote_refresh_guard() as acquired:
        assert acquired is True
        assert "pg_try_advisory_lock" in seen[0][0]
    assert "pg_advisory_unlock" in seen[1][0]
    assert len(seen) == 2


def test_intraday_index_writer_uses_dict_row_for_optional_table(monkeypatch):
    """The migration-ready table check must not use fetchone()[0]."""
    from contextlib import contextmanager
    from services.api.repository import PostgresWorkspaceRepository
    statements = []
    batches = []
    class Conn:
        def execute(self, query, params=None):
            statements.append((query, params))
            return self
        def fetchone(self):
            if "has_table_privilege" in statements[-1][0]:
                return {"allowed": True}
            return {"table_name": "control.operational_index_minutes"}
        def cursor(self):
            return self
        def executemany(self, query, rows):
            batches.append((query, rows))
    @contextmanager
    def fake_connection():
        yield Conn()
    repo = PostgresWorkspaceRepository("postgresql://example.invalid/test")
    monkeypatch.setattr(repo, "_connection", fake_connection)
    now = datetime(2026, 11, 4, 10, 15, tzinfo=TZ).isoformat()
    quote = {"TAIEX": {"price": "43227.63", "quote_at": now,
             "received_at": now, "session": "regular",
             "source": "shioaji", "route_version": "latest-price.v2",
             "previous_close": "43000"}}
    assert repo.save_last_quotes(quote) == 1
    assert any("operational_index_minutes" in query and "INSERT" in query
               for query, _ in statements)
    assert len(batches) == 1
    assert batches[0][1][0][5] == "shioaji"
    assert any("DELETE FROM control.operational_index_minutes" in query
               and "interval '3 days'" in query for query, _ in statements)


def test_twenty_concurrent_quote_readers_singleflight():
    """20 concurrent page readers must produce one upstream quote refresh."""
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Barrier, Event, Lock

    class ConcurrentRepo(SharedRepo):
        def __init__(self):
            super().__init__()
            self.mutex = Lock()
        @contextmanager
        def quote_refresh_guard(self):
            acquired = self.mutex.acquire(blocking=False)
            try:
                yield acquired
            finally:
                if acquired:
                    self.mutex.release()

    started, release = Event(), Event()
    repo = ConcurrentRepo()
    class Source:
        def __init__(self):
            self.calls = 0
        def prices(self, identities):
            self.calls += 1
            started.set()
            assert release.wait(timeout=5)
            now = datetime.now(TZ).isoformat()
            return {"2330": {"price":"100", "source":"shioaji",
                             "quote_at":now, "received_at":now}}
    source = Source()
    router = QuoteRouter(repo, source)
    identities = {"2330":{"market":"TWSE","enabled":True}}
    barrier = Barrier(20)
    def visit(_):
        barrier.wait(timeout=5)
        return router.refresh(identities)
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(visit, i) for i in range(20)]
        assert started.wait(timeout=5)
        release.set()
        results = [f.result(timeout=8) for f in futures]
    assert source.calls == 1
    assert sum(row["status"] == "updated" for row in results) == 1
    assert all(row["status"] in {"updated","fresh","in_flight"} for row in results)
