"""Immutable specialist execution on the existing Core/GCS/control boundary."""
from __future__ import annotations

import json
import os
from uuid import uuid4
from urllib.error import HTTPError

from .coverage import load_or_create_target_snapshot
from .runtime import _fenced_core_manifest, _write_immutable_json, deterministic_processor
from .specialists import DEPENDENCIES, VERSION, analyze_specialists, digest, screening, screening_quality
from .storage import load_core_datasets, sql_catalog_from_environment


def load_market_membership(connection, as_of):
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SELECT symbol,membership_version FROM control.specialist_market_symbols(%s::date)", (as_of,))
        members = cursor.fetchall()
    if not members or len(members) > 500 or len({r[0] for r in members}) != len(members):
        raise ValueError("missing or invalid PIT market membership")
    return {"symbols": sorted(str(r[0]) for r in members), "membership_version": str(members[0][1]),
            "analysis_as_of": as_of}


def specialist_processor(execution, publication_connection, *, store_factory=None, catalog_factory=None):
    if publication_connection is None:  # Local injected stores have no PostgreSQL session.
        return _specialist_processor(execution, publication_connection, store_factory=store_factory, catalog_factory=catalog_factory)
    with publication_connection.transaction():
        locked = publication_connection.execute("SELECT pg_try_advisory_lock(1835102836,2)").fetchone()[0]
    if not locked:
        raise RuntimeError("public data mutation lock is busy")
    try:
        return _specialist_processor(execution, publication_connection, store_factory=store_factory, catalog_factory=catalog_factory)
    finally:
        with publication_connection.transaction():
            publication_connection.execute("SELECT pg_advisory_unlock(1835102836,2)")


def _specialist_processor(execution, publication_connection, *, store_factory=None, catalog_factory=None):
    if store_factory is None:
        from ingestion_core.stage import GcsObjectStore
        store_factory = GcsObjectStore
    bucket = os.environ.get("MART_BUCKET", "").strip()
    if not bucket or "/" in bucket:
        raise ValueError("MART_BUCKET is required")
    store = store_factory(bucket)
    core = _fenced_core_manifest(execution, store_factory)
    deterministic_processor(execution, store_factory)
    as_of = str(execution.request_options["analysis_as_of"])
    manifest_name = f"executions/{execution.execution_id}/specialist-manifest.json"
    try:
        store.read(f"executions/{execution.execution_id}/specialist-retired.json")
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
    else:
        raise RuntimeError("specialist execution retired by retention; submit a new execution")
    try:
        saved = json.loads(store.read(manifest_name))
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
        saved = None
    if saved is not None:
        if saved["core_snapshot_id"] != execution.core_snapshot_id or saved["analysis_as_of"] != as_of \
                or saved["execution_id"] != execution.execution_id \
                or saved["output_hash"] != digest({k: v for k, v in saved.items() if k != "output_hash"}):
            raise RuntimeError("immutable specialist manifest fence mismatch")
        for ref in [saved["screening"], saved["target_snapshot"], saved["market_membership"], *saved["specialists"],
                    *([saved["evaluation"]] if "evaluation" in saved else [])]:
            name = ref["artifact_uri"].split(f"gs://{bucket}/", 1)[1]
            from hashlib import sha256
            if "sha256:" + sha256(store.read(name)).hexdigest() != ref["artifact_hash"]:
                raise RuntimeError("specialist artifact readback hash mismatch")
        return {"artifact_uri": f"gs://{bucket}/{manifest_name}", "core_snapshot_id": execution.core_snapshot_id,
                "reports": saved["specialist_count"] // 5, "publishable": 0,
                "specialist_status": saved["specialist_status"], "screening_count": saved["screening_count"],
                "screening_quality": saved.get("screening_quality"),
                "specialist_count": saved["specialist_count"]}
    target, target_ref = load_or_create_target_snapshot(publication_connection, execution.execution_id,
                                                       as_of, store, bucket)
    membership = load_market_membership(publication_connection, as_of)
    market_symbols = set(membership["symbols"])
    market_ref = _write_immutable_json(store, bucket, f"executions/{execution.execution_id}/market-membership.json", membership)
    symbols = tuple(sorted(market_symbols | set(target["symbols"])))
    catalog = (catalog_factory or sql_catalog_from_environment)()
    try:
        required = {name for names in DEPENDENCIES.values() for name in names}
        inputs = dict(core, iceberg_tables={name: fence for name, fence in core.get("iceberg_tables", {}).items()
                                           if name.split(".", 1)[1][:-3].replace("_", "-") in required})
        if "datasets" in core:
            inputs["datasets"] = {name: rows for name, rows in core["datasets"].items() if name in required}
        datasets = load_core_datasets(catalog, inputs, symbols,
                                     row_limit=int(os.environ.get("CORE_SNAPSHOT_ROW_LIMIT", "250000")))
    finally:
        engine = getattr(catalog, "engine", None)
        if engine is not None:
            engine.dispose()
    screen = screening(datasets, market_symbols, as_of, execution.core_snapshot_id)
    screen_ref = _write_immutable_json(store, bucket, f"executions/{execution.execution_id}/screening.json", screen)
    references = []
    for symbol in target["symbols"]:
        for artifact in analyze_specialists(datasets, symbol, as_of, execution.core_snapshot_id):
            name = f"specialists/{artifact['output_hash'][7:]}.json"
            try:
                existing = json.loads(store.read(name))
            except (FileNotFoundError, HTTPError) as error:
                if isinstance(error, HTTPError) and error.code != 404:
                    raise
                existing = None
            if existing is not None and existing != artifact:
                raise RuntimeError("immutable specialist identity conflict")
            reference = _write_immutable_json(store, bucket, name, artifact)
            if json.loads(store.read(name)) != artifact:
                raise RuntimeError("specialist readback mismatch")
            references.append({"symbol": symbol, "role": artifact["role"], "status": artifact["status"],
                               "reused": existing is not None, **reference})
    manifest = {"artifact_kind": "mart_specialist_execution_v1", "schema_version": "1.0.0",
                "execution_id": execution.execution_id, "analysis_as_of": as_of,
                "core_snapshot_id": execution.core_snapshot_id, "engine_version": VERSION,
                "target_snapshot": target_ref, "market_membership": market_ref, "screening": screen_ref,
                "screening_count": len(screen), "specialist_count": len(references),
                "screening_quality": screening_quality(screen),
                "specialist_status": "partial" if any(r["status"] != "ready" for r in references) else "ready",
                "specialists": references, "llm_api_tokens": 0, "ceo_triggered": False,
                "publication_authority": False}
    if os.environ.get("MART_OOS_EVALUATION", "false").lower() == "true":
        from .evaluation import evaluate_core_history
        evaluations = evaluate_core_history(datasets, target["symbols"], as_of, execution.core_snapshot_id)
        manifest["evaluation"] = _write_immutable_json(store, bucket, f"executions/{execution.execution_id}/oos-evaluation.json", evaluations)
    manifest["output_hash"] = digest(manifest)
    ref = _write_immutable_json(store, bucket, manifest_name, manifest)
    return {**ref, "core_snapshot_id": execution.core_snapshot_id, "reports": len(target["symbols"]),
            "publishable": 0, "specialist_status": manifest["specialist_status"],
            "screening_quality": manifest["screening_quality"],
            "screening_count": len(screen), "specialist_count": len(references)}


