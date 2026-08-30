import json
import sys
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from apps.web.server import WebApplication


class _Core:
    def summary(self, symbol): return {"symbol": symbol}

    def page(self, dataset, symbol, *, limit, offset):
        return type("Page", (), {"dataset_id": dataset, "symbol": symbol, "rows": (), "limit": limit, "offset": offset})()


class _Admin:
    def __init__(self):
        self.enabled = None
        self.actor = None

    def stocks(self, query="", *, enabled=None, limit=50, offset=0):
        return tuple({"symbol": str(index), "name": "Stock", "market": "TWSE", "enabled": True} for index in range(limit))

    def set_stock_enabled(self, symbol, enabled):
        self.enabled = (symbol, enabled)

    def upsert_stock(self, payload):
        return {"symbol": payload["symbol"], "name": payload["name"], "market": payload.get("market", "TWSE"), "enabled": payload.get("enabled", True)}

    def delete_stock(self, symbol):
        return None

    def executions(self, *, limit=50):
        return ({"execution_id": "exec-1", "status": "queued"},)

    def execution_details(self, execution_id):
        return {"execution_id": execution_id, "status": "queued", "items": ()}

    def enqueue_collection(self, config_id, symbols=None, *, trace_id=None):
        return {"execution_id": "collection-1", "config_id": config_id, "requested_symbols": symbols, "status": "queued"}

    def enqueue_analysis(self, config_id, symbols=None, *, trace_id=None):
        return {"execution_id": "analysis-1", "config_id": config_id, "requested_symbols": symbols, "status": "queued"}

    def source_health(self):
        return ({"source_id": "twse", "dataset_id": "ohlcv", "success_rate": 1.0, "last_state": "success"},)

    def membership(self, tier):
        return ({"coverage_tier": tier, "symbol": "2330"},)

    @staticmethod
    def parse_datetime(value):
        return value

    def set_membership(self, tier, symbols, *, effective_from, reason, owner):
        return tuple({"coverage_tier": tier, "symbol": symbol} for symbol in symbols)

    def save_setting(self, key, value, *, actor, expected_version=None):
        self.actor = actor
        return {"key": key, "value": value, "version": 1}


class WebServerTests(unittest.TestCase):
    def request(self, path, *, method="GET", body=None, admin=None, authenticated_actor=None):
        app = WebApplication(core=_Core(), admin=admin)
        encoded = json.dumps(body).encode() if body is not None else b""
        environ = {"PATH_INFO": path, "QUERY_STRING": "", "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(encoded)), "wsgi.input": BytesIO(encoded)}
        if authenticated_actor:
            environ["JANUS_AUTH_EMAIL"] = authenticated_actor
        response = {}
        result = app(environ, lambda status, headers: response.update(status=status, headers=headers))
        content_type = dict(response["headers"])["Content-Type"]
        payload = result[0].decode()
        return response["status"], json.loads(payload) if content_type.startswith("application/json") else payload

    def test_health_and_core_route(self):
        self.assertEqual(self.request("/health")[0], "200 OK")
        status, body = self.request("/api/v1/core/2330/summary")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["symbol"], "2330")

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
        self.assertTrue(body["has_next"])
        status, body = self.request("/api/v1/admin/stocks/2330/enabled", method="PATCH", body={"enabled": False}, admin=admin)
        self.assertEqual(status, "200 OK")
        self.assertEqual(admin.enabled, ("2330", False))

    def test_admin_stock_upsert_is_a_bounded_write_route(self):
        status, body = self.request("/api/v1/admin/stocks", method="POST", body={"symbol": "2330", "name": "台積電"}, admin=_Admin())
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["symbol"], "2330")

    def test_collection_and_analysis_are_separate_queue_routes(self):
        admin = _Admin()
        for kind in ("collection", "analysis"):
            status, body = self.request(f"/api/v1/admin/executions/{kind}", method="POST", body={"config_id": "ohlcv", "symbols": ["2330"]}, admin=admin)
            self.assertEqual(status, "202 Accepted")
            self.assertEqual(body["status"], "queued")
            self.assertTrue(body["execution_id"].startswith(kind))

    def test_execution_health_and_membership_reads_are_bounded_surfaces(self):
        admin = _Admin()
        self.assertEqual(self.request("/api/v1/admin/executions/exec-1", admin=admin)[1]["execution_id"], "exec-1")
        self.assertEqual(self.request("/api/v1/admin/source-health", admin=admin)[1]["items"][0]["source_id"], "twse")
        self.assertEqual(self.request("/api/v1/admin/memberships/core_focus", admin=admin)[1]["items"][0]["symbol"], "2330")

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


if __name__ == "__main__":
    unittest.main()
