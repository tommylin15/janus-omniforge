import pytest

from services.api.engine_security import (
    GeminiFreeQuota, authorize_tools, gemini_api_key, gemini_request, managed_login_params, policy_for,
    validate_provider_environment,
)


def test_profiles_are_fixed_and_have_distinct_policies():
    codex, chatgpt, gemini = map(policy_for, ("codex", "chatgpt", "gemini"))
    assert codex.backend == chatgpt.backend == "codex_app_server"
    assert codex.agentic and not chatgpt.agentic
    assert codex.app_brand == "codex" and chatgpt.app_brand == "chatgpt"
    assert gemini.backend == "gemini_developer_api" and gemini.credential == "api_key" and gemini.grounding
    assert gemini.model == "gemini-2.5-flash" and "google_search" in gemini.tools
    with pytest.raises(ValueError):
        policy_for("openai")


def test_openai_profiles_only_build_managed_login_requests():
    assert managed_login_params("codex") == {
        "type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": "codex"
    }
    assert managed_login_params("chatgpt", device_code=True) == {"type": "chatgptDeviceCode"}
    with pytest.raises(ValueError):
        managed_login_params("gemini")


def test_provider_key_and_prompt_injected_tools_are_rejected():
    with pytest.raises(ValueError):
        validate_provider_environment({"OPENAI_API_KEY": "x"})
    assert authorize_tools("codex", {"read_private_context"}) == {"read_private_context"}
    for tool in ("shell", "write_file", "admin", "mutate_trade", "mutate_note", "mutate_watchlist", "place_order"):
        with pytest.raises(PermissionError):
            authorize_tools("codex", {tool})


def test_gemini_uses_server_key_and_enforces_free_tier_quotas():
    assert gemini_api_key({"GEMINI_API_KEY": "secret"}) == "secret"
    with pytest.raises(ValueError):
        gemini_api_key({})
    quota = GeminiFreeQuota()
    quota.authorize(19, 499)
    for counts in ((20, 0), (0, 500)):
        with pytest.raises(PermissionError):
            quota.authorize(*counts)


def test_gemini_search_request_enables_google_search_grounding():
    assert gemini_request("latest market news", search=True) == {
        "model": "gemini-2.5-flash",
        "input": "latest market news",
        "tools": [{"type": "google_search"}],
    }
