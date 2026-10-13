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
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from .ai_contract import OUTPUT_MODELS, PROVIDER_ROLES, SYSTEM_GUARDRAIL, content_hash, contract_bundle
from .codex_worker import CodexCLIProvider, ProviderResult, PROVIDER_STAGE_VERSION

OMNI_MARKET_PROMPT_MAX_BYTES = 32_768
OMNI_GATEWAY_BODY_MAX_BYTES = 128 * 1024
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
    'auth_secret_unavailable',
    'auth_batch_busy',
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
    schema = OUTPUT_MODELS[role].model_json_schema()
    example = {
        "schema_version": "1.0.0", "role": "ceo",
        "stance": "insufficient_data", "thesis": None,
        "missing_information": ["部分來源資料不足，需保留缺值"],
        "confidence": 0.0, "evidence_ids": [],
        "supporting_roles": [], "opposing_roles": [],
        "contradictions": [], "bull_case": [], "bear_case": [],
        "principal_risks": [], "watch_items": [],
        "change_since_previous_analysis": [],
        "validated_role_artifact_hashes": role_input.get("validated_role_artifact_hashes", []),
    }
    return (
        f"{SYSTEM_GUARDRAIL}\n\nROLE METHODOLOGY:\n{methodology}\n\n"
        "只輸出單一 JSON object，不要 Markdown 或額外欄位。所有 schema required 欄位必填。"
        "stance 限 bullish, neutral, bearish, insufficient_data；thesis 可為 null，"
        "但方向性立場須有附 evidence_ids 的 thesis。所有 claim 必須含 text/evidence_ids，"
        "所有 evidence ID 必須來自 PUBLIC_INPUT，不能杜撰。"
        "confidence 是 0 到 1 的 JSON number，不是獲利機率。"
        "validated_role_artifact_hashes 必須逐一照抄輸入的五個 sha256，不能換順序或數值。"
        "沒有上一份有效報告時 change_since_previous_analysis 必須是空陣列。"
        "不要在文字重述任何未以 numeric_facts key=value 綁定的數字、日期或股號。"
        "資訊不足列在 missing_information；沒有足夠證據就用 insufficient_data、thesis=null。"
        "以下示例為安全的資訊不足情境，實際輸出請以真實證據決定。\n"
        "REQUIRED_JSON_SCHEMA:\n"
        + json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\nJSON_EXAMPLE:\n"
        + json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\nPUBLIC_INPUT:\n"
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
             actual_cost_usd: float | None, billing_mode: str,
             invalid_fields: list[str] | None = None) -> dict[str, Any]:
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
    if invalid_fields is not None:
        value["invalid_fields"] = invalid_fields[:12]
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
    if raw is not None and 'models' in raw:
        from packages.analysis_models import validated_models
        value['models'] = validated_models(raw['models'])
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
        if role not in PROVIDER_ROLES:
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
        if role not in PROVIDER_ROLES:
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
            invalid_fields = None
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
            except ValidationError as error:
                reason = "invalid_structured_output"
                allowed = set(OUTPUT_MODELS[role].model_fields)
                # Never record original provider content, error input or messages.
                invalid_fields = sorted({
                    str(item["loc"][0]) for item in error.errors(include_input=False)
                    if item.get("loc") and str(item["loc"][0]) in allowed
                })[:12] or ["json"]
            except Exception:
                reason = "invalid_structured_output"
                invalid_fields = ["response_structure"]
            attempts.append(_attempt(
                role=role, provider=self.provider_id, transport=self.transport, model=self.model, attempt=number,
                duration_ms=round((time.monotonic() - started) * 1000),
                status="succeeded" if parsed is not None else "failed", reason=reason, usage=usage,
                actual_cost_usd=None, billing_mode="free_tier_only", invalid_fields=invalid_fields,
            ))
            if parsed is not None:
                return ProviderResult("succeeded", parsed, tuple(attempts), None)
            if reason not in _FALLBACK_REASONS or number >= self.max_attempts:
                return ProviderResult("failed", None, tuple(attempts), reason or "transport_error")
            self.sleeper(min(2 ** (number - 1), 2))
        return ProviderResult("failed", None, tuple(attempts), attempts[-1]["reason"] if attempts else "transport_error")



