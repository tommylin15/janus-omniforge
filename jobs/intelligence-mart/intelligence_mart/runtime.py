"""Bounded PostgreSQL connectivity checks for the Mart Cloud Run Job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from ipaddress import ip_interface
import json
import os
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5


_DATABASES = {
    "catalog": ("CATALOG_DB", "catalog", "catalog.iceberg_tables"),
    "publication": ("PUBLICATION_DB", "publication", None),
}


@dataclass(frozen=True)
class AnalysisExecution:
    execution_id: str
    config_id: str
    requested_symbols: tuple[str, ...]
    retry_count: int
    request_options: dict[str, object]

    def validate_input(self) -> None:
        required = (
            "core_execution_id", "analysis_as_of", "core_snapshot_id", "schema_version",
            "feature_version", "model_version", "governance_snapshot_version",
            "core_snapshot_uri", "core_snapshot_hash",
        )
        missing = [name for name in required if not str(self.request_options.get(name, "")).strip()]
        if missing:
            raise ValueError(f"analysis execution is missing immutable input: {','.join(missing)}")
        date.fromisoformat(str(self.request_options["analysis_as_of"]))

    @property
    def core_snapshot_id(self) -> str:
        return str(self.request_options["core_snapshot_id"]).strip()


class PostgreSQLAnalysisQueue:
    """Lease one persisted analysis execution without broad control-plane access."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def claim(self, worker_id: str, *, lease_seconds: int = 300) -> AnalysisExecution | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_id and a positive lease are required")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM control.claim_mart_analysis(%s,%s)",
                (worker_id.strip(), lease_seconds),
            )
            row = cursor.fetchone()
        return AnalysisExecution(row[0], row[1], tuple(row[2]), row[3], row[4]) if row else None

    def transition(self, execution_id: str, worker_id: str, status: str, *,
                   retry_count: int, error_code: str | None = None) -> None:
        if status not in {"succeeded", "retrying", "failed"}:
            raise ValueError("invalid analysis terminal status")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT control.transition_mart_analysis(%s,%s,%s,%s,%s)",
                (execution_id, worker_id, status, retry_count, error_code),
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError("analysis execution lease is no longer owned by this worker")


