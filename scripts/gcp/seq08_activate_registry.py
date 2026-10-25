"""SEQ-08: single create-only ACTIVE pointer for the five approved Dev heads.

Never overwrites/deletes candidate bytes, old pointers, Core, PG or Owner data.
The serving runtime is already released; this command only activates its exact
frozen contract after GitHub, GCS SHA and native XGBoost gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-mart"
POINTER = "models/registry/seq08-four-models-active.json"
RELEASE_SHA = "a2881c5c2532beb5570e29a1fda4472c7bb0d448"
RELEASE_RUN = "40184318031"
JOBS_RUN = "40184957380"
API_RUN = "40192646498"
MAX_MODEL_BYTES = 20 * 1024 * 1024


def command(args, timeout=90):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False, timeout=timeout)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_request():
    requested = read_json("ops/seq08-model-activation-request.json")
    if (requested.get("intent") != "seq08-activate-five-real-heads"
            or requested.get("approved") is not True
            or requested.get("apply") is not True
            or requested.get("scope") != "existing-dev-mart-single-atomic-pointer"
            or requested.get("source_sha") != RELEASE_SHA
            or requested.get("release_run") != RELEASE_RUN
            or requested.get("jobs_run") != JOBS_RUN
            or requested.get("api_run") != API_RUN
            or requested.get("allow_old_model_fallback") is not False
            or requested.get("no_new_resources") is not True):
        raise ValueError("seq08_registry_request_mismatch")
    if (read_json("ops/ghcr-api-only-promote-request.json").get("source_sha") != RELEASE_SHA
            or read_json("ops/ghcr-jobs-rollout-request.json").get("sha") != RELEASE_SHA
            or read_json("ops/ghcr-candidate-request.json").get("sha") != RELEASE_SHA):
        raise ValueError("released_runtime_source_contract_mismatch")
    return requested


def github_gate(run, required_job, *, expected_sha=None):
    result = command(["gh", "run", "view", run,
                      "--json", "status,conclusion,headSha,jobs"], timeout=45)
    if result.returncode:
        raise ValueError("github_gate_readback_failed")
    data = json.loads(result.stdout)
    matching = [j for j in data.get("jobs", []) if j.get("name") == required_job
                and j.get("status") == "completed" and j.get("conclusion") == "success"]
    if (data.get("status") != "completed" or data.get("conclusion") != "success"
            or len(matching) != 1
            or expected_sha is not None and data.get("headSha") != expected_sha):
        raise ValueError("github_gate_not_successful")


def gcs_read(name):
    uri = f"gs://{BUCKET}/{name}"
    result = command(["gcloud", "storage", "cat", uri, "--project", PROJECT], timeout=100)
    if result.returncode == 0:
        return result.stdout
    message = result.stderr.decode("utf-8", "replace").lower()
    if any(phrase in message for phrase in
           ("404", "not found", "does not exist", "no urls matched",
            "matched no objects", "no objects matched")):
        return None
    raise ValueError("gcs_read_error_not_missing")


def verify_five_heads(pointer):
    from xgboost import Booster
    heads = pointer["heads"]
    if set(heads) != {"quant", "risk", "fundamental", "valuation_pe", "valuation_pb"}:
        raise ValueError("incomplete_five_head_pointer")
    for head, desc in sorted(heads.items()):
        path = desc["model_path"]
        role = desc["role"]
        if (not path.startswith(f"models/candidates/{role}/") or ".." in path
                or not path.endswith(f"/{head}/model.ubj")):
            raise ValueError("unapproved_candidate_path")
        blob = gcs_read(path)
        if (not blob or len(blob) > MAX_MODEL_BYTES
                or hashlib.sha256(blob).hexdigest() != desc["model_sha256"]):
            raise ValueError("candidate_model_sha256_mismatch")
        model = Booster()
        model.load_model(bytearray(blob))
        order = desc["feature_order"]
        if (model.num_features() != len(order)
                or model.feature_names is not None and model.feature_names != order):
            raise ValueError("candidate_model_feature_mismatch")
    return len(heads)


def activate(*, apply, writer=None):
    from intelligence_mart.seq08_native_serving import expected_pointer, validate_pointer
    gate_request()
    github_gate(RELEASE_RUN, "release-verify", expected_sha=RELEASE_SHA)
    github_gate(JOBS_RUN, "jobs-rollout")
    github_gate(API_RUN, "promote-api-only")
    pointer = expected_pointer()
    validate_pointer(pointer)
    total = verify_five_heads(pointer)
    desired = json.dumps(pointer, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    current = gcs_read(POINTER)
    if current is not None:
        if current != desired:
            raise ValueError("active_pointer_conflict_no_overwrite")
        state = "EXISTS_IDENTICAL_SHA_VERIFIED"
    elif not apply:
        state = "PREFLIGHT_NO_MUTATION"
    else:
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "seq08-pointer.json"
            file.write_bytes(desired)
            result = (writer or command)(["gcloud", "storage", "cp", str(file),
                f"gs://{BUCKET}/{POINTER}", "--if-generation-match=0",
                "--project", PROJECT], timeout=100)
            if result.returncode:
                raise ValueError("atomic_create_only_failed")
        if gcs_read(POINTER) != desired:
            raise ValueError("active_pointer_readback_mismatch")
        state = "CREATE_ONLY_ACTIVE_SHA_READBACK_PASS"
    return {"status": state, "release_source_sha": RELEASE_SHA, "five_head_sha_verified": total,
            "pointer_sha256": hashlib.sha256(desired).hexdigest(),
            "candidate_mutations": 0, "owner_mutations": 0, "pg_mutations": 0,
            "api_traffic_mutations": 0, "new_resources": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = activate(apply=args.apply)
        args.receipt.write_text(json.dumps(output, sort_keys=True))
        print(json.dumps(output, sort_keys=True))
        return 0
    except Exception as error:
        failure = {"status": "BLOCKED", "reason": str(error)
                   if isinstance(error, ValueError) else type(error).__name__,
                   "gcs_active_write_verified": False}
        args.receipt.write_text(json.dumps(failure, sort_keys=True))
        print(json.dumps(failure, sort_keys=True))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
