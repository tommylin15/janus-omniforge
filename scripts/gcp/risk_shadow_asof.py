#!/usr/bin/env python3
"""Resolve latest *actual* immutable Core EOD snapshot date for one dev Risk shadow job.

Pure resolver is testable; CLI makes bounded authenticated read-only GCS JSON calls.
Never prints snapshot contents, credentials or model output. Matches
specialist_runtime.latest_training_input: max(updated,name) over all
executions/<id>/core-snapshot.json; fail closed on any stale/invalid latest item.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from hashlib import sha256
import json
import os
import re
import subprocess
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BUCKET = "gen-lang-client-0593591102-dev-core"
NAME = re.compile(r"^executions/([A-Za-z0-9_-]+)/core-snapshot\.json$")


def select_latest(items, read_bytes, today: date) -> dict:
    eligible = [item for item in items if NAME.fullmatch(str(item.get("name", "")))]
    if not eligible:
        raise ValueError("no_core_snapshot")
    latest = max(eligible, key=lambda item: (str(item.get("updated") or ""),
                                             str(item["name"])))
    raw = read_bytes(latest["name"])
    core = json.loads(raw)
    name_match = NAME.fullmatch(latest["name"])
    if (not isinstance(core, dict)
        or core.get("execution_id") != name_match.group(1)
        or not isinstance(core.get("snapshot_id"), str)
        or not core["snapshot_id"]
        or not isinstance(core.get("iceberg_tables"), dict)
        or not core["iceberg_tables"]):
        raise ValueError("latest_core_snapshot_invalid")
    as_of = date.fromisoformat(str(core["analysis_as_of"]))
    age = (today - as_of).days
    if age < 0 or age > 7:
        raise ValueError("latest_core_snapshot_out_of_age_bounds")
    return {
        "analysis_as_of": as_of.isoformat(),
        "age_days": age,
        "core_snapshot_hash": sha256(raw).hexdigest(),
        "core_snapshot_id_sha256": sha256(core["snapshot_id"].encode()).hexdigest(),
    }


def gcs_latest() -> dict:
    access_token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True, timeout=30).strip()
    if not access_token:
        raise RuntimeError("gcp_identity_unavailable")

    def read_json(url):
        with urlopen(Request(url, headers={"Authorization": f"Bearer {access_token}"}),
                     timeout=30) as stream:
            return json.load(stream)

    objects = []
    token = None
    for _ in range(100):
        params = {"prefix": "executions/", "maxResults": 1000, "fields": "items(name,updated),nextPageToken"}
        if token:
            params["pageToken"] = token
        data = read_json(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?"
                         + urlencode(params))
        objects.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            break
    else:
        raise RuntimeError("gcs_inventory_exceeds_page_bound")

    def load(name):
        url = (f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/"
               f"{quote(name, safe='')}?alt=media")
        with urlopen(Request(url, headers={"Authorization": f"Bearer {access_token}"}),
                     timeout=30) as stream:
            return stream.read(4_000_001)

    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    result = select_latest(objects, load, today)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--github-env", required=True)
    p.add_argument("--receipt", required=True)
    args = p.parse_args()
    result = gcs_latest()
    with open(args.github_env, "a", encoding="utf-8") as env:
        env.write(f"SCREENING_DATE={result['analysis_as_of']}\n")
    with open(args.receipt, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True)
    print(json.dumps({"resolved_date": result["analysis_as_of"],
                      "source_age_days": result["age_days"],
                      "core_hash_sha256_prefix": result["core_snapshot_hash"][:12]}))


if __name__ == "__main__":
    main()
