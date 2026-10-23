"""Janus v3.8.4 official market/sector history backfill (Colab collection only).

Read-only for canonical/CURRENT.json. Writes immutable research-only source
partitions under derived/factor_inputs/official_index_backfill/v3.8.4.
No ML labels or point-in-time security-industry membership are generated.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

import requests

VERSION = 'v3.8.4'
SOURCES = {
    'twse_market': {
        'endpoint': 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST',
        'source_page': 'https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html',
        'market': 'TWSE', 'kind': 'market_index',
    },
    'twse_sector': {
        'endpoint': 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX',
        'source_page': 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX',
        'market': 'TWSE', 'kind': 'sector_index',
    },
    'tpex_market': {
        'endpoint': 'https://www.tpex.org.tw/www/zh-tw/mainboard/trading/info/daily-indices',
        'source_page': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html',
        'market': 'TPEX', 'kind': 'market_index',
    },
    'tpex_sector': {
        'endpoint': 'https://www.tpex.org.tw/www/zh-tw/mainboard/trading/statistics/indices/daily-sector',
        'source_page': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/statistics/indices/daily-sector.html',
        'market': 'TPEX', 'kind': 'sector_index',
    },
}
RIGHTS = {
    'twse_market': 'https://data.gov.tw/dataset/11755',
    'tpex_market': 'https://data.gov.tw/dataset/11391',
    'twse_sector': 'https://www.twse.com.tw/zh/products/information/history.html',
    'tpex_sector': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/statistics/indices/daily-sector.html',
}
STORAGE_STATUS = 'RESEARCH_DATA_ONLY'
SUCCEEDED = 'VERIFIED'
BLOCK_STATUSES = (401, 403, 429)
MAX_RAW_BYTES = 6_000_000


class SchemaBlocked(ValueError):
    """Official source schema/time value not proven: do not ingest."""


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes) -> str:
    """Never overwrite validated input/output; allow exact idempotent writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha_bytes(raw)
    if path.exists():
        if sha_bytes(path.read_bytes()) != digest:
            raise ValueError(f'IMMUTABLE_CONFLICT: {path}')
        return digest
    tmp = path.with_name(path.name + '.tmp')
    try:
        if tmp.exists():
            tmp.unlink()
        tmp.write_bytes(raw)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return digest


def json_bytes(data: dict | list) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)+'\n').encode('utf-8')


def _date(s) -> str:
    s = str(s).strip().replace('年','/').replace('月','/').replace('日','').replace(' ', '')
    if re.fullmatch(r'20\d{6}', s):
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    m = re.fullmatch(r'(\d{2,4})[/\-](\d{1,2})[/\-](\d{1,2})', s)
    if not m:
        raise SchemaBlocked(f'UNVERIFIED_DATE: {str(s)[:60]}')
    yr=int(m[1]); yr = yr+1911 if yr<1911 else yr
    try:
        return date(yr,int(m[2]),int(m[3])).isoformat()
    except ValueError as exc:
        raise SchemaBlocked(f'INVALID_DATE: {s}') from exc


def _month(v: str) -> str:
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', v):
        raise ValueError('BAD_MONTH_FORMAT')
    return v


def months_between(first: str, last: str) -> list[str]:
    first=_month(first);last=_month(last)
    fy,fm=map(int,first.split('-'));ly,lm=map(int,last.split('-'))
    if (fy,fm)>(ly,lm):
        raise ValueError('START_AFTER_END')
    if (ly-fy)*12+lm-fm>120:
        raise ValueError('BACKFILL_RANGE_TOO_LARGE')
    return [f'{y:04d}-{m:02d}' for y in range(fy,ly+1) for m in range(1,13)
            if (y,m)>=(fy,fm) and (y,m)<=(ly,lm)]


def _number(v) -> float:
    raw=str(v).strip().replace(',','').replace('＋','+').replace('−','-')
    if not re.fullmatch(r'\+?\d+(?:\.\d+)?', raw):
        raise SchemaBlocked(f'BAD_INDEX_NUMBER: {str(v)[:48]}')
    n=float(raw)
    if not 0<n<10**9:
        raise SchemaBlocked('NONPOSITIVE_OR_IMPLAUSIBLE_INDEX')
    return n


