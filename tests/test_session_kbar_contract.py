"""Demand-driven 1m historical Kbars: source separation, cross-user quota, and ACL."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta, date
from pathlib import Path

from services.api.repository import PostgresWorkspaceRepository as Repository


TAIPEI = timezone(timedelta(hours=8))


class _Conn:
    def __init__(self):
        self.statements = []
        self.claims = 0

    def execute(self, sql, args=()):
        self.statements.append((sql, args))
        self.sql = sql
        if "INSERT INTO control.operational_kbar_backfill_state" in sql:
            self.claims += 1
        return self

    def fetchone(self):
        if "count(DISTINCT minute_at)" in self.sql:
            return {"count": 12}
        if "count(*)" in self.sql:
            return {"count": 14}
        if "RETURNING symbol" in self.sql:
            return {"symbol": "2330"} if self.claims == 1 else None
        return None


class _Scope:
    def __init__(self, connection):
        self.conn = connection
    def __enter__(self):
        return self.conn
    def __exit__(self, *_):
        return False


def test_atomic_shared_claim_guards_thrice_daily_and_thirty_minutes():
    repo = object.__new__(Repository)
    db = _Conn()
    repo._connection = lambda: _Scope(db)
    when = datetime(2026, 11, 5, 11, 49, tzinfo=TAIPEI)
    assert repo.reserve_session_kbar_backfill("2330", date(2026, 11, 5), when)
    assert not repo.reserve_session_kbar_backfill("2330", date(2026, 11, 5), when)
    claimed_sql = [sql for sql, _ in db.statements
                   if "INSERT INTO control.operational_kbar_backfill_state" in sql]
    assert claimed_sql and all("ON CONFLICT" in sql for sql in claimed_sql)
    assert all("attempts < 3" in sql and "30 minutes" in sql for sql in claimed_sql)
    assert not repo.reserve_session_kbar_backfill("2330", date(2026, 11, 4), when)
    assert not repo.reserve_session_kbar_backfill("bad/../", date(2026, 11, 5), when)


def test_missing_kbar_source_does_not_override_live_quotes_or_model_prices():
    migration = Path("infra/postgres/migrations/078_session_minute_kbar_backfill.sql").read_text()
    repo = Path("services/api/repository.py").read_text()
    assert "CREATE TABLE IF NOT EXISTS control.operational_session_kbars" in migration
    assert "source text NOT NULL CHECK (source = 'shioaji_kbars')" in migration
    assert "NOT has_table_privilege('janus_public_api'" in migration
    assert "DELETE FROM control.operational_session_kbars" in repo
    assert "WHERE minute_at < now()-interval '3 days'" in repo
    assert "control.operational_last_quotes" in repo
    assert "INSERT INTO control.operational_session_kbars" in repo
    assert "sampled_live_quote" in repo
    assert "historical_1m_close" in repo




def test_iam_private_historical_transport_keeps_broker_source_and_drops_wrong_day(monkeypatch):
    import json
    from urllib.parse import parse_qs, urlsplit
    from services.api.shioaji_quotes import ShioajiQuotes
    from services.api import shioaji_quotes as module
    today = datetime.now(TAIPEI).date().isoformat()
    body = {
        "status": "available", "source": "shioaji_kbars",
        "symbol": "2330", "date": today,
        "points": [
            {"date": f"{today}T09:00:00+08:00", "value": "123.5"},
            {"date": "2026-01-01T09:01:00+08:00", "value": "999"},
        ],
    }
    seen = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, limit): return json.dumps(body).encode()
    def fetch(req, timeout):
        seen.append((req, timeout))
        return Response()
    monkeypatch.setattr(module, "_identity_token", lambda audience: "private-oidc")
    monkeypatch.setattr(module, "urlopen", fetch)
    result = ShioajiQuotes().historical_minutes("2330", today)
    assert result["source"] == "shioaji_kbars"
    assert len(result["points"]) == 1
    assert result["points"][0]["value"] == "123.5"
    assert len(seen) == 1
    request, seconds = seen[0]
    assert seconds <= 16
    assert request.get_header("Authorization") == "Bearer private-oidc"
    url = urlsplit(request.full_url)
    assert url.path == "/kbars"
    assert parse_qs(url.query) == {"symbol": ["2330"], "day": [today]}
    body["source"] = "other"
    try:
        ShioajiQuotes().historical_minutes("2330", today)
        assert False, "untrusted source must fail closed"
    except ValueError:
        pass
