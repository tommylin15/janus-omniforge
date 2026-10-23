"""Janus market / sector research-only Colab trial (2025H1).
Uses public TWSE MI_5MINS_HIST / MI_INDEX and candidate TPEx monthly report APIs.
No FinMind; never writes to canonical or production.
"""
import csv
import hashlib
import io
import json
import math
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

START_MONTH = '2025-01'
END_MONTH = '2025-06'
MAX_REQUESTS = 360
MAX_MINUTES = 90
INTERVAL_SECONDS = 2.0
TIMEOUT_SECONDS = 35
INCLUDE_TPEX = True

ROOT = Path('/content/drive/MyDrive/給ai專用/janusChatGPT')
if not ROOT.is_dir():
    raise RuntimeError('找不到 MyDrive/給ai專用/janusChatGPT；請先執行 Drive 掛載格，不要更改成個人用路徑')
OUT = ROOT / '資料源' / '大盤產業_免費來源_2025H1_試跑'
OUT.mkdir(parents=True, exist_ok=True)

TWSE_MARKET = 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST'
TWSE_SECTOR = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
TPEX = {
    'tpex_market': [
        'https://www.tpex.org.tw/www/zh-tw/mainboard/trading/info/daily-indices',
        'https://www.tpex.org.tw/www/zh-tw/mainboard/trading/info/indices-pricing',
    ],
    'tpex_sector': [
        'https://www.tpex.org.tw/www/zh-tw/mainboard/trading/statistics/indices/daily-sector',
        'https://www.tpex.org.tw/www/zh-tw/indices/stock-index/industrial/idxsm',
    ],
}

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; Janus Research Collection v1)',
                        'Accept': 'application/json,text/plain,*/*'})
t0 = time.monotonic()
last_called = 0.0
n_requests = 0
interrupted = False
states = {}

class SourceError(Exception):
    pass

class BudgetReached(Exception):
    pass


def months(start, end):
    y, m = map(int, start.split('-'))
    ye, me = map(int, end.split('-'))
    if (y, m) > (ye, me) or not (1 <= m <= 12 and 1 <= me <= 12):
        raise ValueError('BAD_MONTH_RANGE')
    while (y, m) <= (ye, me):
        yield f'{y:04d}-{m:02d}'
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def jbytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(payload)
    os.replace(temp, path)


def immutable(path, payload):
    if path.exists():
        if digest(path.read_bytes()) != digest(payload):
            raise SourceError('IMMUTABLE_CONFLICT:' + str(path))
    else:
        atomic(path, payload)


def parse_date(x):
    s = str(x).strip().replace('年', '/').replace('月', '/').replace('日', '')
    s = re.sub(r'\s+', '', s)
    if re.fullmatch(r'\d{7}', s):
        s = f'{s[:3]}/{s[3:5]}/{s[5:]}'
    if re.fullmatch(r'\d{8}', s):
        s = f'{s[:4]}/{s[4:6]}/{s[6:]}'
    tokens = re.split(r'[-/]', s)
    if len(tokens) != 3 or not all(t.isdigit() for t in tokens):
        raise SourceError('INVALID_DATE:' + str(x)[:50])
    y, m, d = map(int, tokens)
    if y <= 1911:
        y += 1911
    return date(y, m, d).isoformat()


def num(x):
    s = re.sub(r'<[^>]+>', '', str(x)).replace(',', '').strip()
    try:
        n = float(s)
    except ValueError as exc:
        raise SourceError('INVALID_INDEX_NUMBER:' + s[:40]) from exc
    if not math.isfinite(n) or not 0 < n < 100000000:
        raise SourceError('INDEX_OUT_OF_RANGE')
    return n


def lookup(row, *keys):
    if not isinstance(row, dict):
        return None
    for key in keys:
        for candidate, value in row.items():
            if re.sub(r'\s+', '', str(candidate)) == re.sub(r'\s+', '', key):
                return value
    return None


def tables(data):
    if not isinstance(data, dict):
        raise SourceError('NOT_JSON_OBJECT')
    entries = data.get('tables')
    if not isinstance(entries, list):
        entries = [data]
    output = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fields = entry.get('fields') or entry.get('columns')
        rows = entry.get('data') or entry.get('aaData') or entry.get('rows')
        if not isinstance(rows, list):
            continue
        parsed = []
        for row in rows:
            if isinstance(row, dict):
                parsed.append(row)
            elif isinstance(row, list) and isinstance(fields, list) and len(row) == len(fields):
                parsed.append(dict(zip(fields, row)))
        if parsed:
            output.append((str(entry.get('title', '')), parsed))
    if not output:
        raise SourceError('SOURCE_SCHEMA_UNSUPPORTED')
    return output