def _fields(rows: list, cols: list[str], *, title: str = ''):
    if not isinstance(rows,list) or not isinstance(cols,list) or not rows:
        raise SchemaBlocked('EMPTY_OR_UNKNOWN_TABLE')
    if any(not isinstance(row,(list,tuple)) or len(row)!=len(cols) for row in rows):
        raise SchemaBlocked('ROW_FIELD_LENGTH_MISMATCH')
    return [{str(k).strip():v for k,v in zip(cols,row)} for row in rows]


def _table_objects(payload: dict):
    if not isinstance(payload,dict):
        raise SchemaBlocked('OBJECT_REQUIRED')
    if payload.get('stat') and str(payload['stat']).upper() not in ('OK','SUCCESS'):
        raise SchemaBlocked('NON_OK_PROVIDER_STAT')
    tables = []
    for t in payload.get('tables', []) if isinstance(payload.get('tables'),list) else []:
        if not isinstance(t,dict):
            continue
        cols=t.get('fields') or t.get('columns') or t.get('head') or t.get('headers')
        vals=t.get('data') or t.get('rows') or t.get('aaData')
        if isinstance(cols,list) and isinstance(vals,list):
            tables.append((str(t.get('title','')), _fields(vals, cols)))
        elif isinstance(vals,list) and vals and all(isinstance(r,dict) for r in vals):
            tables.append((str(t.get('title','')), vals))
    # TWSE often uses fields1/data1, fields2/data2 etc.
    for key,cols in payload.items():
        if not re.fullmatch(r'fields\d*', key):
            continue
        suffix=key[6:]
        vals=payload.get('data'+suffix)
        if isinstance(cols,list) and isinstance(vals,list) and vals:
            title=payload.get('title'+suffix,'')
            tables.append((str(title),_fields(vals,cols)))
    for key in ('data','rows','aaData'):
        values=payload.get(key)
        if isinstance(values,list) and values and all(isinstance(r,dict) for r in values):
            tables.append((str(payload.get('title','')),values))
    return tables


def _get_col(row: dict, choices: tuple[str,...], *, contains: bool = False):
    for expected in choices:
        for col,val in row.items():
            name=re.sub(r'\s+', '',str(col))
            if name == expected or (contains and expected in name):
                return val
    return None


def _dedup(rows: list[dict], keys: tuple[str,...]) -> list[dict]:
    rows=sorted(rows,key=lambda x:tuple(str(x[k]) for k in keys))
    sig=[]
    for row in rows:
        tag=tuple(row[k] for k in keys)
        if sig and tag==sig[-1]:
            raise SchemaBlocked('DUPLICATE_OFFICIAL_KEY')
        sig.append(tag)
    return rows


def parse_twse_market(payload: dict, month: str) -> list[dict]:
    # Must check explicit date and columns, not treat current snapshot as history.
    month=_month(month)
    if not isinstance(payload,dict) or str(payload.get('stat','')).upper() != 'OK':
        raise SchemaBlocked('TWSE_MARKET_NOT_OK')
    fields=payload.get('fields');data=payload.get('data')
    if not isinstance(fields,list) or not isinstance(data,list) or not data:
        raise SchemaBlocked('TWSE_MARKET_SCHEMA')
    matches={}
    for kind,word in [('open','開盤指數'),('high','最高指數'),('low','最低指數'),('close','收盤指數'),('date','日期')]:
        hits=[i for i,f in enumerate(fields) if isinstance(f,str) and word in f]
        if len(hits)!=1:
            raise SchemaBlocked('TWSE_MARKET_COL:'+kind)
        matches[kind]=hits[0]
    out=[]
    for row in data:
        if not isinstance(row,list) or len(row)!=len(fields):
            raise SchemaBlocked('TWSE_MARKET_ROW_SHAPE')
        d=_date(row[matches['date']]);
        if not d.startswith(month+'-'):
            raise SchemaBlocked('TWSE_MARKET_WRONG_MONTH')
        r={'market':'TWSE','index_id':'TAIEX','trade_date':d,
           **{k:_number(row[matches[k]]) for k in ('open','high','low','close')}}
        if not r['low']<=r['open']<=r['high'] or not r['low']<=r['close']<=r['high']:
            raise SchemaBlocked('TWSE_MARKET_OHLC_INVALID')
        out.append(r)
    return _dedup(out,('trade_date','index_id'))


