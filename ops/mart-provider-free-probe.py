"""Operator-authorized provider probes; never print credentials or raw errors."""
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def cloud(*args):
    result = subprocess.run([shutil.which("gcloud.cmd") or "gcloud", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("gcloud command failed")
    return result.stdout.strip()


def request(url, headers, data=None):
    try:
        req = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
        with urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, {}
    except Exception:
        return None, {}


def main():
    project = "gen-lang-client-0593591102"
    bundle = json.loads(cloud("secrets", "versions", "access", "latest", "--secret=janus-runtime-bundle", "--project=" + project))
    result = {"observed_at": datetime.now(timezone.utc).isoformat(), "paid_generation_enabled": False}
    key = bundle.get("openrouter_api_key", "")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    body = {"model": "openrouter/free", "messages": [{"role": "user", "content": "Return JSON with ok true."}],
            "max_tokens": 64, "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": {"name": "probe", "strict": True,
                "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}}},
            "provider": {"require_parameters": True, "max_price": {"prompt": 0, "completion": 0}}}
    status, document = request("https://openrouter.ai/api/v1/chat/completions", headers, body) if key else (None, {})
    cost = document.get("usage", {}).get("cost")
    observed = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
    structured = False
    try:
        structured = json.loads(document["choices"][0]["message"]["content"]) == {"ok": True}
    except Exception:
        pass
    result["openrouter"] = {"http_status": status, "requested_model": "openrouter/free", "actual_model": document.get("model"),
                            "actual_cost_usd": cost if observed else None,
                            "free_request_verified": status == 200 and observed and cost == 0 and structured,
                            "structured_output_valid": structured, "max_price": body["provider"]["max_price"]}
    key = bundle.get("gemini_api_key", "")
    status, document = request("https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": key}) if key else (None, {})
    result["gemini"] = {"models_http_status": status, "model_count": len(document.get("models", [])),
                        "generation_requests": 0, "free_tier_confirmed": False}
    token = cloud("auth", "print-access-token")
    status, lookup = request("https://apikeys.googleapis.com/v2/keys:lookupKey?" + urlencode({"keyString": key}),
                             {"Authorization": "Bearer " + token}) if key else (None, {})
    result["gemini"]["key_project_lookup_http_status"] = status
    parent = lookup.get("parent", "")
    if status == 200 and parent.startswith("projects/"):
        number = parent.split("/")[1]
        status, billing = request("https://cloudbilling.googleapis.com/v1/projects/" + number + "/billingInfo",
                                  {"Authorization": "Bearer " + token})
        result["gemini"].update(project_number=number, billing_http_status=status,
                                billing_enabled=billing.get("billingEnabled"),
                                free_tier_confirmed=status == 200 and billing.get("billingEnabled") is False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "blocked", "reason": "operator_probe_failed", "credential_payload_logged": False}))
        raise SystemExit(1)