class OmniGatewayGeminiProvider:
    """One bounded CEO call through the private omniAgent P0-V text contract.

    The Mart runtime impersonates only its approved market-mart caller identity;
    the Gateway (not Janus) holds the Gemini API key. No automatic retry is safe
    after an ambiguous provider/network outcome.
    """
    provider_id = "gemini"
    transport = "omniagent_gateway"
    model = "gemini-3.5-flash-lite"
    _audience = "https://omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app"
    _principal = "omniagent-codex-market-client@gen-lang-client-0593591102.iam.gserviceaccount.com"
    _allowed_url = re.compile(
        r"https://(?:[a-z0-9-]+---)?omniagent-agent-gateway-2oo7qbkd5q-uc\.a\.run\.app"
    )

    def __init__(self, *, gateway_url: str, opener: Callable[..., Any] = urlopen,
                 token_provider: Callable[[], str] | None = None) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.opener = opener
        self.token_provider = token_provider or self._mint_token
        self.timeout_seconds = 65
        self.max_attempts = 1
        self._owner_id: str | None = None
        self._request_id: str | None = None

    @classmethod
    def from_environment(cls) -> "OmniGatewayGeminiProvider":
        return cls(gateway_url=os.environ.get("MART_OMNI_GATEWAY_URL", ""))

    @classmethod
    def _mint_token(cls) -> str:
        import google.auth
        from google.auth import impersonated_credentials
        from google.auth.transport.requests import Request as GoogleAuthRequest
        source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        target = impersonated_credentials.Credentials(
            source_credentials=source, target_principal=cls._principal,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"], lifetime=300,
        )
        credentials = impersonated_credentials.IDTokenCredentials(
            target_credentials=target, target_audience=cls._audience, include_email=True,
        )
        credentials.refresh(GoogleAuthRequest())
        if not credentials.token:
            raise ValueError("gateway_identity_unavailable")
        return credentials.token

    def bind_context(self, *, owner_id: str, request_id: str) -> None:
        from uuid import UUID
        self._owner_id = str(UUID(str(owner_id)))
        self._request_id = str(UUID(str(request_id)))

    def preflight(self) -> dict[str, Any]:
        enabled = _bool_env("MART_CEO_GEMINI_ONLY") and _bool_env("MART_CEO_GEMINI_VIA_OMNIAGENT")
        valid_url = bool(self._allowed_url.fullmatch(self.gateway_url))
        reason = None if enabled and valid_url else (
            "gateway_route_disabled" if not enabled else "gateway_endpoint_unapproved"
        )
        return {"status": "ready" if reason is None else "blocked", "reason": reason,
                "provider": self.provider_id, "transport": self.transport, "model": self.model,
                "billing_mode": "gateway_free_tier_only", "paid_api_enabled": False,
                "publication_authority": False}

    def invoke(self, role: str, role_input: dict[str, Any]) -> ProviderResult:
        if role != "ceo":
            raise ValueError("omniAgent Gateway is CEO-only")
        preflight = self.preflight()
        if preflight["status"] != "ready":
            return ProviderResult("failed", None, (), preflight["reason"])
        reason: str | None = None
        parsed: dict[str, Any] | None = None
        invalid_fields: list[str] | None = None
        usage: dict[str, int] | None = None
        started = time.monotonic()
        if not self._owner_id or not self._request_id:
            reason = "gateway_context_missing"
        else:
            prompt = _prompt(role, role_input)
            if len(prompt.encode("utf-8")) > OMNI_MARKET_PROMPT_MAX_BYTES:
                reason = "gateway_prompt_too_large"
            else:
                body = {"project": "market-mart", "ownerId": self._owner_id,
                        "requestId": self._request_id, "prompt": prompt, "model": self.model}
                body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                if len(body_bytes) > OMNI_GATEWAY_BODY_MAX_BYTES:
                    reason = "gateway_prompt_too_large"
                else:
                    try:
                        token = self.token_provider()
                        if not isinstance(token, str) or not token:
                            raise ValueError("identity token unavailable")
                    except Exception:
                        reason = "gateway_identity_unavailable"
                    if reason is None:
                        try:
                            request = Request(
                                self.gateway_url + "/v1/gemini/execute",
                                data=body_bytes,
                                method="POST",
                                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                            )
                            with self.opener(request, timeout=self.timeout_seconds) as response:
                                raw = response.read(65537)
                            if len(raw) > 65536:
                                raise ValueError("gateway reply too large")
                            document = json.loads(raw)
                            if (not isinstance(document, dict) or document.get("status") != "completed"
                                    or document.get("project") != "market-mart"
                                    or document.get("ownerId") != self._owner_id
                                    or document.get("requestId") != self._request_id
                                    or document.get("model") != self.model
                                    or not isinstance(document.get("result"), dict)):
                                raise ValueError("gateway response identity mismatch")
                            answer = document["result"].get("text")
                            if not isinstance(answer, str) or not answer.strip() or len(answer) > 32000:
                                raise ValueError("gateway text invalid")
                            observed = document.get("usage")
                            if isinstance(observed, dict):
                                usage = {key: value for key, value in observed.items()
                                         if key in {"input_tokens", "output_tokens", "total_tokens"}
                                         and type(value) is int and value >= 0} or None
                            parsed = OUTPUT_MODELS[role].model_validate_json(answer).model_dump()
                        except HTTPError as error:
                            reason = _safe_reason(error.code)
                        except (URLError, TimeoutError, OSError):
                            reason = "provider_unavailable"
                        except ValidationError as error:
                            reason = "invalid_structured_output"
                            allowed = set(OUTPUT_MODELS[role].model_fields)
                            invalid_fields = sorted({
                                str(item["loc"][0]) for item in error.errors(include_input=False)
                                if item.get("loc") and str(item["loc"][0]) in allowed
                            })[:12] or ["json"]
                        except Exception:
                            reason = "gateway_contract_mismatch"
        attempt = _attempt(
            role=role, provider=self.provider_id, transport=self.transport, model=self.model,
            attempt=1 if reason != "gateway_context_missing" else 0,
            duration_ms=round((time.monotonic() - started) * 1000),
            status="succeeded" if parsed is not None else "failed", reason=reason,
            usage=usage, actual_cost_usd=None, billing_mode="gateway_free_tier_only",
            invalid_fields=invalid_fields,
        )
        return ProviderResult("succeeded" if parsed is not None else "failed",
                              parsed, (attempt,), reason)


