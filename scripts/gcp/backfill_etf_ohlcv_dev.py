"""觸發 Dev 既有 janus-ingestion-core Cloud Run Job 執行已註冊 ETF 官方盤後 EOD OHLCV 回補。"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
import time
from typing import Any

GCP_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(GCP_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(GCP_SCRIPTS_DIR))


def _trigger_etf_backfill(
    cloud: Any,
    fence: Any,
    job_fn: Any,
    terminal: Any,
    root: str,
    *,
    start_date: date,
    end_date: date,
    markets: tuple[str, ...],
    symbols: tuple[str, ...],
) -> str:
    source = job_fn("janus-ingestion-core")
    fence()
    container = source["template"]["template"]["containers"][0]
    command = container.get("command")
    if command not in (None, [], ["python"]):
        raise ValueError("unexpected_ingestion_container_command")
    args = (["python"] if not command else []) + ["-m", "ingestion_core.entrypoint"]
    env_list = [
        {"name": "JANUS_DATA_SUPPLEMENT_MODE", "value": "etf-ohlcv-backfill"},
        {"name": "BACKFILL_START_DATE", "value": start_date.isoformat()},
        {"name": "BACKFILL_END_DATE", "value": end_date.isoformat()},
        {"name": "ETF_BACKFILL_MARKETS", "value": ",".join(markets)},
    ]
    if symbols:
        env_list.append({"name": "ETF_BACKFILL_SYMBOLS", "value": ",".join(symbols)})
    override: dict[str, Any] = {"args": args, "env": env_list}
    if container.get("name"):
        override["name"] = container["name"]

    body = {
        "etag": source["etag"],
        "overrides": {
            "taskCount": 1,
            "timeout": "600s",
            "containerOverrides": [override],
        },
    }
    operation = cloud(f"{root}/jobs/janus-ingestion-core:run", body, "POST")
    name = operation.get("name", "")
    if not name.startswith(root + "/operations/"):
        raise RuntimeError("etf_backfill_dispatch_unknown")

    deadline = time.monotonic() + 660
    while time.monotonic() < deadline:
        current = cloud(name)
        if current.get("done"):
            if current.get("error"):
                raise RuntimeError("etf_backfill_operation_failed")
            execution = current.get("response", {})
            execution_name = execution.get("name", "")
            while (
                execution_name.startswith(root + "/jobs/janus-ingestion-core/executions/")
                and not terminal(execution)
                and time.monotonic() < deadline
            ):
                time.sleep(5)
                execution = cloud(execution_name)
            if terminal(execution) and execution.get("succeededCount") == 1 and not execution.get("failedCount", 0):
                return execution_name or execution.get("name", "")
            raise RuntimeError("etf_backfill_execution_failed")
        time.sleep(5)
    raise RuntimeError("etf_backfill_execution_timed_out")


def main() -> None:
    from ghcr_jobs_rollout import ROOT, cloud, fence, job, terminal

    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--markets", default="TWSE,TPEX")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    start_d = date.fromisoformat(args.start_date.strip())
    end_d = date.fromisoformat(args.end_date.strip())
    if start_d > end_d or (end_d - start_d).days > 31:
        raise ValueError("date range must be 1..31 days")

    markets = tuple(dict.fromkeys(m.strip().upper() for m in args.markets.split(",") if m.strip()))
    if not markets or not set(markets).issubset({"TWSE", "TPEX"}):
        raise ValueError("markets must be subset of TWSE,TPEX")

    symbols = tuple(dict.fromkeys(s.strip().upper() for s in args.symbols.split(",") if s.strip()))

    execution_name = _trigger_etf_backfill(
        cloud,
        fence,
        job,
        terminal,
        ROOT,
        start_date=start_d,
        end_date=end_d,
        markets=markets,
        symbols=symbols,
    )
    receipt = {
        "status": "PASS",
        "operation": "etf-ohlcv-backfill",
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "markets": list(markets),
        "symbols": list(symbols),
        "execution": execution_name,
    }
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
