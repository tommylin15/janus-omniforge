#!/usr/bin/env python3
"""Offline Event label candidate/holdout interface. Never performs canonical writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))
from intelligence_mart.event_labeling import (
    approved_dataset, chronological_oos, from_core_events,
)

MAX_RECORDS = 2000
MAX_RECORD_BYTES = 524288


def _jsonl(path):
    result = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if len(line.encode("utf-8")) > MAX_RECORD_BYTES:
                raise ValueError("oversized_event_or_label")
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("JSONL records must be objects")
            result.append(record)
            if len(result) > MAX_RECORDS:
                raise ValueError("bounded_event_label_batch_exceeded")
    return result


def _create_only(path, payload):
    """Owner-readable research file; fail rather than overwrite immutable receipt."""
    target = Path(path)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=False, indent=2)
            handle.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    candidate = modes.add_parser("candidates")
    candidate.add_argument("--events-jsonl", required=True)
    candidate.add_argument("--core-snapshot-id", required=True)
    candidate.add_argument("--out", required=True)
    oos = modes.add_parser("oos")
    oos.add_argument("--candidates-json", required=True)
    oos.add_argument("--reviews-jsonl", required=True)
    oos.add_argument("--training-grants-json", required=True, help="Independently verified source-scoped rights ledger")
    oos.add_argument("--cutoff", required=True, help="ISO timestamp with timezone")
    oos.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.mode == "candidates":
        payload = from_core_events(_jsonl(args.events_jsonl), core_snapshot_id=args.core_snapshot_id)
        _create_only(args.out, payload)
        return 0
    pool = json.loads(Path(args.candidates_json).read_text(encoding="utf-8"))
    if pool.get("schema_version") != "event-label-v1" or not isinstance(pool.get("candidates"), list):
        raise ValueError("unknown_candidate_schema")
    rights = json.loads(Path(args.training_grants_json).read_text(encoding="utf-8"))
    if rights.get("schema_version") != "event-training-grants-v1" or not isinstance(rights.get("grants"), list):
        raise ValueError("unknown_training_grants_schema")
    approved = approved_dataset(pool["candidates"], _jsonl(args.reviews_jsonl), training_grants=rights["grants"])
    result = chronological_oos(approved, cutoff=args.cutoff)
    result["approved_label_count"] = len(approved)
    result["candidate_count"] = len(pool["candidates"])
    result["unreviewed_or_unapproved_count"] = len(pool["candidates"]) - len(approved)
    _create_only(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
