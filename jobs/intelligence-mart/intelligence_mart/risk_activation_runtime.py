"""Append-only PostgreSQL Risk activation gate driven by the existing dev Mart job.

GCS is the model/registry identity gate; the PG ledger is the live API switch.
Activation must follow pinned deployment + real-prediction readback. Rollback
uses the PG switch first so old immutable products cease being exposed instantly.
"""
from __future__ import annotations
import json
import os

from .runtime import _settings
from ingestion_core.stage import GcsObjectStore
from scripts.gcp.risk_registry_cas import (
    BUCKET, ACTIVE_OBJECT, MODEL_SHA256, validate_pointer)


def activation_plan(*, last, requested_mode, expected_mode, generation,
                    expected_generation, pointer):
    if requested_mode not in ("ACTIVE", "DETERMINISTIC"):
        raise ValueError("invalid Risk activation mode")
    if last is not None and last["mode"] != expected_mode:
        raise ValueError("stale PG expected previous mode")
    if last is None and expected_mode != "DETERMINISTIC":
        raise ValueError("first Risk activation must start deterministic")
    if generation != expected_generation or generation <= 0:
        raise ValueError("Risk registry generation drift")
    validate_pointer(pointer)
    if pointer["mode"] != requested_mode:
        raise ValueError("GCS and PG Risk switch mode mismatch")
    if requested_mode == "ACTIVE" and pointer["model_sha256"] != MODEL_SHA256:
        raise ValueError("unpinned active model")
    if last and int(last["gcs_registry_generation"]) >= generation:
        raise ValueError("Risk registry generation did not advance")
    return {
        "mode": requested_mode,
        "model_sha256": MODEL_SHA256 if requested_mode == "ACTIVE" else None,
        "source_git_sha": pointer["source_git_sha"],
        "gcs_registry_generation": generation,
    }


def run_risk_activation():
    from packages.postgres_bundle import load_postgres_bundle
    from .runtime import _settings
    import psycopg
    req = json.loads(os.environ["RISK_ACTIVATION_REQUEST"])
    if (req.get("intent") != "user-approved-risk-first-release"
            or req.get("environment") != "dev"
            or req.get("approved") is not True
            or req.get("mode") not in ("ACTIVE", "DETERMINISTIC")
            or req.get("expected_mode") not in ("ACTIVE", "DETERMINISTIC")
            or not isinstance(req.get("generation"), int)):
        raise ValueError("unauthorized Risk activation request")
    if (os.environ.get("GCP_PROJECT_ID") != "gen-lang-client-0593591102"
            or os.environ.get("MART_BUCKET") != BUCKET):
        raise ValueError("Risk activation outside dev allowlist")
    store = GcsObjectStore(BUCKET)
    found = [obj for obj in store.objects(ACTIVE_OBJECT) if obj["name"] == ACTIVE_OBJECT]
    if len(found) != 1:
        raise ValueError("Risk registry object absent or ambiguous")
    generation = int(found[0]["generation"])
    pointer = json.loads(store.read(ACTIVE_OBJECT))
    validate_pointer(pointer)
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
    settings = _settings("PUBLICATION_DB")
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"],
                         password=settings["password"], sslmode="require", connect_timeout=5) as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(1835102836, 68)")
            cur.execute("""SELECT mode, model_sha256, gcs_registry_generation
                        FROM private.risk_model_activation ORDER BY activation_id DESC LIMIT 1""")
            prior = cur.fetchone()
            last = dict(zip(("mode", "model_sha256", "gcs_registry_generation"), prior)) if prior else None
            change = activation_plan(last=last, requested_mode=req["mode"],
                expected_mode=req["expected_mode"], generation=generation,
                expected_generation=req["generation"], pointer=pointer)
            cur.execute("""INSERT INTO private.risk_model_activation
                (mode,model_sha256,source_git_sha,gcs_registry_generation,reason)
                VALUES (%s,%s,%s,%s,%s) RETURNING activation_id""",
                (change["mode"], change["model_sha256"], change["source_git_sha"],
                 change["gcs_registry_generation"], "owner_approved_risk_release_or_rollback"))
            activation_id = cur.fetchone()[0]
        row = conn.execute("""SELECT activation_id,mode,model_sha256,gcs_registry_generation
                            FROM private.risk_model_activation ORDER BY activation_id DESC LIMIT 1""").fetchone()
    if row is None or int(row[0]) != activation_id or row[1] != req["mode"] or int(row[3]) != generation:
        raise ValueError("Risk PG activation readback mismatch")
    return {"component": "intelligence-mart", "operation": "risk-activation",
            "status": "PASS", "activation_id": activation_id, "mode": row[1],
            "registry_generation": generation, "model_sha256": row[2],
            "owner_fields_exposed": False}
