from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from services.api.app import create_app


USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class Repository:
    def resolve_user(self, sub, email):
        return USER_ID

    def ledger_history(self, user_id, symbol, year):
        return [{"user_id": user_id, "symbol": symbol or "2330", "event_type": None}]

    def stock_identities(self, symbols):
        return {"2330": {"symbol": "2330", "name": "台積電", "market": "TWSE", "enabled": True}}


class Store:
    def __init__(self):
        self.calls = []

    def mart(self, table, user_id, **filters):
        self.calls.append((table, user_id, filters))
        anchor = {"user_id": str(user_id), "ledger_version": 7, "valuation_date": "2026-09-05"}
        if table == "mart_user_portfolio_summary":
            return [{**anchor, "currency": "TWD", "market_value": "120", "cost_basis": "100",
                     "unrealized_pnl": "20", "unrealized_return": "0.2", "aggregate_status": "available",
                     "affected_symbol_count": 0, "affected_symbols": "[]", "missing_price_count": 0,
                     "stale_price_count": 0, "valuation_status": "available",
                     "cash_safety_status": "insufficient_data", "cash_ratio": None, "minimum_cash_ratio": None}]
        if table == "mart_user_positions":
            if filters == {"valuation_date": "2026-09-05", "ledger_version": 7}:
                return [{**anchor, "symbol": "2330", "currency": "TWD", "stock_name": "台積電",
                         "shares": "1", "average_cost": "100", "market_price": "120", "market_value": "120",
                         "price_status": "available", "price_date": "2026-09-05", "missing_reason": None}]
            return [{"user_id": str(user_id), "ledger_version": 8, "valuation_date": "2026-09-06",
                     "symbol": "2330", "currency": "TWD", "stock_name": "台積電", "shares": "1",
                     "average_cost": "100", "market_price": "121", "market_value": "121",
                     "price_status": "available", "price_date": "2026-09-06", "missing_reason": None}]
        if table == "mart_user_unrealized_pnl":
            if filters == {"valuation_date": "2026-09-05", "ledger_version": 7}:
                return [{**anchor, "symbol": "2330", "currency": "TWD", "unrealized_pnl": "20",
                         "unrealized_return": "0.2", "price_status": "available", "price_date": "2026-09-05",
                         "missing_reason": None}]
            return [{"user_id": str(user_id), "ledger_version": 8, "valuation_date": "2026-09-06",
                     "symbol": "2330", "currency": "TWD", "unrealized_pnl": "21",
                     "unrealized_return": "0.21", "price_status": "available", "price_date": "2026-09-06",
                     "missing_reason": None}]
        return []


def make_client(store=None):
    repository = Repository()
    store = store or Store()
    claims = {"iss": "https://accounts.google.com", "aud": "user-client", "sub": "google-a",
              "email": "owner@example.com", "email_verified": True, "exp": 1_900_000_000}
    app = create_app(repository, store, lambda _token, _audience: claims, audience="user-client")
    return TestClient(app, raise_server_exceptions=False), repository, store


def auth():
    return {"Authorization": "Bearer valid-user-token"}


def test_history_enriches_canonical_stock_name_server_side():
    api, _, _ = make_client()
    response = api.get("/api/v1/me/journal/history", headers=auth())
    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "2330"
    assert response.json()[0]["stock_name"] == "台積電"
    assert response.json()[0]["identity_status"] == "available"


def test_positions_are_joined_from_one_summary_anchored_snapshot():
    api, _, store = make_client()
    response = api.get("/api/v1/me/journal/positions", headers=auth())
    assert response.status_code == 200
    row = response.json()[0]
    assert row["valuation_date"] == "2026-09-05"
    assert row["ledger_version"] == 7
    assert row["stock_name"] == "台積電"
    assert row["unrealized_pnl"] == "20"
    assert row["unrealized_return"] == "0.2"
    assert store.calls[:3] == [
        ("mart_user_portfolio_summary", USER_ID, {}),
        ("mart_user_positions", USER_ID, {"valuation_date": "2026-09-05", "ledger_version": 7}),
        ("mart_user_unrealized_pnl", USER_ID, {"valuation_date": "2026-09-05", "ledger_version": 7}),
    ]


