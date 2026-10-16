"""Bounded, read-only GCS method/hour audit for Iceberg post-release comparisons.

Reads Cloud Monitoring only. It does not infer billable cost or causal savings
from unequal workload windows, and does not read object payloads.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT="gen-lang-client-0593591102"
BUCKET=PROJECT+"-dev-core"
METHODS=("ReadObject","GetObjectMetadata","ListObjects","WriteObject","DeleteObject")

def aggregate(series):
    by_method=defaultdict(lambda:defaultdict(int))
    for item in series:
        if item.get("resource",{}).get("labels",{}).get("bucket_name")!=BUCKET:
            continue
        method=item.get("metric",{}).get("labels",{}).get("method")
        if method not in METHODS:continue
        for point in item.get("points",[]):
            end=point.get("interval",{}).get("endTime")
            if not end:continue
            timestamp=datetime.fromisoformat(end.replace("Z","+00:00"))
            hour=timestamp.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:00 +08")
            count=int(point.get("value",{}).get("int64Value") or 0)
            if count<0:raise RuntimeError("NEGATIVE_GCS_COUNTER")
            by_method[hour][method]+=count
    return [{"hour":h,**{m:by_method[h].get(m,0) for m in METHODS}}
            for h in sorted(by_method)]

def run():
    end=(datetime.now(timezone.utc)-timedelta(minutes=10)).replace(minute=0,second=0,microsecond=0)
    start=end-timedelta(hours=48)
    access=subprocess.check_output(["gcloud","auth","print-access-token"],
          text=True,stderr=subprocess.DEVNULL,timeout=30).strip()
    series=[]
    next_page=""
    for _ in range(10):
        params={"filter":'metric.type="storage.googleapis.com/api/request_count" AND resource.type="gcs_bucket" AND resource.labels.bucket_name="'+BUCKET+'"',
                "interval.startTime":start.isoformat().replace("+00:00","Z"),
                "interval.endTime":end.isoformat().replace("+00:00","Z"),
                "aggregation.alignmentPeriod":"300s","aggregation.perSeriesAligner":"ALIGN_SUM",
                "pageSize":"1000"}
        if next_page:params["pageToken"]=next_page
        url="https://monitoring.googleapis.com/v3/projects/"+PROJECT+"/timeSeries?"+urlencode(params)
        req=Request(url,headers={"Authorization":"Bearer "+access})
        with urlopen(req,timeout=40) as response:
            doc=json.load(response)
        series.extend(doc.get("timeSeries",[]))
        next_page=doc.get("nextPageToken","")
        if not next_page:break
    if next_page:raise RuntimeError("GCS_IO_METRIC_PAGINATION_LIMIT")
    hours=aggregate(series)
    return {"component":"finops-gcs-method-hourly-audit","status":"OBSERVED" if hours else "UNKNOWN",
            "project":PROJECT,"bucket":BUCKET,"method_counts_by_taipei_hour":hours,
            "start_utc":start.isoformat(),"end_utc":end.isoformat(),
            "causal_savings_percent":None,"billing_cost":None,
            "matched_workload_verified":False,
            "note":"48 complete UTC hours only. Hourly counters alone cannot match stock counts, source dates, cold/warm ratios or concurrent maintenance; causal savings remain unknown."}
if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
