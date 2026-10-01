from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap
import time

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from intelligence_mart.ai_providers import CodexCLIProvider, run_ai_provider_stage
from intelligence_mart.ai_targets import TargetSnapshot, load_or_create_target_snapshot, target_snapshot


ROLE_OUTPUT = {
    "schema_version": "1.0.0",
    "stance": "insufficient_data",
    "thesis": None,
    "missing_information": ["missing_fact"],
    "confidence": 0.1,
    "evidence_ids": [],
    "role": "fundamental",
    "key_findings": [],
    "positive_evidence": [],
    "negative_evidence": [],
    "contradictions": [],
    "change_drivers": [],
    "risks": [],
    "what_would_change_my_view": [],
}


class MemoryStore:
    def __init__(self): self.objects: dict[str, bytes] = {}
    def read(self, name: str) -> bytes:
        if name not in self.objects: raise FileNotFoundError(name)
        return self.objects[name]
    def create(self, name: str, payload: bytes, content_type: str) -> bool:
        assert content_type == "application/json"
        if name in self.objects: return False
        self.objects[name] = payload; return True


class Cursor:
    def __init__(self, rows): self.rows, self.executed = rows, []
    def execute(self, sql, params): self.executed.append((sql, params))
    def fetchall(self): return self.rows
    def __enter__(self): return self
    def __exit__(self, *args): return False


class Connection:
    def __init__(self, rows): self.cursor_value, self.transactions = Cursor(rows), 0
    class Tx:
        def __init__(self, outer): self.outer = outer
        def __enter__(self): self.outer.transactions += 1; return self
        def __exit__(self, *args): return False
    def transaction(self): return self.Tx(self)
    def cursor(self): return self.cursor_value