def test_positions_fill_missing_snapshot_identity_from_stock_master():
    api, _, store = make_client()
    mart = store.mart

    def missing_name(table, user_id, **filters):
        rows = mart(table, user_id, **filters)
        if table == "mart_user_positions":
            rows[0]["stock_name"] = None
            rows[0]["identity_status"] = "missing"
            rows[0]["identity_missing_reason"] = "stock_master_not_found"
        return rows

    store.mart = missing_name
    response = api.get("/api/v1/me/journal/positions", headers=auth())
    assert response.status_code == 200
    assert response.json()[0]["stock_name"] == "台積電"
    assert response.json()[0]["identity_status"] == "available"
    assert response.json()[0]["identity_missing_reason"] is None


def test_positions_prefer_operational_projection_and_do_not_mix_stale_private_mart_values():
    class OperationalRepository(Repository):
        def positions(self, user_id):
            return [{"user_id": user_id, "symbol": "2330", "currency": "TWD", "shares": "2",
                     "average_cost": "110", "cost_basis": "220", "ledger_version": 8}]

    repository = OperationalRepository()
    store = Store()
    claims = {"iss": "https://accounts.google.com", "aud": "user-client", "sub": "google-a",
              "email": "owner@example.com", "email_verified": True, "exp": 1_900_000_000}
    api = TestClient(create_app(repository, store, lambda _token, _audience: claims, audience="user-client"),
                     raise_server_exceptions=False)

    response = api.get("/api/v1/me/journal/positions", headers=auth())
    assert response.status_code == 200
    row = response.json()[0]
    assert row["ledger_version"] == 8
    assert row["shares"] == "2"
    assert row["average_cost"] == "110"
    assert row["market_price"] is None
    assert row["market_value"] is None
    assert row["unrealized_pnl"] is None
    assert row["price_status"] == "pending"
    assert row["missing_reason"] == "private_mart_pending"
    assert store.calls == [("mart_user_portfolio_summary", USER_ID, {})]


def test_operational_position_migration_is_bounded_rebuildable_and_api_synchronous():
    root = Path(__file__).parents[1]
    sql = (root / "infra" / "postgres" / "migrations" /
           "041_operational_position_projection.sql").read_text(encoding="utf-8")
    repository = (root / "services" / "api" / "repository.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS private.current_positions" in sql
    assert "CREATE OR REPLACE FUNCTION private.refresh_current_positions" in sql
    assert "SECURITY DEFINER" not in sql
    assert "GRANT REFERENCES ON private.users" not in sql
    assert "REFERENCES private.users" not in sql
    assert "FOR target_user IN SELECT user_id FROM private.users" in sql
    assert "GRANT CREATE ON SCHEMA private TO janus_private_api" in sql
    assert "REVOKE CREATE ON SCHEMA private FROM janus_private_api" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON private.current_positions TO janus_private_api" in sql
    assert repository.count("SELECT private.refresh_current_positions(%s)") == 2
    assert '"current_positions","ledger_events","users"' in repository


def test_summary_contract_allows_withheld_aggregate_and_decodes_affected_symbols():
    store = Store()

    def withheld(table, user_id, **filters):
        store.calls.append((table, user_id, filters))
        if table != "mart_user_portfolio_summary":
            return []
        return [{"user_id": str(user_id), "ledger_version": 7, "valuation_date": "2026-09-05",
                 "currency": "TWD", "market_value": None, "cost_basis": "100", "unrealized_pnl": None,
                 "unrealized_return": None, "aggregate_status": "withheld", "affected_symbol_count": 1,
                 "affected_symbols": '["2330"]', "missing_price_count": 1, "stale_price_count": 0,
                 "valuation_status": "partial", "cash_safety_status": "insufficient_data",
                 "cash_ratio": None, "minimum_cash_ratio": None}]

    store.mart = withheld
    api, _, _ = make_client(store)
    response = api.get("/api/v1/me/portfolio/summary", headers=auth())
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["aggregate_status"] == "withheld"
    assert item["market_value"] is None
    assert item["unrealized_pnl"] is None
    assert item["unrealized_return"] is None
    assert item["affected_symbols"] == ["2330"]