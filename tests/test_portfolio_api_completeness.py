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
