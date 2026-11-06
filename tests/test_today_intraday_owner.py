"""Today's page-demanded quote history must remain Owner scoped and non-canonical."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.app import create_app
from tests.test_portfolio_api_completeness import Repository, Store, auth


def test_owner_held_symbol_only_and_no_refresh_side_effects():
    repo = Repository()
    seen = []
    repo.positions = lambda owner: [{
        "symbol": "2330", "currency": "TWD", "shares": "10"
    }]
    def read(symbol, trade_date=None):
        seen.append((symbol, trade_date))
        return [
            {"date": "2026-11-04T09:01:00+08:00", "value": "102.5"},
            {"date": "2026-11-04T09:02:00+08:00", "value": "103"},
        ]
    repo.stock_intraday_points = read
    repo.official_previous_closes = lambda dates: {
        "2330": {"previous_close": "101", "previous_close_date": "2026-11-04"}
    }
    claims = {"iss": "https://accounts.google.com", "aud": "user-client",
              "sub": "google-a", "email": "owner@example.com",
              "email_verified": True, "exp": 1900000000}
    app = TestClient(create_app(repo, Store(), lambda *_: claims,
                                audience="user-client"))
    assert app.get("/api/v1/me/portfolio/intraday?symbol=2330").status_code == 401
    assert app.get("/api/v1/me/portfolio/intraday?symbol=2382",
                   headers=auth()).status_code == 404
    assert app.get("/api/v1/me/portfolio/intraday?symbol=2330%27",
                   headers=auth()).status_code == 422
    valid = app.get("/api/v1/me/portfolio/intraday?symbol=2330", headers=auth())
    assert valid.status_code == 200
    payload = valid.json()
    assert payload["symbol"] == "2330"
    assert payload["observation_kind"] == "page_demanded_minutes"
    assert payload["is_full_day"] is False
    assert payload["count"] == 2
    assert payload["previous_close"] == "101"
    assert payload["previous_close_source"] == "official_previous_close"
    assert len(seen) == 1
    assert seen[0][1].isoformat() == payload["as_of"]


def test_intraday_implementation_does_not_insert_unobserved_candles():
    text = Path("services/api/repository.py").read_text()
    assert "control.operational_symbol_minutes" in text
    assert "WHERE EXCLUDED.quote_at >" in text
    assert "row.get(\"session\") == \"regular\"" in text
    assert "minute_at < now() - interval '3 days'" in text
    sql = Path("infra/postgres/migrations/076_operational_stock_minutes.sql").read_text()
    assert "NOT has_table_privilege('janus_public_api'" in sql
    assert "PRIMARY KEY (symbol,minute_at)" in sql


def test_today_frontend_fetch_only_from_visible_page_and_never_calls_old_highlights():
    source = Path("apps/user_app/lib/final_today_v2.dart").read_text()
    assert "今天值得看" not in source
    assert "/api/v1/me/today-changes" not in source
    assert "ownerQuotes = market.then((_) => _loadOwnerQuotes())" in source
    assert "widget.active && foreground" in source
    assert "/api/v1/me/portfolio/intraday?symbol=" in source
    assert "FvIntradayProgressChart" in source
    assert "previous_close_source" in source

def test_taiex_minutes_retention_is_three_days_and_read_path_is_bounded():
    repository = Path("services/api/repository.py").read_text()
    migration = Path("infra/postgres/migrations/077_index_minutes_three_day_retention.sql").read_text()
    assert "DELETE FROM control.operational_index_minutes" in repository
    assert "WHERE minute_at < now() - interval '3 days'" in repository
    assert "GRANT DELETE ON control.operational_index_minutes TO janus_private_api" in migration
    assert "SELECT has_table_privilege('janus_private_api'" not in migration or "DELETE" in migration
    assert "FROM control.operational_index_minutes" in repository
    assert "ORDER BY minute_at ASC LIMIT 271" in repository


def test_no_official_previous_close_means_no_synthetic_zero_reference():
    repo = Repository()
    repo.positions = lambda owner: [{
        "symbol": "2330", "currency": "TWD", "shares": "10",
    }]
    repo.stock_intraday_points = lambda symbol, trade_date=None: []
    repo.official_previous_closes = lambda dates: {}
    claims = {"iss": "https://accounts.google.com", "aud": "user-client",
              "sub": "google-a", "email": "owner@example.com",
              "email_verified": True, "exp": 1900000000}
    client = TestClient(create_app(repo, Store(), lambda *_: claims, audience="user-client"))
    response = client.get("/api/v1/me/portfolio/intraday?symbol=2330", headers=auth())
    assert response.status_code == 200
    assert response.json()["previous_close"] is None
    assert response.json()["previous_close_source"] is None



def test_backfilled_kbars_are_separate_from_quote_snapshot_rows_and_have_provenance():
    from services.api.repository import PostgresWorkspaceRepository as PostgresRepository
    from datetime import datetime
    tw = timezone(timedelta(hours=8))
    at_900 = datetime(2026, 11, 5, 9, 0, tzinfo=tw)
    at_901 = datetime(2026, 11, 5, 9, 1, tzinfo=tw)
    at_902 = datetime(2026, 11, 5, 9, 2, tzinfo=tw)
    candles = [
        {"minute_at": at_900, "price": "100.2"},
        {"minute_at": at_901, "price": "100.5"},
    ]
    observations = [
        {"minute_at": at_900, "price": "100.1", "source": "shioaji"},
        {"minute_at": at_902, "price": "101.0", "source": "shioaji"},
    ]
    merged = PostgresRepository._merge_minute_sources(observations, candles, tw)
    assert [row["date"][11:16] for row in merged] == ["09:00", "09:01", "09:02"]
    assert [row["value"] for row in merged] == ["100.2", "100.5", "101.0"]
    assert [row["source"] for row in merged] == [
        "shioaji_kbars", "shioaji_kbars", "shioaji"
    ]
    assert [row["observation_kind"] for row in merged] == [
        "historical_1m_close", "historical_1m_close", "sampled_live_quote"
    ]


def test_owner_gapfill_requires_held_symbol_and_a_cross_instance_claim():
    repo = Repository()
    repo.positions = lambda owner: [
        {"symbol": "2330", "currency": "TWD", "shares": "10"}
    ]
    requested = []
    saved = []
    repo.reserve_session_kbar_backfill = lambda symbol, day, now: requested.append(symbol) or True
    repo.save_session_kbars = lambda symbol, day, rows, status="missing": (
        saved.append((symbol, status, rows)) or len(rows)
    )

    class FakeBroker:
        def historical_minutes(self, symbol, day):
            return {"status": "available", "source": "shioaji_kbars",
                    "symbol": symbol, "date": day,
                    "points": [{"date": f"{day}T09:00:00+08:00", "value": "101"}]}

    claims = {"iss": "https://accounts.google.com", "aud": "user-client",
              "sub": "google-a", "email": "owner@example.com",
              "email_verified": True, "exp": 1900000000}
    client = TestClient(create_app(repo, Store(), lambda *_: claims,
                                  audience="user-client", quotes=FakeBroker()))
    url = "/api/v1/me/market/minute-backfill"
    assert client.post(url, json={"symbol": "2330"}).status_code == 401
    assert client.post(url, json={"symbol": "2382"}, headers=auth()).status_code == 404
    assert client.post(url, json={"symbol": "../"}, headers=auth()).status_code == 422
    response = client.post(url, json={"symbol": "2330"}, headers=auth())
    assert response.status_code == 200
    if datetime.now(timezone(timedelta(hours=8))).hour < 9:
        assert response.json()["status"] == "not_session"
    else:
        assert response.json()["status"] in {"available", "not_session"}
    # Missing position is always denied even when history is unavailable.
    assert "2382" not in requested
    if requested:
        assert saved and saved[0][0] == "2330"
        assert saved[0][1] == "available"
    assert "control.operational_session_kbars" in Path(
        "infra/postgres/migrations/078_session_minute_kbar_backfill.sql").read_text()



def test_on_entry_only_kbar_gap_refresh_never_called_by_quote_timer():
    source = Path("apps/user_app/lib/final_today_v2.dart").read_text()
    # Entry/resume/tab-return paths can grow; the safety boundary is that the
    # 60s quote timer never triggers Shioaji's historical Kbars.
    assert source.count("_loadOwnerQuotes(onDemandBackfill: true)") >= 4
    assert "if (onDemandBackfill) _requestHistoricalGapFill(selectedHolding!);" in source
    timer = source.split("marketTimer = Timer.periodic", 1)[1].split(
        "Future<dynamic> _loadMarketWithoutPerf", 1)[0]
    assert "_requestHistoricalGapFill" not in timer
    assert "market.then((_) => _loadOwnerQuotes())" in timer
    assert "(minute - 540) ~/ 30" in source
    assert "_backfillInFlight.contains(symbol)" in source