def parse_tpex_market(payload: dict, month: str) -> list[dict]:
    month=_month(month)
    tables=_table_objects(payload)
    if not tables:
        raise SchemaBlocked('TPEX_MARKET_UNKNOWN_SCHEMA')
    out=[]
    for title, rows in tables:
        for row in rows:
            d=_get_col(row,('資料日期','交易日期','日期','日　期'), contains=True)
            close=_get_col(row,('收市','收盤指數','收盤價','收盤','收市指數'))
            if d is None or close is None:
                continue
            try:
                ds=_date(d)
            except SchemaBlocked:
                # Explicit table summary is not a tradable daily row.
                continue
            if not ds.startswith(month+'-'):
                raise SchemaBlocked('TPEX_MARKET_WRONG_MONTH')
            rec={'market':'TPEX','index_id':'TPEX','trade_date':ds,'close':_number(close)}
            for k,labels in [('open',('開市','開盤指數','開盤')),('high',('最高','最高價','最高指數')),('low',('最低','最低價','最低指數'))]:
                v=_get_col(row,labels)
                if v is not None and str(v).strip() not in ('','--','－'):
                    rec[k]=_number(v)
            if all(k in rec for k in ('open','high','low')):
                if not rec['low']<=rec['open']<=rec['high'] or not rec['low']<=rec['close']<=rec['high']:
                    raise SchemaBlocked('TPEX_MARKET_OHLC_INVALID')
            out.append(rec)
    if not out:
        raise SchemaBlocked('TPEX_MARKET_NO_VERIFIED_DAILY_ROWS')
    return _dedup(out,('trade_date','index_id'))


def _is_sector(name: str) -> bool:
    name=re.sub(r'\s+','',name).replace('指數','')
    if any(s in name for s in ('報酬','槓桿','反向','成交','臺指','台指','臺灣50','特選')):
        return False
    # Exclude market/cross-market aggregate indices and unverified generic names.
    if any(s in name for s in ('加權股價','未含','寶島')):
        return False
    return ('類' in name or '業' in name) and len(name)<70


def parse_twse_sector(payload: dict, day: str) -> list[dict]:
    day=_date(day)
    if not isinstance(payload,dict):
        raise SchemaBlocked('TWSE_SECTOR_OBJECT_REQUIRED')
    pdate=payload.get('date') or payload.get('Date')
    if pdate is None or _date(pdate)!=day:
        raise SchemaBlocked('TWSE_SECTOR_DATE_NOT_VERIFIED')
    tables=_table_objects(payload)
    out=[]
    for title, rows in tables:
        for row in rows:
            name=_get_col(row,('指數','指數名稱','類股指數','分類指數'))
            close=_get_col(row,('收盤指數','收市指數','收盤'))
            if name is None or close is None or not _is_sector(str(name)):
                continue
            out.append({'market':'TWSE','index_id':re.sub(r'\s+','',str(name)),
                        'trade_date':day,'close':_number(close),'type':'sector_price_index'})
    if not out:
        raise SchemaBlocked('TWSE_SECTOR_TABLE_NOT_CONFIRMED')
    return _dedup(out,('trade_date','index_id'))