def run_acceptance():
    """Real dev input only; uses existing approved identities and never invokes a provider."""
    from urllib.parse import urlparse
    from ingestion_core.stage import GcsObjectStore
    uri = urlparse(os.environ["MART_ACCEPTANCE_INPUT_URI"])
    if uri.scheme != "gs" or uri.netloc != os.environ["MART_BUCKET"] or not uri.path.startswith("/acceptance/specialists/"):
        raise ValueError("acceptance input must stay inside existing Mart dev acceptance prefix")
    event = json.loads(GcsObjectStore(uri.netloc).read(uri.path.lstrip("/")))
    return _run_event(event, "specialist-acceptance")


def latest_training_input(store, today):
    """Select the latest immutable dev snapshot, preserving its actual data date."""
    from datetime import date
    from hashlib import sha256
    manifests = [item for item in store.objects("executions/") if item["name"].endswith("/core-snapshot.json")]
    if not manifests:
        raise ValueError("no Core snapshot for retraining")
    item = max(manifests, key=lambda item: (item["updated"], item["name"]))
    raw = store.read(item["name"])
    core = json.loads(raw)
    age = (today - date.fromisoformat(core["analysis_as_of"])).days
    if not 0 <= age <= 7 or not core.get("iceberg_tables") or item["name"] != f"executions/{core['execution_id']}/core-snapshot.json":
        raise ValueError("invalid or stale retraining Core snapshot")
    return {"executionId": core["execution_id"], "analysisAsOf": core["analysis_as_of"],
            "coreSnapshotId": core["snapshot_id"], "coreSnapshotUri": f"gs://{store.bucket}/{item['name']}",
            "coreSnapshotHash": "sha256:" + sha256(raw).hexdigest(), "martSchemaVersion": "1",
            "featureVersion": "2", "modelVersion": "deterministic-v1", "governanceSnapshotVersion": "gov-1", "scopes": []}


def run_retraining():
    """Monthly challenger fit/OOS on current data; never promotes a model."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ingestion_core.stage import GcsObjectStore
    if os.environ.get("GCP_PROJECT_ID") != "gen-lang-client-0593591102" or os.environ.get("MART_BUCKET") != "gen-lang-client-0593591102-dev-mart":
        raise ValueError("retraining is restricted to existing dev resources")
    if os.environ.get("MART_OOS_EVALUATION", "false").lower() != "true":
        raise ValueError("retraining requires OOS evaluation")
    store = GcsObjectStore("gen-lang-client-0593591102-dev-core")
    event = latest_training_input(store, datetime.now(ZoneInfo("Asia/Taipei")).date())
    return _run_event(event, "specialist-retrain")


def _run_event(event, operation):
    import resource
    import time
    started = time.monotonic()
    from packages.postgres_bundle import load_postgres_bundle
    from .runtime import AnalysisExecution, _settings
    import psycopg
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
    options = {"core_execution_id": event["executionId"], "analysis_as_of": event["analysisAsOf"],
               "core_snapshot_id": event["coreSnapshotId"], "core_snapshot_uri": event["coreSnapshotUri"],
               "core_snapshot_hash": event["coreSnapshotHash"], "schema_version": event["martSchemaVersion"],
               "feature_version": event["featureVersion"], "model_version": event["modelVersion"],
               "governance_snapshot_version": event["governanceSnapshotVersion"], "scopes": event["scopes"]}
    execution = AnalysisExecution(str(uuid4()), operation, (), 0, options)
    execution.validate_input()
    settings = _settings("PUBLICATION_DB")
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"], password=settings["password"],
                        sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5) as connection:
        result = specialist_processor(execution, connection)
    return {"component": "intelligence-mart", "operation": operation, "execution_id": execution.execution_id,
            "llm_api_tokens": 0, "elapsed_seconds": round(time.monotonic() - started, 3),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2), **result}
