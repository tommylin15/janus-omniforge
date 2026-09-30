"""Bounded dev acceptance using an existing immutable Mart snapshot, without AI calls."""

import argparse
from hashlib import sha256
import json
import os
from urllib.parse import urlparse

from pyiceberg.expressions import And, EqualTo
from pyiceberg.table import StaticTable

from ingestion_core.stage import GcsObjectStore
from intelligence_mart.ai_contract import (
    OUTPUT_MODELS, content_hash, contract_bundle, interpretation_artifact, save_interpretation,
)
from intelligence_mart.runtime import _validate_fact_packs, _write_immutable_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--symbol", default="2330")
    args = parser.parse_args()
    bucket = os.environ["MART_BUCKET"]
    if os.environ.get("ENVIRONMENT") != "dev" or "-dev-" not in bucket:
        raise ValueError("acceptance is restricted to the existing dev Mart bucket")
    location = urlparse(args.manifest_uri)
    if location.scheme != "gs" or location.netloc != bucket:
        raise ValueError("manifest must be inside the dev Mart bucket")
    store = GcsObjectStore(bucket)
    manifest = json.loads(store.read(location.path.lstrip("/")))
    reference = next(item for item in manifest["reports"]
                     if item["scope_type"] == "symbol" and item["scope_id"] == args.symbol)
    metadata_uri = reference["artifact_uri"]
    metadata_location = urlparse(metadata_uri)
    if metadata_location.scheme != "gs" or metadata_location.netloc != bucket:
        raise ValueError("metadata must be inside the dev Mart bucket")
    metadata = store.read(metadata_location.path.lstrip("/"))
    if f"sha256:{sha256(metadata).hexdigest()}" != reference["artifact_hash"]:
        raise ValueError("pinned metadata hash mismatch")
    table = StaticTable.from_metadata(metadata_uri, properties={
        "gcs.project-id": os.environ["GCP_PROJECT_ID"],
        "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
    })
    rows = table.scan(snapshot_id=int(reference["iceberg_snapshot_id"]), row_filter=And(
        EqualTo("execution_id", manifest["execution_id"]), EqualTo("scope_id", args.symbol)), limit=1).to_arrow().to_pylist()
    report = json.loads(rows[0]["payload_json"])
    assert report["execution_id"] == manifest["execution_id"]
    assert report["core_snapshot_id"] == manifest["core_snapshot_id"]
    _validate_fact_packs([report])
    bundle = contract_bundle()
    prefix = f"acceptance/ai-role-contract/{content_hash(bundle)[7:]}"
    bundle_ref = _write_immutable_json(store, bucket, f"{prefix}/contract.json", bundle)
    try:
        _write_immutable_json(store, bucket, f"{prefix}/contract.json", {"invalid": True})
    except RuntimeError:
        pass
    else:
        raise AssertionError("old contract was overwritten")
    assert json.loads(store.read(f"{prefix}/contract.json")) == bundle
    failures = []
    for role in OUTPUT_MODELS:
        pack = next(item for item in report["fact_packs"] if item["pack_type"] == ("quant" if role == "cio" else role))
        context = dict(execution_id=manifest["execution_id"], analysis_as_of=report["analysis_as_of"],
                       core_snapshot_id=report["core_snapshot_id"], scope_type="symbol", scope_id=args.symbol,
                       fact_pack_hash=pack["fact_pack_hash"], evidence_hash=pack["evidence_hash"],
                       feature_version=pack["feature_version"],
                       governance_snapshot_version=report["governance_snapshot_version"],
                       provider="acceptance-no-provider", model="not-invoked", parameters={},
                       profile_reference="repository-default-v1")
        if role == "cio":
            context["fact_pack_hash"] = content_hash([item["fact_pack_hash"] for item in report["fact_packs"]])
            context["evidence_hash"] = content_hash([item["evidence_hash"] for item in report["fact_packs"]])
        # Fault injection only: this is never an analyst or CIO success artifact.
        artifact = interpretation_artifact(role, {"role": role}, context)
        assert artifact["status"] == "failed" and "output" not in artifact
        first = save_interpretation(store, bucket, artifact)
        assert save_interpretation(store, bucket, artifact) == first
        stored = json.loads(store.read(first["artifact_uri"].split(f"gs://{bucket}/")[1]))
        assert stored == artifact
        failures.append(first)
    evidence = {"contract": bundle_ref, "source_manifest_uri": args.manifest_uri,
                "core_snapshot_id": report["core_snapshot_id"], "structured_failures": failures,
                "provider_calls": 0, "publication_writes": 0, "five_role_success": False}
    result = _write_immutable_json(store, bucket, f"{prefix}/evidence.json", evidence)
    print(json.dumps({"acceptance": "passed", **result, "failure_count": len(failures),
                      "contract_hash": content_hash(bundle), "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
