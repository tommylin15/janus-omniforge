from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from services.api.app import create_app
from packages.web_api import PublicReportNotFound, QueryValidationError


REPORT = {
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


class Core:
    def page(self, dataset_id: str, symbol: str, *, limit: int, offset: int):
        return SimpleNamespace(dataset_id=dataset_id, symbol=symbol.upper(), rows=[], limit=limit, offset=offset)


class MissingDatasetCore(Core):
    def page(self, dataset_id: str, symbol: str, *, limit: int, offset: int):
        raise QueryValidationError("dataset is not available")


class Admin:
    def stocks(self, query, *, enabled, limit, cursor):
        return ({"symbol": "2330"},)

    def review_mart_report(self, execution_id, scope_type, scope_id, action, reason, actor):
        return {"execution_id": execution_id, "scope_type": scope_type, "scope_id": scope_id,
                "publication_status": "blocked", "reason": reason, "actor": actor}


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
    assert api.get("/admin").status_code == 200


def test_missing_public_dataset_is_waiting_not_a_fetch_or_server_error() -> None:
    api = TestClient(create_app(object(), object(), public=Public(), query_core=MissingDatasetCore()))
    response = api.get("/api/v1/public/events/2330")
    assert response.status_code == 200
    assert response.json()["data_status"] == "waiting"