def parse_tpex_sector(payload: dict, month: str) -> list[dict]:
    month=_month(month)
    tables=_table_objects(payload)
    if not tables:
        raise SchemaBlocked('TPEX_SECTOR_UNKNOWN_SCHEMA')
    out=[]
    for title,rows in tables:
        for row in rows:
            d=_get_col(row,('日期','交易日','資料日期'),contains=True)
            if d is None:
                continue
            try:
                ds=_date(d)
            except SchemaBlocked:
                continue
            if not ds.startswith(month+'-'):
                raise SchemaBlocked('TPEX_SECTOR_WRONG_MONTH')
            # Long rows (date, sector name, close), or monthly wide sector matrix.
            name=_get_col(row,('產業分類','產業別','指數名稱','分類指數','類股指數'))
            close=_get_col(row,('收盤指數','收盤','收市','收市指數'))
            if name is not None and close is not None and _is_sector(str(name)):
                out.append({'market':'TPEX','index_id':str(name).strip(),'trade_date':ds,
                            'close':_number(close),'type':'sector_price_index'})
            else:
                for col,value in row.items():
                    if _is_sector(str(col)) and str(value).strip() not in ('','--','－','—'):
                        out.append({'market':'TPEX','index_id':re.sub(r'\s+','',str(col)),
                                    'trade_date':ds,'close':_number(value),'type':'sector_price_index'})
    if not out:
        raise SchemaBlocked('TPEX_SECTOR_NO_VERIFIED_DAILY_ROWS')
    return _dedup(out,('trade_date','index_id'))


def url_for(source: str, stamp: str) -> str:
    if source not in SOURCES:
        raise ValueError('UNKNOWN_SOURCE')
    if source == 'twse_sector':
        ymd=_date(stamp).replace('-','')
        args={'response':'json','date':ymd,'type':'ALL'}
    else:
        y,m=map(int,_month(stamp).split('-'))
        if source=='twse_market':
            args={'response':'json','date':f'{y:04d}{m:02d}01'}
        else:
            # TPEx website JSON candidate (not the .html landing page). ROC month
            # and actual schema/date must pass parsing before VERIFIED; probe live.
            args={'date':f'{y-1911}/{m:02d}/01','response':'json'}
    return SOURCES[source]['endpoint']+'?'+urlencode(args)


def partition(base: Path, source: str, stamp: str) -> Path:
    if source=='twse_sector':
        stamp=_date(stamp)
        return base/source/stamp[:7]/stamp
    return base/source/_month(stamp)


def _verify_receipt(folder: Path) -> dict | None:
    receipt=folder/'receipt.json'
    if not receipt.exists():
        return None
    r=json.loads(receipt.read_text(encoding='utf-8'))
    if r.get('status')!='VERIFIED':
        return None
    if r.get('version')!=VERSION:
        raise ValueError('VERSION_MISMATCH_EXISTING_RECEIPT')
    for filename,sha in r['checksums'].items():
        file=folder/filename
        if not file.is_file() or sha_bytes(file.read_bytes())!=sha:
            raise ValueError('EXISTING_SUCCESS_HASH_MISMATCH:'+str(file))
    return r


def _save_receipt(folder: Path, receipt: dict):
    folder.mkdir(parents=True,exist_ok=True)
    # Error receipt can be replaced by another attempt, verified is immutable.
    if (folder/'receipt.json').exists():
        previous=json.loads((folder/'receipt.json').read_text('utf-8'))
        if previous.get('status')=='VERIFIED':
            raise ValueError('ALREADY_VERIFIED_REFUSE_OVERWRITE')
    write_new(folder/('receipt-last-attempt-'+receipt['attempt_id']+'.json'),json_bytes(receipt))
    # Error status receipt is mutable pointer to preserved immutable attempts.
    path=folder/'receipt.json'; tmp=folder/'receipt.tmp'
    tmp.write_bytes(json_bytes(receipt));os.replace(tmp,path)


