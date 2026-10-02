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
    for name in ("JANUS_MART_POSTGRES_BUNDLE", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
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


def test_numeric_prompt_tokens_pass_validator_without_relaxing_it():
    from copy import deepcopy
    from intelligence_mart.ai_providers import _role_input
    from intelligence_mart.ai_contract import contract_bundle, interpretation_artifact
    from intelligence_mart.ai_validation import validate_role
    from test_mart_ai_contract import grounded_fixture
    for role in ("positioning", "quant"):
        source, value, context = grounded_fixture(role)
        before = deepcopy(source)
        public_input = _role_input(source, role)
        tokens = public_input["numeric_claim_tokens"]
        assert tokens and all("=None" not in token for token in tokens)
        value["thesis"]["text"] = "; ".join(tokens) + "。"
        artifact = interpretation_artifact(role, value, context)
        assert validate_role(artifact, source)["status"] == "validated"
        value["thesis"]["text"] += " return_20d=null"
        assert "ungrounded_numeric_claim" in validate_role(interpretation_artifact(role, value, context), source)["errors"]
        assert source == before
        prompt = contract_bundle()["prompts"][role]
        assert prompt["version"] == role + "-v2" and "numeric_claim_tokens" in prompt["methodology"]


def test_target_union_and_five_roles_share_execution_and_replay(monkeypatch):
    from intelligence_mart.ai_providers import _lineage
    from intelligence_mart.ai_contract import ROLE_WEIGHTS
    from intelligence_mart.codex_worker import ProviderResult
    from test_mart_ai_contract import grounded_fixture
    source, _, _ = grounded_fixture("quant")
    execution = type("Execution", (), {"execution_id": source["execution_id"],
        "core_snapshot_id": source["core_snapshot_id"],
        "request_options": {"analysis_as_of": source["analysis_as_of"],
                            "scopes": [{"type": "market", "id": "TWSE", "symbols": ["9999"]}]}})()
    calls = []
    class Provider(CodexCLIProvider):
        def preflight(self): return {"status": "ready", "reason": None}
        def invoke(self, role, public_input):
            calls.append((role, public_input))
            _, value, _ = grounded_fixture(role, source)
            return ProviderResult("succeeded", value, (), None)
    provider = Provider(max_attempts=1)
    store = MemoryStore()
    monkeypatch.setenv("MART_AI_ENABLED", "true")
    monkeypatch.setenv("MART_BUCKET", "mart-bucket")
    monkeypatch.setenv("MART_AI_MAX_SYMBOLS_PER_EXECUTION", "1")
    monkeypatch.delenv("MART_AI_FALLBACK_PROVIDER", raising=False)
    monkeypatch.setattr("intelligence_mart.runtime._fenced_core_manifest", lambda *a: {})
    monkeypatch.setattr("intelligence_mart.storage.load_core_datasets", lambda *a, **k: {})
    def analyze_targets(**kwargs):
        assert kwargs["requested_symbols"] == ("2330",)
        assert kwargs["options"]["scopes"] == [{"type": "symbol", "id": "2330", "symbols": ["2330"]}]
        return [source]
    monkeypatch.setattr("intelligence_mart.analysis.analyze", analyze_targets)
    connection = Connection([("2330", True, False), ("2330", False, True), ("2603", False, True)])
    result = run_ai_provider_stage(execution, connection, store_factory=lambda bucket: store,
                                  catalog_factory=object, provider_factory=lambda: provider)
    assert [role for role, _ in calls] == list(ROLE_WEIGHTS)
    for role, public_input in calls:
        assert public_input["execution_id"] == execution.execution_id
        assert public_input["core_snapshot_id"] == execution.core_snapshot_id
        assert public_input["scope"] == source["scope"]
        assert "watchlisted" not in public_input and "held" not in public_input
        assert _lineage(source, role, provider, ProviderResult("succeeded", {}, (), None))["fact_pack_hash"] == public_input["fact_pack"]["fact_pack_hash"]
    target = json.loads(store.read(f"executions/{execution.execution_id}/ai-targets.json"))
    assert target["symbols"] == ["2330", "2603"] and target["deferred_symbols"] == ["2603"]
    artifacts = [json.loads(raw) for raw in store.objects.values()]
    validations = [a for a in artifacts if a.get("artifact_kind") == "mart_ai_validation_v1"]
    assert len(validations) == 5 and all(a["status"] == "validated" for a in validations)
    assert result["ai_status"] == "partial"  # Deferred target and missing data remain honest.
    assert run_ai_provider_stage(execution, object(), store_factory=lambda bucket: store) == result
    assert len(calls) == 5


def test_acceptance_readback_rejects_wrong_bucket_and_tampered_hash():
    sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/gcp"))
    from verify_mart_ai_provider_execution import read_reference
    from intelligence_mart.ai_contract import content_hash
    from intelligence_mart.ai_providers import _save
    store = MemoryStore()
    artifact = {"status": "blocked", "publication_authority": False}
    artifact["artifact_hash"] = content_hash(artifact)
    reference = _save(store, "dev-mart-bucket", "test", artifact)
    assert read_reference(store, "dev-mart-bucket", reference) == artifact
    with pytest.raises(ValueError, match="dev Mart bucket"):
        read_reference(store, "other-bucket", reference)
    with pytest.raises(ValueError, match="object hash mismatch"):
        read_reference(store, "dev-mart-bucket", {**reference, "object_hash": "sha256:" + "0" * 64})
    artifact["status"] = "complete"
    store.objects[reference["artifact_uri"].split("dev-mart-bucket/")[1]] = json.dumps(artifact).encode()
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        read_reference(store, "dev-mart-bucket", {k: v for k, v in reference.items() if k != "object_hash"})


@pytest.mark.parametrize("override", [
    {"ENVIRONMENT": "prod"}, {"MART_CODEX_MAX_ATTEMPTS": "2"},
    {"MART_AI_MAX_SYMBOLS_PER_EXECUTION": "5"}, {"MART_CODEX_MODEL": "other-model"},
    {"MART_CODEX_REASONING_EFFORT": "high"},
    {"MART_OPENROUTER_FREE_ROUTE_CONFIRMED": "true"}, {"MART_GEMINI_FREE_TIER_CONFIRMED": "true"},
])
def test_acceptance_rejects_scope_and_call_budget_before_network(monkeypatch, override):
    sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/gcp"))
    from verify_mart_ai_provider_execution import main
    for key, value in {"ENVIRONMENT": "dev", "MART_BUCKET": "janus-dev-mart",
                       "MART_CODEX_AUTH_SECRET": "janus-mart-codex-auth",
                       "MART_AI_ENABLED": "true", "MART_AI_MAX_SYMBOLS_PER_EXECUTION": "1",
                       "MART_CODEX_MAX_ATTEMPTS": "1", "MART_CODEX_MODEL": "gpt-6.1-sol",
                       "MART_CODEX_REASONING_EFFORT": "low", **override}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["acceptance", "--input-uri", "gs://janus-dev-mart/input.json",
        "--input-hash", "sha256:" + "0" * 64, "--execution-id", "11111111-1111-1111-1111-111111111111"])
    monkeypatch.setattr("verify_mart_ai_provider_execution.GcsObjectStore", lambda *a:
                        (_ for _ in ()).throw(AssertionError("must not reach GCP")))
    with pytest.raises(ValueError):
        main()


