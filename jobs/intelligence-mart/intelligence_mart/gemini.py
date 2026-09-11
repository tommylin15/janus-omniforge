"""Gemini-only, evidence-only optional narration for the public Mart."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .analysis import canonical_json


class GeminiNarrator:
    def __init__(self, api_key: str, *, model: str = "gemini-2.5-flash", attempts: int = 3,
                 opener: Callable[..., Any] = urlopen, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required")
        if os.environ.get("GEMINI_PAID_ENABLED", "false").lower() in {"1", "true", "yes"}:
            raise ValueError("Gemini paid tier requires a separate approved billing gate")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model) or attempts not in range(1, 5):
            raise ValueError("invalid Gemini model or retry bound")
        self.api_key, self.model, self.attempts, self.opener, self.sleeper = api_key, model, attempts, opener, sleeper

    @classmethod
    def from_environment(cls) -> "GeminiNarrator":
        return cls(os.environ.get("GEMINI_API_KEY", ""), model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                   attempts=int(os.environ.get("GEMINI_MAX_ATTEMPTS", "3")))

    def narrate(self, report: dict[str, Any], prompts: dict[str, Any]) -> dict[str, Any]:
        evidence_ids = {item["evidence_id"] for item in report["evidence"]}
        context = {"analysis_as_of": report["analysis_as_of"], "scope": report["scope"],
                   "role_instructions": prompts["roles"], "roles": report["roles"],
                   "aggregate": report["aggregate"], "evidence": report["evidence"]}
        body = {
            "systemInstruction": {"parts": [{"text": prompts["system"]}]},
            "contents": [{"role": "user", "parts": [{"text": canonical_json(context).decode()}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": prompts["response_schema"]},
        }
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(self.model, safe='')}:generateContent"
        last: dict[str, Any] = {"kind": "provider_unavailable", "status": 0}
        for attempt in range(self.attempts):
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
                return {"status": "succeeded", "provider": "gemini", "model": self.model,
                        "prompt_version": prompts["version"], "narrative": narrative}
            except HTTPError as error:
                kind = "quota" if error.code == 429 else "provider_unavailable" if error.code >= 500 else "provider_error"
                last = {"kind": kind, "status": error.code}
                if kind not in {"quota", "provider_unavailable"}:
                    break
            except URLError:
                last = {"kind": "provider_unavailable", "status": 0}
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                last = {"kind": "invalid_structured_output", "status": 200}
                break
            if attempt + 1 < self.attempts:
                self.sleeper(2 ** attempt)
        return {"status": "failed", "provider": "gemini", "model": self.model, "error": last}

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
