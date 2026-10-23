"""Janus TPEx official market/sector collector v2, independent of TWSE trading calendar.
Research-only, no FinMind or paid API; never writes canonical / production.
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

START_MONTH = '2026-01'
END_MONTH = '2026-09'
MAX_REQUESTS = 360
MAX_MINUTES = 90
INTERVAL_SECONDS = 2.0
TIMEOUT_SECONDS = 35

ROOT = Path('/content/drive/MyDrive/給ai專用/janusChatGPT')
OUT = ROOT / '資料源' / '大盤產業_免費來源_2025H1_試跑'


def ensure_drive_root():
    if not ROOT.is_dir():
        raise RuntimeError('找不到 MyDrive/給ai專用/janusChatGPT；請先執行 Drive 掛載格，不要更改成個人用路徑')
    OUT.mkdir(parents=True, exist_ok=True)

TPEX = {
    "tpex_market": "https://www.tpex.org.tw/www/zh-tw/indexInfo/inx",
    "tpex_sector": "https://www.tpex.org.tw/www/zh-tw/indexInfo/idxsm",
}
TPEX_DAILY = "https://www.tpex.org.tw/www/zh-tw/indexInfo/sectinx"
# 與既有試跑輸出共用分區和 checksum；不碰 TWSE 正式資料。
DAILY_FALLBACK = True


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


def clean_label(x):
    return re.sub(r"\s+", "", re.sub(r"<[^>]*>", "", str(x))).strip()


def parse_tpex(data, month, source, expected_dates=None):
    """TPEx 官方月查詢：inx 是日期+OHLC、idxsm 是日期+各類股價格/報酬雙矩陣。"""
    check_stat(data)
    output = []
    for title, rows in tables(data):
        for row in rows:
            raw_day = lookup(row, '日期', '交易日期', '資料日期', '日　期')
            if raw_day is None:
                continue
            day = parse_date(raw_day)
            if not day.startswith(month):
                raise SourceError('TPEX_WRONG_MONTH:' + day)
            if source == 'tpex_market':
                record = {'market': 'TPEX', 'index_id': 'TPEX', 'trade_date': day}
                for field, labels in (
                    ('open', ('開市', '開盤')), ('high', ('最高', '最高價')),
                    ('low', ('最低', '最低價')), ('close', ('收市', '收盤'))
                ):
                    value = lookup(row, *labels)
                    if value is None:
                        raise SourceError('TPEX_INX_MISSING_' + field)
                    record[field] = num(value)
                validate_ohlc(record)
                output.append(record)
            else:
                # 官方 idxsm 月報：價格指數與報酬指數是不同產品，不能混在一起。
                for field, value in row.items():
                    name = clean_label(field)
                    if not name or name in ('日期', '交易日期', '資料日期', '日　期'):
                        continue
                    if any(k in name for k in ('報酬', '漲跌', '增減', '變動', '總計', '合計', '備註', '平均')):
                        continue
                    if name in ('櫃買指數', '櫃買加權指數'):
                        continue
                    # 僅辨識有產業語意的命名。不能把報酬率、統計欄位冒充價格指數。
                    if not any(k in name for k in ('類', '業', '產業', '紡織', '電機', '鋼鐵', '電子', '化學', '觀光', '航運', '半導體', '資訊', '文化', '綠能', '數位', '居家')):
                        continue
                    if str(value).strip() in ('', '--', '－', '—', 'N/A'):
                        continue
                    output.append({'market': 'TPEX', 'index_id': name, 'trade_date': day,
                                   'close': num(value), 'type': 'sector_price_index'})
    validate_tpex_coverage(output, expected_dates, source, month)
    return dedup(output)


def validate_ohlc(r):
    if not (r['low'] <= r['open'] <= r['high'] and r['low'] <= r['close'] <= r['high']):
        raise SourceError('TPEX_OHLC_INVALID:' + r['trade_date'])


def validate_tpex_coverage(rows, expected_dates, source, month=None):
    """TPEx 自己的月指數作主要日曆；月報互核，不以 TWSE 存在作必要條件。"""
    if not rows:
        raise SourceError('TPEX_EMPTY_' + source)
    got = {r['trade_date'] for r in rows}
    if month is None:
        month = min(got)[:7]
    if any(not d.startswith(month) for d in got):
        raise SourceError('TPEX_WRONG_MONTH_OR_RANGE')
    if not (10 <= len(got) <= 25):
        raise SourceError('TPEX_MONTH_DAYCOUNT_OUT_OF_BOUNDS:' + str(len(got)))
    if any(date.fromisoformat(d).weekday() > 4 for d in got):
        raise SourceError('TPEX_NON_TRADING_WEEKEND_DAY')
    if expected_dates is not None:
        expected = set(expected_dates)
        missing = sorted(expected - got)
        unexpected = sorted(got - expected)
        if missing or unexpected:
            raise SourceError('TPEX_MARKET_SECTOR_CALENDAR_MISMATCH:missing=' + ','.join(missing[:30])
                              + ';extra=' + ','.join(unexpected[:30]))
    if source == 'tpex_sector':
        counts = {d: len({r['index_id'] for r in rows if r['trade_date'] == d}) for d in got}
        weak = {d: n for d, n in counts.items() if n < 10}
        if weak:
            raise SourceError('TPEX_SECTOR_COVERAGE_LOW:' + str(weak)[:400])
        if len(rows) != len({(r['trade_date'], r['index_id']) for r in rows}):
            raise SourceError('TPEX_DUPLICATE_SECTOR_ROW')
    else:
        if len(rows) != len(got) or any(r['index_id'] != 'TPEX' for r in rows):
            raise SourceError('TPEX_MARKET_UNEXPECTED_ROWCOUNT_OR_ID')
        for r in rows:
            validate_ohlc(r)


# 日查詢作為月資料 API 無法解析時的官方 fallback；同一日同時取得大盤/產業。
import base64
_daily_cache = {}


def fetch_daily_tpex(day):
    if day in _daily_cache:
        return _daily_cache[day]
    data, raw, url = get_json(TPEX_DAILY, {'date': day.replace('-', '/'), 'response': 'json'})
    check_stat(data)
    body_date = data.get('date')
    if body_date is not None and parse_date(body_date) != day:
        raise SourceError('TPEX_SECTINX_DATE_MISMATCH')
    daily_market = []
    daily_sectors = []
    for title, rows in tables(data):
        if '指數' not in title and '產業' not in title:
            continue
        for row in rows:
            label = lookup(row, '類股名稱', '指數名稱', '類股', '名稱')
            close_val = lookup(row, '收市', '收盤', '收盤指數')
            if label is None or close_val is None:
                continue
            name = clean_label(label)
            if not name or '報酬' in name or name in ('合計', '總計'):
                continue
            if name == '櫃買指數':
                rec = {'market': 'TPEX', 'index_id': 'TPEX', 'trade_date': day,
                       'close': num(close_val)}
                for field, labels in (('open', ('開市', '開盤')),
                                      ('high', ('最高', '最高價')),
                                      ('low', ('最低', '最低價'))):
                    v = lookup(row, *labels)
                    if v is None:
                        raise SourceError('TPEX_DAILY_MISSING_' + field)
                    rec[field] = num(v)
                validate_ohlc(rec)
                daily_market.append(rec)
            else:
                daily_sectors.append({'market': 'TPEX', 'index_id': name,
                                      'trade_date': day, 'close': num(close_val),
                                      'type': 'sector_price_index'})
    if len(daily_market) != 1 or len(daily_sectors) < 10:
        raise SourceError('TPEX_DAILY_SCHEMA_INCOMPLETE:' + day +
                          f':market={len(daily_market)},sectors={len(daily_sectors)}')
    result = (daily_market, dedup(daily_sectors), raw, url)
    _daily_cache[day] = result
    return result


def tpex_market_calendar(month):
    """只使用已通過 receipt 檢查的 TPEx 大盤；從不向 TWSE 取日曆。"""
    rows = verified_rows('tpex_market', month)
    if rows is None:
        raise SourceError('TPEX_MARKET_REFERENCE_MISSING:' + month)
    validate_tpex_coverage(rows, None, 'tpex_market', month)
    return sorted({r['trade_date'] for r in rows})


def index_month_calendar(month):
    """大盤月報真的失敗時，嘗試用官方 TPEx 產業月報取得可核對的日期列表。"""
    year, mm = map(int, month.split('-'))
    params = {'date': f'{year:04d}/{mm:02d}/01', 'response': 'json'}
    payload, _raw, _url = get_json(TPEX['tpex_sector'], params)
    source_rows = parse_tpex(payload, month, 'tpex_sector')
    return sorted({r['trade_date'] for r in source_rows})


def fetch_tpex(source, month):
    # 月大盤用 TPEx 自己的月資料做交易日參照；月產業再與大盤做嚴格逐日交叉比對。
    expected_dates = tpex_market_calendar(month) if source == 'tpex_sector' else None
    year, mm = map(int, month.split('-'))
    params = {'date': f'{year:04d}/{mm:02d}/01', 'response': 'json'}
    monthly_error = None
    try:
        data, raw, url = get_json(TPEX[source], params)
        return parse_tpex(data, month, source, expected_dates), raw, url
    except BudgetReached:
        raise
    except (SourceError, ValueError) as exc:
        monthly_error = f'{type(exc).__name__}:{exc}'
        if not DAILY_FALLBACK:
            raise SourceError('MONTHLY_TPEX_FAILED:' + monthly_error) from exc
        print('月報未通過驗證，改用官方逐日 sectinx：', source, month, monthly_error[:140])

    # 大盤月報無法解析時，改從 TPEx 產業月報取暫定日曆（仍不依賴 TWSE）。
    if expected_dates is None:
        try:
            expected_dates = index_month_calendar(month)
        except BudgetReached:
            raise
        except (SourceError, ValueError) as exc:
            raise SourceError('TPEX_MONTH_AND_REFERENCE_FAILED:' + month +
                              ':market=' + monthly_error[:180] + ':sector_calendar=' + str(exc)[:180]) from exc

    rows = []
    raw_manifest = []
    for day in expected_dates:
        try:
            market, sectors, raw, url = fetch_daily_tpex(day)
        except BudgetReached:
            raise
        except (SourceError, ValueError) as exc:
            raise SourceError('TPEX_MONTHLY_AND_DAILY_FAILED:' + month + ':monthly=' +
                              monthly_error[:200] + ':daily=' + day + ':' + str(exc)[:200]) from exc
        rows.extend(market if source == 'tpex_market' else sectors)
        raw_manifest.append({'date': day, 'url': url,
                             'raw_base64': base64.b64encode(raw).decode('ascii')})
    validate_tpex_coverage(rows, expected_dates, source, month)
    payload = jbytes({'transport': 'tpex_sectinx_daily_raw_bundle',
                      'monthly_error': monthly_error, 'requests': raw_manifest})
    return dedup(rows), payload, TPEX_DAILY


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
    if source not in TPEX:
        raise ValueError('TPEX_ONLY_COLLECTOR_REFUSES_OTHER_SOURCE')
    return fetch_tpex(source, stamp)


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
    for src in ('tpex_market', 'tpex_sector'):
        items = [x for x in entries if x['source'] == src]
        successful = [x for x in items if x['status'] == 'VERIFIED']
        pending = [x for x in items if x['status'] != 'VERIFIED']
        info[src] = {'verified': len(successful), 'unfinished': len(pending),
                     'latest_verified': max((x['period'] for x in successful), default=None),
                     'next_pending': min((x['period'] for x in pending), default=None)}
    report = {'timestamp_utc': utc(), 'collector_version': 'tpex-independent-calendar-v2', 'calendar_basis': 'tpex_market_inx_with_idxsm_fallback', 'start_month': START_MONTH, 'end_month': END_MONTH,
              'requests_used': n_requests, 'max_requests': MAX_REQUESTS,
              'interrupted': interrupted, 'summary': info, 'partitions': entries}
    atomic(OUT / 'progress_tpex_latest.json', jbytes(report))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=['source', 'period', 'status', 'rows', 'reason'])
    writer.writeheader()
    writer.writerows(entries)
    atomic(OUT / 'progress_tpex_latest.csv', buf.getvalue().encode('utf-8-sig'))
    return report


def job(source, period):
    try:
        prior = verified_rows(source, period)
        if prior is not None:
            validate_tpex_coverage(prior, tpex_market_calendar(period) if source == 'tpex_sector' else None, source, period)
            mark(source, period, 'VERIFIED', len(prior), '既有資料 checksum 與 TPEx 日曆驗證通過，直接略過')
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
    ensure_drive_root()
    period_list = list(months(START_MONTH, END_MONTH))
    if len(period_list) > 120:
        raise ValueError('單次最多設定 120 個月')

    for mo in period_list:
        mark('tpex_market', mo)
        mark('tpex_sector', mo)
    save_progress()

    try:
        for mo in period_list:
            market = job('tpex_market', mo)
            if market is None:
                mark('tpex_sector', mo, 'BLOCKED_MARKET_REFERENCE',
                     reason='當月 TPEx 官方大盤無可用驗證日期；不把產業分區標成 VERIFIED')
                save_progress()
                continue
            job('tpex_sector', mo)
    except KeyboardInterrupt:
        interrupted = True
        print('手動停止：已保存的 VERIFIED 分區可續跑。')
    except BudgetReached as exc:
        print('本輪達請求／時間上限，未完成分區留待下次續跑：', exc)
    finally:
        report = save_progress()
        print('\n====== TPEx 獨立交易日曆 v2 進度 ======')
        for src, item in report['summary'].items():
            print(src, 'VERIFIED=', item['verified'],
                  'PENDING/FAILED=', item['unfinished'],
                  'LAST=', item['latest_verified'],
                  'NEXT=', item['next_pending'])
        print('TPEx 完整報表：', OUT / 'progress_tpex_latest.csv')
        print('TPEx JSON 報表：', OUT / 'progress_tpex_latest.json')
        print('既有 progress_latest.csv/json 不覆寫，以免影響先前 TWSE 驗收。')
    return report


if __name__ == '__main__':
    print('資料儲存：', OUT)
    print('TPEx 獨立日曆 v2，只請求 TPEx：', START_MONTH, '～', END_MONTH)
    report = run()
