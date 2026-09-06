"""Owner-scoped, replay-safe persistence for private assistant records."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from .engine_security import AgentEvent, ApprovalDecision, ApprovalRequest, authorize_approval
from .models import SkillDefinition
from .repository import ConflictError


_FORBIDDEN_KEYS = frozenset({
    "api_key", "apikey", "auth_cache", "authcache", "authorization", "credential", "password",
    "raw_provider_error", "refresh_token", "refreshtoken", "secret", "token", "access_token",
    "accesstoken",
})
_FORBIDDEN_SUFFIXES = ("_api_key", "_credential", "_password", "_secret", "_access_token", "_refresh_token")


def safe_private_record(value: Any) -> Any:
    """Reject credential-shaped fields before they can reach durable storage."""
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN_KEYS or normalized.endswith(_FORBIDDEN_SUFFIXES):
                raise ValueError(f"credential field cannot be persisted: {key}")
            result[str(key)] = safe_private_record(item)
        return result
    if isinstance(value, (list, tuple)):
        return [safe_private_record(item) for item in value]
    return value


def _json(value: Any) -> str:
    return json.dumps(safe_private_record(value), default=str, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_json(value).encode()).hexdigest()


class AssistantStorage:
    def __init__(self, repository: Any, store: Any) -> None:
        self.repository, self.store = repository, store

    def append_event(self, owner_id: Any, event: AgentEvent, idempotency_key: str) -> dict[str, Any]:
        record = {
            "event_id": event.event_id, "seq": event.seq, "thread_id": event.thread_id,
            "turn_id": event.turn_id, "event_type": event.event_type.value, "payload": event.payload,
            "item_id": event.item_id, "provider_ids": event.provider_ids,
        }
        digest = _digest(record)
        index = self.repository.reserve_assistant_event(owner_id, event, idempotency_key, digest)
        if index["payload_digest"] != digest:
            raise ConflictError("idempotency key was already used for different event content")
        if index["status"] == "PERSISTED": return index
        ref = self.store.write_assistant_event(user_id=owner_id, record=record)
        self.repository.complete_assistant_event(owner_id, event.thread_id, event.event_id, ref)
        return {**index, "artifact_ref": ref, "status": "PERSISTED"}

    def write_skill_revision(self, owner_id: Any, skill_id: str, revision: int,
                             definition: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        validated = safe_private_record(SkillDefinition.model_validate(definition).model_dump(mode="json"))
        digest = _digest(validated)
        index = self.repository.reserve_skill_revision(
            owner_id, skill_id, revision, idempotency_key, digest,
        )
        if index["content_digest"] != digest:
            raise ConflictError("skill revision conflicts with an existing idempotency key")
        if index["status"] == "PERSISTED": return index
        ref = self.store.write_skill_revision(
            user_id=owner_id, skill_id=skill_id, revision=revision, definition=validated,
            content_digest=digest,
        )
        self.repository.complete_skill_revision(owner_id, skill_id, revision, ref)
        return {**index, "artifact_ref": ref, "status": "PERSISTED"}

    def read_skill_revision(self, owner_id: Any, skill_id: str, revision: int) -> dict[str, Any]:
        index = self.repository.skill_revision(owner_id, skill_id, revision)
        if index["status"] != "PERSISTED":
            raise ValueError("skill revision is not available")
        definition = self.store.read_skill_revision(owner_id, skill_id, revision)
        if definition is None:
            raise ValueError("skill revision artifact is missing")
        return {**index, "definition": definition}

    def request_approval(self, request: ApprovalRequest, artifact_ref: str) -> dict[str, Any]:
        if not artifact_ref.startswith("private.assistant_events/"):
            raise ValueError("approval artifact reference must be an opaque private event reference")
        authorize_approval(request, ApprovalDecision(
            request.owner_id, request.thread_id, request.turn_id, request.request_id,
            request.params_digest, True,
        ), now=datetime.now(timezone.utc))
        return self.repository.save_approval(request, artifact_ref)

    def resolve_approval(self, request: ApprovalRequest, decision: ApprovalDecision,
                         *, now: datetime | None = None) -> dict[str, Any]:
        resolved_at = now or datetime.now(timezone.utc)
        current = self.repository.approval(request.owner_id, request.thread_id, request.turn_id, request.request_id)
        if decision.approved:
            authorize_approval(request, decision, now=resolved_at, already_resolved=current["status"] != "PENDING")
        elif current["status"] != "PENDING" or (
            request.owner_id, request.thread_id, request.turn_id, request.request_id, request.params_digest
        ) != (
            decision.owner_id, decision.thread_id, decision.turn_id, decision.request_id, decision.params_digest
        ):
            raise PermissionError("approval decision binding mismatch or request already resolved")
        status = "APPROVED" if decision.approved else "DENIED"
        return self.repository.resolve_approval(decision, status, resolved_at)
