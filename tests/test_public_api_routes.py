from __future__ import annotations

from types import SimpleNamespace
import logging

from fastapi.testclient import TestClient

from services.api.app import create_app
from packages.web_api import PublicReportNotFound, PublicReportWaiting, QueryValidationError


REPORT = {
    "execution_id": "11111111-1111-1111-1111-111111111111",
    "analysis_as_of": "2026-09-12", "scope_type": "market", "scope_id": "market",
    "data_status": "published", "confidence": 0.8, "completeness": 0.9,
    "schema_version": "1", "model_version": "1", "governance_snapshot_version": "gov-1",
    "data": {"market_status": "open", "summary": "stable", "topics": ["rates"],
              "candidates": [{"symbol": "2330", "score": 80}]},
}


class Public:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def report(self, scope_type: str, scope_id: str, *, analysis_as_of: str = ""):
        self.calls.append((scope_type, scope_id))
        if scope_id == "missing":
            raise PublicReportNotFound
        return {**REPORT, "scope_type": scope_type, "scope_id": scope_id}

    def require_enabled_symbol(self, symbol: str) -> str:
        if symbol.upper() == "9999":
            from packages.web_api import PublicStockNotFound
            raise PublicStockNotFound("stock not found")
        return symbol.upper()


class Core:
    def __init__(self) -> None:
        self.calls = []

    def page(self, dataset_id: str, symbol: str, *, limit: int, offset: int):
        self.calls.append((dataset_id, symbol))
        return SimpleNamespace(dataset_id=dataset_id, symbol=symbol.upper(), rows=[], limit=limit, offset=offset)


class MissingDatasetCore(Core):
    def page(self, dataset_id: str, symbol: str, *, limit: int, offset: int):
        raise QueryValidationError("dataset is not available")


class WaitingPublic(Public):
    def report(self, scope_type: str, scope_id: str, *, analysis_as_of: str = ""):
        if scope_type == "symbol":
            raise PublicReportWaiting
        return super().report(scope_type, scope_id, analysis_as_of=analysis_as_of)


class Admin:
    def stocks(self, query, *, enabled, limit, cursor):
        return ({"symbol": "2330"},)

    def review_mart_report(self, execution_id, scope_type, scope_id, action, reason, actor):
        return {"execution_id": execution_id, "scope_type": scope_type, "scope_id": scope_id,
                "publication_status": "blocked", "reason": reason, "actor": actor}

    def governance(self, governance_key):
        return {"key": governance_key, "status": "development-default", "version": 0, "reason": "repository default", "value": {"version": "1.0.0"}}

    def governance_diff(self, governance_key, value):
        return {"key": governance_key, "base_version": 0, "valid": True, "changes": [{"path": "version", "before": "1.0.0", "after": value["version"]}]}

    def governance_history(self, governance_key, *, limit):
        return ()

    def save_governance(self, governance_key, value, *, actor, reason, status, expected_version):
        return {"key": governance_key, "status": status, "value": value, "version": expected_version + 1, "changes": [], "reason": reason}

    def membership_snapshot(self, coverage_tier):
        return {"items": [{"coverage_tier": coverage_tier, "symbol": "2330"}], "version": 1,
                "effective_from": "2026-09-03T00:00:00+00:00"}

    def set_membership(self, coverage_tier, symbols, *, effective_from, reason, owner, expected_version):
        return {"items": [{"coverage_tier": coverage_tier, "symbol": symbol} for symbol in symbols],
                "version": expected_version + 1, "effective_from": effective_from.isoformat(), "actor": owner}

    def retry_execution_item(self, execution_id, item_key):
        return {"execution": {"execution_id": "new-execution", "status": "queued"},
                "previous_execution_id": execution_id, "retried_item_key": item_key}


def client(public: Public) -> TestClient:
    return TestClient(create_app(object(), object(), public=public, query_core=Core()))


def test_public_endpoint_family_is_read_only_and_uses_public_service() -> None:
    public = Public()
    api = client(public)

    assert api.get("/api/v1/public/daily-brief").status_code == 200
    assert api.get("/api/v1/public/sector-rotation?scope_id=semis").status_code == 200
    assert api.get("/api/v1/public/topics").status_code == 200
    assert api.get("/api/v1/public/candidates").status_code == 200
    assert api.get("/api/v1/public/stock-health/2330").status_code == 200
    assert api.get("/api/v1/public/history/2330").json()["data_status"] == "waiting"
    assert api.get("/api/v1/public/kline/2330").json()["data_status"] == "waiting"
    assert api.get("/api/v1/public/events/2330").json()["data_status"] == "waiting"
    assert api.get("/api/v1/public/daily-brief?scope_id=missing").status_code == 404
    assert all(scope in {"market", "industry", "symbol"} for scope, _ in public.calls)


def test_fastapi_admin_routes_use_admin_auth_and_service_boundary() -> None:
    claims = {"iss": "https://accounts.google.com", "aud": "admin-client", "sub": "admin-sub",
              "email": "admin@example.com", "email_verified": True, "exp": 4_000_000_000}
    api = TestClient(create_app(object(), object(), public=Public(), query_core=Core(), admin_service=Admin(),
                                admin_audience="admin-client", admin_emails=frozenset({"admin@example.com"}),
                                admin_verifier=lambda _token, _audience: claims))
    headers = {"Authorization": "Bearer admin-token"}
    assert api.get("/api/v1/admin/stocks", headers=headers).json()["items"][0]["symbol"] == "2330"
    result = api.patch(
        "/api/v1/admin/mart-reports/11111111-1111-1111-1111-111111111111/symbol/2330/publication",
        headers=headers, json={"action": "block", "reason": "manual review"},
    )
    assert result.status_code == 200
    assert result.json()["actor"] == "admin@example.com"
    assert api.get("/api/v1/admin/memberships/core_focus", headers=headers).json()["version"] == 1
    saved = api.put("/api/v1/admin/memberships/core_focus", headers=headers, json={
        "symbols": ["2330"], "effective_from": "2026-09-04T00:00:00Z",
        "reason": "rebalance", "expected_version": 1,
    })
    assert saved.status_code == 200
    assert saved.json()["actor"] == "admin@example.com"
    retried = api.post("/api/v1/admin/executions/old/items/ohlcv%3ATWSE%3A2330/retry", headers=headers)
    assert retried.status_code == 202
    assert retried.json()["execution"]["status"] == "queued"
    assert api.post("/api/v1/admin/executions/old/items/ohlcv%3ATWSE%3A2330/retry").status_code == 401
    assert api.get("/api/v1/admin/memberships/core_focus").status_code == 401
    assert api.get("/admin").status_code == 200


