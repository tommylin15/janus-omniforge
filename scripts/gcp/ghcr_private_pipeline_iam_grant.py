#!/usr/bin/env python3
"""Grant narrowly scoped actAs to the existing dev CI deployer on ONE runtime SA.

Requires an explicit request and service-account IAM policy editor privileges
on that single service account. Never uses project-wide add-iam-policy-binding.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import ghcr_jobs_rollout as rollout

EXPECTED_PROJECT = "gen-lang-client-0593591102"
TARGET_JOB = "janus-private-pipeline"
ROLE = "roles/iam.serviceAccountUser"
REQUEST = Path("ops/ghcr-private-pipeline-iam-grant-request.json")


def require_request():
    data = json.loads(REQUEST.read_text())
    if (data.get("intent") != "grant-existing-private-pipeline-runtime-actas"
            or data.get("approved") is not True
            or data.get("project") != EXPECTED_PROJECT
            or data.get("job") != TARGET_JOB
            or data.get("role") != ROLE
            or data.get("scope") != "runtime-service-account-only"):
        raise ValueError("iam_grant_request_invalid")


def identity():
    if rollout.PROJECT != EXPECTED_PROJECT:
        raise ValueError("project_drift")
    runtime = rollout.job(TARGET_JOB)["template"]["template"].get("serviceAccount")
    ci = os.environ.get("GCP_CI_SERVICE_ACCOUNT", "")
    if not isinstance(runtime, str) or not re.fullmatch(
            r"[a-zA-Z0-9._-]+@" + re.escape(EXPECTED_PROJECT) + r"\.iam\.gserviceaccount\.com", runtime):
        raise ValueError("runtime_service_account_outside_project")
    if not re.fullmatch(
            r"[a-zA-Z0-9._-]+@" + re.escape(EXPECTED_PROJECT) + r"\.iam\.gserviceaccount\.com", ci):
        raise ValueError("ci_service_account_outside_project")
    if runtime == ci:
        raise ValueError("self_grant_not_allowed")
    return runtime, ci


def permissions(runtime, needed):
    token = rollout.command(["gcloud", "auth", "print-access-token"]).strip()
    url = ("https://iam.googleapis.com/v1/projects/-/serviceAccounts/"
           + quote(runtime, safe="@.-") + ":testIamPermissions")
    req = Request(url, data=json.dumps({"permissions": sorted(needed)}).encode(),
                  method="POST", headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=35) as response:
            return set(json.load(response).get("permissions", []))
    except (HTTPError, URLError, ValueError) as error:
        raise RuntimeError("iam_permission_selftest_unknown") from None


def apply(runtime, ci):
    member = "serviceAccount:" + ci
    # Scope is only the target runtime service account, NEVER the project.
    cmd = ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", runtime,
           "--project=" + EXPECTED_PROJECT, "--member=" + member,
           "--role=" + ROLE, "--condition=None", "--quiet"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    if result.returncode != 0:
        # Never print gcloud raw output (might expose identities or metadata).
        raise RuntimeError("service_account_policy_binding_failed")


def run(receipt):
    output = {"mode": "scoped_service_account_iam", "job": TARGET_JOB,
              "role": ROLE, "project": EXPECTED_PROJECT, "gcp_policy_write": False,
              "result": "BLOCKED"}
    def save():
        receipt.write_text(json.dumps(output, sort_keys=True) + "\n")
    try:
        require_request()
        runtime, ci = identity()
        existing = permissions(runtime, {"iam.serviceAccounts.actAs"})
        if "iam.serviceAccounts.actAs" not in existing:
            must = {"iam.serviceAccounts.getIamPolicy", "iam.serviceAccounts.setIamPolicy"}
            if not must.issubset(permissions(runtime, must)):
                raise RuntimeError("policy_editor_permission_missing")
            apply(runtime, ci)
            output["gcp_policy_write"] = True
        if "iam.serviceAccounts.actAs" not in permissions(runtime, {"iam.serviceAccounts.actAs"}):
            raise RuntimeError("actas_readback_failed")
        output["result"] = "PASS"
        save()
        return 0
    except Exception as err:
        output["error_type"] = type(err).__name__
        safe = str(err)
        output["reason"] = safe if re.fullmatch(r"[a-z][a-z0-9_]{3,90}", safe) else "control_failure"
        save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    return run(parser.parse_args().receipt)


if __name__ == "__main__":
    sys.exit(main())
