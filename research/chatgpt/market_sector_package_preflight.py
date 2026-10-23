#!/usr/bin/env python3
"""唯讀驗證 2025-01～2026-09 TWSE/TPEx 大盤與產業 Drive JSON 資料包。
這是研究 preflight；不變更 canonical、Registry、收檔 receipt 或模型輸入。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SOURCES = {
    "twse_market": ("TWSE", "www.twse.com.tw"),
    "tpex_market": ("TPEX", "www.tpex.org.tw"),
    "twse_sector": ("TWSE", "www.twse.com.tw"),
    "tpex_sector": ("TPEX", "www.tpex.org.tw"),
}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def months(start: str, end: str):
    a, b = map(int, start.split("-"))
    c, d = map(int, end.split("-"))
    if not (1 <= b <= 12 and 1 <= d <= 12) or (a, b) > (c, d):
        raise ValueError("invalid month range")
    while (a, b) <= (c, d):
        yield f"{a:04d}-{b:02d}"
        a, b = (a + 1, 1) if b == 12 else (a, b + 1)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_partition(root: Path, folder: Path, source: str, period: str):
    """Return partition summary and hard issues, without modifying source files."""
    issues = []
    def fail(code: str, detail: str):
        issues.append({"source": source, "period": period, "code": code, "detail": detail})
    receipt_path = folder / "receipt.json"
    if not receipt_path.is_file():
        fail("MISSING_RECEIPT", str(folder.relative_to(root)))
        return None, issues
    try:
        receipt = json.loads(receipt_path.read_text("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        fail("INVALID_RECEIPT", type(exc).__name__)
        return None, issues
    if receipt.get("status") != "VERIFIED":
        fail("NOT_VERIFIED", str(receipt.get("status")))
    if receipt.get("source") != source or receipt.get("period") != period:
        fail("RECEIPT_IDENTITY", "source/period mismatched")
    if receipt.get("classification") != "RESEARCH_ONLY":
        fail("RESEARCH_CLASSIFICATION", str(receipt.get("classification")))
    url = receipt.get("source_url")
    host = urlparse(url).hostname if isinstance(url, str) else None
    if urlparse(url).scheme != "https" or host != SOURCES[source][1]:
        fail("SOURCE_URL", str(url)[:200])
    if not receipt.get("retrieved_at_utc"):
        fail("NO_RETRIEVAL_TIME", "missing retrieved_at_utc")
    checksums = receipt.get("checksums", {})
    normalized = receipt.get("normalized")
    if not isinstance(checksums, dict) or not isinstance(normalized, str):
        fail("CHECKSUM_MANIFEST", "invalid receipt checksums / normalized filename")
        return None, issues
    if len(checksums) != 2 or normalized not in checksums or not any(n.startswith("raw-") for n in checksums):
        fail("CHECKSUM_MANIFEST", "expected one raw and one normalized checksum")
    for filename, digest in checksums.items():
        if (not isinstance(filename, str) or "/" in filename or "\\" in filename or
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            fail("BAD_CHECKSUM_DECLARATION", str(filename)[:100])
            continue
        if digest not in filename:
            fail("FILENAME_SHA_MISMATCH", filename)
        target = folder / filename
        if not target.is_file():
            fail("MISSING_PAYLOAD", filename)
            continue
        if file_sha256(target) != digest:
            fail("PAYLOAD_SHA_MISMATCH", filename)
    target = folder / normalized
    if not target.is_file():
        return None, issues
    try:
        records = json.loads(target.read_text("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        fail("INVALID_NORMALIZED_JSON", type(exc).__name__)
        return None, issues
    if not isinstance(records, list) or not records:
        fail("NO_RECORDS", "normalized JSON empty or not a list")
        return None, issues
    is_sector = source.endswith("_sector")
    dates, keys = set(), set()
    indices = set()
    per_day = Counter()
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            fail("BAD_RECORD", f"record {i} not object")
            continue
        day, name, close = row.get("trade_date"), row.get("index_id"), row.get("close")
        if not isinstance(day, str) or not DATE_PATTERN.fullmatch(day):
            fail("DATE_FORMAT", str(day))
            continue
        try:
            date.fromisoformat(day)
        except ValueError:
            fail("INVALID_DATE", day)
            continue
        if not day.startswith(period[:7]) or (len(period) == 10 and day != period):
            fail("PERIOD_MISMATCH", day)
        if row.get("market") != SOURCES[source][0]:
            fail("MARKET_MISMATCH", f"record {i}")
        if not isinstance(name, str) or not name.strip():
            fail("MISSING_INDEX_ID", f"record {i}")
            continue
        key = (day, name)
        if key in keys:
            fail("DUPLICATE_KEY", f"{day}/{name}")
        keys.add(key)
        dates.add(day)
        indices.add(name)
        per_day[day] += 1
        if not isinstance(close, (float, int)) or isinstance(close, bool) or not math.isfinite(close) or close <= 0:
            fail("BAD_CLOSE", f"{day}/{name}")
        if is_sector:
            if row.get("type") != "sector_price_index":
                fail("INDEX_TYPE", f"{day}/{name}")
        else:
            if name != ("TAIEX" if source == "twse_market" else "TPEX"):
                fail("MARKET_INDEX_ID", f"{day}/{name}")
            vals = [row.get(k) for k in ("open", "high", "low", "close")]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in vals):
                fail("OHLC_MISSING", day)
            elif not (row["low"] <= row["open"] <= row["high"] and row["low"] <= row["close"] <= row["high"]):
                fail("OHLC_INVALID", day)
    if receipt.get("rows") != len(records):
        fail("ROW_COUNT_MISMATCH", f"receipt={receipt.get('rows')}, actual={len(records)}")
    if dates and (receipt.get("first_date") != min(dates) or receipt.get("last_date") != max(dates)):
        fail("DATE_RANGE_MISMATCH", "receipt min/max does not match normalized")
    if is_sector and any(n < 10 for n in per_day.values()):
        fail("SECTOR_BREADTH_LOW", "sector indices < 10 on one or more days")
    if not is_sector and any(n != 1 for n in per_day.values()):
        fail("MARKET_ROWS_PER_DAY", "expected exactly 1 market index per session")
    result = {
        "source": source, "period": period, "path": str(folder.relative_to(root)),
        "rows": len(records), "sessions": len(dates), "index_count": len(indices),
        "trading_days": sorted(dates),
        "normalized_sha256": checksums.get(normalized),
        "receipt_sha256": file_sha256(receipt_path),
        "has_historical_error_file": (folder / "error_latest.json").exists(),
    }
    return result, issues


def run(root: Path, start: str, end: str):
    partitions, issues, monthly = [], [], defaultdict(lambda: defaultdict(set))
    expected_months = list(months(start, end))
    for source in SOURCES:
        for month in expected_months:
            month_dir = root / source / month
            if not month_dir.is_dir():
                issues.append({"source": source, "period": month, "code": "MISSING_MONTH", "detail": str(month_dir)})
                continue
            if source == "twse_sector":
                subdirs = sorted(d for d in month_dir.iterdir() if d.is_dir() and DATE_PATTERN.fullmatch(d.name))
                if not subdirs:
                    issues.append({"source": source, "period": month, "code": "MISSING_DAILY_PARTITIONS", "detail": str(month_dir)})
                candidates = [(d, d.name) for d in subdirs]
            else:
                candidates = [(month_dir, month)]
            for folder, period in candidates:
                result, errs = check_partition(root, folder, source, period)
                issues.extend(errs)
                if result:
                    partitions.append(result)
                    monthly[month][source].update(result["trading_days"])
    for month in expected_months:
        for mkt in ("twse", "tpex"):
            mdays = monthly[month].get(f"{mkt}_market", set())
            sdays = monthly[month].get(f"{mkt}_sector", set())
            if mdays != sdays:
                issues.append({"source": mkt, "period": month, "code": "TRADING_DAY_SET_MISMATCH",
                               "detail": f"market={len(mdays)},sector={len(sdays)},missing_in_sector={sorted(mdays-sdays)},extra_in_sector={sorted(sdays-mdays)}"})
            if mdays and not 10 <= len(mdays) <= 25:
                issues.append({"source": mkt, "period": month, "code": "SESSION_COUNT_OUT_OF_RANGE",
                               "detail": str(len(mdays))})
    status = "PASS" if not issues else "BLOCKED"
    receipt = {
        "kind": "JANUS_MARKET_SECTOR_RESEARCH_PREFLIGHT",
        "status": status, "classification": "RESEARCH_ONLY",
        "publication_allowed": False, "canonical_mutation": False,
        "historical_pit": "NOT_VERIFIED", "industry_membership_crosswalk": "NOT_VERIFIED",
        "source_use_authorization": "REQUIRES_PER_SOURCE_REVIEW",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root), "start_month": start, "end_month": end,
        "expected_months_per_source": len(expected_months),
        "verified_partitions": len(partitions),
        "verified_months_by_source": {s: len({p["period"][:7] for p in partitions if p["source"] == s}) for s in SOURCES},
        "issue_count": len(issues), "issues": issues, "partitions": partitions,
    }
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="包含 4 個 source 子目錄的大盤產業資料夾")
    ap.add_argument("--start-month", default="2025-01")
    ap.add_argument("--end-month", default="2026-09")
    ap.add_argument("--output", type=Path, required=True, help="獨立輸出資料夾；不能放入 source receipt 目錄")
    args = ap.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    if not root.is_dir():
        ap.error(f"input root missing: {root}")
    if out == root or root in out.parents:
        ap.error("--output 不得放在來源資料夾下；避免把驗收輸出混入原始不可變分區")
    report = run(root, args.start_month, args.end_month)
    out.mkdir(parents=True, exist_ok=True)
    (out / "preflight_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "preflight_issues.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=("source", "period", "code", "detail"))
        writer.writeheader()
        writer.writerows(report["issues"])
    print(json.dumps({k: v for k, v in report.items() if k not in ("issues", "partitions")},
                     ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
