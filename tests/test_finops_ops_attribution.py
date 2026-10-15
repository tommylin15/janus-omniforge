from datetime import datetime, timezone

from importlib.machinery import SourceFileLoader
from pathlib import Path

m = SourceFileLoader("finops_attribution", str(Path("scripts/gcp/finops-ops-attribution.py"))).load_module()


def test_hourly_counts_aggregate_by_method_without_caller_inference():
    def item(bucket, method, values):
        return {"resource": {"labels": {"bucket_name": bucket}},
                "metric": {"labels": {"method": method}}, "points": [
                    {"value": {"int64Value": str(value)}, "interval": {"endTime": timestamp}}
                    for timestamp, value in values]}
    got = m.summarize_hourly([
        item(m.BUCKET, "ReadObject", [("2026-10-15T01:00:00Z", 8),
                                       ("2026-10-15T02:00:00Z", 4)]),
        item(m.BUCKET, "GetObjectMetadata", [("2026-10-15T01:00:00Z", 3)]),
        item(m.BUCKET, "ReadObject", [("2026-10-15T01:00:00Z", 2)]),
        item("other-bucket", "ReadObject", [("2026-10-15T01:00:00Z", 999)])
    ])
    assert got["core_requests_by_method"] == {"GetObjectMetadata": 3, "ReadObject": 14}
    assert got["core_top_hours"][0] == {
        "hour_utc": "2026-10-15T01:00Z", "ReadObject": 10,
        "GetObjectMetadata": 3, "other": 0, "total": 13}
    assert got["core_hours"] == 2
