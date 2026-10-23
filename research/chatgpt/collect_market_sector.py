#!/usr/bin/env python3
"""ChatGPT-operated TWSE/TPEx market + sector collector.

Runs the existing fail-closed v3.8.4 collector outside Colab. Intended for
GitHub Actions initiated by ChatGPT, producing a portable artifact that can be
copied to the janusChatGPT Drive folder after the run.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def load_collector(repo_root: Path):
    path = repo_root / "research" / "colab" / "official_index_backfill.py"
    spec = importlib.util.spec_from_file_location("official_index_backfill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load collector: {path}")
    module = importlib.util.module_from_spec(spec)
    # Python 3.12 dataclasses resolves annotations through sys.modules while
    # the class decorator is executing, so register the module before exec.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="out")
    parser.add_argument("--start-month", default="2025-01")
    parser.add_argument("--end-month", default="2026-09")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=300)
    parser.add_argument("--max-minutes", type=int, default=60)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    collector = load_collector(repo_root)
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    pass_summaries: list[dict[str, Any]] = []
    prior_progress: tuple[int, int] | None = None

    for index in range(1, args.passes + 1):
        options = collector.RunOptions(
            start_month=args.start_month,
            end_month=args.end_month,
            max_requests=args.max_requests,
            max_minutes=args.max_minutes,
            interval_seconds=args.interval_seconds,
            include_twse_sector=True,
            include_tpex_sector=True,
        )
        summary = collector.backfill(root, options)
        summary["pass"] = index
        pass_summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

        verified = sum(int(v) for v in summary["partition_verified_counts"].values())
        outstanding = int(summary["outstanding_partition_count"])
        progress = (verified, outstanding)
        if summary["status"] == "SOURCE_DATA_VERIFIED_COMPLETE":
            break
        if prior_progress is not None and progress == prior_progress:
            break
        prior_progress = progress

    result = {
        "collector_version": collector.VERSION,
        "start_month": args.start_month,
        "end_month": args.end_month,
        "passes": pass_summaries,
        "final": pass_summaries[-1] if pass_summaries else None,
    }
    (root / "chatgpt_collection_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Partial data is still uploaded for diagnosis; completion is decided from
    # the receipt summary, never from process exit alone.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
