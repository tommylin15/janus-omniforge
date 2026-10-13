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


def _output(role: str = "ceo") -> dict:
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
        "supporting_roles": [], "opposing_roles": [], "contradictions": [],
        "bull_case": [], "bear_case": [], "principal_risks": [], "watch_items": [],
        "change_since_previous_analysis": [],
        "validated_role_artifact_hashes": ["sha256:" + str(i)*64 for i in range(5)],
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


def test_manual_cancellation_stops_before_any_provider_call():
    failed = ProviderResult('blocked', None, (), 'timeout')
    providers = _providers(failed, failed, failed)
    router = ProviderRouter(providers, route_snapshot())
    result = router.invoke('ceo', {}, should_stop=lambda: True)
    assert result.status == 'failed' and result.reason == 'cancelled'
    assert all(p.calls == 0 for p in providers.values())


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
    result = router.invoke("ceo", {"fact_pack": {}})
    assert result.status == "succeeded"
    assert result.provider == "openrouter"
    assert providers["codex_cli"].calls == 1
    assert providers["openrouter"].calls == 1
    assert providers["gemini"].calls == 0
    assert result.routing["providers"] == list(DEFAULT_ROUTE)


@pytest.mark.parametrize("reason", ["invalid_structured_output", "free_cost_unverified", "paid_cost_detected",
                                     "model_identity_unverified", "auth_persistence_failed", "unsupported_model",
                                     "unsupported_parameter", "unsupported_cli_version", "unsupported_cli_capability",
                                     "grounding_failed", "pit_failed", "missing_data"])
def test_router_does_not_bypass_invalid_structured_output(reason):
    providers = _providers(
        ProviderResult("failed", None, (), reason),
        ProviderResult("succeeded", _output(), (), None),
        ProviderResult("succeeded", _output(), (), None),
    )
    router = ProviderRouter(providers, route_snapshot({}))
    result = router.invoke("ceo", {"fact_pack": {}})
    assert result.status == "failed"
    assert result.reason == reason
    assert providers["openrouter"].calls == 0
    assert providers["gemini"].calls == 0


@pytest.mark.parametrize("before_snapshot", [False, True])
def test_router_stops_on_nonfallback_preflight_failure(before_snapshot):
    providers = _providers(ProviderResult("succeeded", _output(), (), None),
                          ProviderResult("succeeded", _output(), (), None),
                          ProviderResult("succeeded", _output(), (), None))
    if before_snapshot:
        providers["codex_cli"].preflight = lambda: {"status": "blocked", "reason": "unsupported_cli_version"}
    router = ProviderRouter(providers, route_snapshot({}))
    providers["codex_cli"].preflight = lambda: {"status": "blocked", "reason": "unsupported_cli_version"}
    result = router.invoke("ceo", {})
    assert result.reason == "unsupported_cli_version"
    assert all(provider.calls == 0 for provider in providers.values())


def test_ceo_prompt_has_explicit_schema_and_real_execution_hashes():
    from intelligence_mart.provider_routing import _prompt
    hashes = ['sha256:' + str(i) * 64 for i in range(5)]
    prompt = _prompt('ceo', {'validated_role_artifact_hashes': hashes, 'fact_pack': {}})
    assert 'REQUIRED_JSON_SCHEMA' in prompt and 'JSON_EXAMPLE' in prompt
    assert all(h in prompt for h in hashes)
    assert '"change_since_previous_analysis":[]' in prompt
    assert '"thesis":null' in prompt


def test_gemini_invalid_json_audit_contains_only_safe_field_names(monkeypatch):
    monkeypatch.setenv('MART_GEMINI_FREE_TIER_CONFIRMED', 'true')
    result_json = {**_output(), 'confidence': 'never-echo-private-content',
                   'supporting_roles': 'bad-type'}
    response = {'candidates': [{'content': {'parts': [{'text': json.dumps(result_json)}]}}]}
    provider = GeminiRoleProvider(api_key='present', opener=lambda *a, **kw: BytesIO(json.dumps(response).encode()))
    result = provider.invoke('ceo', {})
    assert result.status == 'failed' and result.reason == 'invalid_structured_output'
    assert 'confidence' in result.attempts[0]['invalid_fields']
    assert 'supporting_roles' in result.attempts[0]['invalid_fields']
    assert 'never-echo-private-content' not in json.dumps(result.attempts)



