"""Bounded dev target/Core/provider acceptance; consumes up to five authorized calls."""

import argparse
from hashlib import sha256
import json
import os
from urllib.parse import urlparse
from uuid import UUID

from ingestion_core.stage import GcsObjectStore
from intelligence_mart.ai_contract import content_hash
from intelligence_mart.ai_providers import _load_codex_auth_from_runtime_bundle, run_ai_provider_stage
from intelligence_mart.ai_targets import TargetSnapshot
from intelligence_mart.compat import MartAIAdditiveSidecarV1
from intelligence_mart.runtime import AnalysisExecution, _fenced_core_manifest
from packages.postgres_bundle import load_postgres_bundle


def read_reference(store, bucket, reference):
    uri = urlparse(reference["artifact_uri"])
    if uri.scheme != "gs" or uri.netloc != bucket:
        raise ValueError("acceptance reference must remain in the dev Mart bucket")
    payload = store.read(uri.path.lstrip("/"))
    if "object_hash" in reference and reference["object_hash"] != "sha256:" + sha256(payload).hexdigest():
        raise ValueError("acceptance object hash mismatch")
    artifact = json.loads(payload)
    logical = artifact.get("artifact_hash", "sha256:" + sha256(payload).hexdigest())
    if logical != reference["artifact_hash"]:
        raise ValueError("acceptance reference hash mismatch")
    if "artifact_hash" in artifact and logical != content_hash({k: v for k, v in artifact.items() if k != "artifact_hash"}):
        raise ValueError("acceptance artifact hash mismatch")
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-uri", required=True, help="Existing immutable Mart input.json")
    parser.add_argument("--input-hash", required=True, help="Expected SHA-256 of the immutable input")
    parser.add_argument("--execution-id", required=True, type=UUID, help="New acceptance execution UUID")
    args = parser.parse_args()
    bucket = os.environ["MART_BUCKET"]
    if os.environ.get("ENVIRONMENT") != "dev" or "-dev-" not in bucket:
        raise ValueError("acceptance requires the existing dev Mart bucket")
    if (os.environ.get("MART_AI_ENABLED") != "true" or
            os.environ.get("MART_CODEX_AUTH_SECRET") != "janus-mart-codex-auth" or
            os.environ.get("MART_AI_MAX_SYMBOLS_PER_EXECUTION") != "1" or
            os.environ.get("MART_CODEX_MAX_ATTEMPTS") != "1" or
            os.environ.get("MART_OPENROUTER_FREE_ROUTE_CONFIRMED", "false") != "false" or
            os.environ.get("MART_GEMINI_FREE_TIER_CONFIRMED", "false") != "false" or
            os.environ.get("MART_CODEX_MODEL", "gpt-6.1-sol") != "gpt-6.1-sol" or
            os.environ.get("MART_CODEX_REASONING_EFFORT", "low") != "low"):
        raise ValueError("acceptance requires explicit AI enablement, one symbol and one attempt per role")
    uri = urlparse(args.input_uri)
    if uri.scheme != "gs" or uri.netloc != bucket:
        raise ValueError("input must remain in the existing dev Mart bucket")
    store = GcsObjectStore(bucket)
    payload = store.read(uri.path.lstrip("/"))
    if args.input_hash != "sha256:" + sha256(payload).hexdigest():
        raise ValueError("immutable Mart input hash mismatch")
    source = json.loads(payload)
    if source.get("artifact_kind") != "mart_input_v1":
        raise ValueError("acceptance requires an immutable Mart input")
    if str(args.execution_id) == source.get("analysis_execution_id"):
        raise ValueError("acceptance requires a new execution UUID")
    execution = AnalysisExecution(str(args.execution_id), "provider-acceptance",
                                  tuple(source["requested_symbols"]), 0, source)
    execution.validate_input()
    _fenced_core_manifest(execution, GcsObjectStore)
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
    _load_codex_auth_from_runtime_bundle()
    import psycopg
    settings = {key.lower(): os.environ[f"PUBLICATION_DB_{key}"] for key in ("HOST", "NAME", "USER", "PASSWORD")}
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"],
                         password=settings["password"], connect_timeout=5,
                         sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"),
                         options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000") as connection:
        result = run_ai_provider_stage(execution, connection)
    stage = json.loads(store.read(f"executions/{execution.execution_id}/ai-provider-manifest.json"))
    assert stage["artifact_hash"] == content_hash({k: v for k, v in stage.items() if k != "artifact_hash"})
    target = TargetSnapshot.model_validate(read_reference(store, bucket, stage["target_snapshot"]))
    assert target.execution_id == execution.execution_id and target.analysis_as_of == source["analysis_as_of"]
    assert stage["execution_id"] == execution.execution_id and stage["analysis_as_of"] == source["analysis_as_of"]
    assert stage["core_snapshot_id"] == execution.core_snapshot_id
    calls = 0
    for item in stage["results"]:
        assert item["symbol"] in target.admitted_symbols
        for reference in item["attempts"]:
            attempt = read_reference(store, bucket, reference)
            if attempt["attempt"] > 0:
                assert attempt["transport"] == "codex_cli" and attempt["attempt"] == 1
                calls += 1
        if item.get("sidecar"):
            sidecar = read_reference(store, bucket, item["sidecar"])
            MartAIAdditiveSidecarV1.model_validate(sidecar)
            assert len(sidecar["artifacts"]) == 10
            for reference in sidecar["artifacts"]:
                artifact = read_reference(store, bucket, reference)
                lineage = artifact["lineage"]
                assert lineage["execution_id"] == execution.execution_id
                assert lineage["core_snapshot_id"] == execution.core_snapshot_id
                assert lineage["scope_id"] == item["symbol"]
    assert calls <= 5
    assert store.read(uri.path.lstrip("/")) == payload
    assert run_ai_provider_stage(execution, object()) == result  # Replay cannot spend another call.
    print(json.dumps({"acceptance": stage["status"], **result, "provider_calls": calls,
                      "publication_writes": 0, "auth_lifecycle": stage.get("auth_lifecycle"),
                      "auth_lifecycle_verified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
