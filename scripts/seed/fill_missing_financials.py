#!/usr/bin/env python3
"""Fill missing single-quarter EPS and monthly revenue for all market symbols.

Reads existing data/seed/eps_3y.jsonl.gz and data/seed/revenue_2y.jsonl.gz,
identifies missing symbols from data/seed/ohlcv_2y.jsonl.gz, and fetches them
with rate-limit backoff and dual-source fallbacks.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def http_get(url: str, timeout: int = 10, retries: int = 2) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            if e.code == 999:
                time.sleep(1.5 * (attempt + 1))
            elif attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(0.5)
    raise RuntimeError(f"failed_http_get: {url}")


def fetch_eps_tw_html(symbol: str, market: str) -> list[dict[str, Any]]:
    markets_to_try = [market] + (["TPEX"] if market == "TWSE" else ["TWSE"])
    for m in markets_to_try:
        suffix = "TW" if m.upper() == "TWSE" else "TWO"
        url = f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}/eps"
        try:
            raw = http_get(url)
        except Exception:
            continue
        parser = _TextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        text = " ".join(parser.parts)
        if "單季每股盈餘" not in text:
            continue
        table = text.split("單季每股盈餘", 1)[1].split("單季每股盈餘", 1)[0]
        periods = re.findall(r"\b(20\d{2})\s+Q([1-4])\b", table)
        now_utc = datetime.now(timezone.utc).isoformat()
        doc_sha = "sha256:" + sha256(raw).hexdigest()

        rows: list[dict[str, Any]] = []
        seen = set()
        for year_str, quarter_str in periods:
            year, quarter = int(year_str), int(quarter_str)
            if (year, quarter) in seen:
                continue
            seen.add((year, quarter))
            match = re.search(rf"{year}\s+Q{quarter}\s+(-?\s*\d[\d,]*(?:\.\d+)?)", table)
            if not match:
                continue
            try:
                val_str = match.group(1).replace(" ", "").replace(",", "")
                amount = Decimal(val_str)
                if not amount.is_finite():
                    continue
                period_end = date(year, quarter * 3, monthrange(year, quarter * 3)[1]).isoformat()
                rows.append({
                    "symbol": symbol,
                    "fiscal_year": year,
                    "fiscal_quarter": quarter,
                    "fiscal_period_end": period_end,
                    "statement_type": "income",
                    "metric": "eps_single_quarter",
                    "period_basis": "single_quarter",
                    "unit": "TWD_per_share",
                    "currency": "TWD",
                    "value": str(amount),
                    "source_id": "yahoo-finance",
                    "availability_at": now_utc,
                    "observed_at": now_utc,
                    "source_document_sha256": doc_sha,
                })
            except (ValueError, TypeError, InvalidOperation):
                continue
            if len(rows) >= 12:
                break
        if rows:
            rows.sort(key=lambda r: (r["fiscal_year"], r["fiscal_quarter"]))
            return rows
    return []


def fetch_eps_yahoo_json(symbol: str, market: str) -> list[dict[str, Any]]:
    """Fallback JSON endpoint from query2."""
    markets_to_try = [market] + (["TPEX"] if market == "TWSE" else ["TWSE"])
    for m in markets_to_try:
        suffix = "TW" if m.upper() == "TWSE" else "TWO"
        url = f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}.{suffix}?type=quarterlyBasicEPS&period1=1577836800&period2=1800000000"
        try:
            raw = http_get(url)
            data = json.loads(raw.decode("utf-8"))
            results = data.get("timeseries", {}).get("result", [])
            if not results:
                continue
            items = results[0].get("quarterlyBasicEPS", [])
            now_utc = datetime.now(timezone.utc).isoformat()
            doc_sha = "sha256:" + sha256(raw).hexdigest()
            rows: list[dict[str, Any]] = []
            for it in items:
                as_of = it.get("asOfDate")
                val_raw = it.get("reportedValue", {}).get("raw")
                if not as_of or val_raw is None:
                    continue
                d = date.fromisoformat(as_of)
                year, quarter = d.year, (d.month - 1) // 3 + 1
                period_end = date(year, quarter * 3, monthrange(year, quarter * 3)[1]).isoformat()
                rows.append({
                    "symbol": symbol,
                    "fiscal_year": year,
                    "fiscal_quarter": quarter,
                    "fiscal_period_end": period_end,
                    "statement_type": "income",
                    "metric": "eps_single_quarter",
                    "period_basis": "single_quarter",
                    "unit": "TWD_per_share",
                    "currency": "TWD",
                    "value": str(Decimal(str(val_raw))),
                    "source_id": "yahoo-finance",
                    "availability_at": now_utc,
                    "observed_at": now_utc,
                    "source_document_sha256": doc_sha,
                })
            if rows:
                rows.sort(key=lambda r: (r["fiscal_year"], r["fiscal_quarter"]))
                return rows[-12:]
        except Exception:
            continue
    return []


def fetch_revenue_tw_html(symbol: str, market: str) -> list[dict[str, Any]]:
    markets_to_try = [market] + (["TPEX"] if market == "TWSE" else ["TWSE"])
    for m in markets_to_try:
        suffix = "TW" if m.upper() == "TWSE" else "TWO"
        url = f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}/revenue"
        try:
            raw = http_get(url)
        except Exception:
            continue
        parser = _TextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        text = " ".join(parser.parts)
        pos = text.find("年度/月份")
        if pos == -1:
            continue
        matches = re.findall(r"(20\d{2})/(\d{2})\s+([\d,]+)\s+([-\d.]+%)\s+([\d,]+)\s+([-\d.]+%)", text[pos:])
        now_utc = datetime.now(timezone.utc).isoformat()
        doc_sha = "sha256:" + sha256(raw).hexdigest()

        rows: list[dict[str, Any]] = []
        seen = set()
        for year_str, month_str, rev_str, mom, ly_rev_str, yoy in matches:
            year, month = int(year_str), int(month_str)
            if (year, month) in seen:
                continue
            seen.add((year, month))
            try:
                rev_val = Decimal(rev_str.replace(",", ""))
                if not rev_val.is_finite() or rev_val < 0:
                    continue
                period_end = date(year, month, monthrange(year, month)[1]).isoformat()
                quarter = (month - 1) // 3 + 1
                rows.append({
                    "symbol": symbol,
                    "fiscal_year": year,
                    "fiscal_quarter": quarter,
                    "fiscal_month": month,
                    "fiscal_period_end": period_end,
                    "statement_type": "monthly_revenue",
                    "metric": "monthly_revenue",
                    "period_basis": "monthly",
                    "unit": "TWD_thousands",
                    "currency": "TWD",
                    "value": str(rev_val),
                    "source_id": "yahoo-finance",
                    "availability_at": now_utc,
                    "observed_at": now_utc,
                    "source_document_sha256": doc_sha,
                })
            except (ValueError, TypeError, InvalidOperation):
                continue
            if len(rows) >= 24:
                break
        if rows:
            rows.sort(key=lambda r: (r["fiscal_year"], r["fiscal_month"]))
            return rows
    return []


def main() -> None:
    seed_dir = Path("data/seed")
    eps_path = seed_dir / "eps_3y.jsonl.gz"
    rev_path = seed_dir / "revenue_2y.jsonl.gz"
    ohlcv_path = seed_dir / "ohlcv_2y.jsonl.gz"

    # 1. Existing data
    existing_eps: dict[str, list[dict[str, Any]]] = {}
    if eps_path.exists():
        with gzip.open(eps_path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                r = json.loads(line)
                existing_eps.setdefault(r["symbol"], []).append(r)

    existing_rev: dict[str, list[dict[str, Any]]] = {}
    if rev_path.exists():
        with gzip.open(rev_path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                r = json.loads(line)
                existing_rev.setdefault(r["symbol"], []).append(r)

    # 2. All symbols
    all_symbols: dict[str, str] = {} # symbol -> market
    with gzip.open(ohlcv_path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r = json.loads(line)
            all_symbols[r["symbol"]] = r.get("market", "TWSE")

    print(f"Total symbols in OHLCV universe: {len(all_symbols)}")
    print(f"Existing symbols with EPS: {len(existing_eps)}")
    print(f"Existing symbols with Revenue: {len(existing_rev)}")

    missing_eps_symbols = sorted(s for s in all_symbols if s not in existing_eps)
    missing_rev_symbols = sorted(s for s in all_symbols if s not in existing_rev)
    targets = sorted(set(missing_eps_symbols) | set(missing_rev_symbols))

    print(f"Targets requiring backfill: {len(targets)} (missing EPS: {len(missing_eps_symbols)}, missing Rev: {len(missing_rev_symbols)})")

    new_eps_count = 0
    new_rev_count = 0
    t0 = time.time()

    for i, symbol in enumerate(targets):
        market = all_symbols[symbol]
        # Fetch EPS if missing
        if symbol in missing_eps_symbols:
            eps_rows = fetch_eps_tw_html(symbol, market)
            if not eps_rows:
                eps_rows = fetch_eps_yahoo_json(symbol, market)
            if eps_rows:
                existing_eps[symbol] = eps_rows
                new_eps_count += len(eps_rows)

        # Fetch Revenue if missing
        if symbol in missing_rev_symbols:
            rev_rows = fetch_revenue_tw_html(symbol, market)
            if rev_rows:
                existing_rev[symbol] = rev_rows
                new_rev_count += len(rev_rows)

        time.sleep(0.06)

        if (i + 1) % 50 == 0 or (i + 1) == len(targets):
            elapsed = time.time() - t0
            print(f"[{i+1}/{len(targets)}] Processed {symbol} (EPS +{new_eps_count}, Rev +{new_rev_count}) in {elapsed:.1f}s", flush=True)

    # Write back merged data
    print("Writing merged data to gz files...")
    all_eps_rows = [r for rows in existing_eps.values() for r in rows]
    all_rev_rows = [r for rows in existing_rev.values() for r in rows]

    with gzip.open(eps_path, "wt", encoding="utf-8") as f:
        for r in all_eps_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with gzip.open(rev_path, "wt", encoding="utf-8") as f:
        for r in all_rev_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"DONE! Total EPS symbols: {len(existing_eps)} (total rows: {len(all_eps_rows)})")
    print(f"DONE! Total Rev symbols: {len(existing_rev)} (total rows: {len(all_rev_rows)})")
    print(f"Check 4958 in EPS: {'4958' in existing_eps}, rows: {len(existing_eps.get('4958', []))}")
    print(f"Check 4958 in Rev: {'4958' in existing_rev}, rows: {len(existing_rev.get('4958', []))}")


if __name__ == "__main__":
    main()