def test_secret_auth_rotation_readback_and_fail_closed(monkeypatch):
    from base64 import b64encode
    from intelligence_mart.codex_auth import SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)
    initial = json.dumps({"tokens": {"access_token": "old-a", "refresh_token": "old-r"}})
    rotated = json.dumps({"tokens": {"access_token": "new-a", "refresh_token": "new-r"}})
    auth = SecretAuth()
    calls = []
    def request(suffix, data=None):
        calls.append(suffix)
        if suffix == ":addVersion":
            assert data["payload"]["data"] == b64encode(rotated.encode()).decode()
            return {"name": auth.resource + "/versions/2"}
        raw = initial if suffix == "versions/latest:access" else rotated
        return {"name": auth.resource + ("/versions/1" if raw == initial else "/versions/2"),
                "payload": {"data": b64encode(raw.encode()).decode()}}
    monkeypatch.setattr(auth, "_request", request)
    auth.load()
    assert auth.checkpoint() is None and calls == ["versions/latest:access"]
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", rotated)
    assert auth.checkpoint() is None and auth.rotations_saved == 1
    assert auth.initial_version.endswith("/1") and auth.version.endswith("/2")
    assert rotated not in json.dumps(auth.metadata())
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", '{"OPENAI_API_KEY":"unapproved"}')
    assert auth.checkpoint() == "invalid_refreshed_auth_cache"
    assert calls.count(":addVersion") == 1


def test_secret_auth_accepts_canonical_project_number(monkeypatch):
    from base64 import b64encode
    from intelligence_mart.codex_auth import SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    auth = SecretAuth()
    raw = '{"tokens":{"access_token":"a","refresh_token":"r"}}'
    monkeypatch.setattr(auth, "_request", lambda *a: {
        "name": "projects/123456/secrets/janus-mart-codex-auth/versions/1",
        "payload": {"data": b64encode(raw.encode()).decode()}})
    auth.load()
    assert auth.resource == "projects/123456/secrets/janus-mart-codex-auth"


