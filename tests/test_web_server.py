import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from apps.web.server import WebApplication


class _Core:
    def summary(self, symbol): return {"symbol": symbol}

    def page(self, dataset, symbol, *, limit, offset):
        return type("Page", (), {"dataset_id": dataset, "symbol": symbol, "rows": (), "limit": limit, "offset": offset})()


class _Public:
    def report(self, scope_type, scope_id, *, analysis_as_of=""):
        return {"scope_type": scope_type, "scope_id": scope_id, "analysis_as_of": analysis_as_of or "2026-09-12", "data": {"score": 80}}


class _Admin:
    def __init__(self):
        self.enabled = None
        self.actor = None
        self.cursor = None

    def stocks(self, query="", *, enabled=None, limit=50, cursor=None):
        self.cursor = cursor
        return tuple({"symbol": str(index), "name": "Stock", "market": "TWSE", "enabled": True} for index in range(limit))

    def set_stock_enabled(self, symbol, enabled):
        self.enabled = (symbol, enabled)

    def upsert_stock(self, payload):
        return {"symbol": payload["symbol"], "name": payload["name"], "market": payload.get("market", "TWSE"), "enabled": payload.get("enabled", True)}

    def delete_stock(self, symbol):
        return None

    def stock_references(self, symbol):
        return {"symbol": symbol, "can_delete": False, "references": {"collection_config": 1, "execution": 2, "market": 3, "report": 4, "fundamental": 5}}

    def executions(self, *, limit=50, cursor=None):
        return ({"execution_id": "00000000-0000-0000-0000-000000000001", "status": "queued", "requested_at": "2026-08-31T00:00:00+00:00"},)

    def execution_details(self, execution_id):
        return {"execution_id": execution_id, "status": "queued", "items": ()}

    def enqueue_collection(self, config_id, symbols=None, *, trace_id=None, request_options=None):
        return {"execution_id": "collection-1", "config_id": config_id, "requested_symbols": symbols, "request_options": request_options or {}, "status": "queued"}

    def enqueue_analysis(self, config_id, symbols=None, *, trace_id=None):
        return {"execution_id": "analysis-1", "config_id": config_id, "requested_symbols": symbols, "status": "queued"}

    def mart_reports(self, **_filters):
        return ({"execution_id":"analysis-1","analysis_as_of":"2026-09-12","scope_type":"symbol",
                 "scope_id":"2330","artifact_uri":"gs://mart/metadata.json"},)

    def source_health(self, *, limit=200, cursor=None):
        self.cursor = cursor
        return ({"source_id": "twse", "dataset_id": "ohlcv", "success_rate": 1.0, "last_state": "success"},)

    def collection_configs(self, *, limit=200, cursor=None):
        self.cursor = cursor
        return ({"config_id": "ohlcv", "dataset_id": "ohlcv", "source_ids": ("twse",)},)

    def save_collection_config(self, payload, *, actor):
        self.actor = actor
        return {**payload, "actor": actor}

    def source_review(self, adapter_id):
        return {"adapter_id": adapter_id, "value": None, "version": 0}

    def save_source_review(self, adapter_id, value, *, actor, expected_version=None):
        self.actor = actor
        return {"adapter_id": adapter_id, "value": value, "version": 1}

    def membership_snapshot(self, tier):
        return {"items": ({"coverage_tier": tier, "symbol": "2330"},), "version": 2, "effective_from": "2026-09-03T08:40:00+00:00"}

    @staticmethod
    def parse_datetime(value):
        return value

    def set_membership(self, tier, symbols, *, effective_from, reason, owner, expected_version=None):
        self.actor = owner
        return {"items": tuple({"coverage_tier": tier, "symbol": symbol} for symbol in symbols), "version": expected_version + 1, "effective_from": effective_from}

    def save_setting(self, key, value, *, actor, expected_version=None):
        self.actor = actor
        return {"key": key, "value": value, "version": 1}