def test_gemini_free_entitlement_does_not_fabricate_observed_cost(monkeypatch):
    monkeypatch.setenv("MART_GEMINI_FREE_TIER_CONFIRMED", "true")
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps(_output())}]}}]}
    provider = GeminiRoleProvider(api_key="present", opener=lambda *a, **kw: BytesIO(json.dumps(response).encode()))
    result = provider.invoke("ceo", {})
    assert result.status == "succeeded"
    assert result.attempts[0]["actual_cost_usd"] is None
    assert result.attempts[0]["cost_observability"] == "unknown"


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
    result = provider.invoke("ceo", {"fact_pack": {}})
    assert result.status == "failed"
    assert result.reason == "free_tier_not_confirmed"
    assert result.attempts == ()


def test_bounded_ceo_uses_only_latest_lite_even_when_saved_profile_has_old_model(monkeypatch):
    monkeypatch.setenv('MART_CEO_GEMINI_ONLY', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'present')
    monkeypatch.setenv('MART_GEMINI_FREE_TIER_CONFIRMED', 'true')
    from packages.analysis_models import DEFAULT_MODELS
    models = {**DEFAULT_MODELS, 'gemini': 'gemini-2.5-flash'}
    options = {'ai_provider_routing': {'version': 1, 'providers': ['codex_cli', 'openrouter', 'gemini'], 'models': models}}
    router = ProviderRouter.from_environment(options, bounded_manual=True)
    assert router.routing['execution_providers'] == ['gemini']
    assert router.routing['effective_providers'] == ['gemini']
    assert router.providers['gemini'].model == 'gemini-3.5-flash-lite'
    calls = []
    def unavailable(request, **kwargs):
        calls.append(request.full_url)
        raise TimeoutError()
    router.providers['gemini'].opener = unavailable
    for name in ('codex_cli', 'openrouter'):
        router.providers[name].invoke = lambda *a: pytest.fail('non-Gemini provider called')
    result = router.invoke('ceo', {})
    assert result.status == 'failed' and len(result.attempts) == len(calls) == 1
    assert calls[0].endswith('/gemini-3.5-flash-lite:generateContent')
    normal = ProviderRouter.from_environment(options)
    assert 'execution_providers' not in normal.routing
    assert normal.providers['gemini'].model == 'gemini-2.5-flash'


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

    result = OpenRouterProvider(api_key="present", opener=respond, max_attempts=2).invoke("ceo", {})
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
    result = router.invoke("ceo", {})
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
    result = provider.invoke("ceo", {})
    assert result.status == "failed" and result.reason == "auth_required" and result.attempts == ()


def test_omni_gateway_is_opt_in_and_does_not_load_local_gemini_key(monkeypatch):
    from intelligence_mart.provider_routing import OmniGatewayGeminiProvider
    monkeypatch.setenv("MART_CEO_GEMINI_ONLY", "true")
    monkeypatch.setenv("MART_CEO_GEMINI_VIA_OMNIAGENT", "true")
    monkeypatch.setenv("MART_OMNI_GATEWAY_URL",
        "https://ghcr-965b05542a35---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app")
    monkeypatch.setenv("JANUS_MART_POSTGRES_BUNDLE", '{"gemini_api_key":"must-not-be-loaded"}')
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    router = ProviderRouter.from_environment({}, bounded_manual=True)
    assert isinstance(router.providers["gemini"], OmniGatewayGeminiProvider)
    assert router.routing["execution_policy"] == "omniagent_gateway_gemini_lite_only"
    assert router.routing["effective_providers"] == ["gemini"]
    assert "GEMINI_API_KEY" not in __import__("os").environ
    assert router.providers["gemini"].preflight()["status"] == "ready"


