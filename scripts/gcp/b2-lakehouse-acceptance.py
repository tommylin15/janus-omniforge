#!/usr/bin/env python3
"""B2 Lakehouse shared-catalog live acceptance.

Runs only against the existing Janus dev project. It keeps PyIceberg as the
default reader and proves the remaining B2 compatibility gates with a hard
1 GiB cumulative BigQuery billed-byte budget and 60 second per-query timeout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

PROJECT = "gen-lang-client-0593591102"
LOCATION = "US"
CATALOG = "janus_core_dev"
CORE_NAMESPACE = "b2_core_fixed_20261007"
ACCEPT_NAMESPACE = "b2_acceptance"
CORE_BUCKET = "gen-lang-client-0593591102-dev-core"
MART_BUCKET = "gen-lang-client-0593591102-dev-mart"
CORE_MANIFEST_URI = (
    "gs://gen-lang-client-0593591102-dev-core/"
    "executions/17b091be-c454-4fea-b5de-b16c0a9c8c6c/core-snapshot.json"
)
CORE_MANIFEST_SHA256 = "8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8"
CORE_SNAPSHOT_ID = "sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab"
BUDGET = 1_073_741_824
QUERY_TIMEOUT_SECONDS = 60
TABLES = {
    "core.benchmark_v1": "benchmark_v1",
    "core.ohlcv_v1": "ohlcv_v1",
    "core.financials_v1": "financials_v1",
}


def run(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    if os.name == "nt" and args[0] == "gcloud":
        args = ("gcloud.cmd", *args[1:])
    proc = subprocess.run(
        list(args),
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and proc.returncode:
        raise RuntimeError(
            f"command failed rc={proc.returncode}: {' '.join(args)}\n"
            f"{proc.stderr[-4000:] if proc.stderr else ''}"
        )
    return proc


def token() -> str:
    """Return a Cloud Platform access token without logging credential material."""
    if shutil.which("gcloud"):
        proc = run("gcloud", "auth", "print-access-token", check=False)
        value = (proc.stdout or "").strip()
        if proc.returncode == 0 and value:
            return value
    import google.auth
    from google.auth.transport.requests import Request
    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    credentials.refresh(Request())
    value = str(credentials.token or "").strip()
    if not value:
        raise RuntimeError("unable to obtain Google Cloud access token")
    return value


def api_json(method: str, url: str, *, body: dict[str, Any] | None = None,
             access_token: str | None = None, timeout: int = 65) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token or token()}"}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:8000]
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(raw or b"{}")


def gcs_json(uri: str) -> tuple[dict[str, Any], str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.startswith("/"):
        raise ValueError("expected gs:// object URI")
    object_name = parsed.path.lstrip("/")
    url = (
        "https://storage.googleapis.com/download/storage/v1/b/"
        f"{urllib.parse.quote(parsed.netloc, safe='')}/o/"
        f"{urllib.parse.quote(object_name, safe='')}?alt=media"
    )
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token()}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=65) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:8000]
        raise RuntimeError(f"GET {uri} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def ensure_catalog() -> dict[str, Any]:
    # The billable dev catalog is created by the separately-audited bootstrap.
    # Live acceptance must never silently create or replace it.
    desc = run(
        "gcloud", "biglake", "iceberg", "catalogs", "describe", CATALOG,
        f"--project={PROJECT}", "--format=json", check=False,
    )
    if desc.returncode:
        raise RuntimeError("authorized Lakehouse catalog is missing or unreadable")
    payload = json.loads(desc.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    if CORE_BUCKET not in serialized:
        raise RuntimeError("catalog readback does not prove dev-core default location")
    if '"us"' not in serialized and ': "us"' not in serialized:
        raise RuntimeError("catalog readback does not prove US primary location")
    if "end-user" not in serialized and "end_user" not in serialized:
        raise RuntimeError("catalog readback does not prove end-user credential mode")
    return {"created": False, "readback": payload}


def ensure_namespace(name: str, location: str) -> None:
    probe = run(
        "gcloud", "biglake", "iceberg", "namespaces", "describe", name,
        f"--project={PROJECT}", f"--catalog={CATALOG}", "--format=json", check=False,
    )
    if probe.returncode:
        run(
            "gcloud", "biglake", "iceberg", "namespaces", "create", name,
            f"--project={PROJECT}", f"--catalog={CATALOG}",
            f"--properties=location={location}", "--quiet",
        )


def load_table(table: str, namespace: str) -> dict[str, Any]:
    url = (
        "https://biglake.googleapis.com/iceberg/v1/restcatalog/v1/"
        f"projects/{PROJECT}/catalogs/{CATALOG}/namespaces/{namespace}/tables/{table}"
    )
    return api_json("GET", url)


def metadata_location(payload: dict[str, Any]) -> str:
    for key in ("metadata-location", "metadata_location", "metadataLocation"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    for value in payload.values():
        if isinstance(value, dict):
            found = metadata_location(value)
            if found:
                return found
    return ""


def current_schema(metadata: dict[str, Any]) -> dict[str, Any]:
    sid = metadata["current-schema-id"]
    return next(s for s in metadata["schemas"] if s["schema-id"] == sid)


def field_type(schema: dict[str, Any], name: str) -> Any:
    return next(f["type"] for f in schema["fields"] if f["name"] == name)


class BigQueryBudget:
    def __init__(self, journal: Path) -> None:
        self.journal = journal
        self.jobs = json.loads(journal.read_text()) if journal.exists() else []
        if any(job.get("billed_bytes") is None for job in self.jobs):
            raise RuntimeError("prior query billed bytes unknown; read back job before resuming")
        self.billed = sum(job["billed_bytes"] for job in self.jobs)

    @property
    def remaining(self) -> int:
        return BUDGET - self.billed

    def query(self, sql: str, label: str) -> dict[str, Any]:
        if self.remaining <= 0:
            raise RuntimeError("B2 execution byte budget exhausted before query")
        access_token = token()
        request_id = str(uuid.uuid4())
        url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/queries"
        body = {
            "query": sql,
            "useLegacySql": False,
            "useQueryCache": False,
            "location": LOCATION,
            "maximumBytesBilled": str(self.remaining),
            "timeoutMs": QUERY_TIMEOUT_SECONDS * 1000,
            "jobTimeoutMs": str(QUERY_TIMEOUT_SECONDS * 1000),
            "requestId": request_id,
            "labels": {"janus_gate": "b2", "janus_probe": label[:63].lower().replace("_", "-")},
        }
        started = time.monotonic()
        response = api_json("POST", url, body=body, access_token=access_token,
                            timeout=QUERY_TIMEOUT_SECONDS + 5)
        ref = response.get("jobReference") or {}
        job_id = ref.get("jobId")
        if not job_id:
            raise RuntimeError("BigQuery query did not return a job reference")
        self.jobs.append({"label": label, "job_id": job_id, "billed_bytes": None})
        self.journal.write_text(json.dumps(self.jobs, indent=2) + "\n", newline="\n")
        while not response.get("jobComplete"):
            if time.monotonic() - started >= QUERY_TIMEOUT_SECONDS:
                cancel_url = (
                    f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/jobs/"
                    f"{job_id}/cancel?location={urllib.parse.quote(LOCATION)}"
                )
                try:
                    api_json("POST", cancel_url, body={}, access_token=access_token, timeout=10)
                finally:
                    raise TimeoutError(f"BigQuery query exceeded {QUERY_TIMEOUT_SECONDS}s")
            result_url = (
                f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/queries/{job_id}"
                f"?location={urllib.parse.quote(LOCATION)}&timeoutMs=5000"
            )
            response = api_json("GET", result_url, access_token=access_token, timeout=10)

        job_url = (
            f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/jobs/{job_id}"
            f"?location={urllib.parse.quote(LOCATION)}"
        )
        job = api_json("GET", job_url, access_token=access_token)
        status = job.get("status") or {}
        query_stats = (job.get("statistics") or {}).get("query") or {}
        billed_raw = query_stats.get("totalBytesBilled")
        if billed_raw is None:
            raise RuntimeError("BigQuery billed bytes unknown; B2 fails closed")
        billed = int(billed_raw)
        processed_raw = query_stats.get("totalBytesProcessed")
        processed = int(processed_raw) if processed_raw is not None else None
        self.billed += billed
        if self.billed > BUDGET:
            raise RuntimeError("BigQuery cumulative billed bytes exceeded 1 GiB")
        evidence = {
            "label": label,
            "job_id": job_id,
            "billed_bytes": billed,
            "processed_bytes": processed,
            "elapsed_seconds": time.monotonic() - started,
            "cumulative_billed_bytes": self.billed,
            "remaining_budget_bytes": self.remaining,
        }
        self.jobs[-1] = evidence
        self.journal.write_text(json.dumps(self.jobs, indent=2) + "\n", newline="\n")
        if status.get("errorResult"):
            raise RuntimeError(f"BigQuery job failed: {status['errorResult']}")
        return {"response": response, "job": job, "evidence": evidence}


def row_values(response: dict[str, Any]) -> list[list[Any]]:
    rows = response.get("rows") or []
    return [[cell.get("v") for cell in row.get("f", [])] for row in rows]


def prove_core_pruning(evidence: dict[str, Any], budget: BigQueryBudget) -> None:
    fence = evidence["shared_catalog_mapping"]["core.ohlcv_v1"]
    expected_uri = fence["metadata_location"]
    def check_pointer() -> None:
        if metadata_location(load_table("ohlcv_v1", CORE_NAMESPACE)) != expected_uri:
            raise RuntimeError("Core catalog pointer changed during pruning probe")
    check_pointer()
    fq = f"`{PROJECT}.{CATALOG}.{CORE_NAMESPACE}.ohlcv_v1`"
    results = []
    for label, start in (("core_partition_narrow", "2026-10-01"),
                         ("core_partition_wide", "2026-01-01")):
        results.append(budget.query(
            f"SELECT COUNT(*), SUM(LENGTH(close)) FROM {fq} "
            f"WHERE symbol = '2330' AND trade_date BETWEEN DATE '{start}' AND DATE '2026-10-06'",
            label,
        ))
    check_pointer()
    narrow, wide = [r["evidence"]["processed_bytes"] for r in results]
    passed = isinstance(narrow, int) and isinstance(wide, int) and 0 < narrow < wide
    evidence["core_partition_pruning"] = {
        "table": "core.ohlcv_v1", "snapshot_id": fence["snapshot_id"],
        "metadata_location": expected_uri, "symbol": "2330",
        "narrow_date_bounds": ["2026-10-01", "2026-10-06"],
        "wide_date_bounds": ["2026-01-01", "2026-10-06"],
        "narrow_processed_bytes": narrow, "wide_processed_bytes": wide,
        "narrow_result": row_values(results[0]["response"]),
        "wide_result": row_values(results[1]["response"]), "pass": passed,
    }
    evidence["bigquery_jobs"] = budget.jobs
    evidence["total_billed_bytes"] = budget.billed
    evidence["remaining_budget_bytes"] = budget.remaining
    if not passed:
        raise RuntimeError(f"Core partition pruning not proven: {narrow}, {wide}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-shared-mapping", action="store_true")
    parser.add_argument("--core-pruning-only", action="store_true")
    args = parser.parse_args()

    if args.core_pruning_only:
        evidence = json.loads(args.output.read_text())
        if evidence.get("core_snapshot_id") != CORE_SNAPSHOT_ID or evidence.get("manifest_sha256") != CORE_MANIFEST_SHA256:
            raise RuntimeError("prior acceptance evidence has a different Core fence")
        if not evidence.get("schema_evolution_native_decimal", {}).get("pass") or set(evidence["shared_catalog_mapping"]) != set(TABLES):
            raise RuntimeError("Core-only resume requires completed mapping and decimal gates")
        budget = BigQueryBudget(args.output.with_suffix(".jobs.json"))
        evidence["status"] = "partial"
        try:
            prove_core_pruning(evidence, budget)
            evidence["status"] = "pass"
        finally:
            args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", newline="\n")
        print(json.dumps(evidence["core_partition_pruning"]))
        return

    manifest, manifest_hash = gcs_json(CORE_MANIFEST_URI)
    if manifest_hash != CORE_MANIFEST_SHA256:
        raise RuntimeError("fixed B0 Core manifest hash mismatch")
    if manifest.get("snapshot_id") != CORE_SNAPSHOT_ID:
        raise RuntimeError("fixed B0 Core identity mismatch")

    evidence: dict[str, Any] = {
        "status": "running",
        "project": PROJECT,
        "location": LOCATION,
        "catalog_primary_location": LOCATION,
        "storage_bucket_region": "us-central1",
        "catalog": CATALOG,
        "pyiceberg_default_unchanged": True,
        "storage_read_api_used": False,
        "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
        "execution_byte_budget": BUDGET,
        "core_snapshot_id": CORE_SNAPSHOT_ID,
        "manifest_sha256": manifest_hash,
        "shared_catalog_mapping": {},
    }

    evidence["catalog_readback"] = ensure_catalog()
    ensure_namespace(ACCEPT_NAMESPACE, f"gs://{MART_BUCKET}/acceptance/b2-lakehouse")

    if args.skip_shared_mapping:
        evidence["shared_catalog_mapping_skipped"] = True
    else:
        ensure_namespace(CORE_NAMESPACE, f"gs://{CORE_BUCKET}")
        # Shared catalog exact-snapshot mapping: register exactly the three immutable
        # B0 metadata files and then independently prove the catalog pointer and the
        # metadata's current-snapshot-id.
        for identifier, table_name in TABLES.items():
            fence = manifest["iceberg_tables"][identifier]
            uri = fence["metadata_location"]
            snapshot_id = fence["snapshot_id"]
            existing = run(
                "gcloud", "biglake", "iceberg", "tables", "describe", table_name,
                f"--project={PROJECT}", f"--catalog={CATALOG}",
                f"--namespace={CORE_NAMESPACE}", "--format=json", check=False,
            )
            if existing.returncode:
                run(
                    "gcloud", "biglake", "iceberg", "tables", "register", table_name,
                    f"--project={PROJECT}", f"--catalog={CATALOG}", f"--namespace={CORE_NAMESPACE}",
                    f"--metadata-location={uri}", "--quiet",
                )
            loaded = load_table(table_name, CORE_NAMESPACE)
            catalog_uri = metadata_location(loaded)
            metadata, metadata_hash = gcs_json(uri)
            catalog_match = catalog_uri == uri
            snapshot_match = metadata.get("current-snapshot-id") == snapshot_id
            if not catalog_match or not snapshot_match or metadata.get("format-version") != 2:
                raise RuntimeError(f"shared catalog exact-snapshot mapping failed: {identifier}")
            evidence["shared_catalog_mapping"][identifier] = {
                "table": table_name,
                "metadata_location": uri,
                "catalog_metadata_location": catalog_uri,
                "metadata_sha256": metadata_hash,
                "snapshot_id": snapshot_id,
                "catalog_pointer_exact": catalog_match,
                "snapshot_exact": snapshot_match,
                "format_version": metadata.get("format-version"),
            }

    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", newline="\n")
    budget = BigQueryBudget(args.output.with_suffix(".jobs.json"))

    # Create a tiny research/acceptance Iceberg table in dev-mart only.
    suffix = uuid.uuid4().hex[:10]
    test_table = f"decimal_evolution_{suffix}"
    table_def = {
        "name": test_table,
        "schema": {
            "type": "struct",
            "schema-id": 0,
            "fields": [
                {"id": 1, "name": "id", "required": True, "type": "long"},
                {"id": 2, "name": "amount", "required": False, "type": "decimal(20,4)"},
                {"id": 3, "name": "trade_date", "required": True, "type": "date"},
            ],
        },
        "partition-spec": {
            "spec-id": 0,
            "fields": [
                {
                    "name": "trade_date_day",
                    "transform": "day",
                    "source-id": 3,
                    "field-id": 1000,
                }
            ],
        },
        "stage-create": False,
        "properties": {
            "gcp.biglake.bigquery-dml.enabled": "true",
            "gcp.biglake.table-management.enabled": "false",
            "janus.acceptance": "b2",
        },
    }
    with tempfile.TemporaryDirectory() as td:
        definition = Path(td) / "table.json"
        definition.write_text(json.dumps(table_def))
        run(
            "gcloud", "biglake", "iceberg", "tables", "create",
            f"--project={PROJECT}", f"--catalog={CATALOG}", f"--namespace={ACCEPT_NAMESPACE}",
            f"--create-from-file={definition}", "--quiet",
        )

    fq = f"`{PROJECT}.{CATALOG}.{ACCEPT_NAMESPACE}.{test_table}`"
    created = load_table(test_table, ACCEPT_NAMESPACE)
    created_uri = metadata_location(created)
    created_meta, _ = gcs_json(created_uri)
    created_schema = current_schema(created_meta)
    if field_type(created_schema, "amount") != "decimal(20,4)":
        raise RuntimeError("native Iceberg decimal(20,4) not preserved at creation")
    if (created_meta.get("properties") or {}).get("gcp.biglake.table-management.enabled") != "false":
        raise RuntimeError("automatic table management must remain disabled")

    budget.query(
        f"INSERT INTO {fq} (id, amount, trade_date) VALUES "
        "(1, NUMERIC '1234567890123456.7890', DATE '2026-10-01'), "
        "(2, NUMERIC '-0.0100', DATE '2026-10-06')",
        "decimal_insert_initial",
    )
    first = budget.query(
        f"SELECT CAST(id AS STRING), FORMAT('%.4f', amount), CAST(trade_date AS STRING) "
        f"FROM {fq} ORDER BY id",
        "decimal_read_initial",
    )
    initial_rows = row_values(first["response"])
    expected_initial = [
        ["1", "1234567890123456.7890", "2026-10-01"],
        ["2", "-0.0100", "2026-10-06"],
    ]
    if initial_rows != expected_initial:
        raise RuntimeError(f"native decimal fidelity mismatch: {initial_rows!r}")

    before_evolution = load_table(test_table, ACCEPT_NAMESPACE)
    before_uri = metadata_location(before_evolution)
    before_meta, _ = gcs_json(before_uri)
    before_schema_id = before_meta["current-schema-id"]

    budget.query(f"ALTER TABLE {fq} ADD COLUMN note STRING", "schema_add_column")
    budget.query(
        f"INSERT INTO {fq} (id, amount, trade_date, note) VALUES "
        "(3, NUMERIC '9999999999999999.9999', DATE '2026-10-06', 'evolved')",
        "decimal_insert_evolved",
    )
    evolved = budget.query(
        f"SELECT CAST(id AS STRING), FORMAT('%.4f', amount), CAST(trade_date AS STRING), note "
        f"FROM {fq} ORDER BY id",
        "decimal_read_evolved",
    )
    evolved_rows = row_values(evolved["response"])
    expected_evolved = [
        ["1", "1234567890123456.7890", "2026-10-01", None],
        ["2", "-0.0100", "2026-10-06", None],
        ["3", "9999999999999999.9999", "2026-10-06", "evolved"],
    ]
    if evolved_rows != expected_evolved:
        raise RuntimeError(f"schema evolution/null fidelity mismatch: {evolved_rows!r}")

    after_evolution = load_table(test_table, ACCEPT_NAMESPACE)
    after_uri = metadata_location(after_evolution)
    after_meta, _ = gcs_json(after_uri)
    after_schema = current_schema(after_meta)
    after_schema_id = after_meta["current-schema-id"]
    if after_schema_id == before_schema_id or after_uri == before_uri:
        raise RuntimeError("schema evolution did not produce a new Iceberg schema/metadata file")
    if field_type(after_schema, "amount") != "decimal(20,4)":
        raise RuntimeError("decimal precision/scale changed during schema evolution")
    if field_type(after_schema, "note") != "string":
        raise RuntimeError("evolved string column missing from Iceberg schema")

    # Partition-pruning live evidence. Narrow and wide predicates read the same
    # selected column and disable query cache. The narrow date must process fewer
    # source bytes than the two-partition range; billed minimums may still match.
    narrow = budget.query(
        f"SELECT SUM(id) FROM {fq} WHERE trade_date = DATE '2026-10-01'",
        "partition_narrow",
    )
    wide = budget.query(
        f"SELECT SUM(id) FROM {fq} "
        "WHERE trade_date BETWEEN DATE '2026-10-01' AND DATE '2026-10-06'",
        "partition_wide",
    )
    narrow_bytes = narrow["evidence"]["processed_bytes"]
    wide_bytes = wide["evidence"]["processed_bytes"]
    pruning_pass = (
        isinstance(narrow_bytes, int) and isinstance(wide_bytes, int)
        and 0 <= narrow_bytes < wide_bytes
    )
    if not pruning_pass:
        raise RuntimeError(
            f"partition pruning not proven: narrow={narrow_bytes}, wide={wide_bytes}"
        )

    evidence["schema_evolution_native_decimal"] = {
        "table": test_table,
        "namespace": ACCEPT_NAMESPACE,
        "table_management_enabled": False,
        "created_metadata_location": created_uri,
        "before_schema_id": before_schema_id,
        "after_schema_id": after_schema_id,
        "before_metadata_location": before_uri,
        "after_metadata_location": after_uri,
        "decimal_type_after": field_type(after_schema, "amount"),
        "note_type_after": field_type(after_schema, "note"),
        "initial_rows": initial_rows,
        "evolved_rows": evolved_rows,
        "pass": True,
    }
    evidence["partition_pruning"] = {
        "table": test_table,
        "partition_field": "trade_date",
        "narrow_processed_bytes": narrow_bytes,
        "wide_processed_bytes": wide_bytes,
        "pass": pruning_pass,
    }
    evidence["bigquery_jobs"] = budget.jobs
    evidence["total_billed_bytes"] = budget.billed
    evidence["remaining_budget_bytes"] = budget.remaining
    evidence["status"] = "nonregister-pass" if args.skip_shared_mapping else "partial"
    try:
        if not args.skip_shared_mapping:
            prove_core_pruning(evidence, budget)
            evidence["status"] = "pass"
    finally:
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", newline="\n")
    print(json.dumps({
        "status": evidence["status"],
        "catalog": CATALOG,
        "shared_tables": sorted(evidence["shared_catalog_mapping"]),
        "test_table": test_table,
        "total_billed_bytes": budget.billed,
        "partition_pruning": evidence["partition_pruning"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
