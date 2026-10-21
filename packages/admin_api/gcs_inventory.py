"""Read-only bounded six-bucket GCS usage snapshot for the admin UI."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from ingestion_core.stage import GcsObjectStore
from scripts.gcp.finops_gcs_storage_footprint import inspect_bucket

PROJECT = "gen-lang-client-0593591102"
BUCKETS = (
    (PROJECT + "-dev-stage", "stage"),
    (PROJECT + "-dev-core", "core"),
    (PROJECT + "-dev-mart", "mart"),
    (PROJECT + "-dev-private", "private"),
    (PROJECT + "-dev-research-big-move-500", "research"),
    (PROJECT + "-cloudbuild-regional", "cloudbuild"),
)
_SCAN_LOCK = Lock()


def scan_allowlisted_buckets(pages: int = 20) -> dict:
    if not isinstance(pages, int) or not 1 <= pages <= 20:
        raise ValueError("invalid page budget")
    if not _SCAN_LOCK.acquire(blocking=False):
        return {"status": "BUSY", "buckets": [], "totals": None}
    try:
        token = GcsObjectStore(BUCKETS[0][0], timeout_seconds=8)._token()
        items = []
        for bucket, role in BUCKETS:
            evidence = inspect_bucket(token, bucket, pages)
            current = evidence.get("current") or {}
            noncurrent = evidence.get("noncurrent") or {}
            soft = evidence.get("soft_deleted") or {}
            row = {
                "bucket": bucket, "role": role, "status": evidence.get("status", "UNKNOWN"),
                "current_objects": current.get("objects"), "current_bytes": current.get("bytes"),
                "noncurrent_bytes": noncurrent.get("bytes"), "soft_deleted_bytes": soft.get("bytes"),
                "scan_complete": evidence.get("scan_complete", False),
            }
            if row["status"] not in ("OBSERVED", "TRUNCATED"):
                if isinstance(evidence.get("http_status"), int):
                    row["http_status"] = evidence["http_status"]
                if evidence.get("failure_step") in ("bucket_metadata", "object_versions", "soft_deleted_objects"):
                    row["failure_step"] = evidence["failure_step"]
                if evidence.get("reason") == "BUCKET_READ_UNAVAILABLE":
                    row["reason"] = evidence["reason"]
            })
            if role == "stage":
                row["possible_same_md5_extra_bytes"] = current.get("possible_same_hash_extra_bytes")
                row["duplicate_status"] = "POTENTIAL_ONLY"
                row["stage_categories"] = current.get("by_category")
            items.append(row)
        complete = all(x["status"] == "OBSERVED" and x["scan_complete"] for x in items)
        return {
            "status": "KNOWN_BUCKETS_COMPLETE" if complete else "PARTIAL_NOT_TOTAL",
            "scope": "SIX_ALLOWLISTED_BUCKETS_NOT_PROJECT_BILL",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "buckets": items,
            "totals": ({
                "current_bytes": sum(int(x["current_bytes"]) for x in items),
                "noncurrent_bytes": sum(int(x["noncurrent_bytes"]) for x in items),
                "soft_deleted_bytes": sum(int(x["soft_deleted_bytes"]) for x in items),
                "current_objects": sum(int(x["current_objects"]) for x in items),
            } if complete else None),
        }
    finally:
        _SCAN_LOCK.release()
