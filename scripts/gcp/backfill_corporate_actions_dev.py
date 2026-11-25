"""一次性將歷史除權息（TWSE TWT49U + TPEx 歷史）回補至 Dev control.corporate_actions。

透過既有 janus-ingestion-core Cloud Run Job 與 janus_control 身分寫入，
不新增資料庫角色、不修改既有 IAM 或網路設定，且不觸及任何私人帳本。
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.corporate_actions import CorporateActionRecord, fetch_historical_corporate_actions

REMOTE_UPSERT_SCRIPT = """import base64,json,os,zlib
from datetime import date,datetime,timezone
from decimal import Decimal
from ingestion_core.__main__ import _control_plane
raw=zlib.decompress(base64.b64decode(os.environ['JANUS_CA_ZLIB_B64']))
rows=json.loads(raw.decode('utf-8'))
ctrl=_control_plane()
try:
 with ctrl._tx() as cur:
  cur.execute("SELECT to_regclass('control.corporate_actions')")
  assert cur.fetchone()[0] is not None, 'control.corporate_actions missing'
  for r in rows:
   cur.execute(
    \"\"\"INSERT INTO control.corporate_actions(
        action_id,symbol,market,security_type,ex_date,payment_date,
        action_type,cash_dividend_per_share,stock_dividend_ratio,
        par_value,source_name,source_updated_at)
       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
       ON CONFLICT(symbol,ex_date,action_type) DO UPDATE SET
        market=EXCLUDED.market,security_type=EXCLUDED.security_type,
        payment_date=COALESCE(EXCLUDED.payment_date,control.corporate_actions.payment_date),
        cash_dividend_per_share=EXCLUDED.cash_dividend_per_share,
        stock_dividend_ratio=EXCLUDED.stock_dividend_ratio,
        par_value=EXCLUDED.par_value,source_name=EXCLUDED.source_name,
        source_updated_at=EXCLUDED.source_updated_at\"\"\",
    (r[0],r[1],r[2],r[3],date.fromisoformat(r[4]),date.fromisoformat(r[5]) if r[5] else None,
     r[6],Decimal(r[7]),Decimal(r[8]),Decimal(r[9]) if r[9] else None,r[10],datetime.now(timezone.utc)))
  cur.execute("SELECT COUNT(*),MIN(ex_date)::text,MAX(ex_date)::text FROM control.corporate_actions")
  cnt,mn,mx=cur.fetchone()
 print(json.dumps({'operation':'corporate_actions_backfill','upserted':len(rows),'total_rows':cnt,'min_ex_date':mn,'max_ex_date':mx}))
finally:
 ctrl.close()
"""


def _serialize_records(records: tuple[CorporateActionRecord, ...]) -> list[list[str | None]]:
    return [
        [
            r.action_id,
            r.symbol,
            r.market,
            r.security_type,
            r.ex_date.isoformat(),
            r.payment_date.isoformat() if r.payment_date else None,
            r.action_type,
            str(r.cash_dividend_per_share),
            str(r.stock_dividend_ratio),
            str(r.par_value) if r.par_value is not None else None,
            r.source_name,
        ]
        for r in records
    ]


def _encode_batch_b64(batch: list[list[str | None]]) -> str:
    raw = json.dumps(batch, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")


def build_batches(records: tuple[CorporateActionRecord, ...], *, max_b64_bytes: int = 24000) -> list[str]:
    """將序列化公司行動切分為符合 Cloud Run 環境變數長度限制的壓縮批次。"""
    serialized = _serialize_records(records)
    if not serialized:
        return []
    encoded_batches: list[str] = []
    chunk_size = 500
    idx = 0
    while idx < len(serialized):
        size = min(chunk_size, len(serialized) - idx)
        while size > 1:
            candidate = _encode_batch_b64(serialized[idx : idx + size])
            if len(candidate) <= max_b64_bytes:
                break
            size = max(1, size // 2)
        encoded = _encode_batch_b64(serialized[idx : idx + size])
        if len(encoded) > max_b64_bytes:
            raise ValueError("single corporate action row exceeds env size limit")
        encoded_batches.append(encoded)
        idx += size
    return encoded_batches


def _run_job_batch(cloud, fence, job_fn, terminal, root: str, b64_payload: str) -> str:
    source = job_fn("janus-ingestion-core")
    fence()
    container = source["template"]["template"]["containers"][0]
    args = (["python"] if not container.get("command") else []) + ["-c", REMOTE_UPSERT_SCRIPT]
    override: dict = {
        "args": args,
        "env": [{"name": "JANUS_CA_ZLIB_B64", "value": b64_payload}],
    }
    if container.get("name"):
        override["name"] = container["name"]
    body = {
        "etag": source["etag"],
        "overrides": {"taskCount": 1, "timeout": "300s", "containerOverrides": [override]},
    }
    operation = cloud(f"{root}/jobs/janus-ingestion-core:run", body, "POST")
    name = operation.get("name", "")
    if not name.startswith(root + "/operations/"):
        raise RuntimeError("backfill dispatch unknown")
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        current = cloud(name)
        if current.get("done"):
            if current.get("error"):
                raise RuntimeError("backfill job operation failed")
            execution = current.get("response", {})
            execution_name = execution.get("name", "")
            if execution_name.startswith(root + "/jobs/janus-ingestion-core/executions/"):
                execution = cloud(execution_name)
            if terminal(execution) and execution.get("succeededCount") == 1 and not execution.get("failedCount", 0):
                return execution_name
            if terminal(execution):
                raise RuntimeError("backfill execution failed")
        time.sleep(3)
    raise RuntimeError("backfill execution timed out")


def main() -> None:
    from ghcr_jobs_rollout import ROOT, cloud, fence, job, terminal

    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--include-rights-detail", default="true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    start_d = date.fromisoformat(args.start_date.strip())
    end_d = date.fromisoformat(args.end_date.strip()) if args.end_date.strip() else datetime.now(timezone.utc).date()
    include_detail = args.include_rights_detail.strip().lower() in {"1", "true", "yes", "on"}

    records = fetch_historical_corporate_actions(
        start_d,
        end_d,
        include_rights_detail=include_detail,
        pause_seconds=0.02,
    )
    batches = build_batches(records)
    executions: list[str] = []
    for b64 in batches:
        executions.append(_run_job_batch(cloud, fence, job, terminal, ROOT, b64))

    dates = [r.ex_date.isoformat() for r in records]
    receipt = {
        "status": "PASS",
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "include_rights_detail": include_detail,
        "fetched_records": len(records),
        "cash_records": sum(1 for r in records if r.action_type == "CASH_DIVIDEND"),
        "stock_records": sum(1 for r in records if r.action_type == "STOCK_DIVIDEND"),
        "min_ex_date": min(dates) if dates else None,
        "max_ex_date": max(dates) if dates else None,
        "batch_count": len(batches),
        "executions": executions,
    }
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
