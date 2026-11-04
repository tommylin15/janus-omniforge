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
    assert "markExtrema: true" in source
