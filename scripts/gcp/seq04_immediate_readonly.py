"""SEQ-04 immediate bounded live readback; no GCP, Owner, or canonical writes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
import json
import os
import re
import shlex
import subprocess
import sys

PROJECT = "gen-lang-client-0593591102"
BUCKETS = {role: PROJECT + "-dev-" + role
           for role in ("stage", "core", "mart", "private")}
BASE = "https://storage.googleapis.com/storage/v1"
PUBLIC = "https://janus-api-2oo7qbkd5q-uc.a.run.app"
MAX_STAGE_PAGES = 20
MAX_ROLE_PAGES = 3

def status_error(err: Exception) -> str:
    if isinstance(err, HTTPError):
        return "HTTP_" + str(err.code)
    if isinstance(err, subprocess.TimeoutExpired):
        return "TIMEOUT"
    if isinstance(err, subprocess.CalledProcessError):
        return "COMMAND_FAILED"
    return type(err).__name__.upper()

def get_token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"], check=True,
                          capture_output=True, text=True, timeout=40).stdout.strip()

def api_json(token: str, url: str) -> dict:
    with urlopen(Request(url, headers={"Authorization": "Bearer " + token}),
                 timeout=35) as response:
        return json.load(response)

def list_bucket(token: str, bucket: str, *, prefix: str = "",
                pages: int = 3, limit: int = 1000) -> dict:
    values = []
    page_token = None
    visited = set()
    complete = False
    for index in range(pages):
        query = {"maxResults": str(limit),
                 "fields": "nextPageToken,items(name,size,updated,generation)"}
        if prefix:
            query["prefix"] = prefix
        if page_token:
            query["pageToken"] = page_token
        url = BASE + "/b/" + quote(bucket, safe="") + "/o?" + urlencode(query)
        result = api_json(token, url)
        values.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            complete = True
            break
        if page_token in visited:
            raise RuntimeError("GCS_PAGINATION_LOOP")
        visited.add(page_token)
    return {"items": values, "complete": complete,
            "pages": index + 1, "next_page": bool(page_token)}

def vm_query(sql: str, *, timeout: int = 100) -> list[str]:
    remote = ("sudo docker exec --user postgres janus-postgres "
              "psql -X -qAt -v ON_ERROR_STOP=1 -d janus_control -c "
              + shlex.quote(sql))
    cmd = ["gcloud", "compute", "ssh", "janus-postgres-dev",
           "--project=" + PROJECT, "--zone=us-central1-a",
           "--tunnel-through-iap", "--quiet", "--command=" + remote]
    p = subprocess.run(cmd, capture_output=True, check=True, text=True,
                       timeout=timeout)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]

def stage_dry_run(token: str) -> dict:
    from ingestion_core.stage import GcsObjectStore
    from ingestion_core.retention import POLICY, clean_stage
    assert POLICY["stage_days"] == 2
    inventory = list_bucket(token, BUCKETS["stage"], pages=MAX_STAGE_PAGES)
    if not inventory["complete"] or len(inventory["items"]) > 20000:
        return {"status": "BLOCKED_INCOMPLETE_INVENTORY",
                "sample_objects": len(inventory["items"]),
                "pages": inventory["pages"], "gcs_deletions": 0}
    rows = vm_query("SELECT execution_id::text FROM control.executions "
                    "WHERE status IN ('queued','running','retrying') "
                    "AND claimed_until > now() LIMIT 101")
    if len(rows) > 100 or any(not x or len(x) > 256 or '/' in x or '\\' in x for x in rows):
        return {"status": "BLOCKED_ACTIVE_LEASE_SCOPE",
                "lease_count_capped": len(rows), "gcs_deletions": 0}
    store = GcsObjectStore(BUCKETS["stage"])
    store._token = lambda: token
    objects = tuple(inventory["items"])
    store.objects = lambda prefix: objects if prefix == "" else (
        _ for _ in ()).throw(ValueError("UNBOUNDED_STAGE_PREFIX"))
    result = clean_stage(store, apply=False, now=datetime.now(timezone.utc),
                         active_executions=frozenset(rows))
    total_bytes = sum(int(x["size"]) for x in objects)
    return {"status": "PASS_DRY_RUN", "policy_days": 2,
            "inventory_complete": True, "scanned_objects": len(objects),
            "scanned_bytes": total_bytes, "live_lease_count": len(rows),
            "planned_objects": result["planned_objects"],
            "planned_bytes": result["planned_bytes"],
            "held_active_objects": result["held_active_objects"],
            "gcs_deletions": 0, "generation_fenced_apply": "NOT_ATTEMPTED"}

def iceberg_buckets(token: str) -> dict:
    from ingestion_core.stage import GcsObjectStore
    out = {}
    for role in ("core", "mart", "private"):
        bucket = BUCKETS[role]
        # Metadata-only GCS first, then a bounded GET of an Iceberg metadata
        # document if present. This is NOT proof of catalog's current pointer.
        try:
            inv = list_bucket(token, bucket, prefix="warehouse/",
                              pages=MAX_ROLE_PAGES, limit=500)
            matched = [o for o in inv["items"] if
                       o.get("name", "").endswith(".metadata.json")
                       and int(o.get("size", "0")) <= 2 * 1024 * 1024]
            readable = False
            if matched:
                store = GcsObjectStore(bucket)
                store._token = lambda: token
                payload = store.read(matched[0]["name"])
                parsed = json.loads(payload)
                readable = (isinstance(parsed, dict)
                            and "format-version" in parsed
                            and "table-uuid" in parsed)
            out[role] = {"status": "LIST_PASS" if inv["items"] else "EMPTY_PREFIX",
                         "objects_sampled": len(inv["items"]),
                         "sample_complete": inv["complete"],
                         "metadata_document_readable": readable,
                         "current_catalog_pointer": "NOT_VERIFIED",
                         "private_names_exported": 0}
        except Exception as error:
            out[role] = {"status": "BLOCKED_" + status_error(error),
                         "current_catalog_pointer": "NOT_VERIFIED",
                         "private_names_exported": 0}
    return out

def http_status(path: str, method="GET") -> tuple[int, bytes]:
    data = b"{}" if method == "POST" else None
    req = Request(PUBLIC + path, method=method, data=data,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=25) as response:
            return response.status, response.read(96 * 1024)
    except HTTPError as error:
        return error.code, b""

def serving() -> dict:
    out = {}
    for path, label in (("/health", "health"),
                        ("/api/v1/public/health", "public_health"),
                        ("/app/build-id.txt", "build_sha")):
        try:
            code, body = http_status(path)
            out[label] = {"http": code}
            if label == "build_sha":
                out[label]["expected_source_match"] = (code == 200 and
                    body.decode("utf-8", "replace").strip() ==
                    "032871a38b1dffd11c7bf0cc833563c0c3091841")
        except Exception as error:
            out[label] = {"status": "BLOCKED_" + status_error(error)}
    for symbol in ("2330", "2882"):
        label = "history_" + symbol
        try:
            code, data = http_status("/api/v1/public/history/" + symbol + "?limit=1&offset=0")
            parsed = json.loads(data) if code == 200 else {}
            out[label] = {"http": code, "has_real_rows": bool(parsed.get("rows")),
                          "correct_symbol": parsed.get("symbol") == symbol,
                          "dataset": str(parsed.get("dataset_id") or "")[:50]}
        except Exception as error:
            out[label] = {"status": "BLOCKED_" + status_error(error)}
    for label, path, method in (
        ("owner_anonymous_rejected", "/api/v1/me/profile", "GET"),
        ("admin_anonymous_rejected", "/api/v1/admin/gcs-storage/inspect", "POST"),
    ):
        try:
            code, _ = http_status(path, method)
            out[label] = {"http": code, "pass": code in (401, 403)}
        except Exception as error:
            out[label] = {"status": "BLOCKED_" + status_error(error)}
    out["owner_positive_login"] = "NOT_VERIFIED_AUTH_REQUIRED"
    out["admin_positive_login"] = "NOT_VERIFIED_AUTH_REQUIRED"
    return out

def controller_pg_readback() -> dict:
    result = {}
    queries = {
      "recent_occurrences":
        "SELECT coalesce(state->>'batch','?') || '|' || "
        "coalesce(state->>'status','?') || '|' || "
        "to_char(scheduled_at AT TIME ZONE 'Asia/Taipei', 'YYYY-MM-DD HH24:MI') "
        "FROM control.batch_occurrences WHERE scheduled_at >= now()-interval '36 hours' "
        "ORDER BY scheduled_at DESC LIMIT 24",
      "backup_requests":
        "SELECT backup_date::text || '|' || status || '|' || "
        "coalesce(retention_status,'?') || '|' || "
        "coalesce(size_bytes,0)::text "
        "FROM control.ledger_backup_requests ORDER BY backup_date DESC LIMIT 8",
    }
    for label, sql in queries.items():
        try:
            rows = vm_query(sql)
            result[label] = {"status": "PASS", "count": len(rows),
                             "rows": rows}
        except Exception as error:
            result[label] = {"status": "BLOCKED_" + status_error(error)}
    return result

def main():
    output = {
      "component": "SEQ-04 immediate bounded read-only acceptance",
      "gcp_writes": 0, "owner_writes": 0, "backup_writes": 0,
      "gcs_deletions": 0, "job_dispatches": 0,
      "timestamp_utc": datetime.now(timezone.utc).isoformat(),
      "stage": {"status": "NOT_STARTED"},
      "iceberg_gcs": {"status": "NOT_STARTED"},
      "serving": {"status": "NOT_STARTED"},
      "pg": {"status": "NOT_STARTED"},
    }
    try:
        token = get_token()
    except Exception as error:
        output["stage"] = {"status": "BLOCKED_CREDENTIAL_" + status_error(error)}
        output["iceberg_gcs"] = {"status": "BLOCKED_CREDENTIAL_" + status_error(error)}
    else:
        try:
            output["stage"] = stage_dry_run(token)
        except Exception as error:
            output["stage"] = {"status": "BLOCKED_" + status_error(error),
                               "gcs_deletions": 0}
        try:
            output["iceberg_gcs"] = iceberg_buckets(token)
        except Exception as error:
            output["iceberg_gcs"] = {"status": "BLOCKED_" + status_error(error)}
    try:
        output["pg"] = controller_pg_readback()
    except Exception as error:
        output["pg"] = {"status": "BLOCKED_" + status_error(error)}
    try:
        output["serving"] = serving()
    except Exception as error:
        output["serving"] = {"status": "BLOCKED_" + status_error(error)}
    path = Path("/tmp/seq04-immediate-readonly.json")
    path.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
