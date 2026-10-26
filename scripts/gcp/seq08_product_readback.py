"""SEQ-08 exact, read-only GCS evidence for one completed real Dev Mart execution.

No listing, SQL, remote Job invocation, secret/Owner payload logs, or mutations.
Reports either real Deep Coverage or the specifically approved GCS-only screening
artifact; role/percentile counts must be independently verified against bytes.
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
RUN = "40300491771"
SOURCE = "43543ac684f34341265069244b5507f51afd5cff"
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
        "symbols": list(SAMPLES), "diagnostic_attempt": 5, "read_only": True,
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


def parse_execution_id(entries, cloud_execution, operation="deep-coverage"):
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
                and data.get("operation") == operation
                and data.get("status") not in ("failed", "retrying")):
            candidate = str(data.get("execution_id", ""))
            if UUID_RE.fullmatch(candidate):
                ids.add(candidate)
    if len(ids) != 1:
        raise ValueError("source_mart_artifact_execution_identity_unknown")
    return ids.pop()


def lookup_execution_id(cloud_execution, operation="deep-coverage"):
    query = ('resource.type="cloud_run_job" AND '
             'labels."run.googleapis.com/execution_name"="' + cloud_execution + '"')
    result = run(["gcloud", "logging", "read", query,
                  "--project=" + PROJECT, "--limit=250", "--format=json"], timeout=80)
    if result.returncode:
        raise ValueError("cloud_logging_exact_execution_read_denied")
    return parse_execution_id(json.loads(result.stdout), cloud_execution, operation)


def object_json(path):
    if not (path.startswith("executions/") or re.fullmatch(r"screening/[a-f0-9]{64}\.json", path)) or ".." in path:
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
    # Private-safe diagnostic: aggregate missing feature names and dates only.
    # Do not output held/watchlisted symbol union or any source financial amounts.
    input_by_symbol = {item["symbol"]: item for item in inputs.get("rows", [])}
    if len(input_by_symbol) != len(inputs.get("rows", [])):
        raise ValueError("duplicate_analyst_input_symbol")
    reasons = {role: Counter() for role in EXPECTED_ROLES}
    missing = {role: Counter() for role in EXPECTED_ROLES}
    input_dates = {role: Counter() for role in EXPECTED_ROLES}
    latest_trades = Counter()
    rejected_counts = Counter()
    for raw in inputs.get("rows", []):
        latest_trades[str(raw.get("latest_trade_date"))] += 1
        rejected_counts[str(raw.get("rejected_input_count"))] += 1
        for role in EXPECTED_ROLES:
            row = raw.get("roles", {}).get(role, {})
            for cause in row.get("reasons", []):
                reasons[role][str(cause)] += 1
            for feature in row.get("missing_features", []):
                missing[role][str(feature)] += 1
            input_dates[role][str(row.get("input_as_of"))] += 1
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
            "input_diagnostics": {
                "missing_features": {k: dict(v) for k,v in missing.items()},
                "reasons": {k: dict(v) for k,v in reasons.items()},
                "input_as_of": {k: dict(v) for k,v in input_dates.items()},
                "latest_trade_dates": dict(latest_trades),
                "rejected_input_counts": dict(rejected_counts),
            },
            "samples": sampled, "owner_login_ui": "NOT_VERIFIED",
            "pg_product_readback": "NOT_VERIFIED",
            "gcp_mutations": 0}



def readback_market_screening(execution_id, cloud_execution):
    """Verify actual ranked rows and gates in the exact GCS-only screening artifact.

    Never read/print owner union or mutate immutable PG Screening products.
    The Cloud Run receipt gives an execution-scoped manifest and a content hash
    pointing to one immutable screening/<64-hex>.json artifact.
    """
    import math
    root = "executions/" + execution_id + "/"
    manifest, manifest_hash = object_json(root + "screening-manifest.json")
    if (manifest.get("execution_id") != execution_id
            or not isinstance(manifest.get("identity_hash"), str)
            or not isinstance(manifest.get("screening"), dict)):
        raise ValueError("market_screening_execution_manifest_invalid")
    reference = manifest["screening"]
    prefix = "gs://" + BUCKET + "/"
    uri = reference.get("artifact_uri", "")
    if not isinstance(uri, str) or not uri.startswith(prefix):
        raise ValueError("market_screening_artifact_uri_untrusted")
    path = uri[len(prefix):]
    if not re.fullmatch(r"screening/[a-f0-9]{64}\.json", path):
        raise ValueError("market_screening_artifact_path_untrusted")
    artifact, artifact_hash = object_json(path)
    identity = artifact.get("identity", {})
    rows = artifact.get("rows")
    telemetry = artifact.get("input_telemetry", {}).get("seq08_quant_rank", {})
    if (reference.get("artifact_hash") != artifact_hash
            or artifact.get("identity_hash") != manifest["identity_hash"]
            or artifact.get("artifact_kind") != "mart_market_screening_v1"
            or not isinstance(identity, dict)
            or not isinstance(rows, list)
            or not isinstance(telemetry, dict)
            or not isinstance(identity.get("analysis_as_of"), str)
            or not identity.get("core_snapshot_id")):
        raise ValueError("market_screening_artifact_hash_or_identity_invalid")
    gates = Counter(str(row.get("seq08_quant_rank_gate", "unknown")) for row in rows)
    if (dict(gates) != telemetry.get("gate_counts")
            or gates.get("ranked", 0) != telemetry.get("ranked_rows")):
        raise ValueError("market_screening_rank_gate_count_mismatch")
    ranked_by_market = Counter()
    public_samples = {code: {"present": False} for code in SAMPLES}
    seen = set()
    for row in rows:
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or symbol in seen:
            raise ValueError("market_screening_duplicate_or_invalid_symbol")
        seen.add(symbol)
        rank = row.get("seq08_quant_rank")
        if rank is not None:
            if (not isinstance(rank, dict)
                    or not isinstance(rank.get("value"), (int, float))
                    or isinstance(rank.get("value"), bool)
                    or not math.isfinite(rank["value"])
                    or not 0 < rank["value"] <= 1
                    or rank.get("cohort_size", 0) < 100
                    or rank.get("market") not in ("twse", "tpex")
                    or rank.get("analysis_as_of") != identity["analysis_as_of"]
                    or rank.get("core_snapshot_id") != identity["core_snapshot_id"]
                    or rank.get("source_trade_date") != row.get("latest_trade_date")
                    or rank.get("source") != "full_market_core_same_day_pct_rank"
                    or row.get("seq08_quant_rank_gate") != "ranked"):
                raise ValueError("market_screening_invalid_full_market_rank")
            ranked_by_market[rank["market"]] += 1
        elif row.get("seq08_quant_rank_gate") == "ranked":
            raise ValueError("market_screening_ranked_gate_has_null")
        if symbol in SAMPLES:
            public_samples[symbol] = {
                "present": True,
                "latest_trade_date": row.get("latest_trade_date"),
                "rank_valid": rank is not None,
                "gate": row.get("seq08_quant_rank_gate"),
                "market": rank.get("market") if isinstance(rank, dict) else None,
            }
    return {
        "scope": "EXACT_ONE_GCS_ONLY_MARKET_SCREENING_READBACK",
        "status": "RANK_READY_PASS" if gates.get("ranked", 0) >= 100
                  else "RANK_NOT_READY_PARTIAL",
        "cloud_run_execution": cloud_execution,
        "mart_execution_id": execution_id,
        "source_application_sha": SOURCE,
        "analysis_as_of": identity["analysis_as_of"],
        "core_snapshot_id": identity["core_snapshot_id"],
        "manifest_sha256": manifest_hash,
        "screening_artifact_sha256": artifact_hash,
        "screening_rows": len(rows),
        "ranked_rows": gates.get("ranked", 0),
        "ranked_by_market": dict(ranked_by_market),
        "gate_counts": dict(gates),
        "samples": public_samples,
        "product_projection": False,
        "pg_product_readback": "UNCHANGED_OLD_SNAPSHOT",
        "owner_login_ui": "NOT_VERIFIED",
        "gcp_mutations": 0,
    }


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
        execution_id = lookup_execution_id(cloud_execution, operation="market-screening")
        phase = "GCS_SCREENING_ARTIFACT"
        result = readback_market_screening(execution_id, cloud_execution)
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
