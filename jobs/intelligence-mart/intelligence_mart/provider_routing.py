"""Versioned Mart AI provider routing with free-only remote fallbacks.

This module is deliberately provider-neutral at the orchestration boundary.  It
never grants publication authority and it never turns a paid provider on merely
because a credential exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .ai_contract import OUTPUT_MODELS, ROLE_WEIGHTS, SYSTEM_GUARDRAIL, content_hash, contract_bundle
from .codex_worker import CodexCLIProvider, ProviderResult, PROVIDER_STAGE_VERSION

DEFAULT_ROUTE = ("codex_cli", "openrouter", "gemini")
_ALLOWED_ROUTE = frozenset(DEFAULT_ROUTE)
_FALLBACK_REASONS = frozenset({
    "auth_required",
    "quota",
    "provider_unavailable",
    "timeout",
    "transport_error",
    "codex_cli_unavailable",
    "free_route_unavailable",
    "free_tier_not_confirmed",
})


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _prompt(role: str, role_input: dict[str, Any]) -> str:
    methodology = contract_bundle()["prompts"][role]["methodology"]
    return (
        f"{SYSTEM_GUARDRAIL}\n\nROLE METHODOLOGY:\n{methodology}\n\n"
        "Analyze only PUBLIC_INPUT. Do not invoke tools or external search. "
        "Copy numeric facts exactly as fact_key=value. Return only the requested structured output.\n"
        "PUBLIC_INPUT:\n"
        + json.dumps(role_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _safe_reason(code: int) -> str:
    if code in {401, 403}:
        return "auth_required"
    if code == 429:
        return "quota"
    if code == 402:
        return "free_route_unavailable"
    if code >= 500:
        return "provider_unavailable"
    if code in {400, 404, 422}:
        return "unsupported_parameter"
    return "transport_error"


def _attempt(*, role: str, provider: str, transport: str, model: str, attempt: int,
             duration_ms: int, status: str, reason: str | None, usage: dict[str, int] | None,
             actual_cost_usd: float | None, billing_mode: str) -> dict[str, Any]:
    value = {
        "artifact_kind": "mart_ai_provider_attempt_v1",
        "schema_version": PROVIDER_STAGE_VERSION,
        "role": role,
        "attempt": attempt,
        "provider": provider,
        "transport": transport,
        "model": model,
        "duration_ms": duration_ms,
        "status": status,
        "reason": reason,
        "usage": usage,
        "actual_cost_usd": actual_cost_usd,
        "cost_observability": "observed" if actual_cost_usd is not None else "unknown",
        "billing_mode": billing_mode,
        "paid_api_enabled": False,
        "publication_authority": False,
    }
    value["artifact_hash"] = content_hash(value)
    return value


def load_remote_credentials_from_runtime_bundle() -> None:
    """Map only the two approved provider keys; never log or return their values."""
    raw = os.environ.get("JANUS_MART_POSTGRES_BUNDLE", "").strip()
    if not raw:
        return
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(bundle, dict):
        return
    mappings = {
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "GEMINI_API_KEY": "gemini_api_key",
    }
    for target, source in mappings.items():
        value = bundle.get(source)
        if not os.environ.get(target) and isinstance(value, str) and value.strip():
            os.environ[target] = value.strip()


def route_snapshot(request_options: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = (request_options or {}).get("ai_provider_routing")
    if raw is None:
        route = list(DEFAULT_ROUTE)
        version = 0
        source = "repository_default"
    else:
        if not isinstance(raw, dict):
            raise ValueError("ai_provider_routing must be an object")
        route = raw.get("providers")
        version = raw.get("version")
        if (not isinstance(route, list) or not route or any(not isinstance(item, str) for item in route)
                or len(route) != len(set(route)) or set(route) != _ALLOWED_ROUTE):
            raise ValueError("ai provider route must contain codex_cli, openrouter, gemini exactly once")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("ai provider routing version must be a positive integer")
        source = "execution_snapshot"
    value = {
        "version": version,
        "source": source,
        "providers": route,
        "policies": {
            "codex_cli": "approved_chatgpt_account",
            "openrouter": "free_only",
            "gemini": "free_tier_only",
        },
    }
    value["routing_hash"] = content_hash(value)
    return value


@dataclass(frozen=True)
class RoutedProviderResult:
    status: str
    output: dict[str, Any] | None
    attempts: tuple[dict[str, Any], ...]
    reason: str | None
    provider: str
    transport: str
    model: str
    parameters: dict[str, Any]
    routing: dict[str, Any]


class OpenRouterProvider:
    provider_id = "openrouter"
    transport = "openrouter_api"

    def __init__(self, *, api_key: str, model: str = "openrouter/free", timeout_seconds: int = 60,
                 max_attempts: int = 1, opener: Callable[..., Any] = urlopen,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        if model != "openrouter/free" and not model.endswith(":free"):
            raise ValueError("OpenRouter Mart fallback must use a free route")
        if not 5 <= timeout_seconds <= 180 or not 1 <= max_attempts <= 2:
            raise ValueError("invalid OpenRouter bounds")
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.opener = opener
        self.sleeper = sleeper

    @classmethod
    def from_environment(cls) -> "OpenRouterProvider":
        return cls(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            model=os.environ.get("MART_OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free",
            timeout_seconds=_bounded_int("MART_OPENROUTER_TIMEOUT_SECONDS", 60, 5, 180),
            max_attempts=_bounded_int("MART_OPENROUTER_MAX_ATTEMPTS", 1, 1, 2),
        )

    def preflight(self) -> dict[str, Any]:
        if not self.api_key:
            return {"status": "blocked", "reason": "auth_required", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_only",
                    "paid_api_enabled": False, "publication_authority": False}
        free_only = _bool_env("MART_OPENROUTER_FREE_ONLY", True)
        if not free_only:
            return {"status": "blocked", "reason": "paid_gate_not_authorized", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_only",
                    "paid_api_enabled": False, "publication_authority": False}
        if self.model != "openrouter/free" and not self.model.endswith(":free"):
            return {"status": "blocked", "reason": "paid_model_not_allowed", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_only",
                    "paid_api_enabled": False, "publication_authority": False}
        if not _bool_env("MART_OPENROUTER_FREE_ROUTE_CONFIRMED", False):
            return {"status": "blocked", "reason": "free_route_not_confirmed", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_only",
                    "paid_api_enabled": False, "publication_authority": False}
        return {"status": "ready", "reason": None, "provider": self.provider_id,
                "transport": self.transport, "model": self.model, "billing_mode": "free_only",
                "paid_api_enabled": False, "publication_authority": False}

    def invoke(self, role: str, role_input: dict[str, Any]) -> ProviderResult:
        if role not in ROLE_WEIGHTS:
            raise ValueError("invalid AI analyst role")
        preflight = self.preflight()
        if preflight["status"] != "ready":
            return ProviderResult("failed", None, (), preflight["reason"])
        schema = OUTPUT_MODELS[role].model_json_schema()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_GUARDRAIL},
                {"role": "user", "content": _prompt(role, role_input)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": f"janus_{role}_v1", "strict": True, "schema": schema},
            },
            "provider": {"require_parameters": True, "max_price": {"prompt": 0, "completion": 0}},
            "temperature": 0,
        }
        attempts: list[dict[str, Any]] = []
        for number in range(1, self.max_attempts + 1):
            started = time.monotonic()
            parsed = None
            reason = None
            usage = None
            cost = None
            actual_model = None
            request = Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(),
                method="POST",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                         "X-OpenRouter-Title": "Janus OmniForge"},
            )
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    document = json.load(response)
                actual_model = document.get("model") if isinstance(document, dict) else None
                raw_usage = document.get("usage") if isinstance(document, dict) else None
                if isinstance(raw_usage, dict):
                    usage = {key: int(value) for key, value in raw_usage.items()
                             if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                             and type(value) is int and value >= 0} or None
                    raw_cost = raw_usage.get("cost")
                    if type(raw_cost) in {int, float} and math.isfinite(raw_cost) and raw_cost >= 0:
                        cost = float(raw_cost)
                if cost is None:
                    reason = "free_cost_unverified"
                elif cost > 0:
                    reason = "paid_cost_detected"
                elif not isinstance(actual_model, str) or not actual_model:
                    reason = "model_identity_unverified"
                else:
                    content = document["choices"][0]["message"]["content"]
                    parsed = OUTPUT_MODELS[role].model_validate_json(content).model_dump()
            except HTTPError as error:
                reason = _safe_reason(error.code)
            except (URLError, TimeoutError):
                reason = "provider_unavailable"
            except Exception:
                reason = "invalid_structured_output"
            attempts.append(_attempt(
                role=role, provider=self.provider_id, transport=self.transport,
                model=actual_model if isinstance(actual_model, str) and actual_model else self.model, attempt=number,
                duration_ms=round((time.monotonic() - started) * 1000),
                status="succeeded" if parsed is not None else "failed", reason=reason, usage=usage,
                actual_cost_usd=cost, billing_mode="free_only",
            ))
            if parsed is not None:
                return ProviderResult("succeeded", parsed, tuple(attempts), None)
            if reason not in _FALLBACK_REASONS or number >= self.max_attempts:
                return ProviderResult("failed", None, tuple(attempts), reason or "transport_error")
            self.sleeper(min(2 ** (number - 1), 2))
        return ProviderResult("failed", None, tuple(attempts), attempts[-1]["reason"] if attempts else "transport_error")


class GeminiRoleProvider:
    provider_id = "gemini"
    transport = "gemini_api"

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash", timeout_seconds: int = 60,
                 max_attempts: int = 1, opener: Callable[..., Any] = urlopen,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        if not model or len(model) > 128 or "/" in model:
            raise ValueError("invalid Gemini model")
        if not 5 <= timeout_seconds <= 180 or not 1 <= max_attempts <= 2:
            raise ValueError("invalid Gemini bounds")
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.opener = opener
        self.sleeper = sleeper

    @classmethod
    def from_environment(cls) -> "GeminiRoleProvider":
        return cls(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            model=os.environ.get("MART_GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
            timeout_seconds=_bounded_int("MART_GEMINI_TIMEOUT_SECONDS", 60, 5, 180),
            max_attempts=_bounded_int("MART_GEMINI_MAX_ATTEMPTS", 1, 1, 2),
        )

    def preflight(self) -> dict[str, Any]:
        if not self.api_key:
            return {"status": "blocked", "reason": "auth_required", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_tier_only",
                    "paid_api_enabled": False, "publication_authority": False}
        if not _bool_env("MART_GEMINI_FREE_TIER_CONFIRMED", False):
            return {"status": "blocked", "reason": "free_tier_not_confirmed", "provider": self.provider_id,
                    "transport": self.transport, "model": self.model, "billing_mode": "free_tier_only",
                    "paid_api_enabled": False, "publication_authority": False}
        return {"status": "ready", "reason": None, "provider": self.provider_id,
                "transport": self.transport, "model": self.model, "billing_mode": "free_tier_only",
                "paid_api_enabled": False, "publication_authority": False}

    def invoke(self, role: str, role_input: dict[str, Any]) -> ProviderResult:
        if role not in ROLE_WEIGHTS:
            raise ValueError("invalid AI analyst role")
        preflight = self.preflight()
        if preflight["status"] != "ready":
            return ProviderResult("failed", None, (), preflight["reason"])
        schema = OUTPUT_MODELS[role].model_json_schema()
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_GUARDRAIL}]},
            "contents": [{"role": "user", "parts": [{"text": _prompt(role, role_input)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0,
            },
        }
        attempts: list[dict[str, Any]] = []
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        for number in range(1, self.max_attempts + 1):
            started = time.monotonic()
            parsed = None
            reason = None
            usage = None
            request = Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(),
                method="POST",
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            )
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    document = json.load(response)
                metadata = document.get("usageMetadata") if isinstance(document, dict) else None
                if isinstance(metadata, dict):
                    key_map = {"promptTokenCount": "input_tokens", "candidatesTokenCount": "output_tokens",
                               "totalTokenCount": "total_tokens"}
                    usage = {target: int(metadata[source]) for source, target in key_map.items()
                             if type(metadata.get(source)) is int and metadata[source] >= 0} or None
                parts = document["candidates"][0]["content"]["parts"]
                text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
                parsed = OUTPUT_MODELS[role].model_validate_json(text).model_dump()
            except HTTPError as error:
                reason = _safe_reason(error.code)
            except (URLError, TimeoutError):
                reason = "provider_unavailable"
            except Exception:
                reason = "invalid_structured_output"
            attempts.append(_attempt(
                role=role, provider=self.provider_id, transport=self.transport, model=self.model, attempt=number,
                duration_ms=round((time.monotonic() - started) * 1000),
                status="succeeded" if parsed is not None else "failed", reason=reason, usage=usage,
                actual_cost_usd=None, billing_mode="free_tier_only",
            ))
            if parsed is not None:
                return ProviderResult("succeeded", parsed, tuple(attempts), None)
            if reason not in _FALLBACK_REASONS or number >= self.max_attempts:
                return ProviderResult("failed", None, tuple(attempts), reason or "transport_error")
            self.sleeper(min(2 ** (number - 1), 2))
        return ProviderResult("failed", None, tuple(attempts), attempts[-1]["reason"] if attempts else "transport_error")


class ProviderRouter:
    """Freeze one ordered provider route for an execution and audit every fallback."""

    def __init__(self, providers: dict[str, Any], routing: dict[str, Any]) -> None:
        route = routing.get("providers")
        if not isinstance(route, list) or set(route) != _ALLOWED_ROUTE or len(route) != len(_ALLOWED_ROUTE):
            raise ValueError("invalid provider routing snapshot")
        if set(providers) != _ALLOWED_ROUTE:
            raise ValueError("provider map must contain the complete governed route")
        self.providers = providers
        self.routing = json.loads(json.dumps(routing))
        self.routing["profiles"] = {
            name: {**provider.preflight(), "parameters": {
                key: getattr(provider, key) for key in
                ("cli_version", "reasoning_effort", "timeout_seconds", "max_attempts", "kill_grace_seconds")
                if hasattr(provider, key)}}
            for name, provider in providers.items()
        }
        self.routing["effective_providers"] = [name for name in self.routing["providers"]
                                               if self.routing["profiles"][name]["status"] == "ready"]
        self.routing["routing_hash"] = content_hash({k: v for k, v in self.routing.items() if k != "routing_hash"})
        self.model = "routed"
        self.cli_version = getattr(providers["codex_cli"], "cli_version", "unknown")

    @classmethod
    def from_environment(cls, request_options: dict[str, Any] | None = None,
                         *, codex_provider: CodexCLIProvider | None = None) -> "ProviderRouter":
        load_remote_credentials_from_runtime_bundle()
        codex = codex_provider or CodexCLIProvider.from_environment()
        return cls({
            "codex_cli": codex,
            "openrouter": OpenRouterProvider.from_environment(),
            "gemini": GeminiRoleProvider.from_environment(),
        }, route_snapshot(request_options))

    def preflight(self) -> dict[str, Any]:
        entries = []
        any_ready = False
        for name in self.routing["providers"]:
            value = dict(self.providers[name].preflight())
            value["route_name"] = name
            entries.append(value)
            any_ready = any_ready or value.get("status") == "ready"
        return {
            "status": "ready" if any_ready else "blocked",
            "reason": None if any_ready else "no_executable_provider",
            "provider": "janus",
            "transport": "provider_router",
            "model": "routed",
            "route": self.routing,
            "providers": entries,
            "paid_api_enabled": False,
            "publication_authority": False,
        }

    def invoke(self, role: str, role_input: dict[str, Any]) -> RoutedProviderResult:
        attempts: list[dict[str, Any]] = []
        last_reason = "no_executable_provider"
        last_meta = {"provider": "janus", "transport": "provider_router", "model": "routed"}
        for name in self.routing["providers"]:
            provider = self.providers[name]
            preflight = provider.preflight() if name in self.routing["effective_providers"] else self.routing["profiles"][name]
            last_meta = {
                "provider": str(preflight.get("provider", name)),
                "transport": str(preflight.get("transport", name)),
                "model": str(preflight.get("model", getattr(provider, "model", "unknown"))),
            }
            if preflight.get("status") != "ready":
                last_reason = str(preflight.get("reason") or "provider_blocked")
                attempts.append(_attempt(
                    role=role, provider=last_meta["provider"], transport=last_meta["transport"],
                    model=last_meta["model"], attempt=0, duration_ms=0, status="skipped",
                    reason=last_reason, usage=None, actual_cost_usd=None,
                    billing_mode=str(preflight.get("billing_mode", "unknown")),
                ))
                if last_reason not in _FALLBACK_REASONS and last_reason not in {
                    "free_route_not_confirmed", "paid_gate_not_authorized", "paid_model_not_allowed",
                }:
                    break
                continue
            result = provider.invoke(role, role_input)
            attempts.extend(result.attempts)
            if result.status == "succeeded" and result.output is not None:
                actual_model = result.attempts[-1].get("model", last_meta["model"]) if result.attempts else last_meta["model"]
                return RoutedProviderResult(
                    "succeeded", result.output, tuple(attempts), None,
                    last_meta["provider"], last_meta["transport"], actual_model,
                    {**self.routing["profiles"][name]["parameters"],
                     "route_name": name, "requested_model": last_meta["model"], "billing_mode": preflight.get("billing_mode"),
                     "paid_api_enabled": False}, self.routing,
                )
            last_reason = result.reason or "provider_failed"
            if last_reason not in _FALLBACK_REASONS:
                break
        return RoutedProviderResult(
            "failed", None, tuple(attempts), last_reason,
            last_meta["provider"], last_meta["transport"], last_meta["model"],
            {"paid_api_enabled": False}, self.routing,
        )
