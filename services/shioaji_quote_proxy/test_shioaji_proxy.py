"""Unit tests for Shioaji Quote Proxy."""

import json
import os
import pytest
from fastapi.testclient import TestClient

from services.shioaji_quote_proxy.main import app, resolve_credentials, ShioajiManager


def test_resolve_credentials_from_bundle(monkeypatch):
    test_bundle = {
        "shioaji_api_key": "test_key_123",
        "shioaji_secret_key": "test_secret_456",
        "shioaji_person_id": "A123456789",
        "shioaji_password": "test_password",
    }
    monkeypatch.setenv("JANUS_RUNTIME_BUNDLE", json.dumps(test_bundle))
    monkeypatch.delenv("SHIOAJI_API_KEY", raising=False)
    monkeypatch.delenv("SHIOAJI_SECRET_KEY", raising=False)

    api_key, secret_key, person_id, password = resolve_credentials()
    assert api_key == "test_key_123"
    assert secret_key == "test_secret_456"
    assert person_id == "A123456789"
    assert password == "test_password"


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "janus-shioaji-quote-proxy"
        assert data["region"] == "asia-east1"
        assert "shioaji" in data


def test_quotes_endpoint_validation():
    with TestClient(app) as client:
        # Empty symbols
        resp = client.get("/quotes?symbols=")
        assert resp.status_code == 400

        # Valid symbols structure
        resp = client.get("/quotes?symbols=2382,2327")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "quotes" in data
