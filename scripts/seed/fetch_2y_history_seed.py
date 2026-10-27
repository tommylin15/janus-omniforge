#!/usr/bin/env python3
"""Fetch 2-year historical seed data for TWSE & TPEx stocks.

Produces compressed JSON Lines (.jsonl.gz) seed files:
- ohlcv_2y.jsonl.gz: ~485 trading days of daily OHLCV
- eps_3y.jsonl.gz: up to 12 quarters of single-quarter EPS
- revenue_2y.jsonl.gz: up to 24 months of monthly revenue
"""
from __future__ import annotations

import argparse
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_ohlcv_2y(symbol: str, market: str) -> tuple[list[dict[str, Any]], str]:
    """Fetch ~2 years (485+ trading days) of daily OHLCV from Yahoo Finance."""
    markets_to_try = [market] + (["TPEX"] if market == "TWSE" else ["TWSE"])
    for m in markets_to_try:
        suffix = "TW" if m.upper() == "TWSE" else "TWO"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.{suffix}?range=2y&interval=1d"
        try:
            raw = http_get(url)
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue
        try:
            doc = json.loads(raw.decode("utf-8"))
            results = doc.get("chart", {}).get("result")
            if not results or not isinstance(results, list):
                continue
            res = results[0]
            timestamps = res.get("timestamp", [])
            quote = res.get("indicators", {}).get("quote", [{}])[0]
            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            rows: list[dict[str, Any]] = []
            for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes):
                if ts is None or c is None:
                    continue
                try:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    trade_date = dt.strftime("%Y-%m-%d")
                    c_dec = Decimal(str(c))
                    o_dec = Decimal(str(o if o is not None else c))
                    h_dec = Decimal(str(h if h is not None else max(c, o_dec)))
                    l_dec = Decimal(str(l if l is not None else min(c, o_dec)))
                    v_int = int(v) if v is not None else 0
                    if not c_dec.is_finite() or c_dec <= 0:
                        continue
                    rows.append({
                        "symbol": symbol,
                        "market": m.upper(),
                        "trade_date": trade_date,
                        "open": str(o_dec.quantize(Decimal("0.01"))),
                        "high": str(h_dec.quantize(Decimal("0.01"))),
                        "low": str(l_dec.quantize(Decimal("0.01"))),
                        "close": str(c_dec.quantize(Decimal("0.01"))),
                        "volume_shares": str(v_int),
                        "turnover_twd": None,
                        "source_id": "yahoo-finance",
                    })
                except (ValueError, TypeError, InvalidOperation):
                    continue
            if rows:
                rows.sort(key=lambda r: r["trade_date"])
                return rows, m.upper()
        except Exception:
            continue
    return [], market.upper()


def fetch_eps_3y(symbol: str, market: str) -> list[dict[str, Any]]:
    """Fetch up to 12 quarters of single-quarter EPS from Yahoo Finance TW."""
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
            year = int(year_str)
            quarter = int(quarter_str)
            if (year, quarter) in seen:
                continue
            seen.add((year, quarter))
            pattern = rf"{year}\s+Q{quarter}\s+(-?\s*\d[\d,]*(?:\.\d+)?)"
            match = re.search(pattern, table)
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


def fetch_revenue_2y(symbol: str, market: str) -> list[dict[str, Any]]:
    """Fetch up to 24 months of monthly revenue from Yahoo Finance TW."""
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
            year = int(year_str)
            month = int(month_str)
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


def write_gz_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_full_market_roster() -> list[tuple[str, str, str]]:
    """Load full market common equities (~1,925 stocks) from TWSE and TPEx CSVs."""
    import csv, io
    roster: list[tuple[str, str, str]] = []
    urls = [
        ("TWSE", "https://raw.githubusercontent.com/mlouielu/twstock/dev/twstock/codes/twse_equities.csv"),
        ("TPEX", "https://raw.githubusercontent.com/mlouielu/twstock/dev/twstock/codes/tpex_equities.csv"),
    ]
    for market, url in urls:
        try:
            raw = http_get(url, timeout=20).decode("utf-8")
            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", "")).strip()
                row_type = str(row.get("type", "")).strip()
                if row_type == "股票" and len(code) == 4 and code[0] in "123456789":
                    roster.append((code, market, name))
        except Exception as e:
            print(f"Warning: Failed to fetch {market} roster from {url}: {e}")
    roster.sort(key=lambda x: x[0])
    return roster


