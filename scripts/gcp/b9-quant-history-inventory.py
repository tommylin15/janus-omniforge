"""Read-only inventory of immutable B9 market membership history.

Never turns a date-stamped current selection into verified past PIT membership.
Only safe aggregate counts are printed; no owner/private data or symbol list.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

BUCKET = "gen-lang-client-0593591102-dev-mart"
URI = "gs://" + BUCKET + "/executions/*/market-membership.json"
PATH = re.compile(r"^gs://" + BUCKET + r"/executions/[a-z0-9-]+/market-membership\.json$")


def known_date(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def summarize(records, *, truncated=False):
    """Records are (immutable path, parsed JSON, original byte sha256)."""
    by_date, counts = defaultdict(set), Counter()
    for uri, item, byte_hash in records:
        if not PATH.fullmatch(uri):
            raise ValueError("market membership path outside existing Mart allowlist")
        as_of = known_date(item.get("analysis_as_of"))
        symbols = item.get("symbols")
        version = item.get("membership_version")
        if as_of is None or not isinstance(symbols, list) or not symbols or len(symbols) > 500 or (
                len(symbols) != len(set(symbols))) or not isinstance(version, str) or not version:
            counts["invalid_immutable_membership_shape"] += 1
            continue
        counts["valid_shape_only"] += 1
        by_date[as_of.isoformat()].add((tuple(sorted(symbols)), version))
        clocks = (known_date(item.get("source_published_at")),
                  known_date(item.get("source_observed_at")))
        if not all(clocks) or not item.get("source_provenance_id") or (
                item.get("source_authorization") != "official"):
            counts["missing_source_time_or_authorization"] += 1
        elif max(clocks) > as_of:
            counts["later_source_observation"] += 1
        else:
            counts["source_clock_fields_claimed_pit"] += 1
        if not byte_hash.startswith("sha256:"):
            raise ValueError("missing immutable byte hash")
    conflicts = sum(len(variants) > 1 for variants in by_date.values())
    verified = 0  # metadata alone cannot independently prove original history.
    return {
        "schema_version": "b9-historical-market-membership-inventory-v1",
        "immutable_artifacts_scanned": len(records),
        "distinct_as_of_dates": len(by_date),
        "earliest_as_of": min(by_date) if by_date else None,
        "latest_as_of": max(by_date) if by_date else None,
        "conflicting_dates": conflicts,
        "counts": dict(counts), "inventory_truncated": truncated,
        "independently_verified_historical_pit_dates": verified,
        "status": "insufficient_historical_pit_source_evidence",
        "source_readback": "immutable_bytes_only",
        "canonical_write": False, "retraining": False,
        "promotion_eligible": False,
    }


def inventory(*, maximum=256):
    if not 1 <= maximum <= 512:
        raise ValueError("bounded GCS inventory required")
    listed = subprocess.run(["gcloud", "storage", "ls", URI],
                            capture_output=True, text=True, timeout=90, check=True)
    paths = sorted(set(line.strip() for line in listed.stdout.splitlines() if line.strip()))
    if any(not PATH.fullmatch(uri) for uri in paths):
        raise ValueError("unexpected GCS object outside allowlist")
    truncated = len(paths) > maximum
    records = []
    for uri in paths[:maximum]:
        raw = subprocess.run(["gcloud", "storage", "cat", uri],
                             capture_output=True, timeout=45, check=True).stdout
        records.append((uri, json.loads(raw), "sha256:" + sha256(raw).hexdigest()))
    return summarize(records, truncated=truncated)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--maximum", type=int, default=256)
    args = p.parse_args()
    result = inventory(maximum=args.maximum)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    print("B9 HISTORICAL PIT MEMBERSHIP INVENTORY ONLY; MODEL QUALITY NOT VERIFIED")


if __name__ == "__main__":
    main()
