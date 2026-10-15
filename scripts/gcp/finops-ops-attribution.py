"""One-shot read-only GCS operation time-attribution; no resource mutation.

Cloud Monitoring request_count is bucket/method only. Correlating Cloud Run
execution windows supports hypotheses, NOT definitive per-caller or billed-SKU
attribution. Sanitized fields only; no source object names or credentials.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-core"
REGION = "us-central1"
JOBS = ("janus-batch-controller", "janus-ingestion-core",
        "janus-intelligence-mart", "janus-private-pipeline")
MAX_PAGES = 12


def summarize_hourly(series):
    hourly = defaultdict(int)
    for item in series:
        bucket = item.get("resource", {}).get("labels", {}).get("bucket_name", "unknown")
        method = item.get("metric", {}).get("labels", {}).get("method", "unknown")
        for point in item.get("points", ()):
            n = int(point.get("value", {}).get("int64Value") or 0)
            ts = point.get("interval", {}).get("endTime")
            if ts:
                stamp = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                hour = stamp.strftime("%Y-%m-%dT%H:00Z")
                hourly[(bucket, method, hour)] += n
    core_hourly = defaultdict(lambda: {"ReadObject": 0, "GetObjectMetadata": 0, "other": 0})
    for (bucket, method, hour), count in hourly.items():
        if bucket != BUCKET:
            continue
        key = method if method in {"ReadObject", "GetObjectMetadata"} else "other"
        core_hourly[hour][key] += count
    peaks = sorted(({"hour_utc": hour, **totals, "total": sum(totals.values())}
                    for hour, totals in core_hourly.items()),
                   key=lambda item: (-item["total"], item["hour_utc"]))
    by_method = defaultdict(int)
    for (bucket, method, _), count in hourly.items():
        if bucket == BUCKET:
            by_method[method] += count
    return {"core_requests_by_method": dict(sorted(by_method.items())),
            "core_top_hours": peaks[:18],
            "core_hourly_series": sorted(peaks, key=lambda item: item["hour_utc"]),
            "core_hours": len(peaks)}


def api(url, token):
    request = Request(url, headers={"Authorization": "Bearer " + token,
                                    "Accept": "application/json"})
    with urlopen(request, timeout=40) as response:
        return json.load(response)


def monitored_hours(token, start, end, *, alignment_seconds=3600):
    output, page_token = [], ""
    for _ in range(MAX_PAGES):
        params = {
            "filter": 'metric.type="storage.googleapis.com/api/request_count" AND resource.type="gcs_bucket"',
            "interval.startTime": start.isoformat().replace("+00:00", "Z"),
            "interval.endTime": end.isoformat().replace("+00:00", "Z"),
            "aggregation.alignmentPeriod": str(alignment_seconds) + "s",
            "aggregation.perSeriesAligner": "ALIGN_SUM",
            "pageSize": "1000",
        }
        if page_token:
            params["pageToken"] = page_token
        result = api("https://monitoring.googleapis.com/v3/projects/" + PROJECT +
                     "/timeSeries?" + urlencode(params), token)
        output.extend(result.get("timeSeries", []))
        page_token = result.get("nextPageToken", "")
        if not page_token:
            return output
    raise RuntimeError("monitoring_page_limit_no_complete_evidence")


def job_executions(token, start):
    result = {}
    for job in JOBS:
        executions, page_token = [], ""
        for _ in range(2):
            params = {"pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token
            url = (f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/jobs/"
                   f"{job}/executions?" + urlencode(params))
            try:
                payload = api(url, token)
            except (HTTPError, URLError, TimeoutError):
                result[job] = {"status": "unavailable"}
                break
            for entry in payload.get("executions", []):
                raw = entry.get("startTime") or entry.get("createTime")
                if not raw:
                    continue
                try:
                    at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if at >= start:
                    executions.append({"started_utc": at.isoformat(),
                                       "finished_utc": entry.get("completionTime"),
                                       "completed": any(c.get("type") == "Completed" and
                                                        c.get("state") == "CONDITION_SUCCEEDED"
                                                        for c in entry.get("conditions", []))})
            page_token = payload.get("nextPageToken", "")
            if not page_token:
                break
        if job not in result:
            result[job] = {"status": "observed", "executions": executions,
                           "truncated": bool(page_token)}
    return result


def summarize_five_minute(series):
    totals = defaultdict(lambda: {"ReadObject": 0, "GetObjectMetadata": 0})
    for item in series:
        if item.get("resource", {}).get("labels", {}).get("bucket_name") != BUCKET:
            continue
        method = item.get("metric", {}).get("labels", {}).get("method")
        if method not in {"ReadObject", "GetObjectMetadata"}:
            continue
        for point in item.get("points", []):
            end = point.get("interval", {}).get("endTime")
            if not end:
                continue
            stamp = datetime.fromisoformat(end.replace("Z", "+00:00"))
            bucket = stamp.strftime("%Y-%m-%dT%H:%MZ")
            totals[bucket][method] += int(point.get("value", {}).get("int64Value") or 0)
    points = [{"time_utc": k, **v, "total": sum(v.values())} for k, v in totals.items()]
    cycle = defaultdict(list)
    for p in points:
        minute = int(p["time_utc"][14:16])
        cycle[minute].append(p["total"])
    # Not caller attribution; peak alignment is only circumstantial evidence.
    return {
        "five_minute_top_intervals": sorted(points, key=lambda p: -p["total"])[:18],
        "five_minute_by_clock_minute_avg": [
            {"minute": minute, "average_requests": round(sum(vals) / len(vals), 1),
             "observations": len(vals)} for minute, vals in sorted(cycle.items())
        ],
        "five_minute_count": len(points),
    }


def run():
    end = datetime.now(timezone.utc) - timedelta(minutes=15)
    start = end - timedelta(hours=48)
    record = {"component": "finops-gcs-read-attribution", "start_utc": start.isoformat(),
              "end_utc": end.isoformat(), "metric": "storage.googleapis.com/api/request_count",
              "asserted_caller_attribution": False, "billing_sku_verified": False,
              "caveat": "Hourly bucket/method correlation cannot identify individual callers or GCS object types."}
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"],
                                        stderr=subprocess.DEVNULL, text=True, timeout=25).strip()
        if not token:
            raise RuntimeError("identity_unavailable")
        metrics = monitored_hours(token, start, end)
        record.update(status="observed", **summarize_hourly(metrics))
        record.update(summarize_five_minute(monitored_hours(
            token, end - timedelta(hours=18), end, alignment_seconds=300)))
        record["cloud_run"] = job_executions(token, start)
        return record
    except HTTPError as ex:
        return {**record, "status": "blocked", "reason": "monitoring_http", "http": ex.code}
    except (URLError, TimeoutError, ValueError, RuntimeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as ex:
        return {**record, "status": "blocked", "reason": type(ex).__name__}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result["status"] == "observed" else 2)
