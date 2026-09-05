"""Security contract for the private chat engine boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os


class Engine(str, Enum):
    CODEX = "codex"
    CHATGPT = "chatgpt"
    GEMINI = "gemini"


@dataclass(frozen=True)
class EnginePolicy:
    backend: str
    credential: str
    agentic: bool
    app_brand: str | None = None
    grounding: bool = False
    tools: frozenset[str] = frozenset()
    model: str | None = None


POLICIES = {
    Engine.CODEX: EnginePolicy("codex_app_server", "managed_oauth", True, "codex",
                               tools=frozenset({"read_public_mart", "read_private_context"})),
    Engine.CHATGPT: EnginePolicy("codex_app_server", "managed_oauth", False, "chatgpt",
                                 tools=frozenset({"read_public_mart", "read_private_context"})),
    Engine.GEMINI: EnginePolicy("gemini_developer_api", "api_key", False, grounding=True,
                                tools=frozenset({"read_public_mart", "read_private_context", "google_search"}),
                                model="gemini-2.5-flash"),
}


@dataclass(frozen=True)
class GeminiFreeQuota:
    per_user_daily: int = 20
    project_daily_grounded_prompts: int = 500

    def authorize(self, user_daily_count: int, project_daily_count: int) -> None:
        if user_daily_count >= self.per_user_daily or project_daily_count >= self.project_daily_grounded_prompts:
            raise PermissionError("Gemini free-tier quota exceeded")


def policy_for(value: str) -> EnginePolicy:
    try:
        return POLICIES[Engine(value)]
    except (ValueError, KeyError) as error:
        raise ValueError("unsupported chat engine") from error


def managed_login_params(engine: str, *, device_code: bool = False) -> dict[str, object]:
    policy = policy_for(engine)
    if policy.backend != "codex_app_server":
        raise ValueError("engine does not use ChatGPT managed login")
    if device_code:
        return {"type": "chatgptDeviceCode"}
    return {"type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": policy.app_brand}


def gemini_api_key(env: dict[str, str] | None = None) -> str:
    value = (os.environ if env is None else env).get("GEMINI_API_KEY", "").strip()
    if not value:
        raise ValueError("GEMINI_API_KEY is required")
    return value


def gemini_request(prompt: str, *, search: bool) -> dict[str, object]:
    if not prompt.strip():
        raise ValueError("prompt is required")
    request: dict[str, object] = {"model": policy_for("gemini").model, "input": prompt}
    if search:
        request["tools"] = [{"type": "google_search"}]
    return request


def authorize_tools(engine: str, requested: set[str]) -> frozenset[str]:
    policy = policy_for(engine)
    if not requested <= policy.tools:
        raise PermissionError("chat tool is not allowed")
    return frozenset(requested)


def validate_provider_environment(env: dict[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    forbidden = [key for key in values if key.upper() in {
        "OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_ENDPOINT", "CODEX_API_KEY"
    }]
    if forbidden:
        raise ValueError("API-key provider configuration is forbidden")