def write_partition(folder: Path, raw: bytes, normalized: list[dict], receipt: dict):
    """Raw first, normalized JSON always, and deterministic Parquet; no CURRENT edit."""
    import pandas as pd
    # Colab has pyarrow installed in setup cell; fail rather than mark PASS w/o parquet.
    import pyarrow  # noqa: F401
    raw_sha=sha_bytes(raw)
    raw_name='raw-'+raw_sha+'.bin'
    write_new(folder/raw_name,raw)
    normalized=_dedup(normalized,('trade_date','index_id'))
    norm_name='normalized-'+sha_bytes(json_bytes(normalized))+'.json'
    norm_sha=write_new(folder/norm_name,json_bytes(normalized))
    df=pd.DataFrame(normalized)
    buff=io.BytesIO();df.to_parquet(buff,index=False,engine='pyarrow')
    pqraw=buff.getvalue();pq_name='index-'+sha_bytes(pqraw)+'.parquet'
    pq_sha=write_new(folder/pq_name,pqraw)
    probe=pd.read_parquet(folder/pq_name,engine='pyarrow')
    if len(probe)!=len(normalized) or list(probe.columns)!=list(df.columns):
        raise ValueError('PARQUET_READBACK_MISMATCH')
    receipt.update({'status':'VERIFIED','rows':len(normalized),'first_date':normalized[0]['trade_date'],
                    'last_date':normalized[-1]['trade_date'],
                    'checksums':{raw_name:raw_sha,norm_name:norm_sha,pq_name:pq_sha},
                    'parquet':pq_name,'normalized':norm_name})
    _save_receipt(folder,receipt)


@dataclass
class RunOptions:
    start_month: str = '2025-01'
    end_month: str | None = None
    max_requests: int = 70
    max_minutes: int = 15
    interval_seconds: float = 2.5
    include_twse_sector: bool = True
    include_tpex_sector: bool = True
    timeout_seconds: int = 30

    def validate(self):
        from datetime import timedelta
        today=datetime.now(ZoneInfo('Asia/Taipei')).date()
        last = (today.replace(day=1)-timedelta(days=1)).strftime('%Y-%m')
        if self.end_month is None:self.end_month=last
        if self.end_month>last:raise ValueError('CANNOT_COLLECT_CURRENT_OR_FUTURE_MONTH')
        months_between(self.start_month,self.end_month)
        if not 1<=self.max_requests<=300:raise ValueError('BAD_REQUEST_BUDGET')
        if not 1<=self.max_minutes<=90:raise ValueError('BAD_MINUTE_BUDGET')
        if not 2<=self.interval_seconds<=30:raise ValueError('RATE_LIMIT_INTERVAL_MUST_BE_AT_LEAST_2_SECONDS')
        if not 5<=self.timeout_seconds<=60:raise ValueError('BAD_TIMEOUT')
        return self


def _job_list(months: list[str],base: Path, *, include_twse_sector:bool, include_tpex_sector:bool):
    """Monthly index prioritized; daily TWSE sector uses verified trading dates."""
    for mo in months:
        yield ('twse_market', mo)
        yield ('tpex_market', mo)
        if include_tpex_sector:
            yield ('tpex_sector',mo)
        if include_twse_sector:
            market_folder=partition(base,'twse_market',mo)
            verified=_verify_receipt(market_folder)
            if verified:
                for d in sorted(json.loads((market_folder/verified['normalized']).read_text('utf-8')),
                                key=lambda x:x['trade_date']):
                    yield ('twse_sector',d['trade_date'])


