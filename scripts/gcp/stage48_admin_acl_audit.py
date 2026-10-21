"""STAGE-48H: bounded, read-only IAM diagnosis of the Admin GCS metadata scan.

Print only permission role summaries. Never print tokens, raw GCS responses,
object names, other principals, Owner data or secrets. No IAM/storage mutations.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
BUCKETS = (
    PROJECT + "-dev-stage",
    PROJECT + "-dev-core",
    PROJECT + "-dev-mart",
    PROJECT + "-dev-private",
    PROJECT + "-dev-research-big-move-500",
    PROJECT + "-cloudbuild-regional",
)


def read(*args: str) -> tuple[dict | list | None, str]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=40)
    except (OSError, subprocess.TimeoutExpired):
        return None, "COMMAND_UNAVAILABLE"
    if result.returncode != 0:
        message = result.stderr.lower()
        if "permission" in message or "403" in message or "denied" in message:
            return None, "IAM_DENIED"
        if "not found" in message or "404" in message:
            return None, "NOT_FOUND"
        return None, "READ_ERROR"
    try:
        return json.loads(result.stdout), "OK"
    except (ValueError, TypeError):
        return None, "JSON_UNAVAILABLE"


def main() -> None:
    request = json.loads(Path("ops/finops-stage48-admin-acl-audit.json").read_text())
    if (request.get("intent") != "stage48-admin-readonly-acl"
            or request.get("no_gcp_mutation") is not True
            or request.get("no_owner_mutation") is not True
            or request.get("project") != PROJECT):
        raise ValueError("unapproved_admin_acl_audit")
    service, service_status = read(
        "gcloud", "run", "services", "describe", "janus-api",
        "--project=" + PROJECT, "--region=" + REGION, "--format=json")
    if not isinstance(service, dict):
        print(json.dumps({"status": "BLOCKED", "stage": "service_read",
                          "read_status": service_status, "writes": 0}))
        return
    spec = service.get("spec") or {}
    tmpl = (spec.get("template") or {}).get("spec") or {}
    principal = tmpl.get("serviceAccountName")
    if not principal:
        principal = ((service.get("template") or {}).get("serviceAccount") or "")
    if not isinstance(principal, str) or not principal.endswith(".gserviceaccount.com"):
        print(json.dumps({"status": "BLOCKED", "stage": "service_account_identity_unknown",
                          "service_metadata": "READABLE", "writes": 0}))
        return
    member = "serviceAccount:" + principal
    project_policy, project_status = read("gcloud", "projects", "get-iam-policy", PROJECT,
                                          "--format=json")
    project_roles = sorted({p.get("role") for p in
                            ((project_policy or {}).get("bindings") or [])
                            if member in p.get("members", []) and isinstance(p.get("role"), str)})
    rows = []
    for bucket in BUCKETS:
        policy, status = read("gcloud", "storage", "buckets", "get-iam-policy",
                              "gs://" + bucket, "--format=json")
        roles = sorted({p.get("role") for p in ((policy or {}).get("bindings") or [])
                        if member in p.get("members", []) and isinstance(p.get("role"), str)})
        rows.append({"bucket": bucket, "iam_policy_read": status,
                     "direct_api_sa_roles": roles})
    print(json.dumps({"component": "stage48-admin-acl-readonly", "status": "OBSERVED",
                      "api_sa": principal, "project_iam_read": project_status,
                      "project_api_sa_roles": project_roles, "buckets": rows,
                      "writes": 0, "bucket_payload_get": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
