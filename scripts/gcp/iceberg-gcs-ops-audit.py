"""Read-only, bounded 7-day GCS operation counter for the FinOps incident.

Uses the existing GitHub Actions GCP WIF identity; does not create resources,
read object payloads, or interpret request counts as invoices.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
MAX_PAGES = 25


def aggregate_series(series: list[dict]) -> dict[str, object]:
    by_bucket_method: dict[tuple[str, str], int] = defaultdict(int)
    by_bucket: dict[str, int] = defaultdict(int)
    for item in series:
        bucket = str(item.get("resource", {}).get("labels", {}).get("bucket_name") or "unknown")
        method = str(item.get("metric", {}).get("labels", {}).get("method") or "unknown")
        count = sum(int(point.get("value", {}).get("int64Value") or 0)
                    for point in item.get("points", []))
        by_bucket_method[bucket, method] += count
        by_bucket[bucket] += count
    return {
        "total_requests": sum(by_bucket.values()),
        "buckets": [{"bucket": bucket, "requests": count}
                    for bucket, count in sorted(by_bucket.items(), key=lambda x: (-x[1], x[0]))],
        "methods": [{"bucket": bucket, "method": method, "requests": count}
                    for (bucket, method), count in sorted(by_bucket_method.items(),
                                                         key=lambda x: (-x[1], x[0][0], x[0][1]))],
    }


def run() -> dict[str, object]:
    end = datetime.now(timezone.utc) - timedelta(minutes=10)
    start = end - timedelta(days=7)
    evidence: dict[str, object] = {
        "component": "gcs-ops-audit", "status": "unknown",
        "project": PROJECT,
        "start_utc": start.isoformat(), "end_utc": end.isoformat(),
        "metric": "storage.googleapis.com/api/request_count",
        "scope": "existing project GCS buckets",
        "billing_amount_usd": None, "billing_sku_attribution": "unknown",
        "note": "Operation counts only, not invoice costs or proof of Iceberg attribution.",
    }
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"],
                                        text=True, stderr=subprocess.DEVNULL, timeout=30).strip()
        if not token:
            return {**evidence, "status": "blocked", "reason": "GCP_IDENTITY_UNAVAILABLE"}
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {**evidence, "status": "blocked", "reason": "GCP_IDENTITY_UNAVAILABLE"}

    series: list[dict] = []
    token_page = ""
    for page in range(MAX_PAGES):
        params = {
            "filter": 'metric.type="storage.googleapis.com/api/request_count" AND resource.type="gcs_bucket"',
            "interval.startTime": start.isoformat().replace("+00:00", "Z"),
            "interval.endTime": end.isoformat().replace("+00:00", "Z"),
            "aggregation.alignmentPeriod": "86400s",
            "aggregation.perSeriesAligner": "ALIGN_SUM",
            "pageSize": "1000",
        }
        if token_page:
            params["pageToken"] = token_page
        url = f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?{urlencode(params)}"
        request = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=40) as response:
                doc = json.load(response)
        except HTTPError as error:
            return {**evidence, "status": "blocked", "reason": "MONITORING_READ_FAILED",
                    "http_status": error.code}
        except (URLError, TimeoutError, ValueError):
            return {**evidence, "status": "blocked", "reason": "MONITORING_READ_UNAVAILABLE"}
        series.extend(doc.get("timeSeries", []))
        token_page = doc.get("nextPageToken", "")
        if not token_page:
            break
    if token_page:
        return {**evidence, "status": "partial", "reason": "PAGE_LIMIT_REACHED",
                "pages": MAX_PAGES, "series_observed": len(series),
                **aggregate_series(series)}
    if not series:
        return {**evidence, "status": "unknown", "reason": "NO_MONITORING_SERIES",
                "pages": page + 1, "series_observed": 0}
    return {**evidence, "status": "observed", "pages": page + 1,
            "series_observed": len(series), **aggregate_series(series)}


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as stream:
            stream.write("## FINOPS-ICEBERG-20261015 · GCS operation audit\n\n")
            stream.write(f"Status: **{result['status']}**; period: {result['start_utc']} → {result['end_utc']}\n\n")
            stream.write(f"Observed requests: {result.get('total_requests', 'unknown')}\n\n")
            stream.write("Cloud Billing SKU / dollar attribution: **unknown** (separate billing evidence required).\n\n")
            for item in result.get("buckets", []):
                stream.write(f"- \`{item['bucket']}\`: {item['requests']} requests\n")
            stream.write("\n")
    return 0 if result["status"] == "observed" else 2


if __name__ == "__main__":
    sys.exit(main())