class PostgreSQLPublicationIndex:
    """Register metadata only; the database function cannot accept a full report."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def register_baseline(self, execution: AnalysisExecution, prompt_version: str, prompt_hash: str) -> str | None:
        git_sha = os.environ.get("JANUS_GIT_SHA", "").strip().lower()
        image_digest = os.environ.get("JANUS_IMAGE_DIGEST", "").strip().lower()
        if not git_sha and not image_digest:
            return None
        if not (7 <= len(git_sha) <= 64 and all(character in "0123456789abcdef" for character in git_sha)):
            raise ValueError("JANUS_GIT_SHA must be a hexadecimal revision")
        if (len(image_digest) != 71 or not image_digest.startswith("sha256:")
                or any(character not in "0123456789abcdef" for character in image_digest[7:])):
            raise ValueError("JANUS_IMAGE_DIGEST must be an immutable sha256 digest")
        lineage = {
            "git_sha": git_sha,
            "image_digest": image_digest,
            "governance_revision": str(execution.request_options["governance_snapshot_version"]),
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "schema_revision": str(execution.request_options["schema_version"]),
            "feature_revision": str(execution.request_options["feature_version"]),
            "signal_revision": str(execution.request_options.get("signal_revision", "not_applicable")),
            "model_provider": "gemini" if os.environ.get("MART_LLM_ENABLED", "false").lower() in {"1", "true", "yes"} else "deterministic",
            "model_version": str(execution.request_options["model_version"]),
            "source_config_revision": str(execution.request_options.get("source_config_revision", execution.config_id)),
        }
        digest = f"sha256:{sha256(json.dumps(lineage, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
        baseline_id = str(uuid5(NAMESPACE_URL, f"janus-pilot-baseline:{digest}"))
        params = (baseline_id, "material_change", f"material-{digest[7:19]}", digest, *lineage.values())
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("SELECT publication.register_pilot_baseline(" + ",".join(["%s"] * len(params)) + ")", params)
            return str(cursor.fetchone()[0])

    def register(self, report: dict[str, Any], reference: dict[str, Any], artifact_hash: str, *,
                 retention_days: int, pilot_baseline_id: str | None = None) -> None:
        scope, aggregate = report["scope"], report["aggregate"]
        if retention_days not in range(1, 3651):
            raise ValueError("Mart retention_days must be between 1 and 3650")
        params = (
            report["execution_id"], report["analysis_as_of"], scope["type"], scope["id"], report["core_snapshot_id"],
            reference["artifact_uri"], artifact_hash, report["deterministic_hash"], reference["table_identifier"],
            reference["iceberg_snapshot_id"], str(report["schema_version"]), str(report["feature_version"]),
            str(report["model_version"]), str(report["governance_snapshot_version"]), report["prompt_version"],
            report["prompt_hash"], aggregate["completeness"], aggregate["confidence"], report["data_quality"],
            aggregate["analysis_outcome"], aggregate["publication_status"],
            date.fromisoformat(report["analysis_as_of"]) + timedelta(days=retention_days),
        )
        function = "publication.register_mart_report"
        if pilot_baseline_id:
            function = "publication.register_pilot_mart_report"
            params += (pilot_baseline_id, report["membership_snapshot_hash"])
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("SELECT " + function + "(" + ",".join(["%s"] * len(params)) + ")", params)
            if not cursor.fetchone()[0]:
                raise RuntimeError("Mart publication registration failed")

    def pending_outcomes(self, symbols: list[str], *, limit: int = 1500) -> list[dict[str, Any]]:
        if not symbols:
            return []
        from psycopg.rows import dict_row
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """SELECT report.execution_id AS analysis_execution_id,report.scope_type,report.scope_id,
                          report.analysis_as_of,horizon.horizon_days,report.pilot_baseline_id,
                          report.membership_snapshot_hash
                     FROM publication.mart_report_index report
                     CROSS JOIN (VALUES (5),(20),(60)) horizon(horizon_days)
                     LEFT JOIN publication.pilot_analysis_outcomes outcome
                       ON outcome.analysis_execution_id=report.execution_id
                      AND outcome.scope_type=report.scope_type AND outcome.scope_id=report.scope_id
                      AND outcome.horizon_days=horizon.horizon_days
                    WHERE report.scope_type='symbol' AND report.scope_id=ANY(%s)
                      AND report.analysis_outcome='complete'
                      AND report.publication_status IN ('publishable','published')
                      AND report.pilot_baseline_id IS NOT NULL
                      AND report.membership_snapshot_hash IS NOT NULL
                      AND (outcome.status IS NULL OR outcome.status='pending')
                    ORDER BY report.analysis_as_of,report.execution_id,horizon.horizon_days LIMIT %s""",
                (symbols,min(limit,1500)),
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_outcomes(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        sql = """INSERT INTO publication.pilot_analysis_outcomes(
                    analysis_execution_id,scope_type,scope_id,analysis_as_of,horizon_days,
                    pilot_baseline_id,membership_snapshot_hash,status,exclusion_reason,benchmark_id,
                    entry_date,outcome_date,return_ratio,benchmark_return_ratio,relative_return_ratio,
                    mfe_ratio,mae_ratio,price_snapshot_id,benchmark_snapshot_id,provenance_id)
                 VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                 ON CONFLICT(analysis_execution_id,scope_type,scope_id,horizon_days) DO UPDATE SET
                    status=EXCLUDED.status,exclusion_reason=EXCLUDED.exclusion_reason,
                    entry_date=EXCLUDED.entry_date,outcome_date=EXCLUDED.outcome_date,
                    return_ratio=EXCLUDED.return_ratio,benchmark_return_ratio=EXCLUDED.benchmark_return_ratio,
                    relative_return_ratio=EXCLUDED.relative_return_ratio,mfe_ratio=EXCLUDED.mfe_ratio,
                    mae_ratio=EXCLUDED.mae_ratio,price_snapshot_id=EXCLUDED.price_snapshot_id,
                    benchmark_snapshot_id=EXCLUDED.benchmark_snapshot_id,
                    provenance_id=EXCLUDED.provenance_id,evaluated_at=now()
                 WHERE publication.pilot_analysis_outcomes.status='pending'"""
        fields = ("analysis_execution_id","scope_type","scope_id","analysis_as_of","horizon_days",
                  "pilot_baseline_id","membership_snapshot_hash","status","exclusion_reason","benchmark_id",
                  "entry_date","outcome_date","return_ratio","benchmark_return_ratio","relative_return_ratio",
                  "mfe_ratio","mae_ratio","price_snapshot_id","benchmark_snapshot_id","provenance_id")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.executemany(sql, [tuple(row.get(field) for field in fields) for row in rows])


def consume_queued_analysis(queue: PostgreSQLAnalysisQueue, processor: Callable[[AnalysisExecution], dict[str, object]],
                            *, worker_id: str, max_retries: int = 1) -> dict[str, object]:
    """Process one leased execution; claiming alone can never mark analysis complete."""
    execution = queue.claim(worker_id)
    if execution is None:
        return {"component": "intelligence-mart", "status": "idle", "claimed": False}
    try:
        execution.validate_input()
        result = processor(execution)
        artifact_uri = str(result.get("artifact_uri", ""))
        if not artifact_uri.startswith("gs://") or result.get("core_snapshot_id") != execution.core_snapshot_id:
            raise ValueError("analysis processor must persist an artifact for the claimed Core snapshot")
        queue.transition(execution.execution_id, worker_id, "succeeded", retry_count=execution.retry_count)
        return {"component": "intelligence-mart", "status": "succeeded", "claimed": True,
                "execution_id": execution.execution_id, "retry_count": execution.retry_count,
                "artifact_uri": artifact_uri,
                "reports": int(result.get("reports", 0)),
                "publishable": int(result.get("publishable", 0)),
                "outcomes_updated": int(result.get("outcomes_updated", 0)),
                "pilot_baseline_id": result.get("pilot_baseline_id")}
    except Exception as error:
        retry_count = execution.retry_count + 1
        status = "retrying" if retry_count <= max_retries else "failed"
        queue.transition(execution.execution_id, worker_id, status, retry_count=retry_count,
                         error_code=type(error).__name__.upper()[:64])
        raise


def _fenced_core_manifest(execution: AnalysisExecution, store_factory: Callable[[str], Any]) -> dict[str, Any]:
    """Load a hash-, execution-, and snapshot-fenced Core manifest."""
    source = urlparse(str(execution.request_options["core_snapshot_uri"]))
    if source.scheme != "gs" or not source.netloc or not source.path.strip("/"):
        raise ValueError("core_snapshot_uri must be a gs:// object")
    payload = store_factory(source.netloc).read(source.path.lstrip("/"))
    digest = f"sha256:{sha256(payload).hexdigest()}"
    if digest != execution.request_options["core_snapshot_hash"]:
        raise ValueError("Core snapshot hash mismatch")
    snapshot = json.loads(payload)
    if not isinstance(snapshot, dict):
        raise ValueError("Core snapshot manifest must be a JSON object")
    if str(snapshot.get("execution_id", "")) != execution.request_options["core_execution_id"]:
        raise ValueError("Core snapshot execution mismatch")
    if str(snapshot.get("snapshot_id", "")) != execution.core_snapshot_id:
        raise ValueError("Core snapshot ID mismatch")
    return snapshot


def deterministic_processor(execution: AnalysisExecution, store_factory: Callable[[str], Any] | None = None) -> dict[str, object]:
    """Materialise one immutable, deterministic Mart input artifact."""
    if store_factory is None:
        from ingestion_core.stage import GcsObjectStore
        store_factory = GcsObjectStore
    _fenced_core_manifest(execution, store_factory)
    digest = str(execution.request_options["core_snapshot_hash"])

    artifact = {
        "artifact_kind": "mart_input_v1",
        "analysis_execution_id": execution.execution_id,
        "analysis_as_of": execution.request_options["analysis_as_of"],
        "core_execution_id": execution.request_options["core_execution_id"],
        "core_snapshot_id": execution.core_snapshot_id,
        "core_snapshot_uri": execution.request_options["core_snapshot_uri"],
        "core_snapshot_hash": digest,
        "requested_symbols": list(execution.requested_symbols),
        "schema_version": execution.request_options["schema_version"],
        "feature_version": execution.request_options["feature_version"],
        "model_version": execution.request_options["model_version"],
        "governance_snapshot_version": execution.request_options["governance_snapshot_version"],
    }
    target_bucket = os.environ.get("MART_BUCKET", "").strip()
    if not target_bucket or "/" in target_bucket:
        raise ValueError("MART_BUCKET is required")
    target_name = f"executions/{execution.execution_id}/input.json"
    target_store = store_factory(target_bucket)
    artifact_payload = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if not target_store.create(target_name, artifact_payload, "application/json") \
            and target_store.read(target_name) != artifact_payload:
        raise RuntimeError("immutable Mart input artifact conflict")
    return {"artifact_uri": f"gs://{target_bucket}/{target_name}",
            "core_snapshot_id": execution.core_snapshot_id}


def _write_immutable_json(store: Any, bucket: str, name: str, value: object) -> dict[str, str]:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    if not store.create(name, payload, "application/json") and store.read(name) != payload:
        raise RuntimeError("immutable Mart artifact conflict")
    return {"artifact_uri": f"gs://{bucket}/{name}", "artifact_hash": f"sha256:{sha256(payload).hexdigest()}"}


def mart_processor(execution: AnalysisExecution, publication_connection: Any, *,
                   store_factory: Callable[[str], Any] | None = None,
                   catalog_factory: Callable[[], Any] | None = None,
                   narrator_factory: Callable[[], Any] | None = None) -> dict[str, object]:
    """Run the complete deterministic Mart and optional Gemini/publication stages."""
    if store_factory is None:
        from ingestion_core.stage import GcsObjectStore
        store_factory = GcsObjectStore
    from .analysis import analyze, canonical_json, prompt_bundle, scopes
    from .storage import MartIcebergStore, load_core_datasets, sql_catalog_from_environment

    manifest = _fenced_core_manifest(execution, store_factory)
    deterministic_processor(execution, store_factory)
    prompts, prompt_hash = prompt_bundle()
    bucket = os.environ.get("MART_BUCKET", "").strip()
    target_store = store_factory(bucket)
    target_name = f"executions/{execution.execution_id}/manifest.json"
    catalog = (catalog_factory or sql_catalog_from_environment)()
    warehouse = os.environ.get("MART_ICEBERG_WAREHOUSE", f"gs://{os.environ.get('MART_BUCKET', '')}/warehouse")
    mart_store = MartIcebergStore(catalog, warehouse)
    try:
        configured_scopes = scopes(execution.request_options, execution.requested_symbols)
        selected_symbols = tuple(sorted(set(execution.requested_symbols) | {
            symbol for scope in configured_scopes for symbol in scope["symbols"]
        }))
        datasets = load_core_datasets(catalog, manifest, selected_symbols,
                                     row_limit=int(os.environ.get("CORE_SNAPSHOT_ROW_LIMIT", "100000")))
        reports = analyze(
            execution_id=execution.execution_id,
            analysis_as_of=str(execution.request_options["analysis_as_of"]),
            core_snapshot_id=execution.core_snapshot_id,
            requested_symbols=execution.requested_symbols,
            options=execution.request_options,
            datasets=datasets,
            prompts=prompts,
            prompt_hash=prompt_hash,
        )
        expected_hashes = {(report["scope"]["type"], report["scope"]["id"]): report["deterministic_hash"] for report in reports}
        existing_manifest = None
        try:
            existing_manifest = json.loads(target_store.read(target_name))
        except FileNotFoundError:
            pass
        except Exception as error:
            from urllib.error import HTTPError
            if not isinstance(error, HTTPError) or error.code != 404:
                raise
        if existing_manifest is not None:
            indexed = existing_manifest.get("reports", [])
            actual_hashes = {(item["scope_type"], item["scope_id"]): item["deterministic_hash"] for item in indexed}
            if existing_manifest.get("core_snapshot_id") != execution.core_snapshot_id or actual_hashes != expected_hashes:
                raise RuntimeError("immutable Mart execution manifest conflict")
            narratives = {(item["scope_type"], item["scope_id"]): item for item in existing_manifest.get("llm", [])}
        else:
            narratives: dict[tuple[str, str], dict[str, Any]] = {}
            if os.environ.get("MART_LLM_ENABLED", "false").lower() in {"1", "true", "yes"}:
                if narrator_factory is None:
                    from .gemini import GeminiNarrator
                    narrator_factory = GeminiNarrator.from_environment
                narrator = narrator_factory()
                for report in reports:
                    scope = report["scope"]
                    narratives[(scope["type"], scope["id"])] = narrator.narrate(report, prompts)
            references = mart_store.write(reports, narratives)
    finally:
        mart_store.close()

    publication = PostgreSQLPublicationIndex(publication_connection)
    stored_baseline = existing_manifest.get("pilot_baseline_id") if existing_manifest is not None else None
    pilot_baseline_id = str(stored_baseline) if stored_baseline else publication.register_baseline(
        execution, prompts["version"], prompt_hash)
    if existing_manifest is None:
        artifact_prefix = f"executions/{execution.execution_id}/artifacts"
        governance_diff = execution.request_options.get("governance_diff", [])
        if not isinstance(governance_diff, (dict, list)):
            raise ValueError("governance_diff must be a JSON object or array")
        artifacts = {
            "model": _write_immutable_json(target_store, bucket, f"{artifact_prefix}/model.json", {
                "artifact_kind": "model_v1", "model_version": execution.request_options["model_version"],
                "prompt_version": reports[0]["prompt_version"] if reports else None,
                "prompt_hash": prompt_hash, "llm": [
                    {"scope_type": key[0], "scope_id": key[1], **value}
                    for key, value in sorted(narratives.items())
                ],
            }),
            "evaluation": _write_immutable_json(target_store, bucket, f"{artifact_prefix}/evaluation.json", {
                "artifact_kind": "evaluation_v1", "execution_id": execution.execution_id,
                "reports": [{
                    "scope_type": report["scope"]["type"], "scope_id": report["scope"]["id"],
                    "deterministic_hash": report["deterministic_hash"], **report["aggregate"],
                } for report in reports],
            }),
            "governance_diff": _write_immutable_json(target_store, bucket, f"{artifact_prefix}/governance-diff.json", {
                "artifact_kind": "governance_diff_v1",
                "governance_snapshot_version": execution.request_options["governance_snapshot_version"],
                "base_governance_snapshot_version": execution.request_options.get("base_governance_snapshot_version"),
                "diff": governance_diff,
            }),
        }
        indexed = []
        for report in reports:
            scope = report["scope"]
            reference = references[(scope["type"], scope["id"])]
            artifact = urlparse(reference["artifact_uri"])
            if artifact.scheme != "gs" or not artifact.netloc or not artifact.path.strip("/"):
                raise ValueError("Iceberg metadata location must be an immutable GCS object")
            artifact_payload = store_factory(artifact.netloc).read(artifact.path.lstrip("/"))
            artifact_hash = f"sha256:{sha256(artifact_payload).hexdigest()}"
            indexed.append({"scope_type": scope["type"], "scope_id": scope["id"], **reference,
                            "artifact_hash": artifact_hash, "deterministic_hash": report["deterministic_hash"],
                            "analysis_outcome": report["aggregate"]["analysis_outcome"],
                            "publication_status": report["aggregate"]["publication_status"]})
        result_manifest = {
            "artifact_kind": "mart_execution_v1", "execution_id": execution.execution_id,
            "analysis_as_of": execution.request_options["analysis_as_of"], "core_snapshot_id": execution.core_snapshot_id,
            "pilot_baseline_id": pilot_baseline_id,
            "artifacts": artifacts, "reports": indexed,
            "llm": [{"scope_type": key[0], "scope_id": key[1], **value} for key, value in sorted(narratives.items())],
        }
        payload = canonical_json(result_manifest)
        if not target_store.create(target_name, payload, "application/json") and target_store.read(target_name) != payload:
            raise RuntimeError("immutable Mart execution manifest conflict")
    retention_days = int(execution.request_options.get("retention_days", 365))
    for report, index in zip(reports, indexed, strict=True):
        publication.register(report, index, index["artifact_hash"], retention_days=retention_days,
                             pilot_baseline_id=pilot_baseline_id)
    outcomes_updated = 0
    if pilot_baseline_id:
        from .outcomes import collect_pilot_outcomes
        outcomes_updated = collect_pilot_outcomes(publication, datasets)
    return {"artifact_uri": f"gs://{bucket}/{target_name}", "core_snapshot_id": execution.core_snapshot_id,
            "reports": len(reports), "publishable": sum(item["publication_status"] in {"publishable", "published"} for item in indexed),
            "outcomes_updated": outcomes_updated, "pilot_baseline_id": pilot_baseline_id}


def run_queued_analysis() -> dict[str, object]:
    """Run one persisted analysis execution through the immutable input materialiser."""
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password"),
    })
    if not os.environ.get("GEMINI_API_KEY"):
        bundle = json.loads(os.environ.get("JANUS_MART_POSTGRES_BUNDLE", "{}"))
        key = str(bundle.get("gemini_api_key", "")).strip()
        if key:
            os.environ["GEMINI_API_KEY"] = key
    settings = _settings("PUBLICATION_DB")
    import psycopg

    with psycopg.connect(
        host=settings["host"], dbname=settings["name"], user=settings["user"], password=settings["password"],
        sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
        options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
    ) as connection:
        return consume_queued_analysis(
            PostgreSQLAnalysisQueue(connection), lambda execution: mart_processor(execution, connection),
            worker_id=os.environ.get("QUEUE_WORKER_ID", "intelligence-mart").strip(),
            max_retries=int(os.environ.get("QUEUE_MAX_RETRIES", "1")),
        )


def _settings(prefix: str) -> dict[str, str]:
    names = ("HOST", "NAME", "USER", "PASSWORD")
    values = {name.lower(): os.environ.get(f"{prefix}_{name}", "").strip() for name in names}
    missing = [f"{prefix}_{name}" for name in names if not values[name.lower()]]
    if missing:
        raise ValueError(f"missing database settings: {','.join(missing)}")
    return values


def _is_private(address: str) -> bool:
    parsed = ip_interface(address).ip
    return parsed.is_private and not (parsed.is_loopback or parsed.is_link_local)


def postgres_smoke(connect: Callable[..., Any] | None = None) -> dict[str, object]:
    """Verify both Mart identities reach PostgreSQL privately with bounded grants."""
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password"),
    })
    if connect is None:
        import psycopg

        connect = psycopg.connect

    results: dict[str, object] = {}
    for label, (prefix, schema, writable_table) in _DATABASES.items():
        settings = _settings(prefix)
        with connect(
            host=settings["host"],
            dbname=settings["name"],
            user=settings["user"],
            password=settings["password"],
            sslmode=os.environ.get(f"{prefix}_SSLMODE", "require"),
            connect_timeout=5,
            options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_user, inet_server_addr()::text, "
                    "has_schema_privilege(current_user, %s, 'USAGE')",
                    (schema,),
                )
                role, server_address, schema_usage = cursor.fetchone()
                writable = True
                if writable_table:
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, 'SELECT,INSERT,UPDATE,DELETE')",
                        (writable_table,),
                    )
                    writable = bool(cursor.fetchone()[0])

        if role != settings["user"]:
            raise RuntimeError(f"{label} role mismatch")
        if not _is_private(server_address):
            raise RuntimeError(f"{label} database did not resolve to a private server address")
        if not schema_usage or not writable:
            raise RuntimeError(f"{label} role is missing its bounded schema privileges")
        results[label] = {"role": role, "server_address": server_address, "private": True, "privileges": "ok"}

    return {"component": "intelligence-mart", "status": "ok", "databases": results}
