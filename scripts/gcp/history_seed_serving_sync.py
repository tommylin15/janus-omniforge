#!/usr/bin/env python3
"""Execute bounded full-market 2Y history seed import into PostgreSQL serving via existing dev Job.

Follows Cold/Hot Tiering policy:
- Tier 1: 500 trading days OHLCV
- Tier 2: 120 trading days OHLCV
- Financials: 12 quarters single-quarter EPS + 24 months revenue full market.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghcr_jobs_rollout import ROOT, cloud, job, terminal

JOB = "janus-ingestion-core"
PROJECT = "gen-lang-client-0593591102"

PROBE = r"""
import gzip, io, json, os, sys, time, traceback
from collections import defaultdict
from ingestion_core.__main__ import _control_plane
from ingestion_core.stage import GcsObjectStore

report = {
    'component': 'history_seed_serving_sync',
    'status': 'PARTIAL',
    'owner_mutation': False,
    'job_template_mutation': False,
}

control = None
try:
    req = json.loads(os.environ['HISTORY_SEED_REQUEST'])
    bucket = os.environ.get('STAGE_BUCKET', 'gen-lang-client-0593591102-dev-stage')
    store = GcsObjectStore(bucket, timeout_seconds=180.0)

    t0 = time.time()
    print("Reading seed files from GCS stage...", flush=True)
    ohlcv_raw = store.read('seed_data/ohlcv_2y.jsonl.gz')
    with gzip.GzipFile(fileobj=io.BytesIO(ohlcv_raw)) as gz:
        with io.TextIOWrapper(gz, encoding='utf-8') as stream:
            by_symbol = defaultdict(list)
            total_ohlcv = 0
            for line in stream:
                line = line.strip()
                if not line: continue
                r = json.loads(line)
                by_symbol[r['symbol']].append((
                    r['trade_date'], r['open'], r['high'], r['low'], r['close'],
                    int(r['volume_shares']), r.get('market', 'TWSE')
                ))
                total_ohlcv += 1

    print(f"Parsed {total_ohlcv} OHLCV rows across {len(by_symbol)} symbols in {time.time()-t0:.2f}s", flush=True)

    # Database connection via standard _control_plane() with postgres bundle loaded
    control = _control_plane()
    conn = control.connection

    # Migration 070: allow yahoo-finance for monthly_revenue
    with conn.transaction(), conn.cursor() as cur:
        cur.execute('''
            ALTER TABLE control.market_serving_recent DROP CONSTRAINT IF EXISTS market_serving_recent_source_id_check;
            ALTER TABLE control.market_serving_recent ADD CONSTRAINT market_serving_recent_source_id_check CHECK (
                source_id IN ('twse','tpex','taiex','mops') OR
                (source_id='yahoo-finance' AND dataset_id='financials'
                  AND coalesce(payload_json->>'metric','')='eps_single_quarter'
                  AND coalesce(payload_json->>'period_basis','')='single_quarter'
                  AND coalesce(payload_json->>'unit','')='TWD_per_share') OR
                (source_id IN ('finmind','yahoo-finance') AND dataset_id='financials'
                  AND coalesce(payload_json->>'metric','')='monthly_revenue'
                  AND coalesce(payload_json->>'statement_type','')='monthly_revenue'
                  AND coalesce(payload_json->>'unit','')='TWD_thousands')
            );
            INSERT INTO control.schema_migrations(version) VALUES ('070_yahoo_revenue_serving') ON CONFLICT DO NOTHING;
        ''')

    # Load valid stock_master symbols to guarantee FK integrity
    with conn.cursor() as cur:
        cur.execute("SELECT symbol FROM control.stock_master WHERE enabled=true")
        valid_symbols = {str(r[0]) for r in cur.fetchall()}
    print(f"Loaded {len(valid_symbols)} enabled symbols from control.stock_master", flush=True)

    # Resolve Tier 1
    tier1 = set(req.get('tier1_symbols_fallback', []))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT symbol FROM private.watchlist WHERE active UNION SELECT symbol FROM private.current_positions WHERE shares > 0")
            for row in cur.fetchall():
                tier1.add(str(row[0]).upper())
    except Exception as e:
        print(f"Watchlist lookup notice: {e}", flush=True)

    # Prepare OHLCV rows (only for symbols in stock_master)
    prepared_ohlcv = []
    tier1_count = 0
    tier2_count = 0
    execution_id = '00000000-0000-0000-0000-000000000001'

    for symbol, rows in by_symbol.items():
        if symbol not in valid_symbols:
            continue
        rows.sort(key=lambda x: x[0])
        is_tier1 = symbol in tier1
        limit = 500 if is_tier1 else 120
        selected = rows[-limit:] if len(rows) > limit else rows
        if is_tier1: tier1_count += len(selected)
        else: tier2_count += len(selected)
        for td, o, h, l, c, v, market in selected:
            payload = json.dumps({'trade_date': td, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v, 'turnover': None, 'source_id': 'yahoo-finance'})
            sort_at = f"{td}T13:30:00+08:00"
            natural_key = f"{symbol}_{market}_{td}"
            prepared_ohlcv.append(('ohlcv', symbol, natural_key, sort_at, payload, 'yahoo-finance', f"seed_yahoo_{td}", execution_id))

    print(f"Upserting {len(prepared_ohlcv)} OHLCV rows to control.stock_serving_recent...", flush=True)
    chunk_size = 1000
    with conn.transaction(), conn.cursor() as cur:
        for offset in range(0, len(prepared_ohlcv), chunk_size):
            chunk = prepared_ohlcv[offset:offset+chunk_size]
            cur.executemany('''
                INSERT INTO control.stock_serving_recent(dataset_id, symbol, natural_key, sort_at, payload_json, source_id, provenance_id, execution_id, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                ON CONFLICT (dataset_id, symbol, natural_key) DO UPDATE SET
                    sort_at = EXCLUDED.sort_at,
                    payload_json = EXCLUDED.payload_json,
                    source_id = EXCLUDED.source_id,
                    provenance_id = EXCLUDED.provenance_id,
                    execution_id = EXCLUDED.execution_id,
                    updated_at = now()
                WHERE EXCLUDED.sort_at >= control.stock_serving_recent.sort_at
            ''', chunk)

    # Financials (EPS & Revenue)
    print("Reading and inserting financials...", flush=True)
    eps_raw = store.read('seed_data/eps_3y.jsonl.gz')
    with gzip.GzipFile(fileobj=io.BytesIO(eps_raw)) as gz:
        with io.TextIOWrapper(gz, encoding='utf-8') as stream:
            eps_lines = [line.strip() for line in stream if line.strip()]

    rev_raw = store.read('seed_data/revenue_2y.jsonl.gz')
    with gzip.GzipFile(fileobj=io.BytesIO(rev_raw)) as gz:
        with io.TextIOWrapper(gz, encoding='utf-8') as stream:
            rev_lines = [line.strip() for line in stream if line.strip()]

    prepared_fin = []
    for line in eps_lines:
        r = json.loads(line)
        symbol = r['symbol']
        if symbol not in valid_symbols: continue
        y = r['fiscal_year']; q = r['fiscal_quarter']
        natural_key = f"{symbol}_{y}_Q{q}_eps"
        sort_at = r.get('availability_at') or f"{y}-{q*3:02d}-15T00:00:00+08:00"
        payload = json.dumps({'symbol': symbol, 'fiscal_year': y, 'fiscal_quarter': q, 'fiscal_period_end': r['fiscal_period_end'], 'statement_type': 'income', 'metric': 'eps_single_quarter', 'period_basis': 'single_quarter', 'unit': 'TWD_per_share', 'currency': 'TWD', 'value': r['value'], 'source_id': 'yahoo-finance'})
        prepared_fin.append(('financials', symbol, natural_key, sort_at, payload, 'yahoo-finance', f"seed_eps_{y}Q{q}", execution_id))

    for line in rev_lines:
        r = json.loads(line)
        symbol = r['symbol']
        if symbol not in valid_symbols: continue
        y = r['fiscal_year']; m = r['fiscal_month']
        natural_key = f"{symbol}_{y}_{m:02d}_revenue"
        sort_at = r.get('availability_at') or f"{y}-{m:02d}-10T00:00:00+08:00"
        payload = json.dumps({'symbol': symbol, 'fiscal_year': y, 'fiscal_quarter': r['fiscal_quarter'], 'fiscal_month': m, 'fiscal_period_end': r['fiscal_period_end'], 'statement_type': 'monthly_revenue', 'metric': 'monthly_revenue', 'period_basis': 'monthly', 'unit': 'TWD_thousands', 'currency': 'TWD', 'value': r['value'], 'source_id': 'yahoo-finance'})
        prepared_fin.append(('financials', symbol, natural_key, sort_at, payload, 'yahoo-finance', f"seed_rev_{y}_{m:02d}", execution_id))

    with conn.transaction(), conn.cursor() as cur:
        for offset in range(0, len(prepared_fin), chunk_size):
            chunk = prepared_fin[offset:offset+chunk_size]
            cur.executemany('''
                INSERT INTO control.market_serving_recent(dataset_id, symbol, natural_key, sort_at, payload_json, source_id, provenance_id, execution_id, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                ON CONFLICT (dataset_id, symbol, natural_key) DO UPDATE SET
                    sort_at = EXCLUDED.sort_at,
                    payload_json = EXCLUDED.payload_json,
                    source_id = EXCLUDED.source_id,
                    provenance_id = EXCLUDED.provenance_id,
                    execution_id = EXCLUDED.execution_id,
                    updated_at = now()
                WHERE EXCLUDED.sort_at >= control.market_serving_recent.sort_at
            ''', chunk)

    # Vacuum
    print("Running VACUUM ANALYZE...", flush=True)
    with conn.cursor() as cur:
        cur.execute('VACUUM ANALYZE control.stock_serving_recent, control.market_serving_recent;')

    # Verification counts
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM control.stock_serving_recent WHERE dataset_id='ohlcv'")
        actual_ohlcv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM control.market_serving_recent WHERE dataset_id='financials'")
        actual_fin = cur.fetchone()[0]

    report.update({
        'status': 'PASS',
        'ohlcv_inserted': len(prepared_ohlcv),
        'financials_inserted': len(prepared_fin),
        'db_total_serving_ohlcv': actual_ohlcv,
        'db_total_serving_financials': actual_fin,
        'tier1_symbols_count': len(tier1),
        'tier1_ohlcv_rows': tier1_count,
        'tier2_ohlcv_rows': tier2_count,
        'elapsed_seconds': round(time.time() - t0, 2),
    })