def check_stat(data):
    if not isinstance(data, dict):
        raise SourceError('NOT_JSON_OBJECT')
    stat = data.get('stat')
    if stat is not None and str(stat).upper() not in ('OK', 'SUCCESS'):
        raise SourceError('SOURCE_STAT:' + str(stat)[:120])


def dedup(records):
    result = {}
    for r in records:
        key = (r['trade_date'], r['index_id'])
        if key in result and result[key] != r:
            raise SourceError('DUPLICATE_OFFICIAL_KEY_CONFLICT')
        result[key] = r
    return [result[k] for k in sorted(result)]


def parse_twse_market(data, month):
    check_stat(data)
    output = []
    for _, rows in tables(data):
        for row in rows:
            d, close = lookup(row, '日期', '交易日期'), lookup(row, '收盤指數')
            if d is None or close is None:
                continue
            day = parse_date(d)
            if not day.startswith(month):
                raise SourceError('TWSE_WRONG_MONTH')
            r = {'market': 'TWSE', 'index_id': 'TAIEX', 'trade_date': day, 'close': num(close)}
            for field, label in (('open', '開盤指數'), ('high', '最高指數'), ('low', '最低指數')):
                v = lookup(row, label)
                if v is None:
                    raise SourceError('TWSE_MISSING_' + label)
                r[field] = num(v)
            if not r['low'] <= r['open'] <= r['high'] or not r['low'] <= r['close'] <= r['high']:
                raise SourceError('TWSE_OHLC_INVALID')
            output.append(r)
    if not output:
        raise SourceError('NO_TWSE_MONTHLY_INDEX')
    return dedup(output)


def parse_twse_sector(data, day):
    check_stat(data)
    if data.get('date') and parse_date(data['date']) != day:
        raise SourceError('TWSE_RESPONSE_DATE_MISMATCH')
    output = []
    for title, rows in tables(data):
        if '價格指數' not in title:
            continue
        for row in rows:
            name = lookup(row, '指數', '指數名稱')
            close = lookup(row, '收盤指數')
            if name is None or close is None:
                continue
            name = re.sub(r'<[^>]*>', '', str(name)).strip()
            if name.endswith(('類指數', '類股指數')):
                output.append({'market': 'TWSE', 'index_id': name, 'trade_date': day,
                               'close': num(close), 'type': 'sector_price_index'})
    if not output:
        raise SourceError('NO_TWSE_SECTOR_ROWS')
    return dedup(output)


def parse_tpex(data, month, source):
    check_stat(data)
    output = []
    for _, rows in tables(data):
        for row in rows:
            raw_day = lookup(row, '日期', '交易日期', '資料日期', '日　期')
            if raw_day is None:
                continue
            try:
                day = parse_date(raw_day)
            except (ValueError, SourceError):
                continue
            if not day.startswith(month):
                raise SourceError('TPEX_WRONG_MONTH')
            if source == 'tpex_market':
                name = lookup(row, '指數名稱', '指數', '名稱')
                if name is not None and not any(n in str(name) for n in ('櫃買指數', '櫃買加權', '上櫃指數', '加權指數')):
                    continue
                close = lookup(row, '櫃買指數', '加權指數', '收盤指數', '收盤', '收市指數', '收市')
                if close is not None:
                    output.append({'market': 'TPEX', 'index_id': 'TPEX', 'trade_date': day,
                                   'close': num(close)})
            else:
                label = lookup(row, '產業分類', '產業別', '指數名稱', '分類指數', '類股指數')
                close = lookup(row, '收盤指數', '收盤', '收市指數', '收市')
                if label is not None and close is not None and str(label).strip() not in ('', '總計', '合計'):
                    output.append({'market': 'TPEX', 'index_id': str(label).strip(),
                                   'trade_date': day, 'close': num(close), 'type': 'sector_price_index'})
                else:
                    for field, value in row.items():
                        if any(word in str(field) for word in ('類指數', '類股', '產業')):
                            if str(value).strip() not in ('', '--', '—'):
                                output.append({'market': 'TPEX', 'index_id': str(field).strip(),
                                               'trade_date': day, 'close': num(value),
                                               'type': 'sector_price_index'})
    if not output:
        raise SourceError(source.upper() + '_SCHEMA_UNSUPPORTED')
    return dedup(output)


