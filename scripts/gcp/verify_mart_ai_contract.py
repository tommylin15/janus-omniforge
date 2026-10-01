"""Bounded dev acceptance using an existing immutable Mart snapshot, without AI calls."""

import argparse
from copy import deepcopy
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
from intelligence_mart.ai_validation import VERSION as VALIDATOR_VERSION, validate_role, summarize_roles
from intelligence_mart.compat import artifact_reference, build_compatibility_sidecar, validate_compatibility_sidecar


def verify_compatibility(store, bucket, manifest_uri, report):
    """Bind existing validation fixtures to a real v1 report without changing it."""
    before = deepcopy(report)
    prefix = f"acceptance/ai-validation/{VALIDATOR_VERSION}/{report['deterministic_hash'][7:]}"
    evidence = json.loads(store.read(f"{prefix}/evidence.json"))
    assert evidence["source_manifest_uri"] == manifest_uri
    references = []
    artifacts = {}
    for ref in evidence["fixture_inputs"] + evidence["validations"]:
        uri = urlparse(ref["artifact_uri"])
        assert uri.scheme == "gs" and uri.netloc == bucket
        raw = store.read(uri.path.lstrip("/"))
        assert f"sha256:{sha256(raw).hexdigest()}" == ref["artifact_hash"]
        artifact = json.loads(raw)
        assert content_hash({key: value for key, value in artifact.items() if key != "artifact_hash"}) == artifact["artifact_hash"]
        artifacts[artifact["artifact_hash"]] = (artifact, ref)
    for artifact, ref in artifacts.values():
        if artifact["artifact_kind"] != "mart_ai_validation_v1" or artifact["status"] != "validated":
            continue
        source, source_ref = artifacts[artifact["source_artifact_hash"]]
        assert validate_role(source, report) == artifact
        references.extend((artifact_reference(source, source_ref), artifact_reference(artifact, ref)))
    assert len(references) == 10
    sidecar = build_compatibility_sidecar(report, references)
    prefix = f"acceptance/mart-compat/{sidecar['sidecar_hash'][7:]}"
    ref = _write_immutable_json(store, bucket, f"{prefix}/sidecar.json", sidecar)
    stored = json.loads(store.read(f"{prefix}/sidecar.json"))
    assert validate_compatibility_sidecar(stored, report) == sidecar
    assert report == before
    print(json.dumps({"acceptance": "passed", **ref, "sidecar_hash": sidecar["sidecar_hash"],
                      "base": sidecar["base"], "artifact_count": len(references),
                      "provider_calls": 0, "publication_writes": 0, "five_role_success": False}, sort_keys=True))


def verify_validation(store, bucket, manifest_uri, report):
    """Synthetic output fault injection against a real pinned Fact Pack, never AI execution."""
    refs, results, inputs = [], [], []
    prefix = f"acceptance/ai-validation/{VALIDATOR_VERSION}/{report['deterministic_hash'][7:]}"
    for pack in report["fact_packs"]:
        role = pack["pack_type"]
        context = {key: report[key] for key in ("execution_id", "analysis_as_of", "core_snapshot_id",
                                              "governance_snapshot_version")}
        context.update(scope_type=report["scope"]["type"], scope_id=report["scope"]["id"])
        context.update({key: pack[key] for key in ("fact_pack_hash", "evidence_hash", "feature_version")})
        context.update(provider="acceptance-no-provider", model="not-invoked", parameters={},
                       profile_reference="repository-default-v1")
        output = dict(schema_version="1.0.0", role=role, stance="insufficient_data", thesis=None,
                      missing_information=pack["missing_data"] or ["研究資料仍有限"], confidence=0.0,
                      evidence_ids=[], **{field: [] for field in (
                          "key_findings", "positive_evidence", "negative_evidence", "contradictions",
                          "change_drivers", "risks", "what_would_change_my_view")})
        artifact = interpretation_artifact(role, output, context)
        inputs.append(save_interpretation(store, bucket, artifact))
        result = validate_role(artifact, report)
        assert result["status"] == "validated", result["errors"]
        assert validate_role(artifact, report) == result
        results.append(result)
        cases = [result]
        invalid = deepcopy(output)
        invalid.update(stance="neutral", thesis={"text": "價格999999元", "evidence_ids": ["ev-" + "f" * 24]},
                       evidence_ids=["ev-" + "f" * 24])
        injected = interpretation_artifact(role, invalid, context)
        inputs.append(save_interpretation(store, bucket, injected))
        rejected = validate_role(injected, report)
        assert rejected["status"] == "blocked" and "ungrounded_numeric_claim" in rejected["errors"]
        cases.append(rejected)
        wrong = {**context, "analysis_as_of": "2099-01-01"}
        injected = interpretation_artifact(role, output, wrong)
        inputs.append(save_interpretation(store, bucket, injected))
        rejected = validate_role(injected, report)
        assert rejected["status"] == "blocked" and "lineage_mismatch" in rejected["errors"]
        cases.append(rejected)
        for case in cases:
            ref = save_interpretation(store, bucket, case)
            assert save_interpretation(store, bucket, case) == ref
            assert json.loads(store.read(ref["artifact_uri"].split(f"gs://{bucket}/")[1])) == case
            refs.append(ref)
    summary = summarize_roles(results)
    assert summary["validation_outcome"] == "complete" and summary["five_role_success"] is False
    assert summarize_roles(results[:-1])["validation_outcome"] == "partial"
    evidence = dict(validator_version=VALIDATOR_VERSION, source_manifest_uri=manifest_uri,
                    source_deterministic_hash=report["deterministic_hash"], validations=refs, fixture_inputs=inputs,
                    validation_summary=summary, fixture_outputs=True, provider_calls=0,
                    publication_writes=0, five_role_success=False)
    ref = _write_immutable_json(store, bucket, f"{prefix}/evidence.json", evidence)
    assert json.loads(store.read(f"{prefix}/evidence.json")) == evidence
    print(json.dumps({"acceptance": "passed", **ref, "validation_count": len(refs),
                      "provider_calls": 0, "five_role_success": False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--symbol", default="2330")
    parser.add_argument("--validate-roles", action="store_true")
    parser.add_argument("--verify-compat", action="store_true")
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
    if args.verify_compat:
        verify_compatibility(store, bucket, args.manifest_uri, report)
        assert store.read(metadata_location.path.lstrip("/")) == metadata
        assert json.loads(store.read(location.path.lstrip("/"))) == manifest
        return
    if args.validate_roles:
        verify_validation(store, bucket, args.manifest_uri, report)
        return
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