def test_omni_gateway_rejects_unapproved_endpoint_and_disabled_route(monkeypatch):
    from intelligence_mart.provider_routing import OmniGatewayGeminiProvider
    monkeypatch.setenv("MART_CEO_GEMINI_ONLY", "true")
    monkeypatch.delenv("MART_CEO_GEMINI_VIA_OMNIAGENT", raising=False)
    provider = OmniGatewayGeminiProvider(gateway_url="https://untrusted.example.net")
    assert provider.preflight()["reason"] == "gateway_route_disabled"
    monkeypatch.setenv("MART_CEO_GEMINI_VIA_OMNIAGENT", "true")
    assert provider.preflight()["reason"] == "gateway_endpoint_unapproved"


def _omni_test_provider(monkeypatch, opener, token_provider=lambda: "test-id-token"):
    from intelligence_mart.provider_routing import OmniGatewayGeminiProvider
    monkeypatch.setenv("MART_CEO_GEMINI_ONLY", "true")
    monkeypatch.setenv("MART_CEO_GEMINI_VIA_OMNIAGENT", "true")
    provider = OmniGatewayGeminiProvider(
        gateway_url="https://ghcr-965b05542a35---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app",
        opener=opener, token_provider=token_provider,
    )
    provider.bind_context(owner_id="00000000-0000-4000-8000-000000000001",
                          request_id="00000000-0000-4000-8000-000000000002")
    return provider


def test_omni_gateway_validates_identity_and_ceo_json_before_success(monkeypatch):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "safe bounded evidence")
    calls = []
    def fake_call(request, timeout):
        calls.append((request, timeout))
        body = json.loads(request.data)
        assert body["project"] == "market-mart"
        assert body["ownerId"] == "00000000-0000-4000-8000-000000000001"
        assert body["requestId"] == "00000000-0000-4000-8000-000000000002"
        assert body["prompt"] == "safe bounded evidence"
        return BytesIO(json.dumps({
            "status": "completed", "project": body["project"],
            "ownerId": body["ownerId"], "requestId": body["requestId"],
            "model": body["model"], "result": {"text": json.dumps(_output())},
            "usage": {"input_tokens": 5, "output_tokens": 6, "arbitrary": "private"},
        }).encode())
    provider = _omni_test_provider(monkeypatch, fake_call)
    result = provider.invoke("ceo", {"fact_pack": {}})
    assert result.status == "succeeded" and result.output == _output()
    assert result.attempts[0]["transport"] == "omniagent_gateway"
    assert result.attempts[0]["actual_cost_usd"] is None
    assert result.attempts[0]["usage"] == {"input_tokens": 5, "output_tokens": 6}
    assert len(calls) == 1 and calls[0][1] == 65
    assert calls[0][0].get_header("Authorization") == "Bearer test-id-token"
    assert "test-id-token" not in json.dumps(result.attempts)
    assert calls[0][0].full_url.endswith("/v1/gemini/execute")


@pytest.mark.parametrize("field,value", [
    ("project", "omniagent"), ("ownerId", "00000000-0000-4000-8000-000000000003"),
    ("requestId", "00000000-0000-4000-8000-000000000004"),
    ("model", "gemini-3.5-flash"),
    ("status", "failed"), ("result", {"text": ""}),
])
def test_omni_gateway_forged_or_empty_response_is_never_published(monkeypatch, field, value):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "bounded")
    reply = {"status": "completed", "project": "market-mart",
             "ownerId": "00000000-0000-4000-8000-000000000001",
             "requestId": "00000000-0000-4000-8000-000000000002",
             "model": "gemini-3.5-flash-lite", "result": {"text": json.dumps(_output())}}
    reply[field] = value
    provider = _omni_test_provider(monkeypatch,
        lambda *a, **k: BytesIO(json.dumps(reply).encode()))
    result = provider.invoke("ceo", {})
    assert result.status == "failed" and result.output is None
    assert result.reason == "gateway_contract_mismatch"


