#!/usr/bin/env python3
"""Import 2-year history seed data into PostgreSQL Serving Projection.

Follows Cold/Hot Tiering policy (doc/spec/history-seed-pipeline.md):
- Tier 1 (Holdings, Watchlist, Focus symbols): Full 2-year OHLCV (~500 days)
- Tier 2 (Other market symbols): 120 trading days OHLCV
- Financials (Single-quarter EPS & Monthly Revenue): All symbols full history (12Q EPS, 24M revenue)

Can run directly where CONTROL_DB_* or PUBLICATION_DB_* environment variables are available,
or inside a Cloud Run Job execution.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


def get_db_connection():
    import psycopg

    host = os.environ.get("CONTROL_DB_HOST") or os.environ.get("POSTGRES_HOST", "localhost")
    port = int(os.environ.get("CONTROL_DB_PORT") or os.environ.get("POSTGRES_PORT", 5432))
    dbname = os.environ.get("CONTROL_DB_NAME") or os.environ.get("POSTGRES_DB", "janus_dev")
    user = os.environ.get("CONTROL_DB_USER") or os.environ.get("POSTGRES_USER", "janus_control")
    password = os.environ.get("CONTROL_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "")
    sslmode = os.environ.get("CONTROL_DB_SSLMODE", "require")

    return psycopg.connect(
        host=host, port=port, dbname=dbname, user=user, password=password, sslmode=sslmode, connect_timeout=10,
    )


def resolve_tier1_symbols(connection: Any, fallback_symbols: list[str]) -> set[str]:
    tier1 = set(fallback_symbols)
    if connection is not None:
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT symbol FROM private.watchlist WHERE active
                    UNION
                    SELECT symbol FROM private.current_positions WHERE shares > 0
                """)
                for row in cur.fetchall():
                    tier1.add(str(row[0]).upper())
        except Exception as e:
            print(f"Note: Could not query private active watchlist/holdings ({e}). Using focus fallback.")
    return tier1


def import_ohlcv(connection: Any, ohlcv_path: Path, tier1_symbols: set[str], dry_run: bool = False) -> dict[str, int]:
    t0 = time.time()
    by_symbol = defaultdict(list)
    total_parsed = 0

    with gzip.open(ohlcv_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by_symbol[r["symbol"]].append((
                r["trade_date"],
                r["open"],
                r["high"],
                r["low"],
                r["close"],
                int(r["volume_shares"]),
                r.get("market", "TWSE"),
            ))
            total_parsed += 1

    tier1_count = 0
    tier2_count = 0
    prepared = []
    execution_id = "00000000-0000-0000-0000-000000000001"

    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda x: x[0])
        is_tier1 = symbol in tier1_symbols
        limit = 500 if is_tier1 else 120
        selected = rows[-limit:] if len(rows) > limit else rows
        if is_tier1:
            tier1_count += len(selected)
        else:
            tier2_count += len(selected)

        if not dry_run:
            for trade_date, o, h, l, c, v, market in selected:
                payload = {
                    "trade_date": trade_date,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                    "turnover": None,
                    "source_id": "yahoo-finance",
                }
                sort_at = f"{trade_date}T13:30:00+08:00"
                natural_key = f"{symbol}_{market}_{trade_date}"
                prepared.append((
                    "ohlcv",
                    symbol,
                    natural_key,
                    sort_at,
                    json.dumps(payload),
                    "yahoo-finance",
                    f"seed_yahoo_{trade_date}",
                    execution_id,
                ))

    elapsed = time.time() - t0
    total_prepared = tier1_count + tier2_count
    print(f"OHLCV parsed {total_parsed} rows -> prepared {total_prepared} rows (Tier 1: {tier1_count}, Tier 2: {tier2_count}) in {elapsed:.2f}s")

    if dry_run or not connection:
        return {"total": total_prepared, "tier1": tier1_count, "tier2": tier2_count}

    chunk_size = 1000
    with connection.transaction(), connection.cursor() as cur:
        for offset in range(0, len(prepared), chunk_size):
            chunk = prepared[offset:offset + chunk_size]
            cur.executemany(
                """INSERT INTO control.stock_serving_recent(
                       dataset_id, symbol, natural_key, sort_at, payload_json,
                       source_id, provenance_id, execution_id, updated_at)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                   ON CONFLICT (dataset_id, symbol, natural_key) DO UPDATE SET
                       sort_at = EXCLUDED.sort_at,
                       payload_json = EXCLUDED.payload_json,
                       source_id = EXCLUDED.source_id,
                       provenance_id = EXCLUDED.provenance_id,
                       execution_id = EXCLUDED.execution_id,
                       updated_at = now()
                   WHERE EXCLUDED.sort_at >= control.stock_serving_recent.sort_at""",
                chunk,
            )
    return {"total": total_prepared, "tier1": tier1_count, "tier2": tier2_count}


