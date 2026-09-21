from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from services.api.engine_security import (
    AgentEvent,
    AgentEventType,
    AgentRuntime,
    ApprovalDecision,
    ApprovalRequest,
    Capability,
    ContextEgress,
    CredentialMode,
    RuntimeBinding,
    authorize_approval,
    authorize_context_egress,
    enforce_thread_binding,
    policy_for,
    require_capabilities,
    validate_provider_environment,
)
from services.api.janus_approval_policy import FORBIDDEN_APPROVAL_OPERATIONS


def test_runtime_capability_and_credential_contract():
    assert {runtime.value for runtime in AgentRuntime} == {"openrouter", "gemini", "codex"}
    assert policy_for("openrouter").credential_name == "OPENROUTER_API_KEY"
    assert policy_for("gemini").credential_name == "GEMINI_API_KEY"
    assert policy_for("codex").credential_mode is CredentialMode.MANAGED_AUTH_STORE
    assert all(policy.fallback_runtime is None and not policy.paid_enabled for policy in map(policy_for, AgentRuntime))
    gemini = RuntimeBinding(
        AgentRuntime.GEMINI,
        "gemini-flash",
        "research",
        model_capabilities=frozenset({Capability.STREAMING, Capability.GROUNDING, Capability.CITATIONS}),
    )
    require_capabilities(gemini, {Capability.GROUNDING, Capability.CITATIONS})
    with pytest.raises(PermissionError):
        require_capabilities(gemini, {Capability.TOOLS})
    with pytest.raises(ValueError):
        RuntimeBinding(
            AgentRuntime.OPENROUTER,
            "model-with-invalid-claim",
            "research",
            model_capabilities=frozenset({Capability.GROUNDING}),
        )
    with pytest.raises(ValueError):
        validate_provider_environment({"OPENAI_API_KEY": "forbidden"})


def test_thread_binding_separates_profiles_and_requires_fork_for_runtime_or_model_change():
    capabilities = frozenset({Capability.STREAMING})
    current = RuntimeBinding(AgentRuntime.GEMINI, "gemini-flash", "research", "market-v1", capabilities)
    enforce_thread_binding(current, RuntimeBinding(AgentRuntime.GEMINI, "gemini-flash", "concise", "market-v2", capabilities))
    for changed in (
        RuntimeBinding(AgentRuntime.OPENROUTER, "gemini-flash", "research"),
        RuntimeBinding(AgentRuntime.GEMINI, "gemini-pro", "research"),
    ):
        with pytest.raises(ValueError):
            enforce_thread_binding(current, changed)


def test_agent_event_envelope_is_shared_and_schema_stays_in_sync():
    event = AgentEvent("event-1", 0, "thread-1", "turn-1", AgentEventType.TEXT_DELTA, {"text": "hi"})
    assert event.payload == {"text": "hi"}
    schema = json.loads((Path(__file__).parents[1] / "packages/contracts/assistant.v1.json").read_text())
    assert set(schema["definitions"]["RuntimeBindingV1"]["properties"]["runtime"]["enum"]) == {
        runtime.value for runtime in AgentRuntime
    }
    assert set(schema["definitions"]["AgentEventV1"]["properties"]["type"]["enum"]) == {
        event_type.value for event_type in AgentEventType
    }
    assert {"ContextSourceV1","ContextSelectorV1","ContextPreviewV1","ContextResolveV1"} <= set(schema["definitions"])
    with pytest.raises(ValueError):
        AgentEvent("event-2", -1, "thread-1", "turn-1", AgentEventType.USAGE, {})


def test_private_context_requires_explicit_selection_disclosure_and_consent():
    allowed = ContextEgress("owner-1", "thread-1", AgentRuntime.CODEX, ("private-notes",), True, True, True)
    authorize_context_egress(allowed)
    for denied in (
        ContextEgress("owner-1", "thread-1", AgentRuntime.CODEX, (), True, True, True),
        ContextEgress("owner-1", "thread-1", AgentRuntime.CODEX, ("private-notes",), True, False, True),
        ContextEgress("owner-1", "thread-1", AgentRuntime.CODEX, ("private-notes",), True, True, False),
    ):
        with pytest.raises((ValueError, PermissionError)):
            authorize_context_egress(denied)


def test_approval_is_request_bound_expiring_and_cannot_expand_product_permissions():
    now = datetime.now(timezone.utc)
    digest = "sha256:" + "a" * 64
    request = ApprovalRequest("owner-1", "thread-1", "turn-1", "request-1", "shell", "turn_sandbox", digest, now + timedelta(minutes=5))
    decision = ApprovalDecision("owner-1", "thread-1", "turn-1", "request-1", digest, True)
    authorize_approval(request, decision, now=now)

    with pytest.raises(PermissionError):
        authorize_approval(request, ApprovalDecision("owner-2", "thread-1", "turn-1", "request-1", digest, True), now=now)
    with pytest.raises(PermissionError):
        authorize_approval(request, decision, now=request.expires_at)
    with pytest.raises(PermissionError):
        authorize_approval(request, decision, now=now, already_resolved=True)
    forbidden = ApprovalRequest("owner-1", "thread-1", "turn-1", "request-2", "place_order", "account", digest, now + timedelta(minutes=5))
    with pytest.raises(PermissionError):
        authorize_approval(forbidden, ApprovalDecision("owner-1", "thread-1", "turn-1", "request-2", digest, True), now=now)


def test_janus_domain_denials_remain_in_compatibility_contract():
    schema = json.loads((Path(__file__).parents[1] / "packages/contracts/assistant.v1.json").read_text())
    assert set(schema["definitions"]["ApprovalRequestV1"]["properties"]["operation"]["not"]["enum"]) == FORBIDDEN_APPROVAL_OPERATIONS