def get_json(url, params=None, method='GET'):
    global n_requests, last_called
    if n_requests >= MAX_REQUESTS or (time.monotonic() - t0) / 60 >= MAX_MINUTES:
        raise BudgetReached('本輪已達 request/time 上限')
    wait = INTERVAL_SECONDS - (time.monotonic() - last_called)
    if wait > 0:
        time.sleep(wait)
    n_requests += 1
    last_called = time.monotonic()
    try:
        if method == 'GET':
            response = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        else:
            response = session.post(url, data=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise SourceError('NETWORK:' + type(exc).__name__) from exc
    if response.status_code in (401, 403, 429):
        raise SourceError('ACCESS_OR_RATE_LIMIT:' + str(response.status_code))
    if not response.ok:
        raise SourceError('HTTP:' + str(response.status_code))
    if len(response.content) > 12_000_000:
        raise SourceError('OVERSIZE_RESPONSE')
    try:
        data = response.json()
    except ValueError as exc:
        raise SourceError('NON_JSON_RESPONSE') from exc
    if not isinstance(data, dict):
        raise SourceError('NOT_JSON_OBJECT')
    return data, response.content, response.url


def fetch(source, stamp):
    if source == 'twse_market':
        data, raw, url = get_json(TWSE_MARKET, {'response': 'json', 'date': stamp.replace('-', '') + '01'})
        return parse_twse_market(data, stamp), raw, url
    if source == 'twse_sector':
        data, raw, url = get_json(TWSE_SECTOR, {'response': 'json', 'date': stamp.replace('-', ''),
                                               'type': 'ALLBUT0999'})
        return parse_twse_sector(data, stamp), raw, url
    year, month = map(int, stamp.split('-'))
    stamp_candidates = [f'{year - 1911}/{month:02d}', f'{year - 1911}/{month:02d}/01']
    failures = []
    for endpoint in TPEX[source]:
        for date_arg in stamp_candidates:
            for method in ('GET', 'POST'):
                try:
                    data, raw, url = get_json(endpoint, {'date': date_arg, 'response': 'json'}, method)
                    return parse_tpex(data, stamp, source), raw, url
                except BudgetReached:
                    raise
                except (SourceError, ValueError) as exc:
                    failures.append(f'{method}/{endpoint.rsplit("/", 1)[-1]}({date_arg}):{str(exc)[:80]}')
    raise SourceError('ALL_TPEX_CANDIDATES_FAILED: ' + ' | '.join(failures)[:850])


def part_dir(source, stamp):
    if source == 'twse_sector':
        return OUT / source / stamp[:7] / stamp
    return OUT / source / stamp


def verified_rows(source, stamp):
    folder = part_dir(source, stamp)
    receipt = folder / 'receipt.json'
    if not receipt.exists():
        return None
    try:
        meta = json.loads(receipt.read_text('utf-8'))
        if meta.get('status') != 'VERIFIED' or meta.get('source') != source or meta.get('period') != stamp:
            return None
        for filename, expected in meta['checksums'].items():
            blob = folder / filename
            if not blob.is_file() or digest(blob.read_bytes()) != expected:
                raise SourceError('CHECKSUM_MISMATCH:' + str(blob))
        result = json.loads((folder / meta['normalized']).read_text('utf-8'))
        if len(result) != meta['rows']:
            raise SourceError('ROWCOUNT_MISMATCH')
        return result
    except (KeyError, json.JSONDecodeError) as exc:
        raise SourceError('CORRUPTED_RECEIPT') from exc


def save_verified(source, stamp, records, raw, url):
    folder = part_dir(source, stamp)
    normalized = jbytes(records)
    raw_name = 'raw-' + digest(raw) + '.json'
    data_name = 'normalized-' + digest(normalized) + '.json'
    immutable(folder / raw_name, raw)
    immutable(folder / data_name, normalized)
    meta = {'status': 'VERIFIED', 'source': source, 'period': stamp, 'rows': len(records),
            'first_date': min(r['trade_date'] for r in records),
            'last_date': max(r['trade_date'] for r in records),
            'normalized': data_name, 'checksums': {raw_name: digest(raw), data_name: digest(normalized)},
            'source_url': url, 'retrieved_at_utc': utc(), 'classification': 'RESEARCH_ONLY'}
    atomic(folder / 'receipt.json', jbytes(meta))


def mark(source, period, status='PENDING', rows=0, reason=''):
    states[(source, period)] = {'source': source, 'period': period,
                                 'status': status, 'rows': rows, 'reason': str(reason)[:900]}


def save_progress():
    entries = [states[key] for key in sorted(states)]
    info = {}
    for src in ('twse_market', 'twse_sector', 'tpex_market', 'tpex_sector'):
        items = [x for x in entries if x['source'] == src]
        successful = [x for x in items if x['status'] == 'VERIFIED']
        pending = [x for x in items if x['status'] != 'VERIFIED']
        info[src] = {'verified': len(successful), 'unfinished': len(pending),
                     'latest_verified': max((x['period'] for x in successful), default=None),
                     'next_pending': min((x['period'] for x in pending), default=None)}
    report = {'timestamp_utc': utc(), 'start_month': START_MONTH, 'end_month': END_MONTH,
              'requests_used': n_requests, 'max_requests': MAX_REQUESTS,
              'interrupted': interrupted, 'summary': info, 'partitions': entries}
    atomic(OUT / 'progress_latest.json', jbytes(report))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=['source', 'period', 'status', 'rows', 'reason'])
    writer.writeheader()
    writer.writerows(entries)
    atomic(OUT / 'progress_latest.csv', buf.getvalue().encode('utf-8-sig'))
    return report


