"""Bounded Stage-only live canary for cross-execution raw reuse and provenance.

Run under the existing owned GitHub release lease, paused Scheduler, and
all-page Cloud Run execution fence. All synthetic Stage artifacts are removed
with exact generation preconditions; no PostgreSQL, Core, Mart or Private write.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from uuid import uuid4

from ingestion_core.stage import GcsObjectStore, StageWriter
from packages.provenance import Provenance, content_hash, idempotency_key

BUCKET = "gen-lang-client-0593591102-dev-stage"
COMPONENT = "stage-shared-raw-live-canary"


def main():
    if (os.environ.get("STAGE_BUCKET") != BUCKET or
            os.environ.get("JANUS_STAGE_DEDUPE_CANARY_APPROVED") != "true"):
        raise RuntimeError("stage_dedupe_canary_scope_required")
    store = GcsObjectStore(BUCKET)
    writer = StageWriter(store)
    nonce = uuid4().hex
    execution_ids = ("stagecanary" + nonce + "a", "stagecanary" + nonce + "b")
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    payload = json.dumps({"janus_live_stage_canary": nonce}, sort_keys=True).encode()
    digest = content_hash(payload)
    key = idempotency_key("twse", "ohlcv", observed, digest)
    raw_prefix = f"raw/twse/ohlcv/observed_date={observed.date().isoformat()}/{key}/"
    prefixes = (raw_prefix,) + tuple(f"executions/{execution_id}/stage/" for execution_id in execution_ids)
    # The cryptographic nonce, observed instant and create-if-absent semantics
    # guarantee this canary cannot borrow a real market object.
    for prefix in prefixes:
        if store.objects(prefix):
            raise RuntimeError("stage_canary_namespace_collision")
    made = []
    proof = None
    failure = None
    try:
        for index, execution_id in enumerate(execution_ids):
            provenance = Provenance(
                provenance_id=f"stage-canary-{nonce}-{index}",
                source_id="twse", source_url="https://example.invalid/stage-canary",
                dataset_id="ohlcv", observed_at=observed, published_at=None,
                fetched_at=observed + timedelta(seconds=index),
                content_hash=digest, quality_flags=("unknown",),
            )
            made.append(writer.write_raw(
                payload=payload, media_type="application/json", extension="json",
                execution_id=execution_id, provenance=provenance))
        first, second = made
        expected = {first.object_name, first.sidecar_name,
                    first.manifest_name, second.manifest_name}
        paths = {item["name"] for prefix in prefixes for item in store.objects(prefix)}
        if (first.object_name != second.object_name or
                first.sidecar_name != second.sidecar_name or
                first.manifest_name == second.manifest_name or
                first.reused or not second.reused or paths != expected):
            raise RuntimeError("stage_live_dedupe_object_identity_failed")
        if store.read(first.object_name) != payload:
            raise RuntimeError("stage_live_dedupe_payload_readback_failed")
        observed_ids = []
        for expected_id, result in zip(execution_ids, made):
            saved = json.loads(store.read(result.manifest_name))
            expected_provenance_id = f"stage-canary-{nonce}-{0 if expected_id == execution_ids[0] else 1}"
            if (saved.get("raw_object_name") != first.object_name or
                    saved.get("provenance", {}).get("provenance_id") != expected_provenance_id or
                    saved.get("provenance", {}).get("content_hash") != digest):
                raise RuntimeError("stage_live_per_execution_provenance_failed")
            observed_ids.append(saved["provenance"]["provenance_id"])
        if len(set(observed_ids)) != 2:
            raise RuntimeError("stage_live_provenance_not_distinct")
        proof = {"raw_created_once": True, "second_execution_reused": True,
                 "distinct_provenance_manifests": True, "raw_payload_verified": True,
                 "created_objects": len(paths)}
    except Exception as error:
        failure = type(error).__name__
    finally:
        # Never delete outside cryptographically unique bounded canary prefixes.
        cleanup = []
        for prefix in prefixes:
            cleanup.extend(store.objects(prefix))
        if len(cleanup) > 6 or sum(int(item["size"]) for item in cleanup) > 16384:
            raise RuntimeError("stage_canary_cleanup_scope_exceeded")
        for item in cleanup:
            store.delete(item["name"], generation=item["generation"])
        leftovers = [item["name"] for prefix in prefixes for item in store.objects(prefix)]
        if leftovers:
            raise RuntimeError("stage_canary_generation_cleanup_incomplete")
    receipt = {
        "component": COMPONENT, "status": "PASS" if failure is None and proof is not None else "FAIL",
        "proof": proof, "error_type": failure,
        "deleted_canary_objects": len(cleanup), "leftover_canary_objects": 0,
        "generation_cleanup": "PASS", "core_deleted": 0, "mart_deleted": 0,
        "private_deleted": 0,
    }
    print(json.dumps(receipt, sort_keys=True), flush=True)
    if receipt["status"] != "PASS":
        raise RuntimeError("stage_shared_raw_live_canary_failed")


if __name__ == "__main__":
    main()
