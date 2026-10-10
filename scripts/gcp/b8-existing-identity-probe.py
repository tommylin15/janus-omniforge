#!/usr/bin/env python3
"""B8 read-only catalog pointer probe under existing dev identities; no IAM writes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
CATALOG = "janus_core_dev"
NAMESPACE = "b2_core_fixed_20261007"
CORE_URI = "gs://gen-lang-client-0593591102-dev-core/executions/17b091be-c454-4fea-b5de-b16c0a9c8c6c/core-snapshot.json"
CORE_SHA256 = "8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8"
CORE_ID = "sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab"
CORE_TABLES = ("ohlcv_v1", "benchmark_v1")
DEV_JOBS = ("janus-intelligence-mart", "janus-ingestion-core", "janus-batch-controller")
DEV_SERVICES = ("janus-api",)
SA_RE = re.compile(r"^[a-z0-9-]+@" + re.escape(PROJECT) + r"\.iam\.gserviceaccount\.com$")


def command(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    # Never print raw stdout/stderr: access tokens, IAM diagnostics or private env can leak.
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False, timeout=timeout)


def identity_from_resource(payload: dict) -> str | None:
    """Only a configured same-project service account is an allowed probe candidate."""
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("serviceAccountName", "service_account") and isinstance(v, str):
                    found.append(v)
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload.get("spec", {}))
    walk(payload.get("template", {}))
    unique = sorted(set(found))
    return unique[0] if len(unique) == 1 and SA_RE.fullmatch(unique[0]) else None


def metadata_location(value):
    if isinstance(value, dict):
        for k in ("metadata-location", "metadata_location", "metadataLocation"):
            if isinstance(value.get(k), str):
                return value[k]
        for v in value.values():
            result = metadata_location(v)
            if result:
                return result
    return None


def safe_code(error):
    if isinstance(error, urllib.error.HTTPError):
        return "HTTP_" + str(error.code)
    if isinstance(error, TimeoutError):
        return "TIMEOUT"
    return "UNVERIFIED"


def catalog_check(token: str, manifest: dict) -> dict:
    """Zero BigQuery queries: two BigLake Iceberg REST table metadata GETs."""
    result = {"status": "unverified", "pointers": {}}
    for table in CORE_TABLES:
        url = ("https://biglake.googleapis.com/iceberg/v1/restcatalog/v1/"
               f"projects/{PROJECT}/catalogs/{CATALOG}/namespaces/{NAMESPACE}/tables/{table}")
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.load(response)
            matched = metadata_location(data) == manifest["iceberg_tables"][f"core.{table}"]["metadata_location"]
            result["pointers"][table] = "MATCH" if matched else "MISMATCH"
            if not matched:
                result["status"] = "snapshot_drift"
                return result
        except Exception as exc:
            result["pointers"][table] = safe_code(exc)
            result["status"] = "blocked"
            return result
    result["status"] = "pass"
    return result


def main(output: Path) -> int:
    e = {
        "schema_version": "b8-existing-identity-readback-v1",
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "existing GitHub WIF / Cloud Run dev service-account config",
        "no_iam_changes": True, "no_new_workloads": True,
        "no_bigquery_jobs": True, "no_model_retrain": True,
        "default": "pyiceberg", "cutover": False,
        "core_fence": CORE_ID,
        "manifest_raw_sha256": CORE_SHA256,
        "status": "blocked", "runtime_resources": [],
        "identities": [], "validated_identity": None,
    }
    try:
        core = command("gcloud", "storage", "cat", CORE_URI)
        if core.returncode != 0 or hashlib.sha256(core.stdout).hexdigest() != CORE_SHA256:
            e["status"] = "frozen_core_unreadable_or_drifted"
            return 2
        manifest = json.loads(core.stdout)
        if manifest.get("snapshot_id") != CORE_ID:
            e["status"] = "frozen_core_unreadable_or_drifted"
            return 2

        candidates = []
        for kind, names in (("jobs", DEV_JOBS), ("services", DEV_SERVICES)):
            for name in names:
                cmd = ("gcloud", "run", kind, "describe", name,
                       "--project=" + PROJECT, "--region=" + REGION, "--format=json")
                try:
                    proc = command(*cmd)
                    data = json.loads(proc.stdout) if proc.returncode == 0 else {}
                    sa = identity_from_resource(data)
                    result = "CONFIG_READ" if proc.returncode == 0 else "CONFIG_UNREADABLE"
                except (ValueError, subprocess.TimeoutExpired):
                    sa = None
                    result = "CONFIG_UNVERIFIED"
                e["runtime_resources"].append({"kind": kind, "name": name,
                                               "config": result, "service_account": sa})
                if sa and sa not in candidates:
                    candidates.append(sa)

        # Same WIF service account that already failed the B8 catalog preflight.
        try:
            ci = command("gcloud", "auth", "print-access-token")
            if ci.returncode != 0 or not ci.stdout.strip():
                e["identities"].append({"source": "github-ci-wif", "status": "TOKEN_UNAVAILABLE"})
            else:
                checked = catalog_check(ci.stdout.decode().strip(), manifest)
                e["identities"].append({"source": "github-ci-wif", "catalog": checked})
                if checked["status"] == "pass":
                    e["validated_identity"] = "github-ci-wif"
                    e["status"] = "pass"
                    return 0
        except (ValueError, subprocess.TimeoutExpired):
            e["identities"].append({"source": "github-ci-wif", "status": "TOKEN_UNVERIFIED"})

        # No new permissions: delegation succeeds only if caller ALREADY has
        # iam.serviceAccounts.getAccessToken for the named runtime principal.
        for sa in candidates:
            try:
                proc = command("gcloud", "auth", "print-access-token",
                               "--impersonate-service-account=" + sa)
                if proc.returncode != 0 or not proc.stdout.strip():
                    e["identities"].append({"source": "existing-cloud-run-sa",
                                            "principal": sa, "delegation": "DENIED_OR_UNAVAILABLE",
                                            "catalog": "NOT_TESTED"})
                    continue
                checked = catalog_check(proc.stdout.decode().strip(), manifest)
                e["identities"].append({"source": "existing-cloud-run-sa", "principal": sa,
                                        "delegation": "EXISTING_PERMISSION", "catalog": checked})
                if checked["status"] == "pass":
                    e["validated_identity"] = sa
                    e["status"] = "pass"
                    return 0
            except (ValueError, subprocess.TimeoutExpired):
                e["identities"].append({"source": "existing-cloud-run-sa",
                                        "principal": sa, "delegation": "UNVERIFIED", "catalog": "NOT_TESTED"})
        return 2
    finally:
        output.write_text(json.dumps(e, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                          encoding="utf-8")
        print(json.dumps({"B8_EXISTING_IDENTITY": e["status"],
                          "resource_accounts": len({x.get("service_account") for x in e["runtime_resources"] if x.get("service_account")}),
                          "identity_paths_tested": len(e["identities"]),
                          "validated_identity": e["validated_identity"],
                          "no_iam_changes": True, "no_bigquery_jobs": True}, sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: b8-existing-identity-probe.py OUTPUT_JSON")
    raise SystemExit(main(Path(sys.argv[1])))