def test_secret_save_failure_has_no_retry_and_blocks_next_role(monkeypatch):
    from intelligence_mart.codex_auth import SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", '{"tokens":{"access_token":"a","refresh_token":"r"}}')
    auth = SecretAuth()
    attempts = []
    def fail(*args):
        attempts.append(1)
        raise OSError("secret-must-not-leak")
    monkeypatch.setattr(auth, "_request", fail)
    assert auth.checkpoint() == "auth_persistence_failed"
    assert auth.checkpoint() == "auth_persistence_failed" and len(attempts) == 1
    provider = CodexCLIProvider(max_attempts=1)
    provider.auth_error = auth.reason
    result = provider.invoke("fundamental", {})
    assert result.reason == "auth_persistence_failed" and result.attempts == ()
    assert "secret-must-not-leak" not in json.dumps(auth.metadata())


def test_dedicated_auth_never_uses_shared_bundle(monkeypatch):
    from intelligence_mart.ai_providers import _load_codex_auth_from_runtime_bundle
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    monkeypatch.setenv("JANUS_MART_POSTGRES_BUNDLE", '{"codex_auth_json":{"tokens":{"access_token":"old","refresh_token":"old"}}}')
    monkeypatch.delenv("MART_CODEX_AUTH_JSON", raising=False)
    _load_codex_auth_from_runtime_bundle()
    import os
    assert "MART_CODEX_AUTH_JSON" not in os.environ


def test_account_lock_busy_never_reads_auth_and_releases_on_exit(monkeypatch):
    from intelligence_mart.codex_auth import auth_session, SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    for key in ("HOST", "NAME", "USER", "PASSWORD"):
        monkeypatch.setenv("PUBLICATION_DB_" + key, "test")
    statements = []
    class LockCursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql): statements.append(sql)
        def fetchone(self): return (locked,)
    class LockConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def cursor(self): return LockCursor()
    def connect(**kwargs):
        assert kwargs["autocommit"] is True
        return LockConnection()
    monkeypatch.setattr("psycopg.connect", connect)
    loaded = []
    monkeypatch.setattr(SecretAuth, "load", lambda self: loaded.append(1))
    locked = False
    with auth_session() as auth:
        assert auth.reason == "auth_batch_busy" and loaded == []
    assert len(statements) == 1
    locked = True
    with pytest.raises(RuntimeError), auth_session() as auth:
        assert loaded == [1]
        raise RuntimeError("test cancellation")
    assert "pg_advisory_unlock" in statements[-1]


def test_worker_persists_rotation_before_next_role_and_stops_on_save_failure(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from intelligence_mart.codex_auth import SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    monkeypatch.setenv("MART_CODEX_WORK_ROOT", str(tmp_path))
    monkeypatch.delenv("CODEX_ACCESS_TOKEN", raising=False)
    initial = '{"tokens":{"access_token":"old","refresh_token":"old"}}'
    rotated = '{"tokens":{"access_token":"new","refresh_token":"new"}}'
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", initial)
    auth = SecretAuth()
    auth.saved = initial
    saves, launches = [], []
    def fail_save(*args):
        saves.append(1)
        raise OSError("secret-not-logged")
    def launch(command, **kwargs):
        assert command[-1] == "-" and kwargs["stdin"] == subprocess.PIPE
        assert all("PUBLIC_INPUT" not in arg for arg in command)
        launches.append(1)
        Path(command[command.index("-o") + 1]).write_text(json.dumps(ROLE_OUTPUT))
        (Path(kwargs["env"]["CODEX_HOME"]) / "auth.json").write_text(rotated)
        def communicate(**kwargs):
            assert len(kwargs["input"].encode()) > 131072
            return "", ""
        return SimpleNamespace(returncode=0, communicate=communicate)
    monkeypatch.setattr(auth, "_request", fail_save)
    monkeypatch.setattr("intelligence_mart.codex_worker.subprocess.Popen", launch)
    provider = CodexCLIProvider(max_attempts=1)
    provider.auth_checkpoint = auth.checkpoint
    first = provider.invoke("fundamental", {"large_input": "x" * 140000})
    second = provider.invoke("quant", {})
    assert first.output is None and first.reason == second.reason == "auth_persistence_failed"
    assert len(first.attempts) == 1 and second.attempts == ()
    assert launches == [1] and saves == [1]
    assert "secret-not-logged" not in json.dumps(first.attempts)


def test_lost_lock_blocks_even_without_rotation(monkeypatch):
    from intelligence_mart.codex_auth import SecretAuth
    monkeypatch.setenv("GCP_PROJECT_ID", "janus-dev")
    monkeypatch.setenv("MART_CODEX_AUTH_SECRET", "janus-mart-codex-auth")
    monkeypatch.setenv("MART_CODEX_AUTH_JSON", "unchanged")
    auth = SecretAuth()
    auth.saved = "unchanged"
    class LostConnection:
        def cursor(self): raise OSError("lost session")
    auth.connection = LostConnection()
    assert auth.checkpoint() == "auth_lock_lost"
