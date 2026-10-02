from __future__ import annotations

import json
from io import BytesIO

import pytest

from intelligence_mart.codex_worker import ProviderResult
from intelligence_mart.ai_contract import content_hash
from intelligence_mart.provider_routing import (
    DEFAULT_ROUTE,
    GeminiRoleProvider,
    OpenRouterProvider,
    ProviderRouter,
    load_remote_credentials_from_runtime_bundle,
    route_snapshot,
)


class _Provider:
    def __init__(self, name: str, *, result: ProviderResult, ready: bool = True) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.cli_version = "0.159.2" if name == "codex_cli" else "n/a"
        self.result = result
        self.ready = ready
        self.calls = 0

    def preflight(self):
        return {
            "status": "ready" if self.ready else "blocked",
            "reason": None if self.ready else "auth_required",
            "provider": "openai" if self.name == "codex_cli" else self.name,
            "transport": self.name,
            "model": self.model,
            "billing_mode": "test",
            "paid_api_enabled": False,
            "publication_authority": False,
        }

    def invoke(self, role, role_input):
        self.calls += 1
        return self.result


def _output(role: str = "fundamental") -> dict:
    evidence_id = "ev-0123456789abcdef01234567"
    claim = {"text": "supported", "evidence_ids": [evidence_id]}
    return {
        "schema_version": "1.0.0",
        "role": role,
        "stance": "neutral",
        "thesis": claim,
        "missing_information": [],
        "confidence": 0.5,
        "evidence_ids": [evidence_id],
        "key_findings": [claim],
        "positive_evidence": [],
        "negative_evidence": [],
        "contradictions": [],
        "change_drivers": [],
        "risks": [],
        "what_would_change_my_view": [],
    }


def _providers(codex_result: ProviderResult, openrouter_result: ProviderResult, gemini_result: ProviderResult):
    return {
        "codex_cli": _Provider("codex_cli", result=codex_result),
        "openrouter": _Provider("openrouter", result=openrouter_result),
        "gemini": _Provider("gemini", result=gemini_result),
    }


def test_repository_default_route_is_codex_openrouter_gemini():
    snapshot = route_snapshot({})
    assert snapshot["providers"] == list(DEFAULT_ROUTE)
    assert snapshot["version"] == 0
    assert snapshot["source"] == "repository_default"
    assert snapshot["routing_hash"].startswith("sha256:")


def test_execution_route_requires_all_three_providers_exactly_once():
    snapshot = route_snapshot({"ai_provider_routing": {"version": 7, "providers": ["openrouter", "codex_cli", "gemini"]}})
    assert snapshot["providers"] == ["openrouter", "codex_cli", "gemini"]
    assert snapshot["version"] == 7
    with pytest.raises(ValueError):
        route_snapshot({"ai_provider_routing": {"version": 8, "providers": ["codex_cli", "openrouter"]}})


def test_router_falls_back_on_transport_failure_only():
    providers = _providers(
        ProviderResult("failed", None, (), "provider_unavailable"),
        ProviderResult("succeeded", _output(), (), None),
        ProviderResult("succeeded", _output(), (), None),
    )
    router = ProviderRouter(providers, route_snapshot({}))
    result = router.invoke("fundamental", {"fact_pack": {}})
    assert result.status == "succeeded"
    assert result.provider == "openrouter"
    assert providers["codex_cli"].calls == 1
    assert providers["openrouter"].calls == 1
    assert providers["gemini"].calls == 0
    assert result.routing["providers"] == list(DEFAULT_ROUTE)


@pytest.mark.parametrize("reason", ["invalid_structured_output", "free_cost_unverified", "paid_cost_detected",
                                     "model_identity_unverified", "auth_persistence_failed"])
def test_router_does_not_bypass_invalid_structured_output(reason):
    providers = _providers(
        ProviderResult("failed", None, (), reason),
        ProviderResult("succeeded", _output(), (), None),
        ProviderResult("succeeded", _output(), (), None),
    )
    router = ProviderRouter(providers, route_snapshot({}))
    result = router.invoke("fundamental", {"fact_pack": {}})
    assert result.status == "failed"
    assert result.reason == reason
    assert providers["openrouter"].calls == 0
    assert providers["gemini"].calls == 0


def test_openrouter_is_hard_limited_to_free_routes(monkeypatch):
    with pytest.raises(ValueError):
        OpenRouterProvider(api_key="present", model="openai/gpt-paid")
    provider = OpenRouterProvider(api_key="present", model="openrouter/free")
    monkeypatch.setenv("MART_OPENROUTER_FREE_ONLY", "false")
    assert provider.preflight()["status"] == "blocked"
    assert provider.preflight()["reason"] == "paid_gate_not_authorized"


