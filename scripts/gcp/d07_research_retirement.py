#!/usr/bin/env python3
"""D07-PRE one-shot bounded retirement of unreferenced legacy research cloud resources.

Never drops shared Core/Mart/Owner assets. No access to research payload, tokens
or secret values in receipts. Invoked only with the committed approved request.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
CONFIG = Path("ops/d07-research-retirement.json")
OUTPUT = Path("d07-research-retirement-receipt.json")
RUN = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
SCHED = f"https://cloudscheduler.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}"
BQ = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}"
MAX_PAGES = 15
# Exact legacy research identifiers, not pattern-based whole-project pruning.
RESEARCH_JOBS = frozenset({
    "janus-research-big-move-500", "janus-specialist-retrain",
    "janus-ml-oos", "janus-ml-oos-retrain",
})
RESEARCH_SCHEDULERS = frozenset({
    "janus-research-big-move-500", "janus-specialist-retrain",
    "janus-specialist-retrain-monthly", "janus-ml-oos",
})
# These datasets (if they exist) are entirely dedicated to old ML/OOS experiments.
RESEARCH_DATASETS = frozenset({
    "janus_research_ml_oos", "janus_ml_oos", "janus_legacy_research",
    "janus_specialist_training",
})
RESEARCH_TABLES = frozenset({
    "b5_ml_oos", "b6_ml_oos_cache", "b7_ml_oos_reconciliation",
    "b8_ml_oos_comparison", "specialist_retrain", "specialist_training",
})
PROTECTED = ("owner", "private", "portfolio", "market", "screen",
             "core", "serving", "backup", "stage", "iceberg", "api", "ledger")


def request_json(uri, token, method="GET"):
    req = Request(uri, headers={"Authorization": "Bearer " + token,
                                "Accept": "application/json"}, method=method)
    try:
        with urlopen(req, timeout=35) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return None
        # Never expose remote error body: it may contain project configuration.
        raise RuntimeError(f"gcp_{method.lower()}_http_{exc.code}") from None


def all_pages(base, key, token, page_name="pageToken", size_name="pageSize"):
    result, seen, uri = [], set(), base
    for _ in range(MAX_PAGES):
        data = request_json(uri, token)
        if data is None:
            raise RuntimeError("listing_disappeared")
        result.extend(data.get(key, []))
        after = data.get("nextPageToken")
        if not after:
            return result
        if after in seen:
            raise RuntimeError("pagination_loop")
        seen.add(after)
        separator = "&" if "?" in base else "?"
        uri = base + separator + urlencode({page_name: after})
    raise RuntimeError("pagination_limit_exceeded")


def identifier(resource):
    return str(resource.get("name", resource.get("jobReference", ""))).rsplit("/", 1)[-1]


def active_reference(raw, name):
    # Check JSON serialized metadata, never print it. Match whole token.
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", raw) is not None


def inventory(token):
    jobs = all_pages(RUN + "/jobs?pageSize=100", "jobs", token)
    schedulers = all_pages(SCHED + "/jobs?pageSize=100", "jobs", token)
    datasets = all_pages(BQ + "/datasets?all=true&maxResults=100", "datasets", token)
    bq_tables = {}
    for ds in datasets:
        dsid = ds["datasetReference"]["datasetId"]
        tables = all_pages(BQ + "/datasets/" + quote(dsid) + "/tables?maxResults=100",
                           "tables", token)
        bq_tables[dsid] = tables
    return jobs, schedulers, datasets, bq_tables


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config != {"intent": "retire-unreferenced-d07-legacy-research",
                   "project": PROJECT, "region": REGION, "apply": True}:
        raise ValueError("unexpected_retirement_request")
    token = subprocess.run(["gcloud", "auth", "print-access-token"],
                           check=True, capture_output=True, text=True, timeout=25).stdout.strip()
    if not token:
        raise RuntimeError("missing_wif_access_token")
    jobs, schedulers, datasets, table_sets = inventory(token)
    job_names = {identifier(job): job for job in jobs}
    sched_names = {identifier(sch): sch for sch in schedulers}
    candidates = {
        "jobs": sorted(RESEARCH_JOBS & job_names.keys()),
        "schedulers": sorted(RESEARCH_SCHEDULERS & sched_names.keys()),
        "datasets": sorted(RESEARCH_DATASETS & table_sets.keys()),
        "tables": sorted(f"{ds}.{t['tableReference']['tableId']}"
                         for ds, ts in table_sets.items()
                         for t in ts if t["tableReference"]["tableId"] in RESEARCH_TABLES),
    }
    output = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT, "region": REGION, "intent": config["intent"],
        "inventory": {"jobs": len(jobs), "schedulers": len(schedulers),
                      "datasets": len(datasets), "tables": sum(map(len, table_sets.values())),
                      "job_ids": sorted(job_names), "scheduler_ids": sorted(sched_names),
                      "dataset_ids": sorted(table_sets),
                      "table_ids": sorted(f"{ds}.{t['tableReference']['tableId']}"
                                          for ds, ts in table_sets.items() for t in ts)},
        "candidates": candidates, "deleted": {"jobs": [], "schedulers": [],
                                                "tables": [], "datasets": []},
        "blocked": {}, "remaining": {}, "status": "PARTIAL",
        "scope": "retired_dedicated_research_only",
        "shared_jobs_untouched": True, "gcs_data_deleted": 0,
    }

    def safe_delete(uri, name, bucket):
        try:
            request_json(uri, token, method="DELETE")
            if request_json(uri, token) is not None:
                output["blocked"][name] = "delete_not_absent_on_readback"
            else:
                output["deleted"][bucket].append(name)
        except RuntimeError as exc:
            output["blocked"][name] = str(exc)

    # Dedicated Scheduler jobs only. Keep centralized Janus Scheduler.
    for name in candidates["schedulers"]:
        target = json.dumps(sched_names[name].get("httpTarget", {}),
                            separators=(",", ":"), sort_keys=True)
        if any(active_reference(target, p) for p in PROTECTED):
            output["blocked"]["scheduler:" + name] = "references_protected_runtime"
            continue
        safe_delete(SCHED + "/jobs/" + quote(name), name, "schedulers")

    # Never remove a Job that still has any Scheduler targeting it.
    current_schedules = all_pages(SCHED + "/jobs?pageSize=100", "jobs", token)
    for name in candidates["jobs"]:
        if any(active_reference(json.dumps(s, sort_keys=True), name) for s in current_schedules):
            output["blocked"]["job:" + name] = "live_scheduler_reference"
            continue
        if any(word in name for word in PROTECTED):
            output["blocked"]["job:" + name] = "protected_runtime_name"
            continue
        safe_delete(RUN + "/jobs/" + quote(name), name, "jobs")

    # Read actual BQ table metadata and block if any view references candidates.
    view_defs = []
    for ds, tables in table_sets.items():
        for table in tables:
            tid = table["tableReference"]["tableId"]
            if table.get("type") in ("VIEW", "MATERIALIZED_VIEW"):
                detail = request_json(BQ + "/datasets/" + quote(ds) +
                                      "/tables/" + quote(tid), token)
                if detail:
                    view_defs.append((f"{ds}.{tid}",
                                      json.dumps(detail.get("view", detail.get("materializedView", {})))))
    for fq in candidates["tables"]:
        ds, tid = fq.split(".", 1)
        if any(word in ds or word in tid for word in PROTECTED):
            output["blocked"]["table:" + fq] = "canonical_or_shared_resource"
            continue
        if any((active_reference(definition, tid) or active_reference(definition, fq))
               and ref != fq for ref, definition in view_defs):
            output["blocked"]["table:" + fq] = "active_view_dependency"
            continue
        safe_delete(BQ + "/datasets/" + quote(ds) +
                    "/tables/" + quote(tid), fq, "tables")

    # Dataset deletion is nonrecursive: cannot accidentally erase unrelated tables.
    for ds in candidates["datasets"]:
        if any(word in ds for word in PROTECTED):
            output["blocked"]["dataset:" + ds] = "protected_name"
            continue
        table_readback = all_pages(BQ + "/datasets/" + quote(ds) +
                                   "/tables?maxResults=100", "tables", token)
        if table_readback:
            output["blocked"]["dataset:" + ds] = "not_empty_or_unreviewed_tables"
            continue
        safe_delete(BQ + "/datasets/" + quote(ds), ds, "datasets")

    after_jobs, after_sched, after_ds, after_tables = inventory(token)
    after_names = {
        "jobs": {identifier(o) for o in after_jobs},
        "schedulers": {identifier(o) for o in after_sched},
        "datasets": set(after_tables),
        "tables": {f"{ds}.{t['tableReference']['tableId']}"
                   for ds, rows in after_tables.items() for t in rows},
    }
    output["remaining"] = {key: sorted(set(values) & after_names[key])
                           for key, values in candidates.items()}
    output["status"] = ("PASS" if not output["remaining"]["jobs"]
                        and not output["remaining"]["schedulers"]
                        and not output["remaining"]["tables"]
                        and not output["remaining"]["datasets"]
                        and not output["blocked"] else "PARTIAL")
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
