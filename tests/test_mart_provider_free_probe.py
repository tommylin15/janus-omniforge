import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("billing_enabled", [False, True])
def test_free_probe_preserves_billing_gate_and_redacts_credentials(monkeypatch, capsys, billing_enabled):
    path = Path(__file__).parents[1] / "ops/mart-provider-free-probe.py"
    spec = importlib.util.spec_from_file_location("free_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    monkeypatch.setattr(probe, "cloud", lambda *args: "gcp-token-secret" if args[0] == "auth" else
                        json.dumps({"openrouter_api_key": "router-secret", "gemini_api_key": "gemini-secret"}))
    urls = []

    def request(url, headers, data=None):
        urls.append(url)
        if "chat/completions" in url:
            assert data["provider"]["max_price"] == {"prompt": 0, "completion": 0}
            return 200, {"model": "test:free", "usage": {"cost": 0},
                         "choices": [{"message": {"content": '{"ok":true}'}}]}
        if "lookupKey" in url:
            return 200, {"parent": "projects/123/locations/global"}
        if "billingInfo" in url:
            return 200, {"billingEnabled": billing_enabled}
        return 200, {"models": []}

    monkeypatch.setattr(probe, "request", request)
    probe.main()
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["gemini"]["free_tier_confirmed"] is (not billing_enabled)
    assert result["openrouter"]["free_request_verified"] is True
    assert all("generateContent" not in url for url in urls)
    assert all(secret not in output for secret in ("router-secret", "gemini-secret", "gcp-token-secret"))
