"""Gemini-only, evidence-only optional narration for the public Mart."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .analysis import canonical_json
from packages.observability import redact


_STABLE_MODEL_PRIORITY = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash")
_DAILY_MODEL_CACHE: dict[str, tuple[str, ...]] = {}


def _safe_http_error(error: HTTPError) -> dict[str, str]:
    try:
        detail = json.loads(error.read())
        provider = detail.get("error", {}) if isinstance(detail, dict) else {}
    except Exception:
        return {}
    if not isinstance(provider, dict):
        return {}
    result = {}
    status = str(provider.get("status", ""))[:64]
    message = redact(provider.get("message", ""))
    reasons = [str(item.get("reason", ""))[:64] for item in provider.get("details", [])
               if isinstance(item, dict) and item.get("reason")]
    if status:
        result["provider_status"] = status
    if reasons:
        result["provider_reason"] = reasons[0]
    if message:
        result["message"] = message
    return result


def _select_stable_models(document: Any) -> tuple[str, ...]:
    available = set()
    for item in document.get("models", []) if isinstance(document, dict) else []:
        if not isinstance(item, dict) or "generateContent" not in item.get("supportedGenerationMethods", []):
            continue
        name = str(item.get("name", "")).removeprefix("models/")
        if name in _STABLE_MODEL_PRIORITY:
            available.add(name)
    return tuple(name for name in _STABLE_MODEL_PRIORITY if name in available)[:3]


def _daily_stable_models(api_key: str, opener: Callable[..., Any] = urlopen) -> tuple[str, ...]:
    today = date.today().isoformat()
    if today in _DAILY_MODEL_CACHE:
        return _DAILY_MODEL_CACHE[today]
    request = Request("https://generativelanguage.googleapis.com/v1beta/models",
                      headers={"x-goog-api-key": api_key})
    try:
        with opener(request, timeout=10) as response:
            selected = _select_stable_models(json.load(response))
    except Exception:
        selected = ()
    result = selected or _STABLE_MODEL_PRIORITY[:3]
    _DAILY_MODEL_CACHE[today] = result
    return result


class GeminiNarrator:
    def __init__(self, api_key: str, *, model: str = "gemini-2.5-flash", models: tuple[str, ...] | None = None,
                 attempts: int = 3,
                 opener: Callable[..., Any] = urlopen, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required")
        paid = os.environ.get("GEMINI_PAID_ENABLED", "false").lower() in {"1", "true", "yes"}
        approved = os.environ.get("GEMINI_BILLING_APPROVED", "false").lower() in {"1", "true", "yes"}
        if paid and not approved:
            raise ValueError("Gemini paid tier requires a separate approved billing gate")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model) or attempts not in range(1, 5):
            raise ValueError("invalid Gemini model or retry bound")
        selected = tuple(models or (model,))
        if not selected or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", item) for item in selected):
            raise ValueError("invalid Gemini model or retry bound")
        self.api_key, self.models, self.attempts, self.opener, self.sleeper = api_key, selected, attempts, opener, sleeper

    @property
    def model(self) -> str:
        return self.models[0]

    @classmethod
    def from_environment(cls) -> "GeminiNarrator":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        configured = os.environ.get("GEMINI_MODEL", "").strip()
        models = (configured,) if configured else _daily_stable_models(api_key)
        return cls(api_key, model=models[0], models=models, attempts=int(os.environ.get("GEMINI_MAX_ATTEMPTS", "3")))

    def narrate(self, report: dict[str, Any], prompts: dict[str, Any]) -> dict[str, Any]:
        evidence_ids = {item["evidence_id"] for item in report["evidence"]}
        context = {"analysis_as_of": report["analysis_as_of"], "scope": report["scope"],
                   "role_instructions": prompts["roles"], "roles": report["roles"],
                   "aggregate": report["aggregate"], "evidence": report["evidence"]}
        fault = os.environ.get("MART_ACCEPTANCE_FAULT", "").strip()
        if fault and os.environ.get("ENVIRONMENT", "").lower() != "dev":
            raise ValueError("Mart acceptance faults are dev-only")
        if fault not in {"", "quota", "provider_unavailable", "invalid_structured_output"}:
            raise ValueError("invalid Mart acceptance fault")
        failures = []
        for model in self.models:
            result = self._narrate_model(model, report, prompts, context, evidence_ids, fault)
            if result["status"] == "succeeded":
                return result
            failures.append(result["error"])
        return {"status": "failed", "provider": "gemini", "model": self.model,
                "attempted_models": list(self.models), "error": failures[-1]}

    def _narrate_model(self, model: str, report: dict[str, Any], prompts: dict[str, Any],
                       context: dict[str, Any], evidence_ids: set[str], fault: str) -> dict[str, Any]:
        body = {
            "systemInstruction": {"parts": [{"text": prompts["system"]}]},
            "contents": [{"role": "user", "parts": [{"text": canonical_json(context).decode()}]}],
            "generationConfig": {"responseFormat": {"text": {
                "mimeType": "APPLICATION_JSON", "schema": prompts["response_schema"],
            }}},
        }
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent"
        last: dict[str, Any] = {"kind": "provider_unavailable", "status": 0}
        for attempt in range(self.attempts):
            if fault:
                last = {"kind": fault, "status": 429 if fault == "quota" else 503 if fault == "provider_unavailable" else 200}
                if fault == "invalid_structured_output":
                    break
                if attempt + 1 < self.attempts:
                    self.sleeper(2 ** attempt)
                continue
            request = Request(endpoint, data=canonical_json(body), method="POST",
                              headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key})
            try:
                with self.opener(request, timeout=30) as response:
                    document = json.load(response)
                parts = document.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                narrative = json.loads("".join(str(part.get("text", "")) for part in parts))
                expected = {"summary", "bull_case", "bear_case", "risks", "evidence_ids"}
                if not isinstance(narrative, dict) or set(narrative) != expected \
                        or not isinstance(narrative["summary"], str) \
                        or any(not isinstance(narrative[name], list) or any(not isinstance(item, str) for item in narrative[name])
                               for name in ("bull_case", "bear_case", "risks", "evidence_ids")) \
                        or not set(narrative["evidence_ids"]) <= evidence_ids:
                    raise ValueError("Gemini narrative contains unvalidated evidence")
                allowed = self._numbers(context)
                claimed = self._numbers({key: value for key, value in narrative.items() if key != "evidence_ids"})
                if not claimed <= allowed:
                    raise ValueError("Gemini narrative contains a number absent from evidence")
                return {"status": "succeeded", "provider": "gemini", "model": model,
                        "prompt_version": prompts["version"], "narrative": narrative}
            except HTTPError as error:
                kind = "quota" if error.code == 429 else "provider_unavailable" if error.code >= 500 else "provider_error"
                last = {"kind": kind, "status": error.code, **_safe_http_error(error)}
                if kind not in {"quota", "provider_unavailable"}:
                    break
            except URLError:
                last = {"kind": "provider_unavailable", "status": 0}
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                last = {"kind": "invalid_structured_output", "status": 200}
                break
            if attempt + 1 < self.attempts:
                self.sleeper(2 ** attempt)
        return {"status": "failed", "provider": "gemini", "model": model, "error": last}

    @classmethod
    def _numbers(cls, value: Any, key: str = "") -> set[str]:
        if key in {"evidence_id", "evidence_ids", "provenance_id", "core_snapshot_id", "location", "deterministic_hash"}:
            return set()
        if isinstance(value, dict):
            return set().union(*(cls._numbers(item, str(name)) | set(re.findall(r"\d+(?:\.\d+)?", str(name)))
                                 for name, item in value.items())) if value else set()
        if isinstance(value, list):
            return set().union(*(cls._numbers(item, key) for item in value)) if value else set()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {str(value), f"{float(value):g}"}
        return set(re.findall(r"[-+]?\d+(?:\.\d+)?%?", str(value)))