def test_omni_gateway_schema_failure_stays_blocked_and_redacted(monkeypatch):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "bounded")
    reply = {"status": "completed", "project": "market-mart",
             "ownerId": "00000000-0000-4000-8000-000000000001",
             "requestId": "00000000-0000-4000-8000-000000000002",
             "model": "gemini-3.5-flash-lite",
             "result": {"text": json.dumps({**_output(), "confidence": "private-content"})}}
    provider = _omni_test_provider(monkeypatch,
        lambda *a, **k: BytesIO(json.dumps(reply).encode()))
    result = provider.invoke("ceo", {})
    assert result.reason == "invalid_structured_output"
    assert result.output is None
    assert "confidence" in result.attempts[0]["invalid_fields"]
    assert "private-content" not in json.dumps(result.attempts)


def test_omni_gateway_oversized_prompt_never_sends_or_mints_token(monkeypatch):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "x" * 32769)
    provider = _omni_test_provider(monkeypatch,
        lambda *a, **kw: pytest.fail("no HTTP"), token_provider=lambda: pytest.fail("no token"))
    result = provider.invoke("ceo", {"fact_pack": {}})
    assert result.reason == "gateway_prompt_too_large"
    assert len(result.attempts) == 1


def test_omni_gateway_full_32k_multibyte_prompt_passes_without_truncation(monkeypatch):
    import intelligence_mart.provider_routing as routing
    prompt = "台" * 10000
    assert len(prompt.encode("utf-8")) == 30000
    monkeypatch.setattr(routing, "_prompt", lambda *args: prompt)
    called = []
    def response(request, timeout):
        body = json.loads(request.data)
        called.append(request.data)
        assert body["project"] == "market-mart" and body["prompt"] == prompt
        assert len(body["prompt"].encode("utf-8")) == 30000
        assert len(request.data) < 131072
        return BytesIO(json.dumps({
            "status": "completed", "project": body["project"],
            "ownerId": body["ownerId"], "requestId": body["requestId"],
            "model": body["model"], "result": {"text": json.dumps(_output())},
        }).encode())
    provider = _omni_test_provider(monkeypatch, response)
    result = provider.invoke("ceo", {"validated_role_artifact_hashes": _output()["validated_role_artifact_hashes"]})
    assert result.status == "succeeded" and len(called) == 1


@pytest.mark.parametrize("oversize", ["a" * 32769, "台" * 10923])
def test_omni_gateway_above_32k_rejects_before_identity(monkeypatch, oversize):
    import intelligence_mart.provider_routing as routing
    assert len(oversize.encode("utf-8")) > 32768
    monkeypatch.setattr(routing, "_prompt", lambda *args: oversize)
    provider = _omni_test_provider(monkeypatch, lambda *a, **k: pytest.fail("network forbidden"),
                                   token_provider=lambda: pytest.fail("identity forbidden"))
    result = provider.invoke("ceo", {})
    assert result.reason == "gateway_prompt_too_large" and result.status == "failed"
    assert len(result.attempts) == 1


def test_omni_gateway_missing_context_and_identity_failure_do_not_send(monkeypatch):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "bounded")
    provider = _omni_test_provider(monkeypatch,
        lambda *a, **kw: pytest.fail("no HTTP"), token_provider=lambda: (_ for _ in ()).throw(ValueError("secret")))
    assert provider.invoke("ceo", {}).reason == "gateway_identity_unavailable"
    provider._owner_id = None
    assert provider.invoke("ceo", {}).reason == "gateway_context_missing"


def test_omni_gateway_ambiguous_transport_failure_is_single_attempt(monkeypatch):
    import intelligence_mart.provider_routing as routing
    monkeypatch.setattr(routing, "_prompt", lambda *args: "bounded")
    called = []
    def failed(*args, **kwargs):
        called.append(True)
        raise TimeoutError("unknown terminal")
    provider = _omni_test_provider(monkeypatch, failed)
    result = provider.invoke("ceo", {})
    assert result.status == "failed" and result.reason == "provider_unavailable"
    assert len(called) == 1 and len(result.attempts) == 1
    assert "unknown terminal" not in json.dumps(result.attempts)