def job(source, period):
    try:
        prior = verified_rows(source, period)
        if prior is not None:
            mark(source, period, 'VERIFIED', len(prior), '既有資料 checksum 通過，直接略過')
            save_progress()
            return prior
        records, raw, url = fetch(source, period)
        save_verified(source, period, records, raw, url)
        mark(source, period, 'VERIFIED', len(records))
        print(f'VERIFIED {source:<13} {period}: {len(records)} rows')
        save_progress()
        return records
    except BudgetReached:
        mark(source, period, 'PENDING', reason='本輪 request/time 上限')
        save_progress()
        raise
    except (OSError, SourceError, ValueError) as exc:
        reason = f'{type(exc).__name__}: {exc}'
        mark(source, period, 'FAILED', reason=reason)
        atomic(part_dir(source, period) / 'error_latest.json', jbytes({'time': utc(), 'reason': reason}))
        print(f'FAILED   {source:<13} {period}: {reason[:155]}')
        save_progress()
        return None


def run():
    global interrupted
    period_list = list(months(START_MONTH, END_MONTH))
    if len(period_list) > 120:
        raise ValueError('單次最多設定 120 個月')
    for mo in period_list:
        mark('twse_market', mo)
        mark('twse_sector', mo, 'WAITING_CALENDAR', reason='待 TWSE 月索引驗證交易日期')
        if INCLUDE_TPEX:
            mark('tpex_market', mo)
            mark('tpex_sector', mo)
    save_progress()
    try:
        for mo in period_list:
            market = job('twse_market', mo)
            if market:
                states.pop(('twse_sector', mo), None)
                for row in market:
                    mark('twse_sector', row['trade_date'])
                save_progress()
            if INCLUDE_TPEX:
                job('tpex_market', mo)
                job('tpex_sector', mo)
            if market:
                for row in market:
                    job('twse_sector', row['trade_date'])
    except KeyboardInterrupt:
        interrupted = True
        print('手動停止，已落盤之成功分區可斷點續傳。')
    except BudgetReached as exc:
        print('本輪暫停，未完成分區留待續收：', exc)
    finally:
        report = save_progress()
        print('\n====== 進度彙總 ======')
        for src, item in report['summary'].items():
            print(src, 'VERIFIED=', item['verified'], 'PENDING/FAILED=', item['unfinished'],
                  'LAST=', item['latest_verified'], 'NEXT=', item['next_pending'])
        print('完整報表：', OUT / 'progress_latest.csv')
        print('JSON 報表：', OUT / 'progress_latest.json')
    return report

print('資料儲存：', OUT)
print('試跑範圍：', START_MONTH, '～', END_MONTH)
report = run()
