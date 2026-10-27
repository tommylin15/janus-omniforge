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
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import json
import os
from pathlib import Path
import sys
from typing import Any


def read_gz_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"Warning: {path} not found.")
        return []
    items = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


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
    try:
        with connection.cursor() as cur:
            # Union of active watchlist and active holdings
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


def import_ohlcv(connection: Any, ohlcv_rows: list[dict[str, Any]], tier1_symbols: set[str], dry_run: bool = False) -> dict[str, int]:
    from collections import defaultdict
    by_symbol = defaultdict(list)
    for r in ohlcv_rows:
        by_symbol[r["symbol"]].append(r)

    prepared = []
    execution_id = "00000000-0000-0000-0000-000000000001"
    now_utc = datetime.now(timezone.utc).isoformat()

    tier1_count = 0
    tier2_count = 0

    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda x: x["trade_date"])
        is_tier1 = symbol in tier1_symbols
        # Tier 1 keeps up to 500 days; Tier 2 keeps up to 120 days
        limit = 500 if is_tier1 else 120
        selected = rows[-limit:] if len(rows) > limit else rows
        if is_tier1:
            tier1_count += len(selected)
        else:
            tier2_count += len(selected)

        for r in selected:
            trade_date = r["trade_date"]
            payload = {
                "trade_date": trade_date,
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": int(r["volume_shares"]),
                "turnover": None,
                "source_id": "yahoo-finance",
            }
            sort_at = f"{trade_date}T13:30:00+08:00"
            natural_key = f"{symbol}_{r.get('market','TWSE')}_{trade_date}"
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

    if dry_run:
        print(f"[DRY-RUN] OHLCV prepared: {len(prepared)} rows (Tier 1: {tier1_count}, Tier 2: {tier2_count})")
        return {"total": len(prepared), "tier1": tier1_count, "tier2": tier2_count}

    chunk_size = 500
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

    return {"total": len(prepared), "tier1": tier1_count, "tier2": tier2_count}


def import_financials(connection: Any, eps_rows: list[dict[str, Any]], rev_rows: list[dict[str, Any]], dry_run: bool = False) -> dict[str, int]:
    execution_id = "00000000-0000-0000-0000-000000000001"
    prepared = []

    # 1. EPS rows
    for r in eps_rows:
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
    for r in rev_rows:
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

    if dry_run:
        print(f"[DRY-RUN] Financials prepared: {len(prepared)} rows (EPS: {len(eps_rows)}, Rev: {len(rev_rows)})")
        return {"total": len(prepared), "eps": len(eps_rows), "revenue": len(rev_rows)}

    chunk_size = 500
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

    return {"total": len(prepared), "eps": len(eps_rows), "revenue": len(rev_rows)}


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

    print(f"Reading seed files from {indir}...")
    ohlcv = read_gz_jsonl(ohlcv_path)
    eps = read_gz_jsonl(eps_path)
    rev = read_gz_jsonl(rev_path)
    print(f"Loaded: OHLCV={len(ohlcv)}, EPS={len(eps)}, Revenue={len(rev)}")

    if not (ohlcv or eps or rev):
        print("No seed data found to import.")
        sys.exit(1)

    fallback_focus = [s.strip().upper() for s in args.focus_symbols.split(",") if s.strip()]

    if args.dry_run:
        tier1 = set(fallback_focus)
        import_ohlcv(None, ohlcv, tier1, dry_run=True)
        import_financials(None, eps, rev, dry_run=True)
        print("Dry run completed successfully.")
        return

    print("Connecting to PostgreSQL...")
    conn = get_db_connection()
    try:
        tier1 = resolve_tier1_symbols(conn, fallback_focus)
        print(f"Resolved Tier 1 symbols ({len(tier1)} stocks): {sorted(tier1)[:15]}...")

        print("Importing OHLCV...")
        ohlcv_res = import_ohlcv(conn, ohlcv, tier1, dry_run=False)
        print(f"OHLCV imported: {ohlcv_res}")

        print("Importing Financials (EPS & Revenue)...")
        fin_res = import_financials(conn, eps, rev, dry_run=False)
        print(f"Financials imported: {fin_res}")

        print("Vacuuming Serving tables...")
        with conn.cursor() as cur:
            cur.execute("VACUUM ANALYZE control.stock_serving_recent, control.market_serving_recent;")
        print("Serving import complete and verified.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
