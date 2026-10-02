"""Additive Mart AI provider orchestration using governed provider routing."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any, Callable
from urllib.error import HTTPError

from .ai_contract import ROLE_WEIGHTS, content_hash, interpretation_artifact, save_interpretation
from .ai_targets import load_or_create_target_snapshot
from .ai_validation import summarize_roles, validate_role
from .compat import artifact_reference, build_compatibility_sidecar
from .codex_worker import CodexCLIProvider, ProviderResult, PROVIDER_STAGE_VERSION, _canonical
from .provider_routing import ProviderRouter, RoutedProviderResult

# The Codex worker explicitly deny-lists OPENAI_API_KEY and Janus database/runtime secrets.


def _save(store: Any, bucket: str, prefix: str, artifact: dict[str, Any]) -> dict[str, str]:
    logical = str(artifact.get("artifact_hash") or content_hash(artifact))
    payload = _canonical(artifact)
    name = f"{prefix}/{logical[7:]}.json"
    if not store.create(name, payload, "application/json") and store.read(name) != payload:
        raise RuntimeError("immutable AI artifact conflict")
    return {"artifact_uri": f"gs://{bucket}/{name}", "artifact_hash": logical,
            "object_hash": f"sha256:{sha256(payload).hexdigest()}"}


def _role_input(report: dict[str, Any], role: str) -> dict[str, Any]:
    pack = next((x for x in report.get("fact_packs", []) if x.get("pack_type") == role), None)
    if pack is None:
        raise ValueError("target report is missing a role Fact Pack")
    allowed = set(pack.get("evidence_ids", []))
    return {"schema_version": "mart_ai_role_input_v1", "role": role, "execution_id": report["execution_id"],
            "analysis_as_of": report["analysis_as_of"], "core_snapshot_id": report["core_snapshot_id"],
            "scope": report["scope"], "fact_pack": pack,
            "numeric_claim_tokens": [f"{key}={value}" for key, value in pack["facts"].items()
                                     if isinstance(value, (int, float)) and not isinstance(value, bool)],
            "evidence": [x for x in report.get("evidence", []) if x.get("evidence_id") in allowed]}


def _lineage(report: dict[str, Any], role: str, provider: Any, result: ProviderResult | RoutedProviderResult) -> dict[str, Any]:
    pack = next(x for x in report["fact_packs"] if x["pack_type"] == role)
    if isinstance(result, RoutedProviderResult):
        provider_name = result.provider
        model = result.model
        parameters = {"transport": result.transport, **result.parameters,
                      "routing_version": result.routing["version"],
                      "routing_hash": result.routing["routing_hash"],
                      "provider_route": result.routing["providers"]}
    else:
        provider_name = "openai"
        model = provider.model
        parameters = {"transport": "codex_cli", "cli_version": provider.cli_version,
                      "reasoning_effort": provider.reasoning_effort, "timeout_seconds": provider.timeout_seconds,
                      "max_attempts": provider.max_attempts, "web_search": "disabled", "sandbox_mode": "read-only"}
    return {"execution_id": report["execution_id"], "analysis_as_of": report["analysis_as_of"],
            "core_snapshot_id": report["core_snapshot_id"], "scope_type": report["scope"]["type"],
            "scope_id": report["scope"]["id"], "fact_pack_hash": pack["fact_pack_hash"],
            "evidence_hash": pack["evidence_hash"], "feature_version": str(report["feature_version"]),
            "governance_snapshot_version": str(report["governance_snapshot_version"]), "provider": provider_name,
            "model": model, "parameters": parameters,
            "profile_reference": os.environ.get("MART_AI_PROFILE_REFERENCE", "mart-ai-provider-default-v1")}


def run_ai_provider_stage(execution: Any, publication_connection: Any, *, store_factory: Callable[[str], Any] | None = None,
                          catalog_factory: Callable[[], Any] | None = None,
                          provider_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    from .codex_auth import auth_session
    kwargs = dict(store_factory=store_factory, catalog_factory=catalog_factory, provider_factory=provider_factory)
    enabled = os.environ.get("MART_AI_ENABLED", "false").lower() in {"1", "true", "yes"}
    if not enabled or provider_factory is not None or not os.environ.get("MART_CODEX_AUTH_SECRET"):
        return _run_ai_provider_stage(execution, publication_connection, **kwargs)
    with auth_session() as auth:
        codex = CodexCLIProvider.from_environment()
        codex.auth_error, codex.auth_checkpoint = auth.reason, auth.checkpoint
        codex.auth_metadata = auth.metadata
        router = ProviderRouter.from_environment(execution.request_options, codex_provider=codex)
        kwargs["provider_factory"] = lambda: router
        return _run_ai_provider_stage(execution, publication_connection, **kwargs)


def _run_ai_provider_stage(execution: Any, publication_connection: Any, *, store_factory=None,
                           catalog_factory=None, provider_factory=None) -> dict[str, Any]:
    if os.environ.get("MART_AI_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return {"ai_status": "disabled", "ai_target_count": 0, "ai_admitted_count": 0,
                "ai_five_role_success_count": 0, "ai_artifact_uri": None}
    if store_factory is None:
        from ingestion_core.stage import GcsObjectStore
        store_factory = GcsObjectStore
    from .analysis import analyze, prompt_bundle
    from .runtime import _fenced_core_manifest, _validate_fact_packs
    from .storage import load_core_datasets, sql_catalog_from_environment
    bucket = os.environ.get("MART_BUCKET", "").strip()
    if not bucket or "/" in bucket:
        raise ValueError("MART_BUCKET is required")
    store = store_factory(bucket)
    manifest_name = f"executions/{execution.execution_id}/ai-provider-manifest.json"
    try:
        existing = json.loads(store.read(manifest_name))
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
        existing = None
    if existing is not None:
        if (existing.get("execution_id") != execution.execution_id or
                existing.get("analysis_as_of") != execution.request_options["analysis_as_of"] or
                existing.get("core_snapshot_id") != execution.core_snapshot_id):
            raise RuntimeError("immutable AI provider manifest identity mismatch")
        if existing.get("artifact_hash") != content_hash({k: v for k, v in existing.items() if k != "artifact_hash"}):
            raise RuntimeError("immutable AI provider manifest hash mismatch")
        return {"ai_status": existing["status"], "ai_target_count": existing["target_count"],
                "ai_admitted_count": existing["admitted_count"],
                "ai_five_role_success_count": existing["five_role_success_count"],
                "ai_artifact_uri": f"gs://{bucket}/{manifest_name}"}

    target, target_ref = load_or_create_target_snapshot(
        publication_connection, execution.execution_id, str(execution.request_options["analysis_as_of"]), store, bucket)
    admitted = list(target["admitted_symbols"])
    if provider_factory is None:
        _load_codex_auth_from_runtime_bundle()
        provider = ProviderRouter.from_environment(execution.request_options)
    else:
        provider = provider_factory()
    preflight = provider.preflight() if admitted else {
        "status": "not_required", "reason": "no_targets", "provider": "janus", "transport": "provider_router",
        "model": "routed", "paid_api_enabled": False, "publication_authority": False,
    }
    preflight.update(artifact_kind="mart_ai_provider_preflight_v1", schema_version=PROVIDER_STAGE_VERSION,
                     execution_id=execution.execution_id)
    preflight["artifact_hash"] = content_hash(preflight)
    preflight_ref = _save(store, bucket, "provider-preflight", preflight)
    results: list[dict[str, Any]] = []

    if admitted:
        manifest = _fenced_core_manifest(execution, store_factory)
        catalog = (catalog_factory or sql_catalog_from_environment)()
        try:
            datasets = load_core_datasets(
                catalog, manifest, tuple(admitted), row_limit=int(os.environ.get("CORE_SNAPSHOT_ROW_LIMIT", "250000")))
            prompts, prompt_hash = prompt_bundle()
            reports = analyze(
                execution_id=execution.execution_id,
                analysis_as_of=str(execution.request_options["analysis_as_of"]),
                core_snapshot_id=execution.core_snapshot_id,
                requested_symbols=tuple(admitted),
                options={**execution.request_options,
                         "scopes": [{"type": "symbol", "id": symbol, "symbols": [symbol]} for symbol in admitted]},
                datasets=datasets, prompts=prompts, prompt_hash=prompt_hash)
            _validate_fact_packs(reports)
        finally:
            engine = getattr(catalog, "engine", None)
            if engine is not None:
                engine.dispose()
        by_symbol = {r["scope"]["id"]: r for r in reports if r["scope"]["type"] == "symbol"}
        for symbol in admitted:
            report = by_symbol.get(symbol)
            if report is None:
                results.append({"symbol": symbol, "status": "blocked", "reason": "missing_fact_pack",
                                "five_role_success": False, "publication_authority": False})
                continue
            validations, refs, attempts, failures = [], [], [], {}
            for role in ROLE_WEIGHTS:
                provider_result = provider.invoke(role, _role_input(report, role)) if preflight["status"] == "ready" else \
                    ProviderResult("failed", None, (), preflight.get("reason") or "provider_blocked")
                for attempt in provider_result.attempts:
                    attempts.append({"role": role, **_save(store, bucket, "provider-attempts", attempt)})
                interpretation = interpretation_artifact(role, provider_result.output,
                                                         _lineage(report, role, provider, provider_result))
                if provider_result.output is None:
                    failures[role] = provider_result.reason or "provider_failed"
                    interpretation["error"] = {"kind": "provider_failed", "reason": failures[role]}
                    interpretation["artifact_hash"] = content_hash(
                        {k: v for k, v in interpretation.items() if k != "artifact_hash"})
                interpretation_ref = save_interpretation(store, bucket, interpretation)
                refs.append(artifact_reference(interpretation, interpretation_ref))
                validation = validate_role(interpretation, report)
                validation_ref = _save(store, bucket, "validations", validation)
                validations.append(validation)
                refs.append(artifact_reference(validation, validation_ref))
                if validation.get("status") != "validated":
                    failures.setdefault(role, "validation_blocked")
            summary = summarize_roles(validations)
            sidecar_ref = None
            if refs:
                sidecar_ref = _save(store, bucket, "compat-sidecars", build_compatibility_sidecar(report, refs))
            results.append({"symbol": symbol, "status": "complete" if summary["five_role_success"] else "partial",
                            "five_role_success": summary["five_role_success"],
                            "validation_outcome": summary["validation_outcome"],
                            "analysis_outcome": summary["analysis_outcome"], "attempts": attempts,
                            "role_failures": failures, "sidecar": sidecar_ref, "publication_authority": False})

    successes = sum(bool(x.get("five_role_success")) for x in results)
    status = "idle" if not admitted else "blocked" if preflight["status"] != "ready" else \
        "complete" if successes == len(admitted) and not target["deferred_symbols"] else "partial"
    routed = isinstance(provider, ProviderRouter)
    routing = provider.routing if routed else None
    stage = {
        "artifact_kind": "mart_ai_provider_execution_v1", "schema_version": PROVIDER_STAGE_VERSION,
        "execution_id": execution.execution_id, "analysis_as_of": execution.request_options["analysis_as_of"],
        "core_snapshot_id": execution.core_snapshot_id, "status": status, "target_count": len(target["symbols"]),
        "admitted_count": len(admitted), "deferred_symbols": target["deferred_symbols"], "target_snapshot": target_ref,
        "target_membership_hash": target["membership_hash"], "preflight": preflight_ref,
        "preflight_status": preflight["status"], "preflight_reason": preflight.get("reason"),
        "provider": "janus" if routed else "openai", "transport": "provider_router" if routed else "codex_cli",
        "model": "routed" if routed else provider.model, "cli_version": getattr(provider, "cli_version", None),
        "provider_route": routing, "fallback_provider": routing["providers"][1] if routing else None,
        "fallback_reason": "governed_route" if routing else "not_configured",
        "five_role_success_count": successes, "results": results, "private_fields_exposed": False,
        "publication_authority": False,
    }
    auth_provider = provider.providers.get("codex_cli") if routed else provider
    if hasattr(auth_provider, "auth_metadata"):
        stage["auth_lifecycle"] = auth_provider.auth_metadata()
        if auth_provider.auth_error:
            stage["auth_lifecycle"].update(status="blocked", reason=auth_provider.auth_error,
                                           required_user_action=True)
    stage["artifact_hash"] = content_hash(stage)
    payload = _canonical(stage)
    if not store.create(manifest_name, payload, "application/json") and store.read(manifest_name) != payload:
        raise RuntimeError("immutable AI provider manifest conflict")
    return {"ai_status": status, "ai_target_count": len(target["symbols"]), "ai_admitted_count": len(admitted),
            "ai_five_role_success_count": successes, "ai_artifact_uri": f"gs://{bucket}/{manifest_name}"}


def _load_codex_auth_from_runtime_bundle() -> None:
    if os.environ.get("MART_CODEX_AUTH_SECRET"):
        return  # Dedicated storage never falls back to the shared bundle.
    raw = os.environ.get("JANUS_MART_POSTGRES_BUNDLE", "").strip()
    if not raw:
        return
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(bundle, dict):
        return
    if not os.environ.get("CODEX_ACCESS_TOKEN") and str(bundle.get("codex_access_token", "")).strip():
        os.environ["CODEX_ACCESS_TOKEN"] = str(bundle["codex_access_token"]).strip()
    if not os.environ.get("MART_CODEX_AUTH_JSON") and isinstance(bundle.get("codex_auth_json"), (dict, str)):
        value = bundle["codex_auth_json"]
        os.environ["MART_CODEX_AUTH_JSON"] = json.dumps(value, separators=(",", ":")) if isinstance(value, dict) else str(value)


def provider_smoke() -> dict[str, Any]:
    if os.environ.get("MART_CODEX_AUTH_SECRET"):
        from packages.postgres_bundle import load_postgres_bundle
        from .codex_auth import auth_session
        load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
            "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
        with auth_session() as auth:
            provider = CodexCLIProvider.from_environment()
            provider.auth_error = auth.reason
            return {"component": "intelligence-mart", "operation": "provider-smoke",
                    **provider.preflight(), "auth_lifecycle": auth.metadata()}
    _load_codex_auth_from_runtime_bundle()
    return {"component": "intelligence-mart", "operation": "provider-smoke",
            **CodexCLIProvider.from_environment().preflight()}


def provider_mart_processor(execution: Any, publication_connection: Any) -> dict[str, Any]:
    from .runtime import mart_processor
    result = dict(mart_processor(execution, publication_connection))
    result.update(run_ai_provider_stage(execution, publication_connection))
    return result


def run_provider_queued_analysis() -> dict[str, Any]:
    from packages.postgres_bundle import load_postgres_bundle
    from .runtime import PostgreSQLAnalysisQueue
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
    _load_codex_auth_from_runtime_bundle()
    settings = {name.lower(): os.environ.get(f"PUBLICATION_DB_{name}", "").strip()
                for name in ("HOST", "NAME", "USER", "PASSWORD")}
    missing = [f"PUBLICATION_DB_{name.upper()}" for name, value in settings.items() if not value]
    if missing:
        raise ValueError(f"missing database settings: {','.join(missing)}")
    import psycopg
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"],
                         password=settings["password"],
                         sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
                         options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000") as connection:
        queue = PostgreSQLAnalysisQueue(connection)
        worker_id = os.environ.get("QUEUE_WORKER_ID", "intelligence-mart").strip()
        execution = queue.claim(worker_id)
        if execution is None:
            return {"component": "intelligence-mart", "status": "idle", "claimed": False}
        try:
            execution.validate_input()
            result = provider_mart_processor(execution, connection)
            if not str(result.get("artifact_uri", "")).startswith("gs://") or result.get("core_snapshot_id") != execution.core_snapshot_id:
                raise ValueError("analysis processor must persist an artifact for the claimed Core snapshot")
            queue.transition(execution.execution_id, worker_id, "succeeded", retry_count=execution.retry_count)
            return {"component": "intelligence-mart", "status": "succeeded", "claimed": True,
                    "execution_id": execution.execution_id, "artifact_uri": result["artifact_uri"],
                    "reports": int(result.get("reports", 0)), "publishable": int(result.get("publishable", 0)),
                    "ai_status": result.get("ai_status", "disabled"),
                    "ai_target_count": int(result.get("ai_target_count", 0)),
                    "ai_admitted_count": int(result.get("ai_admitted_count", 0)),
                    "ai_five_role_success_count": int(result.get("ai_five_role_success_count", 0)),
                    "ai_artifact_uri": result.get("ai_artifact_uri")}
        except Exception as error:
            retry_count = execution.retry_count + 1
            max_retries = int(os.environ.get("QUEUE_MAX_RETRIES", "1"))
            queue.transition(execution.execution_id, worker_id,
                             "retrying" if retry_count <= max_retries else "failed",
                             retry_count=retry_count, error_code=type(error).__name__.upper()[:64])
            raise