class WebServerTests(unittest.TestCase):
    def request(self, path, *, method="GET", body=None, admin=None, public=None, authenticated_actor=None):
        app = WebApplication(core=_Core(), admin=admin, public=public)
        target = urlsplit(path)
        encoded = json.dumps(body).encode() if body is not None else b""
        environ = {"PATH_INFO": target.path, "QUERY_STRING": target.query, "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(encoded)), "wsgi.input": BytesIO(encoded)}
        if authenticated_actor:
            environ["JANUS_AUTH_EMAIL"] = authenticated_actor
        response = {}
        result = app(environ, lambda status, headers: response.update(status=status, headers=headers))
        content_type = dict(response["headers"])["Content-Type"]
        payload = result[0].decode()
        return response["status"], json.loads(payload) if content_type.startswith("application/json") else payload

    def test_health_and_core_route(self):
        status, health = self.request("/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(health["revision"], "local")
        status, body = self.request("/api/v1/core/2330/summary")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["symbol"], "2330")

    def test_public_report_route_reads_persisted_service(self):
        status, body = self.request("/api/v1/public/reports/symbol/2330?analysis_as_of=2026-09-12", public=_Public())
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["data"]["score"], 80)

    def test_core_dataset_route_passes_dataset_before_symbol(self):
        status, body = self.request("/api/v1/core/2330/datasets/ohlcv")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["dataset_id"], "ohlcv")
        self.assertEqual(body["symbol"], "2330")

    def test_missing_runtime_dependency_is_safe(self):
        status, body = self.request("/api/v1/admin/stocks")
        self.assertEqual(status, "503 Service Unavailable")
        self.assertEqual(body["error"], "admin unavailable")

    def test_admin_page_and_assets_are_served(self):
        status, body = self.request("/admin/stocks")
        self.assertEqual(status, "200 OK")
        self.assertIn("資料營運中心", body)
        self.assertNotIn("raw payload", body.lower())
        self.assertEqual(self.request("/assets/admin.css")[0], "200 OK")
        self.assertEqual(self.request("/assets/admin.js")[0], "200 OK")

    def test_admin_stocks_are_paginated_and_can_be_toggled(self):
        admin = _Admin()
        status, body = self.request("/api/v1/admin/stocks", admin=admin)
        self.assertEqual(status, "200 OK")
        self.assertEqual(len(body["items"]), 10)
        self.assertEqual(body["next_cursor"], "9")
        self.request("/api/v1/admin/stocks?cursor=2330", admin=admin)
        self.assertEqual(admin.cursor, "2330")
        self.assertEqual(self.request("/api/v1/admin/stocks?offset=10", admin=admin)[0], "400 Bad Request")
        status, body = self.request("/api/v1/admin/stocks/2330/enabled", method="PATCH", body={"enabled": False}, admin=admin)
        self.assertEqual(status, "200 OK")
        self.assertEqual(admin.enabled, ("2330", False))

    def test_admin_stock_upsert_is_a_bounded_write_route(self):
        status, body = self.request("/api/v1/admin/stocks", method="POST", body={"symbol": "2330", "name": "台積電"}, admin=_Admin())
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["symbol"], "2330")

    def test_admin_stock_reference_summary_is_structured(self):
        status, body = self.request("/api/v1/admin/stocks/2330/references", admin=_Admin())
        self.assertEqual(status, "200 OK")
        self.assertFalse(body["can_delete"])
        self.assertEqual(body["references"]["fundamental"], 5)

    def test_collection_and_analysis_use_persisted_queues(self):
        admin = _Admin()
        status, body = self.request("/api/v1/admin/executions/collection", method="POST", body={"config_id": "ohlcv", "symbols": ["2330"]}, admin=admin)
        self.assertEqual(status, "202 Accepted")
        self.assertEqual(body["status"], "queued")

        status, body = self.request("/api/v1/admin/executions/analysis", method="POST", body={"config_id": "ohlcv", "symbols": ["2330"]}, admin=admin)
        self.assertEqual(status, "202 Accepted")
        self.assertEqual(body["status"], "queued")

        status, body = self.request("/api/v1/admin/executions/collection", method="POST", body={"config_id": "ohlcv", "symbols": ["2330"], "options": {"start_date": "2026-08-24", "end_date": "2026-08-28", "source_ids": ["twse"]}}, admin=admin)
        self.assertEqual(status, "202 Accepted")
        self.assertEqual(body["request_options"]["source_ids"], ["twse"])

    def test_mart_report_query_is_a_persisted_metadata_surface(self):
        status, body = self.request("/api/v1/admin/mart-reports?scope_type=symbol&scope_id=2330", admin=_Admin())
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["items"][0]["artifact_uri"], "gs://mart/metadata.json")

    def test_execution_health_and_membership_reads_are_bounded_surfaces(self):
        admin = _Admin()
        self.assertEqual(self.request("/api/v1/admin/executions/exec-1", admin=admin)[1]["execution_id"], "exec-1")
        self.assertEqual(self.request("/api/v1/admin/source-health", admin=admin)[1]["items"][0]["source_id"], "twse")
        self.assertEqual(self.request("/api/v1/admin/memberships/core_focus", admin=admin)[1]["items"][0]["symbol"], "2330")
        self.assertEqual(self.request("/api/v1/admin/source-catalog", admin=admin)[1]["items"][0]["config_id"], "ohlcv")
        self.request("/api/v1/admin/source-health?cursor=twse,ohlcv", admin=admin)
        self.assertEqual(admin.cursor, "twse,ohlcv")
        self.request("/api/v1/admin/source-catalog?cursor=ohlcv", admin=admin)
        self.assertEqual(admin.cursor, "ohlcv")

    def test_invalid_json_shape_is_a_safe_client_error(self):
        status, body = self.request("/api/v1/admin/stocks/2330/enabled", method="PATCH", body={"enabled": "false"}, admin=_Admin())
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(body["error"], "enabled must be a boolean")

    def test_authenticated_email_cannot_be_spoofed_as_audit_actor(self):
        admin = _Admin()
        status, _ = self.request(
            "/api/v1/admin/settings/schedule", method="PUT",
            body={"value": {"time": "08:00"}, "actor": "spoofed@example.com"},
            admin=admin, authenticated_actor="owner@example.com",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(admin.actor, "owner@example.com")

        status, body = self.request(
            "/api/v1/admin/memberships/core_focus", method="PUT",
            body={"symbols": ["2330"], "effective_from": "2026-09-04T00:00:00Z", "reason": "rebalance", "owner": "spoofed@example.com", "expected_version": 2},
            admin=admin, authenticated_actor="owner@example.com",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["version"], 3)
        self.assertEqual(admin.actor, "owner@example.com")

    def test_source_review_uses_authenticated_actor(self):
        admin = _Admin()
        status, body = self.request("/api/v1/admin/source-reviews/anue", method="PUT", body={"value": {"status": "candidate"}, "expected_version": 0, "actor": "spoofed@example.com"}, admin=admin, authenticated_actor="reviewer@example.com")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["adapter_id"], "anue")
        self.assertEqual(admin.actor, "reviewer@example.com")

    def test_source_config_uses_authenticated_actor(self):
        admin = _Admin()
        status, body = self.request("/api/v1/admin/source-catalog", method="PUT", body={"config_id": "ohlcv", "dataset_id": "ohlcv", "source_ids": ["twse"], "actor": "spoofed@example.com"}, admin=admin, authenticated_actor="operator@example.com")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["actor"], "operator@example.com")


if __name__ == "__main__":
    unittest.main()
