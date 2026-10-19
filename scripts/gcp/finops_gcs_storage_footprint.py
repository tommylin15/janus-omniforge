"""One-shot, metadata-only Janus GCS footprint audit.

No object payload GET, mutation, row inspection, secrets, private paths or object
names in output. A partial inventory is never labelled a project total.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import json
import subprocess
import sys

PROJECT = "gen-lang-client-0593591102"
REQUEST = Path("ops/finops-gcs-storage-footprint.json")
OUTPUT = Path("gcs-storage-footprint-report.json")
MAX_BUCKETS = 15
MAX_PAGES = 30
FIELDS = ("nextPageToken,items(name,size,generation,timeDeleted,md5Hash,"
          "storageClass,timeCreated,updated,eventBasedHold,temporaryHold)")
BUCKET_FIELDS = ("nextPageToken,items(name,versioning,softDeletePolicy,"
                 "defaultEventBasedHold,retentionPolicy,storageClass)")
BASE = "https://storage.googleapis.com/storage/v1"


def api_json(token: str, url: str) -> dict:
    req = Request(url, headers={"Authorization": "Bearer " + token,
                                "Accept": "application/json"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def kind(name: str, role: str) -> str:
    """Predefined categories only; never include private object-name segments."""
    if role == "private":
        return "private-restricted"
    if name.startswith(("pilot-ledger-backups/", "backups/", "backup/")):
        return "backups"
    if role == "stage":
        if name.startswith("raw/"):
            return "stage-raw"
        if name.startswith("quarantine/"):
            return "stage-quarantine"
        if name.startswith("executions/"):
            parts = name.split("/")
            if len(parts) >= 4 and parts[2] == "stage":
                if parts[3] == "raw":
                    return ("stage-exec-raw-payload" if parts[-1].startswith("payload.")
                            else "stage-exec-raw-sidecar")
                if parts[3] == "quarantine":
                    return "stage-exec-quarantine"
                if len(parts) == 4 and name.endswith(".json"):
                    return "stage-exec-manifest"
                return "stage-exec-other-stage"
            if len(parts) == 3 and parts[2] == "core-commit.json":
                return "stage-exec-core-commit"
            return "stage-exec-other"
        if "/stage/" in name:
            return "stage-other"
    if name.startswith("warehouse/"):
        if name.endswith(".parquet"):
            return "iceberg-data-parquet"
        if name.endswith(".avro"):
            return "iceberg-manifest-avro"
        if name.endswith((".metadata.json", ".metadata.json.gz")):
            return "iceberg-metadata-json"
        return "iceberg-other"
    if name.startswith("ml-oos-data/"):
        return "ml-oos-data"
    if name.startswith("executions/"):
        return "execution-receipts"
    if role == "research":
        return "research-artifacts"
    if role == "cloudbuild":
        return "ci-build-artifacts"
    return "other"


def role_for(bucket: str) -> str:
    if bucket.endswith("-dev-core"):
        return "core"
    if bucket.endswith("-dev-stage"):
        return "stage"
    if bucket.endswith("-dev-mart"):
        return "mart"
    if bucket.endswith("-dev-private"):
        return "private"
    if "-research" in bucket:
        return "research"
    if "cloudbuild" in bucket:
        return "cloudbuild"
    return "other"


def bucket_listing(token: str, fallback: list[str], get=api_json) -> tuple[list[str], str]:
    names: list[str] = []
    page = ""
    try:
        for _ in range(3):
            params = {"project": PROJECT, "maxResults": "100", "fields": BUCKET_FIELDS}
            if page:
                params["pageToken"] = page
            payload = get(token, BASE + "/b?" + urlencode(params))
            names.extend(x["name"] for x in payload.get("items", []))
            page = payload.get("nextPageToken", "")
            if len(names) > MAX_BUCKETS or (page and len(names) >= MAX_BUCKETS):
                return sorted(set(fallback)), "BUCKET_LIST_LIMIT"
            if not page:
                return sorted(set(names)), "COMPLETE"
    except (HTTPError, URLError, TimeoutError, ValueError):
        return sorted(set(fallback)), "FALLBACK_NO_PROJECT_BUCKET_LIST"
    return sorted(set(fallback)), "BUCKET_LIST_PAGINATION_LIMIT"


def list_objects(token: str, bucket: str, mode: str, pages: int, get=api_json) -> dict:
    data = []
    page = ""
    for index in range(pages):
        params = {"maxResults": "1000", "fields": FIELDS}
        if mode == "versions":
            params["versions"] = "true"
        if mode == "soft":
            params["softDeleted"] = "true"
        if page:
            params["pageToken"] = page
        url = BASE + "/b/" + quote(bucket, safe="") + "/o?" + urlencode(params)
        payload = get(token, url)
        data.extend(payload.get("items", []))
        page = payload.get("nextPageToken", "")
        if not page:
            return {"items": data, "pages": index + 1, "complete": True}
    return {"items": data, "pages": pages, "complete": False}


def summarized(items: list[dict], role: str) -> dict:
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"objects": 0, "bytes": 0})
    classes: dict[str, int] = defaultdict(int)
    hash_count: dict[tuple, list[int]] = {}
    total = 0
    now = datetime.now(timezone.utc)
    age_over_7 = {"objects": 0, "bytes": 0}
    age_over_30 = {"objects": 0, "bytes": 0}
    age_unknown = {"objects": 0, "bytes": 0}
    for obj in items:
        size = int(obj.get("size") or 0)
        if size < 0:
            raise ValueError("negative size")
        total += size
        cls = obj.get("storageClass") or "UNKNOWN"
        classes[cls] += size
        group = kind(obj.get("name", ""), role)
        groups[group]["objects"] += 1
        groups[group]["bytes"] += size
        # Age is observational, never a claim of deletion eligibility.
        stamp = obj.get("updated") or obj.get("timeCreated")
        try:
            recorded_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            elapsed = now - recorded_at
            if elapsed >= timedelta(days=7):
                age_over_7["objects"] += 1
                age_over_7["bytes"] += size
                groups[group]["older_than_7d_objects"] = groups[group].get("older_than_7d_objects", 0) + 1
                groups[group]["older_than_7d_bytes"] = groups[group].get("older_than_7d_bytes", 0) + size
            if elapsed >= timedelta(days=30):
                age_over_30["objects"] += 1
                age_over_30["bytes"] += size
        except (AttributeError, TypeError, ValueError):
            age_unknown["objects"] += 1
            age_unknown["bytes"] += size
        # Same hash is only a similarity signal; deletion requires lineage checks.
        digest = obj.get("md5Hash")
        if digest and role != "private":
            key = (group, cls, size, digest)
            row = hash_count.setdefault(key, [0, size])
            row[0] += 1
    duplicated_count = sum(count - 1 for count, _ in hash_count.values() if count > 1)
    duplicated_bytes = sum((count - 1) * size for count, size in hash_count.values() if count > 1)
    return {"objects": len(items), "bytes": total,
            "under_1mib": sum(int(x.get("size") or 0) < 1048576 for x in items),
            "older_than_7d_metadata_only": age_over_7,
            "older_than_30d_metadata_only": age_over_30,
            "age_missing": age_unknown,
            "age_is_not_retention_eligibility": True,
            "by_category": dict(sorted(groups.items())),
            "by_storage_class_bytes": dict(sorted(classes.items())),
            "possible_same_hash_extra_objects": duplicated_count,
            "possible_same_hash_extra_bytes": duplicated_bytes,
            "duplicate_detection": "POTENTIAL_ONLY_NOT_SAFE_TO_DELETE"}


def inspect_bucket(token: str, bucket: str, pages: int, get=api_json) -> dict:
    result = {"bucket": bucket, "role": role_for(bucket), "status": "UNKNOWN",
              "current": None, "noncurrent": None, "soft_deleted": None,
              "bucket_versioning": None, "soft_delete_retention_seconds": None,
              "scan_complete": False}
    try:
        info = get(token, BASE + "/b/" + quote(bucket, safe="") +
                   "?fields=name,versioning,softDeletePolicy,defaultEventBasedHold,retentionPolicy")
        result["bucket_versioning"] = info.get("versioning", {}).get("enabled", False)
        duration = info.get("softDeletePolicy", {}).get("retentionDurationSeconds", 0)
        result["soft_delete_retention_seconds"] = int(duration)
        result["default_event_based_hold"] = bool(info.get("defaultEventBasedHold", False))
        versions = list_objects(token, bucket, "versions", pages, get)
        current = [o for o in versions["items"] if not o.get("timeDeleted")]
        old = [o for o in versions["items"] if o.get("timeDeleted")]
        result["current"] = {**summarized(current, result["role"]),
                             "complete": versions["complete"], "pages": versions["pages"]}
        result["noncurrent"] = {**summarized(old, result["role"]),
                                "complete": versions["complete"], "pages": versions["pages"]}
        result["scan_complete"] = versions["complete"]
        result["soft_deleted"] = {"status": "NOT_APPLICABLE", "objects": 0, "bytes": 0}
        if result["soft_delete_retention_seconds"] > 0:
            soft = list_objects(token, bucket, "soft", pages, get)
            result["soft_deleted"] = {**summarized(soft["items"], result["role"]),
                                      "complete": soft["complete"], "pages": soft["pages"]}
            result["scan_complete"] &= soft["complete"]
        result["status"] = "OBSERVED" if result["scan_complete"] else "TRUNCATED"
    except HTTPError as exc:
        result["status"] = "ABSENT" if exc.code == 404 else "BLOCKED"
        result["http_status"] = exc.code
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        result["status"] = "BLOCKED"
        result["reason"] = "BUCKET_READ_UNAVAILABLE"
    return result


def report(token: str, request: dict, get=api_json) -> dict:
    if (request.get("intent") != "read-only-gcs-storage-footprint"
            or request.get("no_gcp_mutation") is not True
            or request.get("project") != PROJECT):
        raise ValueError("invalid read-only audit request")
    pages = request.get("max_pages_per_bucket", 20)
    if not isinstance(pages, int) or not 1 <= pages <= MAX_PAGES:
        raise ValueError("page budget exceeded")
    fallback = request.get("known_buckets", [])
    if (not isinstance(fallback, list) or len(fallback) > MAX_BUCKETS
            or not all(isinstance(x, str) and x.startswith(PROJECT) for x in fallback)):
        raise ValueError("invalid fallback bucket allowlist")
    buckets, inventory_scope = bucket_listing(token, fallback, get)
    inspected = [inspect_bucket(token, name, pages, get) for name in buckets]
    complete = inventory_scope == "COMPLETE" and all(
        x["status"] in ("OBSERVED", "ABSENT") for x in inspected)
    current_bytes = sum((x["current"] or {}).get("bytes", 0) for x in inspected)
    old_bytes = sum((x["noncurrent"] or {}).get("bytes", 0) for x in inspected)
    soft_bytes = sum((x["soft_deleted"] or {}).get("bytes", 0) for x in inspected)
    return {"component": "gcs-storage-footprint", "project": PROJECT,
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "OBSERVED_COMPLETE" if complete else "PARTIAL_NOT_PROJECT_TOTAL",
            "bucket_discovery": inventory_scope, "buckets_inspected": len(inspected),
            "totals_only_if_complete": ({"current_bytes": current_bytes,
                                         "noncurrent_bytes": old_bytes,
                                         "soft_deleted_bytes": soft_bytes,
                                         "total_object_bytes": current_bytes + old_bytes + soft_bytes}
                                        if complete else None),
            "observed_lower_bound_bytes": current_bytes + old_bytes + soft_bytes,
            "buckets": inspected,
            "billing_cost": None, "billable_storage_bytes": None,
            "object_storage_footprint_not_invoice": True,
            "notes": ("Current, noncurrent and soft-deleted object payload sizes, "
                      "not physical storage overhead, retention eligibility or billable cost. "
                      "Only metadata read. Object names, hashes and private identities omitted. "
                      "The inventory is point-in-time non-atomic; live writes can change totals. "
                      "Possible identical MD5 is not evidence of safe deletion.")}


def get_access_token() -> tuple[str | None, list[str]]:
    """Try regular gcloud and ADC WIF, reporting codes only, not stderr/identity."""
    checks = []
    commands = (
        ("gcloud", ["gcloud", "auth", "print-access-token"]),
        ("adc", ["gcloud", "auth", "application-default", "print-access-token"]),
    )
    for label, command in commands:
        try:
            done = subprocess.run(command, check=False, capture_output=True,
                                  text=True, timeout=30)
            token = done.stdout.strip()
            if done.returncode == 0 and token:
                return token, checks + [label + ":OK"]
            message = done.stderr.lower()
            if "getaccesstoken" in message or "permission denied" in message:
                code = "IAM_OR_IMPERSONATION_DENIED"
            elif "invalid" in message and ("credential" in message or "grant" in message):
                code = "INVALID_CREDENTIAL"
            elif "account" in message and "no" in message:
                code = "NO_ACTIVE_ACCOUNT"
            else:
                code = "TOKEN_COMMAND_FAILED"
            checks.append(label + ":" + code + ":exit" + str(done.returncode))
        except (OSError, subprocess.TimeoutExpired):
            checks.append(label + ":UNAVAILABLE")
    return None, checks


def main() -> int:
    try:
        request = json.loads(REQUEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        result = {"component": "gcs-storage-footprint", "status": "BLOCKED",
                  "reason": "REQUEST_FILE_UNAVAILABLE", "buckets": []}
    else:
        try:
            token, token_checks = get_access_token()
            if not token:
                result = {"component": "gcs-storage-footprint", "status": "BLOCKED",
                          "reason": "GCP_WIF_TOKEN_UNAVAILABLE",
                          "auth_checks": token_checks, "buckets": []}
        except (OSError, subprocess.TimeoutExpired):
            result = {"component": "gcs-storage-footprint", "status": "BLOCKED",
                      "reason": "GCP_AUTH_COMMAND_UNAVAILABLE", "buckets": []}
        if token:
            try:
                result = report(token, request)
            except (ValueError, TypeError) as exc:
                # Only local, enumerated validation failures, never raw HTTP bodies/tokens.
                result = {"component": "gcs-storage-footprint", "status": "BLOCKED",
                          "reason": "AUDIT_REQUEST_VALIDATION_FAILED",
                          "error_type": type(exc).__name__, "buckets": []}
    result.setdefault("billing_cost", None)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": result["status"], "reason": result.get("reason"),
                      "error_type": result.get("error_type"),
                      "auth_checks": result.get("auth_checks"),
                      "bucket_discovery": result.get("bucket_discovery"),
                      "buckets_inspected": result.get("buckets_inspected"),
                      "totals_only_if_complete": result.get("totals_only_if_complete"),
                      "observed_lower_bound_bytes": result.get("observed_lower_bound_bytes"),
                      "by_bucket": [{"bucket": x["bucket"], "role": x["role"],
                                     "status": x["status"],
                                     "current_bytes": (x["current"] or {}).get("bytes"),
                                     "noncurrent_bytes": (x["noncurrent"] or {}).get("bytes"),
                                     "soft_deleted_bytes": (x["soft_deleted"] or {}).get("bytes"),
                                     "current_objects": (x["current"] or {}).get("objects"),
                                     "age_7d": ((x["current"] or {}).get("older_than_7d_metadata_only")
                                                if x["role"] == "stage" else None),
                                     "stage_categories": ((x["current"] or {}).get("by_category")
                                                          if x["role"] == "stage" else None),
                                     "potential_same_hash_extra_bytes": ((x["current"] or {}).get("possible_same_hash_extra_bytes")
                                                                         if x["role"] == "stage" else None),
                                     "soft_delete_retention_seconds": x.get("soft_delete_retention_seconds")}
                                    for x in result.get("buckets", [])]}, sort_keys=True))
    return 0 if result["status"] == "OBSERVED_COMPLETE" else 2


if __name__ == "__main__":
    sys.exit(main())
