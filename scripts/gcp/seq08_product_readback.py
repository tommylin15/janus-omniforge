"""SEQ-08 exact, read-only GCS evidence for one completed real Dev Mart execution.

No listing, SQL, remote Job invocation, secret/Owner payload logs, or mutations.
The status counts are intentionally independent of the Job's exit status.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-mart"
RUN = "40195093746"
SOURCE = "a2881c5c2532beb5570e29a1fda4472c7bb0d448"
EXPECTED_ROLES = ("quant", "risk", "fundamental", "valuation")
SAMPLES = ("2330", "2882")
MAX_BYTES = 8 * 1024 * 1024
EXEC_RE = re.compile(r"janus-intelligence-mart-[a-z0-9-]{4,64}")
UUID_RE = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")


def run(args, timeout=75):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


def require_request(data):
    if data != {
        "intent": "seq08-exact-real-mart-product-readonly",
        "source_sha": SOURCE, "successful_mart_run": RUN,
        "symbols": list(SAMPLES), "read_only": True,
        "no_gcp_mutation": True, "no_owner_mutation": True,
        "no_new_resources": True
    }:
        raise ValueError("readback_request_scope_mismatch")


def receipt():
    with tempfile.TemporaryDirectory() as directory:
        call = run(["gh", "run", "download", RUN, "-n",
                    "seq08-real-mart-execution-receipt", "-D", directory])
        if call.returncode:
            raise ValueError("source_job_receipt_unavailable")
        data = json.loads((Path(directory) / "seq08-real-mart.json").read_text())
    name = data.get("cloud_run_execution", "")
    if (data.get("phase") != "REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING"
            or data.get("source_sha") != SOURCE
            or data.get("job") != "janus-intelligence-mart"
            or not EXEC_RE.fullmatch(name)):
        raise ValueError("source_job_receipt_not_exact_success")
    return name


def parse_execution_id(entries, cloud_execution):
    ids = set()
    for item in entries:
        raw = item.get("textPayload")
        if not isinstance(raw, str):
            data = item.get("jsonPayload")
        else:
            start = raw.find("{")
            if start < 0:
                continue
            try:
                data = json.loads(raw[start:])
            except (ValueError, TypeError):
                continue
        if not isinstance(data, dict):
            continue
        if (data.get("component") == "intelligence-mart"
                and data.get("operation") == "deep-coverage"
                and data.get("status") not in ("failed", "retrying")):
            candidate = str(data.get("execution_id", ""))
            if UUID_RE.fullmatch(candidate):
                ids.add(candidate)
    if len(ids) != 1:
        raise ValueError("source_mart_artifact_execution_identity_unknown")
    return ids.pop()


def lookup_execution_id(cloud_execution):
    query = ('resource.type="cloud_run_job" AND '
             'labels."run.googleapis.com/execution_name"="' + cloud_execution + '"')
    result = run(["gcloud", "logging", "read", query,
                  "--project=" + PROJECT, "--limit=250", "--format=json"], timeout=80)
    if result.returncode:
        raise ValueError("cloud_logging_exact_execution_read_denied")
    return parse_execution_id(json.loads(result.stdout), cloud_execution)


def object_json(path):
    if not path.startswith("executions/") or ".." in path:
        raise ValueError("GCS_path_outside_exact_execution")
    result = run(["gcloud", "storage", "cat", "gs://" + BUCKET + "/" + path,
                  "--project", PROJECT], timeout=95)
    if result.returncode or not result.stdout or len(result.stdout) > MAX_BYTES:
        raise ValueError("exact_GCS_artifact_unreadable")
    return json.loads(result.stdout), "sha256:" + sha256(result.stdout).hexdigest()


def readback(execution_id, cloud_execution):
    root = "executions/" + execution_id + "/"
    manifest, manifest_hash = object_json(root + "specialist-manifest.json")
    if (manifest.get("execution_id") != execution_id
            or not manifest.get("analysis_as_of")
            or not manifest.get("core_snapshot_id")
            or not isinstance(manifest.get("four_model_serving"), dict)
            or not isinstance(manifest.get("analyst_inputs"), dict)):
        raise ValueError("mart_manifest_new_serving_reference_missing")
    ref = manifest["four_model_serving"]
    if ref.get("artifact_uri") != "gs://" + BUCKET + "/" + root + "four-model-serving.json":
        raise ValueError("mart_serving_ref_wrong_execution")
    output, output_hash = object_json(root + "four-model-serving.json")
    if (output_hash != ref.get("artifact_hash")
            or output.get("owner_fields_exposed") is not False
            or output.get("analysis_as_of") != manifest["analysis_as_of"]
            or output.get("core_snapshot_id") != manifest["core_snapshot_id"]
            or output.get("artifact_kind") != "mart_four_model_serving_v1"
            or not isinstance(output.get("rows"), list)):
        raise ValueError("model_serving_live_hash_or_identity_mismatch")
    inputs_ref = manifest["analyst_inputs"]
    if inputs_ref.get("artifact_uri") != "gs://" + BUCKET + "/" + root + "analyst-inputs.json":
        raise ValueError("mart_analyst_inputs_ref_wrong_execution")
    inputs, input_hash = object_json(root + "analyst-inputs.json")
    if (input_hash != inputs_ref.get("artifact_hash")
            or inputs.get("output_hash") != output.get("source_analyst_input_hash")
            or inputs.get("core_snapshot_id") != output["core_snapshot_id"]):
        raise ValueError("live_model_features_hash_mismatch")
    counts = {role: Counter() for role in EXPECTED_ROLES}
    sampled = {code: {"present": False} for code in SAMPLES}
    target = set()
    for row in output["rows"]:
        symbol, roles = row.get("symbol"), row.get("roles")
        if (not isinstance(symbol, str) or symbol in target
                or not isinstance(roles, dict)
                or set(roles) != set(EXPECTED_ROLES)):
            raise ValueError("live_model_roles_or_unique_symbol_mismatch")
        target.add(symbol)
        for role in EXPECTED_ROLES:
            item = roles[role]
            status = item.get("status")
            if status not in {"ACTIVE_PREDICTED", "ACTIVE_CACHED",
                              "ABSTAINED_X_ONLY", "FEATURE_INCOMPATIBLE_OR_MISSING",
                              "MISSING_OR_INACTIVE_ARTIFACT"}:
                raise ValueError("live_model_status_unknown")
            counts[role][status] += 1
        if symbol in SAMPLES:
            sampled[symbol] = {"present": True, "roles": {
                role: {"status": roles[role]["status"],
                       "prediction_available": roles[role].get("prediction") is not None,
                       "missing_features": roles[role].get("missing_features", []),
                       "reasons": roles[role].get("reasons", [])}
                for role in EXPECTED_ROLES}}
    return {"scope": "EXACT_ONE_REAL_DEV_EXECUTION_READ_ONLY",
            "status": "READBACK_PASS" if target else "EMPTY_TARGET_PARTIAL",
            "cloud_run_execution": cloud_execution,
            "mart_execution_id": execution_id,
            "source_application_sha": SOURCE,
            "analysis_as_of": manifest["analysis_as_of"],
            "core_snapshot_id": str(manifest["core_snapshot_id"]),
            "manifest_sha256": manifest_hash,
            "model_artifact_sha256": output_hash,
            "target_symbol_count": len(target),
            "model_status_counts": {k: dict(v) for k,v in counts.items()},
            "samples": sampled, "owner_login_ui": "NOT_VERIFIED",
            "pg_product_readback": "NOT_VERIFIED",
            "gcp_mutations": 0}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    phase = "REQUEST"
    try:
        require_request(json.loads(Path("ops/seq08-product-readback-request.json").read_text()))
        phase = "SOURCE_RECEIPT"
        cloud_execution = receipt()
        phase = "CLOUD_LOG_IDENTITY"
        execution_id = lookup_execution_id(cloud_execution)
        phase = "GCS_MODEL_ARTIFACTS"
        result = readback(execution_id, cloud_execution)
        args.receipt.write_text(json.dumps(result, sort_keys=True))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        result = {"status": "BLOCKED", "phase": phase, "reason": reason,
                  "gcp_mutations": 0, "owner_mutations": 0}
        args.receipt.write_text(json.dumps(result, sort_keys=True))
        print(json.dumps(result, sort_keys=True))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
