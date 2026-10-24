#!/usr/bin/env python3
"""Independent, bounded dev Private ledger backup retention (GCS metadata only).

Dry-run by default. No PostgreSQL mutation, pg_dump, or extra GCP resources.
One run may delete at most 3 daily + 1 weekly + 1 monthly, by generation.
Invoked by the existing VM after a Controller-requested successful backup.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-private"
ROOT = "pilot-ledger-backups/"
POLICY = {"daily": 7, "weekly": 4, "monthly": 6}
CAP = {"daily": 3, "weekly": 1, "monthly": 1}
PATTERN = {
    "weekly": re.compile(r"^pilot-ledger-backups/weekly/(\d{4}-\d{2}-\d{2})\.dump$"),
    "daily": re.compile(r"^pilot-ledger-backups/daily/(\d{4}-\d{2}-\d{2})\.dump$"),
    "monthly": re.compile(r"^pilot-ledger-backups/monthly/(\d{4}-\d{2})\.dump$"),
}
MAX_OBJECT_BYTES = 67_108_864
MAX_OBJECTS = {"daily": 60, "weekly": 16, "monthly": 24}
OUT = Path("private-ledger-backup-retention-receipt.json")
REQ = Path("ops/private-ledger-backup-retention-request.json")


def request_guard(request: dict) -> None:
    if not (
        request.get("intent") == "dev-private-ledger-retention-independent"
        and request.get("scope") == "existing-dev-private-backup-prefixes"
        and request.get("dry_run_first") is True
        and request.get("daily_keep") == 7
        and request.get("weekly_keep") == 4
        and request.get("max_weekly_deletes_per_run") == 1
        and request.get("monthly_keep") == 6
        and request.get("max_daily_deletes_per_run") == 3
        and request.get("max_monthly_deletes_per_run") == 1
        and request.get("no_new_resources") is True
        and request.get("no_iam_expansion") is True
        and request.get("no_pg_mutation") is True
        and request.get("no_new_backup") is True
    ):
        raise ValueError("retention_request_policy_or_scope_invalid")


def access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, timeout=20, check=False
    )
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("existing_wif_token_unavailable")
    return result.stdout.strip()


def api(token: str, object_path: str, *, params=None, method="GET"):
    if method not in ("GET", "DELETE"):
        raise ValueError("retention_http_method_outside_allowlist")
    url = "https://storage.googleapis.com/storage/v1/b/" + quote(BUCKET, safe="") + object_path
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Authorization": "Bearer " + token}, method=method)
    try:
        with urlopen(request, timeout=35) as reply:
            raw = reply.read()
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        raise RuntimeError(f"gcs_retention_http_{error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("gcs_retention_transport_error") from None


def inventory(token, kind: str) -> list[dict]:
    if kind not in POLICY:
        raise ValueError("unknown_backup_kind")
    prefix = ROOT + kind + "/"
    page, pages, result, seen = None, 0, [], set()
    while True:
        params = {
            "prefix": prefix, "versions": "false", "maxResults": 100,
            "fields": "nextPageToken,items(name,generation,size,timeCreated)"
        }
        if page:
            params["pageToken"] = page
        data = api(token, "/o", params=params)
        values = data.get("items") or []
        if not isinstance(values, list):
            raise ValueError("retention_inventory_shape_invalid")
        result.extend(values)
        if len(result) > MAX_OBJECTS[kind]:
            raise ValueError("retention_inventory_limit_exceeded")
        page = data.get("nextPageToken")
        pages += 1
        if not page:
            break
        if page in seen or pages > 10:
            raise ValueError("retention_inventory_pagination_incomplete")
        seen.add(page)
    keys = set()
    for obj in result:
        match = PATTERN[kind].fullmatch(obj.get("name", ""))
        if not match or (obj["name"] in keys):
            raise ValueError("retention_unrecognized_or_duplicate_name")
        keys.add(obj["name"])
        if not str(obj.get("generation", "")).isdigit():
            raise ValueError("retention_generation_missing")
        if not str(obj.get("size", "")).isdigit() or not 1024 <= int(obj["size"]) <= MAX_OBJECT_BYTES:
            raise ValueError("retention_object_size_invalid")
        date_name = match.group(1)
        try:
            datetime.fromisoformat(date_name + ("-01" if kind == "monthly" else ""))
            datetime.fromisoformat(obj["timeCreated"].replace("Z", "+00:00"))
        except (TypeError, ValueError, KeyError):
            raise ValueError("retention_date_metadata_invalid") from None
    return sorted(result, key=lambda r: r["name"], reverse=True)


def keyset(rows: list[dict]):
    return {(r["name"], str(r["generation"]), str(r["size"])) for r in rows}


def plan(daily: list[dict], monthly: list[dict], *, weekly=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    weekly = weekly or []
    if len(daily) < POLICY["daily"] or not monthly:
        raise ValueError("retention_insufficient_backup_generations")
    newest = datetime.fromisoformat(daily[0]["timeCreated"].replace("Z", "+00:00"))
    hours = (now - newest).total_seconds() / 3600
    if not 0 <= hours <= 36:
        raise ValueError("retention_recent_daily_backup_not_verified")
    latest_month = datetime.fromisoformat(monthly[0]["name"].split("/")[-1][:-5] + "-01")
    month_stale = (now.date() - latest_month.date()).days > 62
    protected = {
        "daily": daily[:POLICY["daily"]],
        "weekly": weekly[:POLICY["weekly"]],
        "monthly": monthly[:POLICY["monthly"]],
    }
    expired = {
        "daily": daily[POLICY["daily"]:][:CAP["daily"]],
        "weekly": weekly[POLICY["weekly"]:][:CAP["weekly"]],
        "monthly": ([] if month_stale else monthly[POLICY["monthly"]:][:CAP["monthly"]]),
    }
    return {
        "protected": protected, "expired": expired,
        "monthly_status": "STALE_NO_MONTHLY_DELETE" if month_stale else "ELIGIBLE",
        "daily_latest_age_hours": round(hours, 2),
        "daily_count": len(daily), "monthly_count": len(monthly),
    }


def run(*, mode: str, request: dict, token=None, now=None):
    request_guard(request)
    if mode not in ("dry-run", "apply"):
        raise ValueError("retention_mode_invalid")
    if mode == "apply" and (
        request.get("approved_scheduled_apply") is not True
        or os.getenv("JANUS_BACKUP_RETENTION_SCHEDULED_APPLY") != "true"):
        raise ValueError("retention_apply_not_activated")
    token = token or access_token()
    before = {kind: inventory(token, kind) for kind in POLICY}
    p = plan(before["daily"], before["monthly"], weekly=before["weekly"], now=now)
    receipt = {
        "component": "janus_independent_private_backup_retention_v1",
        "mode": mode, "policy": POLICY,
        "status": "DRY_RUN_PASS" if mode == "dry-run" else "IN_PROGRESS",
        "count_before": {kind: len(rows) for kind, rows in before.items()},
        "bytes_before": {kind: sum(int(r["size"]) for r in rows) for kind,rows in before.items()},
        "planned_deletes": {kind: len(p["expired"][kind]) for kind in POLICY},
        "protected_count": {kind: len(p["protected"][kind]) for kind in POLICY},
        "monthly_status": p["monthly_status"],
        "daily_latest_age_hours": p["daily_latest_age_hours"],
        "actual_deletes": {kind: 0 for kind in POLICY},
        "actual_deleted_bytes": {kind: 0 for kind in POLICY},
        "private_data_read": False, "backup_reexecutions": 0,
        "iam_changes": 0, "new_resources": 0, "pg_mutations": 0,
    }
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    if mode == "apply":
        # Re-check the exact same inventory/generations before *any* DELETE.
        next_scan = {kind: inventory(token, kind) for kind in POLICY}
        if any(keyset(next_scan[k]) != keyset(before[k]) for k in POLICY):
            raise RuntimeError("retention_preapply_inventory_drift")
        for kind in POLICY:
            for obj in p["expired"][kind]:
                api(token, "/o/" + quote(obj["name"], safe=""),
                    params={"ifGenerationMatch": str(obj["generation"])},
                    method="DELETE")
                receipt["actual_deletes"][kind] += 1
                receipt["actual_deleted_bytes"][kind] += int(obj["size"])
                # Persist bounded partial-progress facts before verification.
                receipt["status"] = "PARTIAL_PENDING_READBACK"
                OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
            after = inventory(token, kind)
            expected = keyset(before[kind]) - keyset(p["expired"][kind])
            if keyset(after) != expected or not keyset(p["protected"][kind]).issubset(keyset(after)):
                raise RuntimeError("retention_generation_readback_mismatch")
        receipt["status"] = "APPLY_PASS"
        receipt["count_after"] = {kind: len(inventory(token, kind)) for kind in POLICY}
        receipt["bytes_after"] = {
            kind: sum(int(r["size"]) for r in inventory(token, kind)) for kind in POLICY
        }
        if any(receipt["bytes_before"][k] - receipt["bytes_after"][k] !=
               receipt["actual_deleted_bytes"][k] for k in POLICY):
            raise RuntimeError("retention_byte_readback_mismatch")
        OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    args = parser.parse_args()
    request = json.loads(REQ.read_text(encoding="utf-8"))
    try:
        receipt = run(mode=args.mode, request=request)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    except Exception as error:
        print(json.dumps({"status": "BLOCKED",
                          "reason_class": type(error).__name__,
                          "reason_code": str(error) if isinstance(error, (ValueError, RuntimeError)) else "unexpected_failure"},
                          sort_keys=True))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
