#!/usr/bin/env python3
"""Exact-GCS-generation Risk model activation/rollback primitive for Actions.

No arbitrary GCS targets, model hashes, branches, service or API calls.
A caller must first verify dev rollout, test evidence and owner approval.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from risk_registry_cas import (ACTIVE_OBJECT, BUCKET, MODEL_SHA256,
                               REQUIRED_PROMOTION_EVIDENCE,
                               canonical, plan_transition,
                               validate_pointer, validate_transition_readback)


def _token():
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True, timeout=20).strip()


def _url(*, upload=False, gen=None):
    obj = quote(ACTIVE_OBJECT, safe="")
    bucket = quote(BUCKET, safe="")
    if upload:
        return (f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
                f"?uploadType=media&name={obj}&ifGenerationMatch={gen}")
    return f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{obj}"


def read_pointer(token):
    endpoint = _url()
    try:
        with urlopen(Request(endpoint,
              headers={"Authorization": "Bearer " + token}), timeout=25) as r:
            metadata = json.load(r)
    except HTTPError as e:
        if e.code == 404:
            return None, 0
        raise
    if metadata.get("bucket") != BUCKET or metadata.get("name") != ACTIVE_OBJECT:
        raise RuntimeError("Risk registry object identity mismatch")
    gen = int(metadata["generation"])
    if gen <= 0:
        raise ValueError("invalid GCS generation")
    with urlopen(Request(endpoint+"?alt=media",
          headers={"Authorization": "Bearer " + token}), timeout=25) as r:
        raw = r.read()
    pointer = json.loads(raw)
    validate_pointer(pointer)
    if raw != canonical(pointer):
        raise ValueError("noncanonical Risk pointer bytes")
    return pointer, gen


def apply(mode, source_sha, evidence):
    if (os.getenv("GITHUB_REF") != "refs/heads/main"
            or os.getenv("RISK_ACTIVE_APPROVED") != "true"
            or os.getenv("GCP_PROJECT_ID") != "gen-lang-client-0593591102"):
        raise PermissionError("Risk publication requires approved main/dev workflow")
    if mode not in ("ACTIVE", "DETERMINISTIC"):
        raise ValueError("invalid Risk promotion mode")
    token = _token()
    prior, generation = read_pointer(token)
    proof = evidence if mode == "ACTIVE" else {}
    plan = plan_transition(current=prior, current_generation=generation,
        expected_previous_sha256=prior.get("model_sha256") if prior else None,
        candidate_sha256=MODEL_SHA256, source_sha=source_sha,
        proof=proof, approved=True, activate=(mode=="ACTIVE"))
    value = canonical(plan["next"])
    req = Request(_url(upload=True, gen=generation), data=value, method="POST",
        headers={"Authorization": "Bearer "+token, "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=40) as response:
            metadata = json.load(response)
    except HTTPError as e:
        if e.code in (409, 412):
            raise RuntimeError("Risk registry CAS generation conflict") from None
        raise
    next_generation = int(metadata["generation"])
    after, observed_generation = read_pointer(token)
    if observed_generation != next_generation:
        raise RuntimeError("Risk registry readback generation drift")
    validate_transition_readback(plan, after, observed_generation)
    return {
        "status": "PASS", "registry_mode": mode,
        "previous_mode": prior["mode"] if prior else "DETERMINISTIC",
        "previous_generation": generation,
        "generation": observed_generation,
        "model_version": after.get("model_version"), "model_sha256": after.get("model_sha256"),
        "source_git_sha": source_sha,
        "pointer_sha256": sha256(canonical(after)).hexdigest(),
        "service_activated": False, "api_activated": False,
    }


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--mode", choices=("ACTIVE","DETERMINISTIC"), required=True)
    cli.add_argument("--source-sha", required=True)
    cli.add_argument("--evidence", type=Path, required=True)
    cli.add_argument("--receipt", type=Path, required=True)
    args=cli.parse_args()
    if args.mode == "ACTIVE":
        evidence=json.loads(args.evidence.read_text())
        if set(evidence) != set(REQUIRED_PROMOTION_EVIDENCE):
            raise ValueError("promotion proof shape mismatch")
    else:
        evidence={}
    receipt=apply(args.mode, args.source_sha, evidence)
    args.receipt.write_text(json.dumps(receipt, sort_keys=True)+"\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
