"""Janus D07-PRE research-only TWSE/TPEx common-stock historical daily collector.

Run manually in Google Colab. Uses official day-scoped batch endpoints, one
request per market/day (not one per stock/month), with immutable month folders.
Company master is *current* only; historical survivorship is NOT certified.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import time
from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

import requests

TWSE_COMPANIES = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
TPEX_COMPANIES = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
TPEX_COMPANIES_CSV = 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'
TWSE_DAILY = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
TPEX_DAILY = 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php'
HEADERS = ('symbol', 'market', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'turnover', 'source', 'observed_at')
EMPTY_TOKENS = {'', '--', '---', '-', '－', 'N/A', 'null', '除權', '除息'}
EXCLUDE_NAME = re.compile(r'ETF|ETN|指數投資|認購|認售|權證|存託憑證|特別股|受益憑證|債券|基金', re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def number(raw: Any) -> float | None:
    s = re.sub(r'<[^>]+>', '', str(raw if raw is not None else '')).replace(',', '').strip()
    if s in EMPTY_TOKENS:
        return None
    try:
        return float(s)
    except (ValueError, OverflowError):
        return None


def shares(raw: Any) -> int | None:
    n = number(raw)
    return int(n) if n is not None and n >= 0 and n.is_integer() else None


def company_universe(rows: list[dict], market: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not isinstance(rows, list):
        raise ValueError('company master must be JSON/CSV list')
    for r in rows:
        code = str(r.get('公司代號', r.get('SecuritiesCompanyCode', ''))).strip()
        name = str(r.get('公司名稱', r.get('CompanyName', ''))).strip()
        if not re.fullmatch(r'[1-9][0-9]{3}', code) or not name or EXCLUDE_NAME.search(name):
            continue
        result[code] = {'symbol': code, 'market': market, 'name': name}
    if len(result) < 1:
        raise ValueError(f'{market} official company master yielded no ordinary-stock candidates')
    return result


def csv_company_rows(body: bytes) -> list[dict]:
    content = None
    for encoding in ('utf-8-sig', 'big5'):
        try:
            content = body.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if content is None:
        raise ValueError('company CSV decode error')
    return list(csv.DictReader(io.StringIO(content)))


def _twse_fields_and_rows(payload: dict) -> tuple[list, list]:
    tables = payload.get('tables') or []
    for t in tables:
        f = t.get('fields') or []
        if '證券代號' in f and '收盤價' in f and '成交股數' in f:
            return f, t.get('data') or []
    for idx in (5, 8, 9, 4, 1):
        fields = payload.get(f'fields{idx}') or []
        if '證券代號' in fields and '收盤價' in fields and '成交股數' in fields:
            return fields, payload.get(f'data{idx}') or []
    raise ValueError('TWSE schema changed: equity table missing')


def _row(symbol: str, market: str, trading_date: str, fields: dict, observed_at: str, source: str) -> dict | None:
    close = number(fields.get('close'))
    vol = shares(fields.get('volume'))
    if close is None or close <= 0 or vol is None:
        return None
    return dict(symbol=symbol, market=market, trade_date=trading_date,
                open=number(fields.get('open')), high=number(fields.get('high')),
                low=number(fields.get('low')), close=close, volume=vol,
                turnover=shares(fields.get('turnover')), source=source, observed_at=observed_at)


def parse_twse(payload: dict, trade_day: date, whitelist: dict[str, dict], observed_at: str) -> list[dict]:
    fields, data = _twse_fields_and_rows(payload)
    ix = {str(v).replace(' ', ''): i for i, v in enumerate(fields)}
    keys = ['證券代號', '成交股數', '收盤價', '開盤價', '最高價', '最低價', '成交金額']
    if not all(k in ix for k in keys):
        raise ValueError('TWSE daily mandatory fields missing')
    out = []
    for item in data:
        symbol = re.sub('<[^>]*>', '', str(item[ix['證券代號']])).strip()
        if symbol not in whitelist:
            continue
        f = {'open': item[ix['開盤價']], 'high': item[ix['最高價']],
             'low': item[ix['最低價']], 'close': item[ix['收盤價']],
             'volume': item[ix['成交股數']], 'turnover': item[ix['成交金額']]}
        r = _row(symbol, 'twse', trade_day.isoformat(), f, observed_at, 'TWSE:MI_INDEX')
        if r:
            out.append(r)
    return out


def parse_tpex(payload: dict, trade_day: date, whitelist: dict[str, dict], observed_at: str) -> list[dict]:
    tables = payload.get('tables') or []
    if not tables and 'aaData' in payload:
        tables = [{'data': payload['aaData']}]
    if not tables:
        raise ValueError('TPEx historical daily data table missing')
    out = []
    for table in tables:
        fields = [str(f).replace(' ', '') for f in table.get('fields', [])]
        for values in table.get('data', []):
            if not isinstance(values, list) or len(values) < 10:
                continue
            symbol = re.sub(r'<[^>]*>', '', str(values[0])).strip()
            if symbol not in whitelist:
                continue
            if all(x in fields for x in ('收盤', '開盤', '最高', '最低', '成交股數', '成交金額')):
                m = {key: fields.index(key) for key in ('收盤', '開盤', '最高', '最低', '成交股數', '成交金額')}
                vals = dict(close=values[m['收盤']], open=values[m['開盤']], high=values[m['最高']],
                            low=values[m['最低']], volume=values[m['成交股數']], turnover=values[m['成交金額']])
            else:
                # Legacy official stk_wn1430_result.php table layout.
                vals = dict(close=values[2], open=values[4], high=values[5],
                            low=values[6], volume=values[8], turnover=values[9])
            r = _row(symbol, 'tpex', trade_day.isoformat(), vals, observed_at, 'TPEx:OTC_DAILY')
            if r:
                out.append(r)
    return out


def no_trading(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    text = str(payload.get('stat') or payload.get('message') or payload.get('msg') or '')
    return any(word in text for word in ('沒有符合條件', '查無資料', '未有資料', '休市', '很抱歉', 'No data', 'NO DATA'))


def fetch_json(session, url: str, params: dict | None, *, retries: int = 3) -> tuple[Any, str]:
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=35, headers={'User-Agent': 'JanusResearch/0.1 (+personal noncommercial research)'})
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f'retryable HTTP {r.status_code}')
            r.raise_for_status()
            return r.json(), digest(r.content)
        except (requests.RequestException, ValueError, RuntimeError):
            if attempt + 1 == retries:
                raise
            time.sleep(min(30, 2 ** attempt * 3))
    raise AssertionError('unreachable')


def fetch_company_snapshots(session) -> tuple[dict, dict]:
    l, lhash = fetch_json(session, TWSE_COMPANIES, None)
    o_source = TPEX_COMPANIES
    try:
        o, ohash = fetch_json(session, TPEX_COMPANIES, None)
        if not isinstance(o, list):
            raise ValueError('TPEx company API not a list')
    except (ValueError, requests.RequestException, RuntimeError):
        r = session.get(TPEX_COMPANIES_CSV, timeout=35)
        r.raise_for_status()
        o, ohash = csv_company_rows(r.content), digest(r.content)
        o_source = TPEX_COMPANIES_CSV
    return ({'twse': company_universe(l, 'twse'), 'tpex': company_universe(o, 'tpex')},
            {'twse': {'url': TWSE_COMPANIES, 'sha256': lhash},
             'tpex': {'url': o_source, 'sha256': ohash}})


def daily_url(market: str, day: date) -> tuple[str, dict]:
    if market == 'twse':
        return TWSE_DAILY, {'date': day.strftime('%Y%m%d'), 'type': 'ALLBUT0999', 'response': 'json'}
    roc = f'{day.year - 1911}/{day.month:02d}/{day.day:02d}'
    return TPEX_DAILY, {'l': 'zh-tw', 'd': roc, 'se': 'EW'}


def read_chunk(path: Path, universe_hash: str) -> dict:
    raw = gzip.decompress(path.read_bytes())
    data = json.loads(raw)
    if data.get('universe_hash') != universe_hash or data.get('schema_version') != 1:
        raise ValueError('checkpoint universe/schema changed; choose a new revision')
    return data


def collect_chunk(session, market: str, dates: list[date], universe: dict, universe_hash: str,
                  path: Path, *, min_interval: float, request_budget: list[int]) -> bool:
    if path.exists():
        read_chunk(path, universe_hash)
        return True
    if request_budget[0] < len(dates):
        return False
    rows, statuses = [], []
    for day in dates:
        url, params = daily_url(market, day)
        payload, source_hash = fetch_json(session, url, params)
        request_budget[0] -= 1
        observed = utc_now()
        if no_trading(payload):
            statuses.append({'day': day.isoformat(), 'status': 'OFFICIAL_NO_DATA', 'sha256': source_hash})
        else:
            parsed = parse_twse(payload, day, universe, observed) if market == 'twse' else parse_tpex(payload, day, universe, observed)
            if not parsed:
                raise ValueError(f'{market} {day} no valid ordinary-stock bars; not treated as holiday')
            rows.extend(parsed)
            statuses.append({'day': day.isoformat(), 'status': 'COLLECTED',
                             'rows': len(parsed), 'sha256': source_hash})
        if min_interval:
            time.sleep(min_interval)
    content = {'schema_version': 1, 'universe_hash': universe_hash, 'market': market,
               'days': statuses, 'rows': rows}
    write_atomic(path, gzip.compress(json_bytes(content), mtime=0))
    return True


def month_days(month: str, end: date) -> list[date]:
    start = date.fromisoformat(month + '-01')
    ny = start.year + (start.month == 12)
    nm = start.month % 12 + 1
    stop = min(date(ny, nm, 1), end + timedelta(days=1))
    arr = []
    while start < stop:
        if start.weekday() < 5:
            arr.append(start)
        start += timedelta(days=1)
    return arr


def months_between(start: str, end: str) -> list[str]:
    s, e = date.fromisoformat(start + '-01'), date.fromisoformat(end + '-01')
    if s > e or (e.year - s.year) * 12 + e.month - s.month > 35:
        raise ValueError('month range invalid or exceeds 36 months')
    out = []
    while s <= e:
        out.append(s.strftime('%Y-%m'))
        s = date(s.year + (s.month == 12), s.month % 12 + 1, 1)
    return out


def csv_payload(rows: list[dict], cols=HEADERS) -> bytes:
    o = io.StringIO(newline='')
    w = csv.DictWriter(o, fieldnames=list(cols), extrasaction='ignore')
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return o.getvalue().encode('utf-8')


def finalize_month(root: Path, month: str, revision: str, days: list[date], rosters: dict,
                   hashes: dict, *, allow_partial: bool = False) -> dict:
    folder = root / month
    paths = {m: [folder / '_checkpoint' / revision / f'{m}-{i:03d}.json.gz'
                 for i in range(0, len(days), 10)] for m in ('twse', 'tpex')}
    manifest_path = folder / f'manifest-{revision}.json'
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text('utf-8'))
        for name, sha in existing.get('sha256', {}).items():
            if not (folder / name).exists() or digest((folder / name).read_bytes()) != sha:
                raise ValueError('published archive corrupted: use new revision, no overwrite')
        return {'status': 'ALREADY_ARCHIVED', 'month': month}
    if not all(p.exists() for files in paths.values() for p in files):
        return {'status': 'PARTIAL', 'month': month, 'pending_chunks': sum(not p.exists() for files in paths.values() for p in files)}
    chunks = [read_chunk(p, hashes['universe']) for files in paths.values() for p in files]
    rows = [r for ch in chunks for r in ch['rows']]
    ids = [(r['symbol'], r['trade_date']) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate symbol/day across official chunks')
    # Whole-company master is latest snapshot, NOT the historical as-of universe.
    universe_rows = sorted([x for market in ('twse', 'tpex') for x in rosters[market].values()],
                           key=lambda r: (r['market'], r['symbol']))
    statuses = [s for ch in chunks for s in ch['days']]
    rows.sort(key=lambda r: (r['symbol'], r['trade_date']))
    content = {
        f'ohlcv-{revision}.csv.gz': gzip.compress(csv_payload(rows), mtime=0),
        f'universe-{revision}.csv': csv_payload(universe_rows, ('symbol', 'market', 'name')),
    }
    market_counts = {}
    for market in ('twse', 'tpex'):
        actual = len({r['symbol'] for r in rows if r['market'] == market})
        market_counts[market] = {'snapshot_symbols': len(rosters[market]), 'symbols_with_bars': actual,
                                 'observed_ratio': actual / max(1, len(rosters[market]))}
    quality = {'status': 'PROBE', 'market_counts': market_counts,
               'historical_pit': 'NOT_VERIFIED', 'historical_survivorship': 'CURRENT_MASTER_ONLY',
               'research_70pct_certified': False, 'missing_financials': 'UNAVAILABLE',
               'corporate_actions': 'UNADJUSTED', 'market_calendar': 'EXPLICIT_OFFICIAL_NO_DATA',
               'collected_days': sum(s['status'] == 'COLLECTED' for s in statuses),
               'no_data_days': sum(s['status'] == 'OFFICIAL_NO_DATA' for s in statuses)}
    content[f'quality-{revision}.json'] = json_bytes(quality)
    manifest = {'schema_version': 1, 'month': month, 'revision': revision,
                'kind': 'COLAB_RESEARCH_PROBE', 'publication_allowed': False,
                'source_urls': [TWSE_DAILY, TPEX_DAILY, TWSE_COMPANIES, TPEX_COMPANIES],
                'source_master_hash': hashes['universe'], 'captured_master_at': hashes['captured_at'],
                'source_daily_sha256': statuses,
                'sha256': {name: digest(data) for name, data in content.items()},
                'created_at': utc_now()}
    for name, body in content.items():
        if (folder / name).exists():
            raise ValueError('orphan published member; manual inspection before new revision')
        write_atomic(folder / name, body)
    write_atomic(manifest_path, json_bytes(manifest))
    for name, sha in manifest['sha256'].items():
        if digest((folder / name).read_bytes()) != sha:
            raise ValueError('published monthly hash verification failed; checkpoints retained')
    # Reduce Drive small objects only after full month and hash verification.
    for parts in paths.values():
        for chunk in parts:
            chunk.unlink()
    (folder / '_checkpoint' / revision).rmdir()
    (folder / '_checkpoint').rmdir()
    return {'status': 'PROBE_ARCHIVED', 'month': month, 'rows': len(rows),
            'market_counts': market_counts, 'sha256': digest(json_bytes(manifest))}


def execute(root: Path, start_month: str, end_month: str, revision: str,
            *, max_requests: int = 120, min_interval: float = 2.0, session=None,
            today: date | None = None) -> list[dict]:
    if not re.fullmatch(r'r[1-9][0-9]{0,2}', revision):
        raise ValueError('revision must be r1..r999')
    today = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    allmonths = months_between(start_month, end_month)
    if date.fromisoformat(end_month + '-01') >= today.replace(day=1):
        raise ValueError('only fully closed historical months are supported; wait until next month')
    if max_requests < 0 or max_requests > 500:
        raise ValueError('max_requests must be bounded between 0 and 500')
    root.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()
    ctl = root / '_control'
    # Snapshot once per research revision: retries never silently change universe.
    snap = ctl / f'universe-{revision}.json'
    if snap.exists():
        cached = json.loads(snap.read_text('utf-8'))
        universe = cached['data']
        hashes = {'universe': digest(json_bytes(cached)), 'captured_at': cached['captured_at']}
    else:
        rosters, provenance = fetch_company_snapshots(session)
        cached = {'captured_at': utc_now(), 'data': rosters, 'provenance': provenance,
                  'historical_survivorship': 'CURRENT_MASTER_ONLY'}
        write_atomic(snap, json_bytes(cached))
        universe = rosters
        hashes = {'universe': digest(json_bytes(cached)), 'captured_at': cached['captured_at']}
    budget = [max_requests]
    outputs = []
    for month in allmonths:
        if (root / month / f'manifest-{revision}.json').exists():
            # Finalized month is immutable: validate before accepting.
            existing = json.loads((root / month / f'manifest-{revision}.json').read_text('utf-8'))
            if all((root / month / name).exists() and digest((root / month / name).read_bytes()) == sha
                   for name, sha in existing['sha256'].items()):
                outputs.append({'status': 'ALREADY_ARCHIVED', 'month': month})
                continue
            raise ValueError('finalized monthly file failed checksum; no silent overwrite')
        days = month_days(month, today - timedelta(days=1))
        if not days:
            outputs.append({'status': 'NOT_MATURED', 'month': month})
            continue
        for market in ('twse', 'tpex'):
            for i in range(0, len(days), 10):
                path = root / month / '_checkpoint' / revision / f'{market}-{i:03d}.json.gz'
                if not collect_chunk(session, market, days[i:i+10], universe[market], hashes['universe'],
                                     path, min_interval=min_interval, request_budget=budget):
                    break
        outputs.append(finalize_month(root, month, revision, days, universe, hashes))
        if budget[0] == 0:
            break
    return outputs


def main() -> None:
    p = argparse.ArgumentParser(description='Official TWSE/TPEx Colab historical common-stock pilot; no model publish')
    p.add_argument('--drive-root', required=True, type=Path, help='mounted private janusChatGPT/資料源')
    p.add_argument('--start', required=True, help='YYYY-MM')
    p.add_argument('--end', required=True, help='YYYY-MM')
    p.add_argument('--revision', default='r1')
    p.add_argument('--max-requests', type=int, default=120)
    p.add_argument('--interval', type=float, default=2.0)
    a = p.parse_args()
    if a.interval < 1.0:
        p.error('interval must be >= 1 second')
    result = execute(a.drive_root, a.start, a.end, a.revision,
                     max_requests=a.max_requests, min_interval=a.interval)
    for item in result:
        print(json.dumps(item, ensure_ascii=False))


if __name__ == '__main__':
    main()