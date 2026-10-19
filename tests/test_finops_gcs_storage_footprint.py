import importlib.util
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

module_path = Path(__file__).resolve().parents[1] / "scripts/gcp/finops_gcs_storage_footprint.py"
spec = importlib.util.spec_from_file_location("gcs_footprint", module_path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_bucket_grouping_and_private_redaction():
    assert audit.kind("warehouse/ohlcv/data/1.parquet", "core") == "iceberg-data-parquet"
    assert audit.kind("raw/twse/ohlcv/x/payload.json", "stage") == "stage-raw"
    assert audit.kind("warehouse/private-user/secret", "private") == "private-restricted"
    result = audit.summarized([{"name": "user/secret.txt", "size": "15",
                                "md5Hash": "should-not-print", "storageClass": "STANDARD"}], "private")
    assert "user/secret" not in str(result)
    assert "should-not-print" not in str(result)
    assert result["bytes"] == 15
    assert result["possible_same_hash_extra_bytes"] == 0


def test_same_hash_is_only_candidate():
    rows = [{"name": x, "size": "12", "md5Hash": "same", "storageClass": "STANDARD"}
            for x in ("raw/x.json", "raw/y.json")]
    summary = audit.summarized(rows, "stage")
    assert summary["possible_same_hash_extra_bytes"] == 12
    assert summary["duplicate_detection"] == "POTENTIAL_ONLY_NOT_SAFE_TO_DELETE"


def test_versioned_and_soft_deleted_split():
    def fetch(_token, url):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/b/sample"):
            return {"versioning": {"enabled": True},
                    "softDeletePolicy": {"retentionDurationSeconds": "604800"}}
        if query.get("softDeleted") == ["true"]:
            return {"items": [{"name": "old", "size": "7", "generation": "8"}]}
        assert query.get("versions") == ["true"]
        return {"items": [
            {"name": "a", "generation": "9", "size": "30"},
            {"name": "a", "generation": "8", "timeDeleted": "2026-10-10T00:00:00Z",
             "size": "20"}]}
    x = audit.inspect_bucket("token", "sample", 3, fetch)
    assert x["status"] == "OBSERVED"
    assert (x["current"]["bytes"], x["noncurrent"]["bytes"],
            x["soft_deleted"]["bytes"]) == (30, 20, 7)
    assert x["scan_complete"]


def test_page_budget_truncation_does_not_claim_total():
    def fetch(_token, url):
        return {"items": [{"name": "x", "size": "5"}], "nextPageToken": "still-more"}
    x = audit.list_objects("token", "b", "versions", 2, fetch)
    assert x["complete"] is False and x["pages"] == 2


def test_bounded_bucket_scope_not_misreported_as_full():
    def fetch(_token, url):
        if "/b?" in url:
            raise HTTPError(url, 403, "denied", {}, None)
        if url.endswith("fields=name%2Cversioning%2CsoftDeletePolicy%2CdefaultEventBasedHold%2CretentionPolicy"):
            return {"versioning": {"enabled": False}}
        return {"items": []}
    request = {"intent": "read-only-gcs-storage-footprint",
               "no_gcp_mutation": True, "project": audit.PROJECT,
               "known_buckets": [audit.PROJECT + "-dev-core"],
               "max_pages_per_bucket": 2}
    x = audit.report("t", request, fetch)
    assert x["bucket_discovery"] == "FALLBACK_NO_PROJECT_BUCKET_LIST"
    assert x["status"] == "PARTIAL_NOT_PROJECT_TOTAL"
    assert x["totals_only_if_complete"] is None


@pytest.mark.parametrize("bad", [
    {"intent": "delete"},
    {"intent": "read-only-gcs-storage-footprint", "no_gcp_mutation": False},
    {"intent": "read-only-gcs-storage-footprint", "no_gcp_mutation": True,
     "project": "unapproved", "max_pages_per_bucket": 2},
])
def test_invalid_requests_fail_closed(bad):
    with pytest.raises(ValueError):
        audit.report("token", bad)