def test_fastapi_governance_routes_are_typed_and_versioned() -> None:
    claims = {"iss": "https://accounts.google.com", "aud": "admin-client", "sub": "admin-sub",
              "email": "admin@example.com", "email_verified": True, "exp": 4_000_000_000}
    api = TestClient(create_app(object(), object(), public=Public(), query_core=Core(), admin_service=Admin(),
                                admin_audience="admin-client", admin_emails=frozenset({"admin@example.com"}),
                                admin_verifier=lambda _token, _audience: claims))
    headers = {"Authorization": "Bearer admin-token"}
    value = {"version": "1.0.0"}
    assert api.get("/api/v1/admin/governance/policy", headers=headers).json()["version"] == 0
    assert api.post("/api/v1/admin/governance/policy/diff", headers=headers, json={"value": value}).json()["valid"]
    saved = api.put("/api/v1/admin/governance/policy", headers=headers, json={"value": value, "reason": "test", "expected_version": 0})
    assert saved.status_code == 200
    assert api.get("/api/v1/admin/governance/policy/history", headers=headers).json()["items"] == []


def test_missing_public_dataset_is_waiting_not_a_fetch_or_server_error() -> None:
    api = TestClient(create_app(object(), object(), public=Public(), query_core=MissingDatasetCore()))
    response = api.get("/api/v1/public/events/2330")
    assert response.status_code == 200
    assert response.json()["data_status"] == "waiting"


def test_missing_or_disabled_stock_is_404_before_any_core_query() -> None:
    public, core = Public(), Core()
    api = TestClient(create_app(object(), object(), public=public, query_core=core))
    response = api.get("/api/v1/public/history/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "stock not found"}
    assert core.calls == []


def test_enabled_stock_without_report_returns_waiting() -> None:
    api = TestClient(create_app(object(), object(), public=WaitingPublic(), query_core=Core()))
    for path in ("/api/v1/public/reports/symbol/2330", "/api/v1/public/stock-health/2330"):
        response = api.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "analysis_as_of": "", "scope_type": "symbol", "scope_id": "2330",
            "data_status": "waiting", "data": {},
        }


def test_cors_is_scoped_to_public_and_user_routers(monkeypatch) -> None:
    monkeypatch.setenv("USER_CORS_ORIGINS", "https://user.example")
    api = TestClient(create_app(object(), object(), public=Public(), query_core=Core()))
    headers = {"Origin": "https://user.example", "Access-Control-Request-Method": "GET"}
    assert api.options("/api/v1/public/health", headers=headers).headers["access-control-allow-origin"] == "https://user.example"
    assert "access-control-allow-origin" not in api.options("/api/v1/admin/stocks", headers=headers).headers


def test_router_rate_limits_are_separate_and_health_is_exempt(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("PRIVATE_RATE_LIMIT_PER_MINUTE", "1")
    api = TestClient(create_app(object(), object(), public=Public(), query_core=Core()))

    assert api.get("/api/v1/public/daily-brief").status_code == 200
    limited = api.get("/api/v1/public/topics")
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert api.get("/api/v1/me/profile").status_code in {401, 503}
    assert api.get("/api/v1/me/profile").status_code == 429
    assert api.get("/api/v1/public/health").status_code == 200


def test_admin_audit_policy_never_logs_token_query_or_body(caplog) -> None:
    claims = {"iss": "https://accounts.google.com", "aud": "admin-client", "sub": "admin-sub",
              "email": "admin@example.com", "email_verified": True, "exp": 4_000_000_000}
    api = TestClient(create_app(object(), object(), public=Public(), query_core=Core(), admin_service=Admin(),
                                admin_audience="admin-client", admin_emails=frozenset({"admin@example.com"}),
                                admin_verifier=lambda _token, _audience: claims))
    caplog.set_level(logging.INFO, logger="services.api.app")
    response = api.get("/api/v1/admin/stocks?q=query-secret",
                       headers={"Authorization": "Bearer bearer-secret"})

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert "api_audit family=admin method=GET status=200" in caplog.text
    assert "api_request family=admin method=GET status=200 duration_ms=" in caplog.text
    assert "query-secret" not in caplog.text
    assert "bearer-secret" not in caplog.text


def test_openapi_keeps_public_private_and_admin_response_boundaries_distinct() -> None:
    schema = create_app(object(), object(), public=Public(), query_core=Core()).openapi()
    components = schema["components"]["schemas"]
    assert {"PublicReportListOut", "PublicDatasetOut", "PrivateResponseOut", "AdminResponseOut"} <= set(components)
    assert schema["paths"]["/api/v1/public/daily-brief"]["get"]["tags"] == ["public"]
    assert schema["paths"]["/api/v1/me/profile"]["get"]["tags"] == ["private"]
    assert schema["paths"]["/api/v1/admin/stocks"]["get"]["tags"] == ["admin"]