class ProviderRouter:
    """Freeze one ordered provider route for an execution and audit every fallback."""

    def __init__(self, providers: dict[str, Any], routing: dict[str, Any]) -> None:
        route = routing.get("providers")
        if not isinstance(route, list) or set(route) != _ALLOWED_ROUTE or len(route) != len(_ALLOWED_ROUTE):
            raise ValueError("invalid provider routing snapshot")
        if set(providers) != _ALLOWED_ROUTE:
            raise ValueError("provider map must contain the complete governed route")
        if 'execution_providers' in routing and routing['execution_providers'] != ['gemini']:
            raise ValueError('invalid Gemini-only execution route')
        self.providers = providers
        self.routing = json.loads(json.dumps(routing))
        self.routing["profiles"] = {
            name: {**provider.preflight(), "parameters": {
                key: getattr(provider, key) for key in
                ("cli_version", "reasoning_effort", "timeout_seconds", "max_attempts", "kill_grace_seconds")
                if hasattr(provider, key)}}
            for name, provider in providers.items()
        }
        self.routing["effective_providers"] = [name for name in self.routing.get("execution_providers", self.routing["providers"])
                                               if self.routing["profiles"][name]["status"] == "ready"]
        self.routing["routing_hash"] = content_hash({k: v for k, v in self.routing.items() if k != "routing_hash"})
        self.model = "routed"
        self.cli_version = getattr(providers["codex_cli"], "cli_version", "unknown")

    @classmethod
    def from_environment(cls, request_options: dict[str, Any] | None = None,
                         *, codex_provider: CodexCLIProvider | None = None,
                         bounded_manual: bool = False) -> "ProviderRouter":
        use_gateway = bounded_manual and _bool_env("MART_CEO_GEMINI_VIA_OMNIAGENT", False)
        if not use_gateway:
            load_remote_credentials_from_runtime_bundle()
        codex = codex_provider or CodexCLIProvider.from_environment()
        providers = {
            "codex_cli": codex,
            "openrouter": OpenRouterProvider.from_environment(),
            "gemini": (OmniGatewayGeminiProvider.from_environment() if use_gateway
                       else GeminiRoleProvider.from_environment()),
        }
        routing = route_snapshot(request_options)
        if 'models' in routing:
            for name, model in routing['models'].items():
                providers[name].model = model
        if bounded_manual:
            for provider in providers.values():
                provider.timeout_seconds = min(provider.timeout_seconds, 120)
                provider.max_attempts = 1
            if _bool_env("MART_CEO_GEMINI_ONLY", False):
                providers['gemini'].model = 'gemini-3.5-flash-lite'
                routing['execution_providers'] = ['gemini']
                routing['execution_policy'] = 'gemini_lite_only'
                if use_gateway:
                    routing['execution_policy'] = 'omniagent_gateway_gemini_lite_only'
        return cls(providers, routing)

    def preflight(self) -> dict[str, Any]:
        entries = []
        any_ready = False
        for name in self.routing.get("execution_providers", self.routing["providers"]):
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

    def invoke(self, role: str, role_input: dict[str, Any], *, should_stop=None) -> RoutedProviderResult:
        attempts: list[dict[str, Any]] = []
        last_reason = "no_executable_provider"
        last_meta = {"provider": "janus", "transport": "provider_router", "model": "routed"}
        for name in self.routing.get("execution_providers", self.routing["providers"]):
            if should_stop is not None and should_stop():
                last_reason = "cancelled"
                break
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