def backfill(root: str | Path, options: RunOptions, *, fetch=None, sleep=None, clock=None) -> dict:
    """Incremental official collection. The source endpoints are runtime-gated.

    Cannot declare any target complete without actual normalized parquet + hash.
    Source refusal stops that provider host, never switches identities/proxies.
    """
    o=options.validate()
    root=Path(root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError('JANUS_DATASET_ROOT_DOES_NOT_EXIST:'+str(root))
    out=(root/'derived'/'factor_inputs'/'official_index_backfill'/VERSION)
    out.mkdir(parents=True,exist_ok=True)
    months=months_between(o.start_month,o.end_month)
    fetch=fetch or requests.get;sleep=sleep or time.sleep;clock=clock or time.monotonic
    began=clock();calls=0;events=[];refused_hosts=set();invalid_sources=set();states={}
    for source,stamp in _job_list(months,out,include_twse_sector=o.include_twse_sector,
                                    include_tpex_sector=o.include_tpex_sector):
        folder=partition(out,source,stamp)
        past=_verify_receipt(folder)
        if past:
            states[source+'_SKIPPED_VERIFIED']=states.get(source+'_SKIPPED_VERIFIED',0)+1
            continue
        market=SOURCES[source]['market']
        if source in invalid_sources:
            events.append({'source':source,'period':stamp,'status':'SKIPPED_INVALID_SOURCE','rows':0,
                           'reason':'SOURCE_PROBE_FAILED_EARLIER_IN_RUN'})
            continue
        if market in refused_hosts:
            events.append({'source':source,'period':stamp,'status':'SOURCE_BLOCKED_HOST'});continue
        if calls>=o.max_requests or (clock()-began)>o.max_minutes*60:
            events.append({'source':source,'period':stamp,'status':'BUDGET_PAUSED'});break
        url=url_for(source,stamp)
        stamped=datetime.now(timezone.utc).isoformat()
        try:
            r=fetch(url,timeout=o.timeout_seconds,
                    headers={'User-Agent':'JanusFourModelResearch/1.0; research only; manual Colab'})
            calls+=1
            status=int(r.status_code)
            raw=r.content
            if len(raw)>MAX_RAW_BYTES:
                raise SchemaBlocked('SOURCE_RESPONSE_OVERSIZED')
            folder.mkdir(parents=True,exist_ok=True)
            rawsha=sha_bytes(raw)
            write_new(folder/('raw-'+rawsha+'.bin'),raw)
            receipt={'version':VERSION,'source':source,'market':market,'period':stamp,
                'url':url,'source_page':SOURCES[source]['source_page'],
                'source_rights_review_url':RIGHTS[source],
                'source_endpoint_use_authorization':'REQUIRES_INDIVIDUAL_VERIFICATION',
                'fetched_at_utc':stamped,'source_publication_time':'NOT_VERIFIED',
                'historical_industry_membership_pit':'NOT_VERIFIED',
                'http_status':status,'raw_sha256':rawsha,
                'response_content_type':str((getattr(r,'headers',{}) or {}).get('Content-Type',''))[:128],
                'publication_allowed':False,
                'canonical_current_mutated':False,'status':'UNKNOWN',
                'attempt_id':re.sub(r'[^0-9]','',stamped)[:20]+'-'+rawsha[:8]}
            if status in BLOCK_STATUSES:
                receipt['status']='SOURCE_BLOCKED'; refused_hosts.add(market)
            elif status!=200:
                receipt['status']='SOURCE_ENDPOINT_INVALID' if status in (404,410) else 'HTTP_ERROR'
                if status in (404,410):
                    invalid_sources.add(source)
                    receipt['detail']='HTTP_SOURCE_PATH_NOT_FOUND'
            else:
                try:
                    payload=json.loads(raw.decode('utf-8-sig'))
                    parse={'twse_market':parse_twse_market,'tpex_market':parse_tpex_market,
                           'twse_sector':parse_twse_sector,'tpex_sector':parse_tpex_sector}[source]
                    normalized=parse(payload,stamp)
                    if source in ('twse_market','tpex_market') and len(normalized)<10:
                        raise SchemaBlocked('MONTH_HAS_FEWER_THAN_10_DAILY_INDEX_ROWS')
                    if source=='twse_sector' and len(normalized)<5:
                        raise SchemaBlocked('FEWER_THAN_5_TWSE_SECTOR_INDICES')
                    if source=='tpex_sector':
                        if len({r['trade_date'] for r in normalized})<10:
                            raise SchemaBlocked('TPEX_SECTOR_MONTH_INCOMPLETE')
                        if len({r['index_id'] for r in normalized})<5:
                            raise SchemaBlocked('TPEX_SECTOR_TOO_FEW_INDUSTRIES')
                    write_partition(folder,raw,normalized,receipt)
                except (ValueError,KeyError,TypeError,UnicodeError) as exc:
                    peek=raw[:4096].lstrip().lower()
                    if peek.startswith((b'<!doctype html', b'<html')) or b'<html' in peek[:256]:
                        title_404=b'<title>404' in peek or b'<h1>404' in peek
                        receipt['status']='SOURCE_ENDPOINT_INVALID' if title_404 else 'SOURCE_FORMAT_UNSUPPORTED'
                        receipt['detail']='HTTP_200_HTML_404' if title_404 else 'NON_JSON_HTML_PAGE_NOT_API'
                        invalid_sources.add(source)
                    else:
                        receipt['status']='SCHEMA_BLOCKED';receipt['detail']=str(exc)[:240]
            if receipt['status']!='VERIFIED':
                _save_receipt(folder,receipt)
            events.append({'source':source,'period':stamp,'status':receipt['status'],
                           'rows':receipt.get('rows',0),'reason':receipt.get('detail','')})
        except (requests.RequestException,OSError) as exc:
            events.append({'source':source,'period':stamp,'status':'NETWORK_OR_IO_FAILED','reason':str(exc)[:160]})
        if calls < o.max_requests and o.interval_seconds:
            sleep(o.interval_seconds)
    counts={}
    for e in events:counts[e['status']]=counts.get(e['status'],0)+1
    # Existing verified partitions are materialized, not just current-run statuses.
    tally={}
    for src in SOURCES:
        total=0
        if (out/src).exists():
            for q in (out/src).rglob('receipt.json'):
                if _verify_receipt(q.parent):total+=1
        tally[src]=total
    # Completeness is partition-level, never only requests_used or old 264 batches.
    # Even a complete data capture does not certify historical sector membership/PIT.
    pending=[]
    for mo in months:
        for src in ('twse_market','tpex_market') + (('tpex_sector',) if o.include_tpex_sector else ()):
            if not _verify_receipt(partition(out,src,mo)):
                pending.append({'source':src,'period':mo})
        if o.include_twse_sector:
            receipt=_verify_receipt(partition(out,'twse_market',mo))
            if not receipt:
                pending.append({'source':'twse_sector','period':mo,'reason':'TWSE_MONTH_CALENDAR_MISSING'})
            else:
                calendar=json.loads((partition(out,'twse_market',mo)/receipt['normalized']).read_text('utf-8'))
                for day in sorted({r['trade_date'] for r in calendar}):
                    if not _verify_receipt(partition(out,'twse_sector',day)):
                        pending.append({'source':'twse_sector','period':day})
    data_complete = len(pending)==0
    summary={'version':VERSION,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'start_month':o.start_month,'end_month':o.end_month,'requests_used':calls,
        'request_budget':o.max_requests,'partition_verified_counts':tally,
        'current_run_status_counts':counts,'status':('SOURCE_DATA_VERIFIED_COMPLETE' if data_complete else 'PARTIAL_OR_PENDING'),
        'outstanding_partition_count':len(pending),'outstanding_first_20':pending[:20],
        'source_authorization':'PER_SOURCE_REVIEW_REQUIRED',
        'historical_industry_membership_pit':'NOT_VERIFIED',
        'canonical_current_unchanged':True,'publication_allowed':False,
        'reason':'僅以各月／日實際保存且雜湊通過者為 VERIFIED；未驗證來源不能宣稱全量完成。'}
    reports=root/'reports';reports.mkdir(exist_ok=True)
    # Keep distinct dated run receipt + latest convenience files.
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_new(reports/('大盤產業補收_'+runid+'.json'),json_bytes({'summary':summary,'events':events}))
    (reports/'大盤產業補收_latest.json').write_bytes(json_bytes({'summary':summary,'events':events}))
    with (reports/'大盤產業補收_latest.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        w=csv.DictWriter(handle,fieldnames=('source','period','status','rows','reason'));w.writeheader()
        for e in events:w.writerow({k:e.get(k,'') for k in w.fieldnames})
    summary['reports_dir']=str(reports)
    summary['research_data_dir']=str(out)
    return summary