def _collect_single_symbol(item: tuple[str, str, str]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    symbol, market, name = item
    ohlcv, _ = fetch_ohlcv_2y(symbol, market)
    eps = fetch_eps_3y(symbol, market)
    rev = fetch_revenue_2y(symbol, market)
    return symbol, ohlcv, eps, rev


def main() -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    parser = argparse.ArgumentParser(description="Fetch 2-year history seed data")
    parser.add_argument("--symbols", help="Comma-separated stock symbols or 'all' for full market universe")
    parser.add_argument("--outdir", default="data/seed", help="Output directory")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent workers (default: 8)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of symbols (for testing)")
    args = parser.parse_args()

    symbols_input = (args.symbols or "").strip()
    if symbols_input == "all" or not symbols_input:
        print("Loading full market equities roster...")
        roster = load_full_market_roster()
        if not roster:
            print("Fallback to default core batch of symbols...")
            roster = [
                ("2330", "TWSE", "台積電"), ("2317", "TWSE", "鴻海"), ("2454", "TWSE", "聯發科"),
                ("2382", "TWSE", "廣達"), ("2308", "TWSE", "台達電"), ("2882", "TWSE", "國泰金"),
                ("2881", "TWSE", "富邦金"), ("2603", "TWSE", "長榮"), ("6488", "TPEX", "環球晶"),
                ("8069", "TPEX", "元太"), ("5347", "TPEX", "世界"), ("3293", "TPEX", "鈊象"),
            ]
        symbols_with_market = roster
    else:
        symbols_with_market = []
        for s in symbols_input.split(","):
            s = s.strip()
            if not s:
                continue
            m = "TPEX" if s[0] in "5683" else "TWSE"
            symbols_with_market.append((s, m, s))

    if args.limit > 0:
        symbols_with_market = symbols_with_market[:args.limit]

    total_symbols = len(symbols_with_market)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting seed collection for {total_symbols} symbols using {args.workers} workers...")
    all_ohlcv: list[dict[str, Any]] = []
    all_eps: list[dict[str, Any]] = []
    all_revenue: list[dict[str, Any]] = []
    done_count = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_collect_single_symbol, item): item[0] for item in symbols_with_market}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                symbol, ohlcv, eps, rev = future.result()
                all_ohlcv.extend(ohlcv)
                all_eps.extend(eps)
                all_revenue.extend(rev)
                done_count += 1
                if done_count % 50 == 0 or done_count == total_symbols:
                    elapsed = time.time() - t0
                    rate = done_count / elapsed if elapsed > 0 else 0
                    print(f"[{done_count}/{total_symbols}] ({done_count*100/total_symbols:.1f}%) "
                          f"OHLCV={len(all_ohlcv)} EPS={len(all_eps)} Rev={len(all_revenue)} "
                          f"({rate:.1f} sym/s, elapsed {elapsed:.0f}s)")
            except Exception as e:
                print(f"Error collecting {sym}: {e}")

    # Write out compressed JSON Lines
    ohlcv_path = out_dir / "ohlcv_2y.jsonl.gz"
    eps_path = out_dir / "eps_3y.jsonl.gz"
    rev_path = out_dir / "revenue_2y.jsonl.gz"

    write_gz_jsonl(ohlcv_path, all_ohlcv)
    write_gz_jsonl(eps_path, all_eps)
    write_gz_jsonl(rev_path, all_revenue)

    elapsed_total = time.time() - t0
    print("\n=== Collection Complete ===")
    print(f"Total time: {elapsed_total:.1f} seconds")
    print(f"OHLCV: {len(all_ohlcv)} rows -> {ohlcv_path} ({ohlcv_path.stat().st_size / 1024:.1f} KB)")
    print(f"EPS: {len(all_eps)} rows -> {eps_path} ({eps_path.stat().st_size / 1024:.1f} KB)")
    print(f"Revenue: {len(all_revenue)} rows -> {rev_path} ({rev_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