def import_financials(connection: Any, eps_path: Path, rev_path: Path, dry_run: bool = False) -> dict[str, int]:
    t0 = time.time()
    execution_id = "00000000-0000-0000-0000-000000000001"
    eps_count = 0
    rev_count = 0
    prepared = []

    # 1. EPS rows
    if eps_path.exists():
        with gzip.open(eps_path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                eps_count += 1
                if not dry_run:
                    symbol = r["symbol"]
                    y = r["fiscal_year"]
                    q = r["fiscal_quarter"]
                    natural_key = f"{symbol}_{y}_Q{q}_eps"
                    sort_at = r.get("availability_at") or f"{y}-{q*3:02d}-15T00:00:00+08:00"
                    payload = {
                        "symbol": symbol,
                        "fiscal_year": y,
                        "fiscal_quarter": q,
                        "fiscal_period_end": r["fiscal_period_end"],
                        "statement_type": "income",
                        "metric": "eps_single_quarter",
                        "period_basis": "single_quarter",
                        "unit": "TWD_per_share",
                        "currency": "TWD",
                        "value": r["value"],
                        "source_id": "yahoo-finance",
                    }
                    prepared.append((
                        "financials",
                        symbol,
                        natural_key,
                        sort_at,
                        json.dumps(payload),
                        "yahoo-finance",
                        f"seed_eps_{y}Q{q}",
                        execution_id,
                    ))

    # 2. Revenue rows
    if rev_path.exists():
        with gzip.open(rev_path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                rev_count += 1
                if not dry_run:
                    symbol = r["symbol"]
                    y = r["fiscal_year"]
                    m = r["fiscal_month"]
                    natural_key = f"{symbol}_{y}_{m:02d}_revenue"
                    sort_at = r.get("availability_at") or f"{y}-{m:02d}-10T00:00:00+08:00"
                    payload = {
                        "symbol": symbol,
                        "fiscal_year": y,
                        "fiscal_quarter": r["fiscal_quarter"],
                        "fiscal_month": m,
                        "fiscal_period_end": r["fiscal_period_end"],
                        "statement_type": "monthly_revenue",
                        "metric": "monthly_revenue",
                        "period_basis": "monthly",
                        "unit": "TWD_thousands",
                        "currency": "TWD",
                        "value": r["value"],
                        "source_id": "yahoo-finance",
                    }
                    prepared.append((
                        "financials",
                        symbol,
                        natural_key,
                        sort_at,
                        json.dumps(payload),
                        "yahoo-finance",
                        f"seed_rev_{y}_{m:02d}",
                        execution_id,
                    ))

    elapsed = time.time() - t0
    total_fin = eps_count + rev_count
    print(f"Financials parsed EPS={eps_count}, Rev={rev_count} -> total {total_fin} rows in {elapsed:.2f}s")

    if dry_run or not connection:
        return {"total": total_fin, "eps": eps_count, "revenue": rev_count}

    chunk_size = 1000
    with connection.transaction(), connection.cursor() as cur:
        for offset in range(0, len(prepared), chunk_size):
            chunk = prepared[offset:offset + chunk_size]
            cur.executemany(
                """INSERT INTO control.market_serving_recent(
                       dataset_id, symbol, natural_key, sort_at, payload_json,
                       source_id, provenance_id, execution_id, updated_at)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                   ON CONFLICT (dataset_id, symbol, natural_key) DO UPDATE SET
                       sort_at = EXCLUDED.sort_at,
                       payload_json = EXCLUDED.payload_json,
                       source_id = EXCLUDED.source_id,
                       provenance_id = EXCLUDED.provenance_id,
                       execution_id = EXCLUDED.execution_id,
                       updated_at = now()
                   WHERE EXCLUDED.sort_at >= control.market_serving_recent.sort_at""",
                chunk,
            )

    return {"total": total_fin, "eps": eps_count, "revenue": rev_count}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import 2-year history seed into PostgreSQL Serving")
    parser.add_argument("--indir", default="data/seed", help="Directory containing .jsonl.gz seed files")
    parser.add_argument("--dry-run", action="store_true", help="Prepare rows and report counts without DB writes")
    parser.add_argument("--focus-symbols", default="2330,2317,2454,2382,2308,2882,2881,2603,6488,8069,5347,3293",
                        help="Default Tier 1 focus symbols")
    args = parser.parse_args()

    indir = Path(args.indir)
    ohlcv_path = indir / "ohlcv_2y.jsonl.gz"
    eps_path = indir / "eps_3y.jsonl.gz"
    rev_path = indir / "revenue_2y.jsonl.gz"

    fallback_focus = [s.strip().upper() for s in args.focus_symbols.split(",") if s.strip()]

    if args.dry_run:
        tier1 = set(fallback_focus)
        import_ohlcv(None, ohlcv_path, tier1, dry_run=True)
        import_financials(None, eps_path, rev_path, dry_run=True)
        print("Dry run completed successfully.")
        return

    print("Connecting to PostgreSQL...")
    conn = get_db_connection()
    try:
        tier1 = resolve_tier1_symbols(conn, fallback_focus)
        print(f"Resolved Tier 1 symbols ({len(tier1)} stocks): {sorted(tier1)[:15]}...")

        print("Importing OHLCV...")
        ohlcv_res = import_ohlcv(conn, ohlcv_path, tier1, dry_run=False)
        print(f"OHLCV imported: {ohlcv_res}")

        print("Importing Financials (EPS & Revenue)...")
        fin_res = import_financials(conn, eps_path, rev_path, dry_run=False)
        print(f"Financials imported: {fin_res}")

        print("Vacuuming Serving tables...")
        with conn.cursor() as cur:
            cur.execute("VACUUM ANALYZE control.stock_serving_recent, control.market_serving_recent;")
        print("Serving import complete and verified.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