except Exception as err:
    traceback.print_exc()
    report['status'] = f"FAIL_{type(err).__name__}"
    report['error'] = str(err)
finally:
    if control is not None:
        try: control.close()
        except Exception: pass

print("HISTORY_SEED_RECEIPT:" + json.dumps(report, sort_keys=True, ensure_ascii=False), flush=True)
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python history_seed_serving_sync.py <request_json>")
        sys.exit(1)

    req = json.loads(Path(sys.argv[1]).read_text())
    if (req.get('intent') != 'history-seed-serving-sync'
            or req.get('approved') is not True
            or req.get('no_owner_mutation') is not True
            or req.get('no_job_template_mutation') is not True):
        raise ValueError('invalid_history_seed_serving_request')

    j = job(JOB)
    containers = j['template']['template']['containers']
    if len(containers) != 1 or containers[0].get('command') not in (None, [], ['python']):
        raise ValueError('job_entrypoint_drift')

    override = {
        'args': (['python'] if not containers[0].get('command') else []) + ['-c', PROBE],
        'env': [
            {'name': 'QUEUE_CONSUMER', 'value': 'false'},
            {'name': 'HISTORY_SEED_REQUEST', 'value': json.dumps(req, separators=(',', ':'))},
        ],
    }
    if containers[0].get('name'):
        override['name'] = containers[0]['name']

    print(f"Triggering Cloud Run Job {JOB} with history seed probe...")
    op = cloud(f'{ROOT}/jobs/{JOB}:run', {
        'etag': j['etag'],
        'overrides': {'taskCount': 1, 'timeout': '1200s', 'containerOverrides': [override]},
    }, 'POST')

    name = op.get('name', '')
    if not name.startswith(ROOT + '/operations/'):
        raise RuntimeError('invalid_job_run_operation')

    until = time.monotonic() + 1260
    while not op.get('done') and time.monotonic() < until:
        time.sleep(10)
        op = cloud(name)
        print(f"Waiting for Job completion (elapsed: {time.monotonic() - (until - 1260):.0f}s)...")

    if not op.get('done') or op.get('error'):
        raise RuntimeError(f"Job execution failed or timed out: {op.get('error')}")

    exe = op.get('response', {})
    execution = exe.get('name', '').rsplit('/', 1)[-1]

    # Dump logs if execution was not successful
    if not terminal(exe) or exe.get('succeededCount') != 1 or exe.get('failedCount', 0):
        print(f"Cloud Run Job failed: {execution}, details: {json.dumps(exe)}")
        filt = f'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="{execution}"'
        cp = subprocess.run([
            'gcloud', 'logging', 'read', filt, f'--project={PROJECT}',
            '--limit=100', '--format=json',
        ], text=True, capture_output=True, timeout=50)
        if cp.returncode == 0:
            for event in json.loads(cp.stdout):
                print(event.get('textPayload', ''))
        raise RuntimeError('job_execution_not_terminal_success')

    print(f"Cloud Run Job succeeded: {execution}")

    # Read receipt from Cloud Logging
    filt = f'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="{execution}"'
    receipt = None
    for _ in range(6):
        cp = subprocess.run([
            'gcloud', 'logging', 'read', filt, f'--project={PROJECT}',
            '--limit=300', '--format=json',
        ], text=True, capture_output=True, timeout=50)
        if cp.returncode == 0:
            for event in json.loads(cp.stdout):
                text = event.get('textPayload', '')
                if 'HISTORY_SEED_RECEIPT:' in text:
                    blob = text.split('HISTORY_SEED_RECEIPT:', 1)[1].strip()
                    try:
                        receipt = json.loads(blob)
                        break
                    except Exception:
                        continue
        if receipt:
            break
        time.sleep(5)

    if receipt is None:
        raise RuntimeError('history_seed_receipt_not_observed_in_logs')

    out = {'execution': execution, 'receipt': receipt}
    Path('/tmp/history-seed-serving-readback.json').write_text(json.dumps(out, sort_keys=True, indent=2) + '\n')
    print(json.dumps(out, sort_keys=True, indent=2))

    if receipt.get('status') != 'PASS':
        raise RuntimeError(f"history_seed_import_not_pass: {receipt.get('status')}")
    print("Full market history seed successfully projected into PostgreSQL serving!")


if __name__ == '__main__':
    main()
