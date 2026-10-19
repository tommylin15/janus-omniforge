"""Admin six-bucket GCS inventory: bounded, read-only, no sensitive details."""
from unittest.mock import patch
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from packages.admin_api import gcs_inventory as inventory


def _bucket_summary(token, bucket, pages):
    assert token == "test-access-token"
    assert pages == 20
    current = {"objects": 3, "bytes": 120, "possible_same_hash_extra_bytes": 10,
               "by_category": {"stage-raw": {"objects": 3, "bytes": 120}}}
    return {"status": "OBSERVED", "scan_complete": True,
            "current": current, "noncurrent": {"bytes": 5},
            "soft_deleted": {"bytes": 0},
            "token": "do-not-expose", "secret_object_path": "owner/secret"}


def test_allowlisted_gcs_inventory_reads_only_six_names_and_omits_private_details():
    calls = []
    def scan(token, bucket, pages):
        calls.append(bucket)
        return _bucket_summary(token, bucket, pages)
    with patch.object(inventory.GcsObjectStore, "_token", return_value="test-access-token"), \
         patch.object(inventory, "inspect_bucket", side_effect=scan):
        result = inventory.scan_allowlisted_buckets()
    assert result["status"] == "KNOWN_BUCKETS_COMPLETE"
    assert calls == [name for name, role in inventory.BUCKETS]
    assert result["totals"]["current_bytes"] == 720
    assert result["totals"]["current_objects"] == 18
    assert result["buckets"][0]["possible_same_md5_extra_bytes"] == 10
    assert "possible_same_md5_extra_bytes" not in result["buckets"][3]
    assert "secret" not in str(result)
    assert "test-access-token" not in str(result)
    assert result["scope"] == "SIX_ALLOWLISTED_BUCKETS_NOT_PROJECT_BILL"


def test_gcs_inventory_partial_never_fabricates_total():
    def inspect(token, bucket, pages):
        result = _bucket_summary(token, bucket, pages)
        if "private" in bucket:
            result["status"] = "BLOCKED"
            result["current"] = None
            result["scan_complete"] = False
        return result
    with patch.object(inventory.GcsObjectStore, "_token", return_value="test-access-token"), \
         patch.object(inventory, "inspect_bucket", side_effect=inspect):
        result = inventory.scan_allowlisted_buckets()
    assert result["status"] == "PARTIAL_NOT_TOTAL"
    assert result["totals"] is None
    assert result["buckets"][3]["current_bytes"] is None


def test_single_flight_gcs_scanner_fail_closed():
    assert inventory._SCAN_LOCK.acquire(blocking=False)
    try:
        assert inventory.scan_allowlisted_buckets()["status"] == "BUSY"
    finally:
        inventory._SCAN_LOCK.release()


def test_invalid_page_budget_has_no_requests():
    with patch.object(inventory.GcsObjectStore, "_token") as credentials:
        try:
            inventory.scan_allowlisted_buckets(25)
        except ValueError:
            pass
        else:
            raise AssertionError("unbounded page budget accepted")
        credentials.assert_not_called()