def test_gemini_generation_is_blocked_until_free_tier_confirmed(monkeypatch):
    monkeypatch.delenv("MART_GEMINI_FREE_TIER_CONFIRMED", raising=False)
    provider = GeminiRoleProvider(api_key="present")
    assert provider.preflight()["status"] == "blocked"
    assert provider.preflight()["reason"] == "free_tier_not_confirmed"
    result = provider.invoke("fundamental", {"fact_pack": {}})
    assert result.status == "failed"
    assert result.reason == "free_tier_not_confirmed"
    assert result.attempts == ()


@pytest.mark.parametrize("cost,reason", [(0, None), (None, "free_cost_unverified"),
                                        (0.01, "paid_cost_detected"), (True, "free_cost_unverified"),
                                        (float("nan"), "free_cost_unverified"), (-1, "free_cost_unverified")])
def test_openrouter_enforces_zero_price_and_requires_observed_zero_cost(cost, reason, monkeypatch):
    monkeypatch.setenv("MART_OPENROUTER_FREE_ROUTE_CONFIRMED", "true")
    requests = []

    def respond(request, **kwargs):
        requests.append(json.loads(request.data))
        return BytesIO(json.dumps({"model": "test/model:free", "usage": {"cost": cost},
                                  "choices": [{"message": {"content": json.dumps(_output())}}]}).encode())

    result = OpenRouterProvider(api_key="present", opener=respond, max_attempts=2).invoke("fundamental", {})
    assert requests[0]["provider"] == {"require_parameters": True, "max_price": {"prompt": 0, "completion": 0}}
    assert len(requests) == 1  # A billing gate failure cannot retry or fall back.
    assert result.reason == reason
    assert result.status == ("succeeded" if reason is None else "failed")
    assert result.attempts[0]["actual_cost_usd"] == (cost if reason != "free_cost_unverified" else None)
    assert result.attempts[0]["cost_observability"] == ("unknown" if reason == "free_cost_unverified" else "observed")


def test_router_freezes_profile_parameters_and_records_actual_model():
    providers = _providers(ProviderResult("failed", None, (), "provider_unavailable"),
                          ProviderResult("succeeded", _output(), ({"model": "test/model:free"},), None),
                          ProviderResult("failed", None, (), "auth_required"))
    providers["openrouter"].timeout_seconds = 60
    route = route_snapshot({})
    router = ProviderRouter(providers, route)
    route["providers"].reverse()
    result = router.invoke("fundamental", {})
    assert result.model == "test/model:free"
    assert result.parameters["timeout_seconds"] == 60
    assert result.routing["providers"] == list(DEFAULT_ROUTE)
    assert result.routing["routing_hash"] == content_hash(
        {k: v for k, v in result.routing.items() if k != "routing_hash"})


def test_openrouter_stays_out_of_effective_route_until_free_request_verified(monkeypatch):
    monkeypatch.delenv("MART_OPENROUTER_FREE_ROUTE_CONFIRMED", raising=False)
    providers = _providers(ProviderResult("succeeded", _output(), (), None),
                          ProviderResult("failed", None, (), "provider_unavailable"),
                          ProviderResult("failed", None, (), "auth_required"))
    providers["openrouter"] = OpenRouterProvider(api_key="present")
    router = ProviderRouter(providers, route_snapshot({}))
    assert "openrouter" not in router.routing["effective_providers"]
    assert router.routing["profiles"]["openrouter"]["reason"] == "free_route_not_confirmed"


def test_runtime_bundle_maps_only_remote_provider_keys(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("JANUS_MART_POSTGRES_BUNDLE", json.dumps({
        "openrouter_api_key": "or-secret",
        "gemini_api_key": "gm-secret",
        "control_password": "must-not-map",
    }))
    load_remote_credentials_from_runtime_bundle()
    assert monkeypatch.getenv("OPENROUTER_API_KEY") if hasattr(monkeypatch, "getenv") else True
    assert "CONTROL_DB_PASSWORD" not in __import__("os").environ
    assert __import__("os").environ["OPENROUTER_API_KEY"] == "or-secret"
    assert __import__("os").environ["GEMINI_API_KEY"] == "gm-secret"


@pytest.mark.parametrize("provider_class", [OpenRouterProvider, GeminiRoleProvider])
def test_missing_credentials_block_without_network_calls(provider_class):
    def no_network(*args, **kwargs):
        raise AssertionError("blocked provider must not make a request")
    provider = provider_class(api_key="", opener=no_network)
    assert provider.preflight()["reason"] == "auth_required"
    result = provider.invoke("fundamental", {})
    assert result.status == "failed" and result.reason == "auth_required" and result.attempts == ()
