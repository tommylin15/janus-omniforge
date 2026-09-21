"""Executable security contract for every private-assistant runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping
import os
import re

from .janus_approval_policy import FORBIDDEN_APPROVAL_OPERATIONS


class AgentRuntime(str, Enum):
    OPENROUTER = "openrouter"
    GEMINI = "gemini"
    CODEX = "codex"


class AgentEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    ITEM_UPSERT = "item_upsert"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESOLVED = "approval_resolved"
    CITATION = "citation"
    USAGE = "usage"
    TURN_COMPLETED = "turn_completed"
    TURN_CANCELLED = "turn_cancelled"
    TURN_ERROR = "turn_error"


class Capability(str, Enum):
    STREAMING = "streaming"
    TOOLS = "tools"
    GROUNDING = "grounding"
    CITATIONS = "citations"
    ITEMS = "items"
    APPROVALS = "approvals"
    MANAGED_AUTH = "managed_auth"


class CredentialMode(str, Enum):
    SECRET_MANAGER = "secret_manager"
    MANAGED_AUTH_STORE = "managed_auth_store"


@dataclass(frozen=True)
class ProviderPolicy:
    credential_mode: CredentialMode
    credential_name: str
    capabilities: frozenset[Capability]
    paid_enabled: bool = False
    fallback_runtime: AgentRuntime | None = None


PROVIDER_POLICIES = {
    AgentRuntime.OPENROUTER: ProviderPolicy(
        CredentialMode.SECRET_MANAGER,
        "OPENROUTER_API_KEY",
        frozenset({Capability.STREAMING, Capability.TOOLS}),
    ),
    AgentRuntime.GEMINI: ProviderPolicy(
        CredentialMode.SECRET_MANAGER,
        "GEMINI_API_KEY",
        frozenset({Capability.STREAMING, Capability.TOOLS, Capability.GROUNDING, Capability.CITATIONS}),
    ),
    AgentRuntime.CODEX: ProviderPolicy(
        CredentialMode.MANAGED_AUTH_STORE,
        "codex_managed_auth",
        frozenset({
            Capability.STREAMING,
            Capability.TOOLS,
            Capability.ITEMS,
            Capability.APPROVALS,
            Capability.MANAGED_AUTH,
        }),
    ),
}


@dataclass(frozen=True)
class RuntimeBinding:
    runtime: AgentRuntime
    model: str
    assistant_profile: str
    skill_profile: str | None = None
    model_capabilities: frozenset[Capability] = frozenset()

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.assistant_profile.strip():
            raise ValueError("model and assistant_profile are required")
        if self.skill_profile is not None and not self.skill_profile.strip():
            raise ValueError("skill_profile cannot be blank")
        if not self.model_capabilities <= policy_for(self.runtime).capabilities:
            raise ValueError("model capabilities exceed provider capabilities")


@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    seq: int
    thread_id: str
    turn_id: str
    event_type: AgentEventType
    payload: Mapping[str, object]
    item_id: str | None = None
    provider_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.event_id, self.thread_id, self.turn_id)):
            raise ValueError("event, thread, and turn IDs are required")
        if self.seq < 0:
            raise ValueError("event seq must be non-negative")
        if any(not key.strip() or not value.strip() for key, value in self.provider_ids.items()):
            raise ValueError("provider ID mappings cannot be blank")


@dataclass(frozen=True)
class ContextEgress:
    owner_id: str
    thread_id: str
    runtime: AgentRuntime
    source_ids: tuple[str, ...]
    contains_private_data: bool
    provider_disclosed: bool
    private_data_consent: bool


@dataclass(frozen=True)
class ApprovalRequest:
    owner_id: str
    thread_id: str
    turn_id: str
    request_id: str
    operation: str
    scope: str
    params_digest: str
    expires_at: datetime


@dataclass(frozen=True)
class ApprovalDecision:
    owner_id: str
    thread_id: str
    turn_id: str
    request_id: str
    params_digest: str
    approved: bool


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_PROVIDER_KEYS = frozenset({
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "OPENAI_ENDPOINT",
    "CODEX_API_KEY",
})


def policy_for(runtime: str | AgentRuntime) -> ProviderPolicy:
    try:
        return PROVIDER_POLICIES[AgentRuntime(runtime)]
    except (ValueError, KeyError) as error:
        raise ValueError("unsupported agent runtime") from error


def require_capabilities(binding: RuntimeBinding, required: set[Capability]) -> None:
    if not required <= binding.model_capabilities:
        raise PermissionError("selected model lacks required capabilities")


def enforce_thread_binding(current: RuntimeBinding, requested: RuntimeBinding) -> None:
    if current.runtime != requested.runtime or current.model != requested.model:
        raise ValueError("runtime or model changes require a new or forked thread")


def validate_provider_environment(env: Mapping[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    if any(key.upper() in _FORBIDDEN_PROVIDER_KEYS for key in values):
        raise ValueError("direct OpenAI API configuration is forbidden")


def authorize_context_egress(request: ContextEgress) -> None:
    if not request.owner_id.strip() or not request.thread_id.strip() or not request.source_ids:
        raise ValueError("owner, thread, and explicitly selected sources are required")
    if any(not source.strip() for source in request.source_ids):
        raise ValueError("source IDs cannot be blank")
    if len(request.source_ids) != len(set(request.source_ids)):
        raise ValueError("source IDs must be unique")
    if not request.provider_disclosed:
        raise PermissionError("provider disclosure is required before context egress")
    if request.contains_private_data and not request.private_data_consent:
        raise PermissionError("private data egress requires explicit consent")


def authorize_approval(
    request: ApprovalRequest,
    decision: ApprovalDecision,
    *,
    now: datetime,
    already_resolved: bool = False,
) -> None:
    if request.operation in FORBIDDEN_APPROVAL_OPERATIONS:
        raise PermissionError("approval cannot grant product mutation or admin access")
    if request.operation in {"shell", "write_file"} and request.scope != "turn_sandbox":
        raise PermissionError("shell and file writes are limited to the turn sandbox")
    if not _DIGEST.fullmatch(request.params_digest):
        raise ValueError("approval params_digest must be a sha256 digest")
    if request.expires_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("approval timestamps must be timezone-aware")
    expected = (
        request.owner_id,
        request.thread_id,
        request.turn_id,
        request.request_id,
        request.params_digest,
    )
    actual = (
        decision.owner_id,
        decision.thread_id,
        decision.turn_id,
        decision.request_id,
        decision.params_digest,
    )
    if actual != expected:
        raise PermissionError("approval decision binding mismatch")
    if already_resolved:
        raise PermissionError("approval request was already resolved")
    if not decision.approved:
        raise PermissionError("approval was denied")
    if now >= request.expires_at:
        raise PermissionError("approval expired")
