"""Governed Codex CLI workers for additive Mart AI role artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from typing import Any, Callable

from .ai_contract import OUTPUT_MODELS, PROVIDER_ROLES, SYSTEM_GUARDRAIL, content_hash, contract_bundle

CODEX_CLI_VERSION = "0.159.2"
PROVIDER_STAGE_VERSION = "1.0.0"
DEFAULT_MODEL = "gpt-6.1-sol"
_ALLOWED_REASONING = frozenset({"low", "medium", "high", "xhigh", "max"})
_RETRYABLE = frozenset({"quota", "provider_unavailable", "timeout", "transport_error"})


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def _safe_reason(text: str) -> str:
    value = text.lower()
    if any(x in value for x in ("not logged in", "login required", "unauthorized", "authentication", "access token", "401")):
        return "auth_required"
    if any(x in value for x in ("rate limit", "quota", "too many requests", "429")):
        return "quota"
    if any(x in value for x in ("model not found", "unsupported model", "does not have access", "model access")):
        return "unsupported_model"
    if any(x in value for x in ("unknown field", "unknown config", "invalid value", "unsupported parameter", "configuration error")):
        return "unsupported_parameter"
    if any(x in value for x in ("unavailable", "service unavailable", "temporarily", "502", "503", "504")):
        return "provider_unavailable"
    return "transport_error"


def _usage(stdout: str) -> dict[str, int] | None:
    terminal = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") in {"turn.completed", "turn.failed"}:
            terminal = event
    raw = (terminal or {}).get("usage")
    if not isinstance(raw, dict):
        return None
    clean = {k: v for k, v in raw.items() if k in {"input_tokens", "cached_input_tokens", "output_tokens"}
             and type(v) is int and v >= 0}
    return clean or None


@dataclass(frozen=True)
class ProviderResult:
    status: str
    output: dict[str, Any] | None
    attempts: tuple[dict[str, Any], ...]
    reason: str | None


class CodexCLIProvider:
    """Bounded, isolated wrapper around the pinned Codex CLI."""

    def __init__(self, *, binary: str = "codex", model: str = DEFAULT_MODEL, reasoning_effort: str = "low",
                 timeout_seconds: int = 180, max_attempts: int = 2, kill_grace_seconds: int = 3) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model):
            raise ValueError("invalid Codex model")
        if reasoning_effort not in _ALLOWED_REASONING:
            raise ValueError("invalid Codex reasoning effort")
        if timeout_seconds not in range(10, 901) or max_attempts not in range(1, 4) or kill_grace_seconds not in range(1, 11):
            raise ValueError("invalid Codex worker bounds")
        self.binary, self.model, self.reasoning_effort = binary, model, reasoning_effort
        self.timeout_seconds, self.max_attempts, self.kill_grace_seconds = timeout_seconds, max_attempts, kill_grace_seconds
        self.cli_version = CODEX_CLI_VERSION
        self.auth_checkpoint: Callable[[], str | None] | None = None
        self.auth_error: str | None = None

    @classmethod
    def from_environment(cls) -> "CodexCLIProvider":
        return cls(
            binary=os.environ.get("MART_CODEX_BINARY", "codex").strip() or "codex",
            model=os.environ.get("MART_CODEX_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            reasoning_effort=os.environ.get("MART_CODEX_REASONING_EFFORT", "low").strip().lower(),
            timeout_seconds=int(os.environ.get("MART_CODEX_TIMEOUT_SECONDS", "180")),
            max_attempts=int(os.environ.get("MART_CODEX_MAX_ATTEMPTS", "2")),
            kill_grace_seconds=int(os.environ.get("MART_CODEX_KILL_GRACE_SECONDS", "3")),
        )

    def _auth(self) -> tuple[str | None, str | None]:
        token = os.environ.get("CODEX_ACCESS_TOKEN", "").strip()
        cache = os.environ.get("MART_CODEX_AUTH_JSON", "").strip()
        if token and cache:
            return None, "ambiguous_auth"
        if token:
            return "access_token", None
        if cache:
            try:
                parsed = json.loads(cache)
            except json.JSONDecodeError:
                return None, "invalid_auth_cache"
            if not isinstance(parsed, dict) or not parsed:
                return None, "invalid_auth_cache"
            if parsed.get("OPENAI_API_KEY") or parsed.get("auth_mode") not in {None, "chatgpt"}:
                return None, "unapproved_auth_mode"
            tokens = parsed.get("tokens")
            if not isinstance(tokens, dict) or not tokens.get("access_token") or not tokens.get("refresh_token"):
                return None, "invalid_auth_cache"
            return "auth_cache", None
        return None, "auth_required"

    @staticmethod
    def _base_env(home: str = "/tmp") -> dict[str, str]:
        return {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": home,
                "LANG": os.environ.get("LANG", "C.UTF-8"), "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
                "NO_COLOR": "1"}

    def preflight(self) -> dict[str, Any]:
        mode, error = self._auth()
        error = self.auth_error or error
        common = {"provider": "openai", "transport": "codex_cli", "model": self.model,
                  "cli_version": self.cli_version, "publication_authority": False}
        if error:
            return {"status": "blocked", "reason": error, **common}
        env = self._base_env()
        try:
            version = subprocess.run([self.binary, "--version"], capture_output=True, text=True, timeout=5, env=env)
            match = re.fullmatch(r"codex-cli (\d+\.\d+\.\d+)", version.stdout.strip())
            version_text = match.group(1) if match else "unknown"
            if version.returncode or self.cli_version != version_text:
                return {"status": "blocked", "reason": "unsupported_cli_version", **common, "cli_version": version_text}
            help_run = subprocess.run([self.binary, "exec", "--help"], capture_output=True, text=True, timeout=5, env=env)
            help_text = (help_run.stdout or "") + (help_run.stderr or "")
            if help_run.returncode or any(flag not in help_text for flag in ("--json", "--output-schema", "--skip-git-repo-check", "--ephemeral")):
                return {"status": "blocked", "reason": "unsupported_cli_capability", **common}
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "blocked", "reason": "codex_cli_unavailable", **common}
        return {"status": "ready", "reason": None, **common, "auth_mode": mode,
                "billing_mode": "chatgpt_codex_account", "paid_api_enabled": False}

    def _workspace(self, role: str, schema: dict[str, Any], auth_mode: str) -> tempfile.TemporaryDirectory[str]:
        root = Path(os.environ.get("MART_CODEX_WORK_ROOT", "/tmp/janus-codex-workers"))
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        workspace = tempfile.TemporaryDirectory(prefix=f"{role}-", dir=root)
        path = Path(workspace.name); path.chmod(0o700)
        codex_home = path / "home" / ".codex"; codex_home.mkdir(parents=True, mode=0o700)
        model_line = '' if self.model == "account_default" else f'model = \"{self.model}\"\n'
        (codex_home / "config.toml").write_text(
            model_line + f'model_reasoning_effort = "{self.reasoning_effort}"\n'
            'approval_policy = "never"\nsandbox_mode = "read-only"\nweb_search = "disabled"\n'
            'check_for_update_on_startup = false\ncli_auth_credentials_store = "file"\n'
            'forced_login_method = "chatgpt"\n[features]\napps = false\nmulti_agent = false\n'
            'shell_tool = false\nunified_exec = false\nplugins = false\nhooks = false\n'
            'browser_use = false\ncomputer_use = false\ntool_search = false\n'
            'image_generation = false\nview_image = false\n', encoding="utf-8")
        if auth_mode == "auth_cache":
            (codex_home / "auth.json").write_text(os.environ["MART_CODEX_AUTH_JSON"], encoding="utf-8")
            (codex_home / "auth.json").chmod(0o600)
        (path / "schema.json").write_bytes(_canonical(schema))
        return workspace

    def _env(self, path: Path, auth_mode: str) -> dict[str, str]:
        env = self._base_env(str(path / "home")); env["CODEX_HOME"] = str(path / "home" / ".codex")
        # Never inherit OPENAI_API_KEY, Janus DB credentials, runtime bundles, or GCP secrets.
        if auth_mode == "access_token":
            env["CODEX_ACCESS_TOKEN"] = os.environ["CODEX_ACCESS_TOKEN"]
        for name in ("SSL_CERT_FILE", "SSL_CERT_DIR", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
            if os.environ.get(name): env[name] = os.environ[name]
        return env

    def invoke(self, role: str, role_input: dict[str, Any]) -> ProviderResult:
        if role not in PROVIDER_ROLES:
            raise ValueError("invalid AI analyst role")
        if self.auth_checkpoint and not self.auth_error:
            self.auth_error = self.auth_checkpoint()
        auth_mode, auth_error = self._auth()
        auth_error = self.auth_error or auth_error
        if auth_error or auth_mode is None:
            return ProviderResult("failed", None, (), auth_error or "auth_required")
        schema = OUTPUT_MODELS[role].model_json_schema()
        methodology = contract_bundle()["prompts"][role]["methodology"]
        prompt = (f"{SYSTEM_GUARDRAIL}\n\nROLE METHODOLOGY:\n{methodology}\n\n"
                  "Analyze only PUBLIC_INPUT. Do not invoke tools. Copy numeric facts exactly as fact_key=value. "
                  "Return only the requested structured output.\nPUBLIC_INPUT:\n" +
                  json.dumps(role_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))
        attempts: list[dict[str, Any]] = []
        for number in range(1, self.max_attempts + 1):
            with self._workspace(role, schema, auth_mode) as workspace_name:
                path = Path(workspace_name); output = path / "output.json"
                command = [self.binary, "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                           "--output-schema", str(path / "schema.json"), "-o", str(output), "-"]
                started = time.monotonic(); reason = None; stdout = ""; stderr = ""; returncode = None
                try:
                    process = subprocess.Popen(command, cwd=path, env=self._env(path, auth_mode), text=True,
                                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                    stdout, stderr = process.communicate(input=prompt, timeout=self.timeout_seconds); returncode = process.returncode
                except OSError:
                    reason = "codex_cli_unavailable"
                except subprocess.TimeoutExpired:
                    reason = "timeout"
                    try: os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: stdout, stderr = process.communicate(timeout=self.kill_grace_seconds)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        stdout, stderr = process.communicate()
                    returncode = process.returncode
                if auth_mode == "auth_cache":
                    # Keep rotated credentials for subsequent roles; never place them in artifacts.
                    refreshed = path / "home" / ".codex" / "auth.json"
                    if refreshed.exists():
                        os.environ["MART_CODEX_AUTH_JSON"] = refreshed.read_text(encoding="utf-8")
                    if self.auth_checkpoint:
                        self.auth_error = self.auth_checkpoint()
                        if self.auth_error:
                            reason = self.auth_error
                parsed = None
                if reason is None and returncode == 0 and output.exists():
                    try: parsed = OUTPUT_MODELS[role].model_validate_json(output.read_text()).model_dump()
                    except Exception: reason = "invalid_structured_output"
                elif reason is None:
                    reason = _safe_reason(stderr[-4096:] + "\n" + stdout[-4096:])
                if reason == "auth_required":
                    self.auth_error = reason
                attempt = {"artifact_kind": "mart_ai_provider_attempt_v1", "schema_version": PROVIDER_STAGE_VERSION,
                           "role": role, "attempt": number, "provider": "openai", "transport": "codex_cli",
                           "model": self.model, "cli_version": self.cli_version, "exit_code": returncode,
                           "duration_ms": round((time.monotonic() - started) * 1000),
                           "status": "succeeded" if parsed is not None else "failed", "reason": reason,
                           "usage": _usage(stdout), "actual_cost_usd": None, "cost_observability": "unknown",
                           "paid_api_enabled": False, "publication_authority": False}
                attempt["artifact_hash"] = content_hash(attempt); attempts.append(attempt)
                if parsed is not None:
                    return ProviderResult("succeeded", parsed, tuple(attempts), None)
                if reason not in _RETRYABLE:
                    return ProviderResult("failed", None, tuple(attempts), reason)
                if number < self.max_attempts: time.sleep(min(2 ** (number - 1), 2))
        return ProviderResult("failed", None, tuple(attempts), attempts[-1]["reason"] if attempts else "transport_error")