def _fake_codex(tmp_path: Path, *, mode: str = "success") -> tuple[str, Path]:
    env_capture, state, script = tmp_path / "env-capture.json", tmp_path / "state", tmp_path / "codex"
    script.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, os, pathlib, subprocess, sys, time
        capture = pathlib.Path({str(env_capture)!r}); state = pathlib.Path({str(state)!r}); args = sys.argv[1:]
        capture.write_text(json.dumps(sorted(os.environ)))
        if args == ['--version']:
            print('codex-cli 0.159.2'); raise SystemExit(0)
        if args[:2] == ['exec', '--help'] or args == ['exec', '--help']:
            print('--json --output-schema --skip-git-repo-check --ephemeral'); raise SystemExit(0)
        if args and args[0] == 'exec':
            if {mode!r} == 'timeout': subprocess.Popen(['sleep', '30']); time.sleep(30); raise SystemExit(0)
            if {mode!r} == 'retry' and not state.exists():
                state.write_text('1'); print('service unavailable 503', file=sys.stderr); raise SystemExit(1)
            out = pathlib.Path(args[args.index('-o') + 1]); out.write_text(json.dumps({ROLE_OUTPUT!r}))
            print(json.dumps({{'type':'turn.completed','usage':{{'input_tokens':12,'output_tokens':8}}}})); raise SystemExit(0)
        raise SystemExit(2)
    """), encoding="utf-8")
    script.chmod(0o755); return str(script), env_capture


def test_target_union_is_deduplicated_bounded_and_private_safe():
    snapshot = target_snapshot("exec-1", "2026-10-01", [
        {"symbol": "2330", "watchlisted": True, "held": False}, {"symbol": "1101", "watchlisted": False, "held": True},
        {"symbol": "2603", "watchlisted": True, "held": False}, {"symbol": "2603", "watchlisted": False, "held": True},
    ], max_symbols=2)
    parsed = TargetSnapshot.model_validate(snapshot)
    assert parsed.symbols == ["1101", "2330", "2603"]
    assert parsed.admitted_symbols == ["1101", "2330"] and parsed.deferred_symbols == ["2603"]
    persisted = parsed.model_dump(); assert parsed.private_fields_exposed is False
    assert "watchlisted" not in json.dumps(persisted) and "held" not in json.dumps(persisted) and "user" not in json.dumps(persisted)


def test_target_snapshot_replays_saved_membership_without_private_reread():
    store = MemoryStore(); connection = Connection([("2330", True, False), ("2603", False, True)])
    first, first_ref = load_or_create_target_snapshot(connection, "exec-1", "2026-10-01", store, "mart-bucket")
    assert connection.transactions == 1 and "control.mart_ai_target_symbols" in connection.cursor_value.executed[0][0]
    connection.cursor_value.rows = [("9999", True, True)]
    second, second_ref = load_or_create_target_snapshot(connection, "exec-1", "2026-10-01", store, "mart-bucket")
    assert connection.transactions == 1 and second == first and second_ref == first_ref


def test_codex_provider_scrubs_runtime_secrets_and_accepts_structured_output(tmp_path, monkeypatch):
    binary, capture = _fake_codex(tmp_path)
    monkeypatch.setenv("CODEX_ACCESS_TOKEN", "codex-secret"); monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("JANUS_MART_POSTGRES_BUNDLE", '{"password":"must-not-leak"}'); monkeypatch.setenv("PUBLICATION_DB_PASSWORD", "must-not-leak")
    provider = CodexCLIProvider(binary=binary, max_attempts=1, timeout_seconds=10)
    assert provider.preflight()["status"] == "ready"
    names = json.loads(capture.read_text()); assert "OPENAI_API_KEY" not in names and "JANUS_MART_POSTGRES_BUNDLE" not in names and "PUBLICATION_DB_PASSWORD" not in names
    result = provider.invoke("fundamental", {"public": "fact-pack-only"})
    assert result.status == "succeeded" and result.output == ROLE_OUTPUT and result.attempts[0]["usage"] == {"input_tokens": 12, "output_tokens": 8}
    names = json.loads(capture.read_text()); assert "CODEX_ACCESS_TOKEN" in names and "OPENAI_API_KEY" not in names


def test_codex_provider_retry_is_bounded_and_audited(tmp_path, monkeypatch):
    binary, _ = _fake_codex(tmp_path, mode="retry"); monkeypatch.setenv("CODEX_ACCESS_TOKEN", "codex-secret")
    result = CodexCLIProvider(binary=binary, max_attempts=2, timeout_seconds=10).invoke("fundamental", {})
    assert result.status == "succeeded" and len(result.attempts) == 2 and result.attempts[0]["reason"] == "provider_unavailable"
    assert all(item["actual_cost_usd"] is None and item["cost_observability"] == "unknown" for item in result.attempts)


def test_codex_provider_timeout_cancels_process_group(tmp_path, monkeypatch):
    binary, _ = _fake_codex(tmp_path, mode="timeout"); monkeypatch.setenv("CODEX_ACCESS_TOKEN", "codex-secret")
    provider = CodexCLIProvider(binary=binary, max_attempts=1, timeout_seconds=10, kill_grace_seconds=1); provider.timeout_seconds = 0.2
    started = time.monotonic(); result = provider.invoke("fundamental", {})
    assert time.monotonic() - started < 3 and result.status == "failed" and result.reason == "timeout"


def test_unapproved_fallback_fails_closed(monkeypatch):
    monkeypatch.setenv("MART_AI_ENABLED", "true"); monkeypatch.setenv("MART_AI_FALLBACK_PROVIDER", "gemini")
    execution = type("Execution", (), {"execution_id": "x", "core_snapshot_id": "y", "request_options": {"analysis_as_of": "2026-10-01"}})()
    with pytest.raises(ValueError, match="separately approved provider profile"): run_ai_provider_stage(execution, object())


def test_migration_has_replay_floor_pit_fence_and_private_projection_only():
    sql = (Path(__file__).parents[1] / "infra/postgres/migrations/036_mart_ai_targets.sql").read_text()
    for needle in ("replay_supported_from", "control.mart_ai_target_history", "pg_advisory_xact_lock", "AFTER DELETE ON private.watchlist",
                   "AFTER INSERT ON private.ledger_events", "AFTER DELETE ON private.ledger_events", "p_as_of < replay_floor",
                   "timezone('Asia/Taipei',now())::date", "AT TIME ZONE 'Asia/Taipei'",
                   "RETURNS TABLE(symbol varchar(16),watchlisted boolean,held boolean)",
                   "GRANT EXECUTE ON FUNCTION control.mart_ai_target_symbols(date) TO janus_mart_publication",
                   "GRANT SELECT ON control.mart_ai_target_history_meta,control.mart_ai_target_history", "036_mart_ai_targets"):
        assert needle in sql
    assert "SECURITY DEFINER" not in sql and "GRANT SELECT ON private.watchlist TO janus_mart_publication" not in sql
    assert "GRANT SELECT ON private.ledger_events TO janus_mart_publication" not in sql


def test_runtime_build_and_migration_wiring_are_pinned_and_bounded():
    root = Path(__file__).parents[1]; dockerfile = (root / "jobs/intelligence-mart/Dockerfile").read_text()
    assert "@openai/codex@0.159.2" in dockerfile and "codex --version" in dockerfile and "OPENAI_API_KEY" not in dockerfile
    cloudbuild = (root / "scripts/gcp/cloudbuild-postgres-migration.yaml").read_text()
    assert "/opt/janus/migrations/036_mart_ai_targets.sql" in cloudbuild and "control.mart_ai_target_symbols(date)" in cloudbuild
    assert 'test "${privilege_check}" = "t|t|t|t|t|f|f"' in cloudbuild


def test_provider_entrypoint_is_additive_and_keeps_publication_authority_false():
    text = (Path(__file__).parents[1] / "jobs/intelligence-mart/intelligence_mart/ai_providers.py").read_text()
    assert "result = dict(mart_processor(execution, publication_connection))" in text
    assert "result.update(run_ai_provider_stage(execution, publication_connection))" in text
    assert '"publication_authority": False' in text and '"paid_api_enabled": False' in text and "OPENAI_API_KEY" in text


def test_worker_auth_and_diagnostics_fail_closed(tmp_path, monkeypatch):
    from intelligence_mart.codex_worker import _usage
    from types import SimpleNamespace
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", '{"OPENAI_API_KEY":"do-not-persist"}')
    provider = CodexCLIProvider(max_attempts=1)
    assert provider.model == "gpt-6.1-sol" and provider.reasoning_effort == "low"
    assert provider.preflight()["reason"] == "unapproved_auth_mode"
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", '{"tokens":{"access_token":"a","refresh_token":"r"}}')
    monkeypatch.setenv("MART_CODEX_WORK_ROOT", str(tmp_path))
    monkeypatch.setattr("intelligence_mart.codex_worker.subprocess.run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout="", stderr="secret-do-not-persist"))
    assert provider.preflight()["cli_version"] == "unknown"
    assert "secret-do-not-persist" not in json.dumps(provider.preflight())
    assert _usage('null\n[]\n{"type":"turn.completed","usage":{"input_tokens":3,"secret":7,"output_tokens":true}}') == {"input_tokens": 3}
    with provider._workspace("fundamental", {}, "auth_cache") as workspace:
        config = (Path(workspace) / "home/.codex/config.toml").read_text()
        assert 'shell_tool = false' in config and 'forced_login_method = "chatgpt"' in config
        assert 'model = "gpt-6.1-sol"' in config and 'model_reasoning_effort = "low"' in config
    monkeypatch.setattr("intelligence_mart.codex_worker.subprocess.Popen", lambda *a, **k:
                        (_ for _ in ()).throw(OSError("secret-do-not-persist")))
    result = provider.invoke("fundamental", {})
    assert result.reason == "codex_cli_unavailable" and len(result.attempts) == 1
    assert "secret-do-not-persist" not in json.dumps(result.attempts)


def test_blocked_provider_persists_five_failures_and_replays_without_calls(monkeypatch):
    from test_intelligence_mart_pipeline import report
    from urllib.error import HTTPError
    source = report()
    execution = type("Execution", (), {"execution_id": source["execution_id"],
        "core_snapshot_id": source["core_snapshot_id"],
        "request_options": {"analysis_as_of": source["analysis_as_of"]}})()
    class GcsMemoryStore(MemoryStore):
        def read(self, name):
            if name not in self.objects:
                raise HTTPError("https://storage.googleapis.com", 404, "missing", {}, None)
            return super().read(name)
    store = GcsMemoryStore()
    monkeypatch.setenv("MART_AI_ENABLED", "true"); monkeypatch.setenv("MART_BUCKET", "mart-bucket")
    monkeypatch.delenv("MART_AI_FALLBACK_PROVIDER", raising=False)
    monkeypatch.delenv("MART_CODEX_AUTH_JSON", raising=False); monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("intelligence_mart.runtime._fenced_core_manifest", lambda *a: {})
    monkeypatch.setattr("intelligence_mart.storage.load_core_datasets", lambda *a, **k: {})
    monkeypatch.setattr("intelligence_mart.analysis.analyze", lambda **k: [source])
    result = run_ai_provider_stage(execution, Connection([("2330", True, False)]),
        store_factory=lambda bucket: store, catalog_factory=object)
    assert result["ai_status"] == "blocked" and result["ai_five_role_success_count"] == 0
    objects = [json.loads(raw) for raw in store.objects.values()]
    assert len([x for x in objects if x.get("artifact_kind") == "mart_ai_interpretation_v1" and x["status"] == "failed"]) == 5
    assert len([x for x in objects if x.get("artifact_kind") == "mart_ai_validation_v1" and x["status"] == "blocked"]) == 5
    assert run_ai_provider_stage(execution, object(), store_factory=lambda bucket: store) == result
    execution.core_snapshot_id = "other-core"
    with pytest.raises(RuntimeError, match="identity mismatch"):
        run_ai_provider_stage(execution, object(), store_factory=lambda bucket: store)
