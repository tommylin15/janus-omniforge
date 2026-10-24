"""Janus Valuation 04 research-only FinMind scoped backfill. No canonical writes."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import time
from collections import defaultdict
from pathlib import Path

BASE_URL = 'https://api.finmindtrade.com/api/v4/data'
OFFICIAL = {'twse': 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
            'tpex': 'https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'}
DATASETS = {'valuation': 'TaiwanStockPER',
            'income': 'TaiwanStockFinancialStatements',
            'balance': 'TaiwanStockBalanceSheet'}
REQUIRED = ('00_summary.json', '01_普通股估值與季報逐股核對.csv',
            '02_PE_PB_30有效月末缺口逐月查核.csv',
            '03_30有效月末_股票分支短缺清單.csv',
            '04_財報無紀錄_相關性待核查.csv', 'master_sources.json')
EXPECTED_RELEASE = 'release-0bbae8d9c1ca7d8d'
EXPECTED_CURRENT_SHA = '0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd'
EXPECTED_MANIFEST_SHA = '7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542'


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()

def atomic_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.part')
    with open(tmp, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def atomic_json(path: Path, data):
    atomic_bytes(path, (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())

def records(path: Path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def atomic_csv(path: Path, rows: list[dict], fields: list[str]):
    f=io.StringIO(newline=''); writer=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    writer.writeheader(); writer.writerows(rows)
    atomic_bytes(path, f.getvalue().encode('utf-8-sig'))

def month_ord(s):
    m=re.fullmatch(r'(\d{4})-(\d\d)', str(s))
    if not m: raise ValueError('bad month: '+str(s))
    y,n=map(int,m.groups());
    if n not in range(1,13): raise ValueError('bad month')
    return y*12+n-1

def ymonth(n): return f'{n//12:04d}-{n%12+1:02d}'
def first_day(m): return str(m)+'-01'
def last_day(m):
    o=month_ord(m)
    return str(dt.date.fromisoformat(first_day(ymonth(o+1)))-dt.timedelta(days=1))

def quarter_end(q):
    if not re.fullmatch(r'\d{4}Q[1-4]', str(q)): raise ValueError('bad quarter')
    y=int(q[:4]); n=int(q[-1])*3
    return last_day(f'{y}-{n:02d}')

def listing_date(value):
    s=re.sub(r'[^0-9]', '', str(value or ''))
    if len(s)==7: s=str(int(s[:3])+1911)+s[3:]
    if len(s)!=8: return None
    try:
        d=dt.date(int(s[:4]),int(s[4:6]),int(s[6:8]));
        if d<dt.date(1990,1,1) or d>dt.date(2026,10,24):return None
        return d.isoformat()
    except ValueError: return None

def parse_official_master(market: str, raw: bytes):
    if market=='twse':
        j=json.loads(raw)
        if not isinstance(j,list): raise ValueError('TWSE master not list')
        rows=j
    else:
        rows=None
        for enc in ('utf-8-sig','cp950','big5'):
            try:
                rows=list(csv.DictReader(io.StringIO(raw.decode(enc))));break
            except UnicodeDecodeError: pass
        if rows is None: raise ValueError('TPEx master encoding')
    if not rows or not any('公司代號' in r for r in rows): raise ValueError('official roster schema')
    result={}
    for r in rows:
        symbol=str(r.get('公司代號','')).strip(); name=str(r.get('公司名稱','')).strip()
        if not re.fullmatch(r'[1-9][0-9]{3}',symbol) or symbol.startswith('91'): continue
        if re.search('存託|TDR|特別股|受益證券|基金|權證|ETF|ETN',name,re.I): continue
        ld=None
        for k,v in r.items():
            if '上市日期' in str(k) or '上櫃日期' in str(k) or str(k).strip() in ('上市日','上櫃日'):
                ld=listing_date(v)
                if ld: break
        result[(market,symbol)]={'name':name,'listing_date':ld}
    if not result: raise ValueError('official roster produced zero candidates')
    return result

def read_sources(source_dir: Path):
    source_dir=Path(source_dir).resolve()
    for n in REQUIRED:
        if not (source_dir/n).is_file(): raise FileNotFoundError(f'需要第20版盤點產物：{source_dir/n}')
    summary=json.loads((source_dir/REQUIRED[0]).read_text('utf-8'))
    src=summary.get('source',{})
    if src.get('release')!=EXPECTED_RELEASE or src.get('current_sha256')!=EXPECTED_CURRENT_SHA or src.get('manifest_sha256')!=EXPECTED_MANIFEST_SHA:
        raise ValueError('研究資料版本不一致；不對其他 release 任意補收')
    if summary.get('target_valid_monthends_per_PE_or_PB')!=30 or summary.get('requests_executed')!=0:
        raise ValueError('第20版預查欄位不符')
    data={n:records(source_dir/n) for n in REQUIRED if n.endswith('.csv')}
    meta={'source':src,'as_of_month':summary['existing_last_month'],'existing_first_month':summary['existing_first_month'],
          'input_sha256':{n:sha((source_dir/n).read_bytes()) for n in REQUIRED},
          'summary_snapshot':{k:summary.get(k) for k in ('ordinary_roster_candidates_not_PIT_verified','stock_branch_pairs_below_30')}}
    return data,meta

def select_tasks(data, meta, official: dict, *, max_lookback_months=60):
    """Fail closed on IPO-before-listing, nonpositive, and unsupported scope."""
    asof=meta['as_of_month']; first=ymonth(month_ord(asof)-max_lookback_months+1)
    src01={ (r['market'].lower().strip(),r['symbol'].strip()):r for r in data[REQUIRED[1]] }
    below={}
    for r in data[REQUIRED[3]]:
        key=(r['market'].lower().strip(),r['symbol'].strip(),r['branch'].strip().lower())
        if key[2] not in ('pe','pb'): continue
        if int(float(r['shortfall']))>0: below[key]=r
    gaps=defaultdict(set)
    for r in data[REQUIRED[2]]:
        key=(r['market'].lower().strip(),r['symbol'].strip(),r['branch'].strip().lower())
        if key in below and r.get('gap_reason') in ('MISSING_MONTH_ROW','NULL_MULTIPLE'):
            gaps[key].add(r['month'])
    financial=defaultdict(set)
    for r in data[REQUIRED[4]]:
        market,symbol=r['market'].lower().strip(),r['symbol'].strip()
        dataset={'TaiwanStockFinancialStatements':'income','TaiwanStockBalanceSheet':'balance'}.get(r.get('dataset'))
        if dataset and (market,symbol) in src01 and str(src01[(market,symbol)].get('has_any_valuation_evidence','')).lower()=='true':
            financial[(market,symbol,dataset)].update(q.strip() for q in str(r.get('missing_quarters','')).split(',') if re.fullmatch(r'\d{4}Q[1-4]',q.strip()))
    grouped=defaultdict(lambda: {'branches':set(),'months':set(),'earlier':False})
    blocked=[]
    for (market,symbol,branch),r in sorted(below.items()):
        k=(market,symbol); ordinary=official.get(k)
        base=src01.get(k)
        if not ordinary or not base or str(base.get('has_any_valuation_evidence','')).lower()!='true':
            blocked.append({'market':market,'symbol':symbol,'branch':branch,'reason':'NOT_CONFIRMED_CURRENT_ORDINARY_OR_NO_EXISTING_VALUATION'});continue
        listing=ordinary.get('listing_date')
        initial_month=base.get('first_observed_month') or meta.get('existing_first_month','')
        current_gaps=[]
        for month in gaps.get((market,symbol,branch),set()):
            if month_ord(month)<month_ord(first) or month_ord(month)>month_ord(asof): continue
            # IPO unknown: only query months at/after existing documented valuation observations.
            if listing and last_day(month)<listing: continue
            if not listing and initial_month and month_ord(month)<month_ord(initial_month):continue
            current_gaps.append(month)
        state=grouped[k]
        state['branches'].add(branch)
        state['months'].update(current_gaps)
        # Earlier-history is only eligible with authoritative current listing date available;
        # not an assertion that PIT or historical ordinary-share classification is proven.
        existing_first=meta.get('existing_first_month','2023-10')
        if r.get('may_need_pre_existing_history_before') and listing and listing<first_day(existing_first):
            prior_months=[ymonth(n) for n in range(month_ord(first),month_ord(existing_first)) if last_day(ymonth(n))>=listing]
            # Need only enough candidate months to fill shortfall + capped buffer. Latest first.
            need=min(len(prior_months),int(float(r['shortfall']))+4)
            state['months'].update(prior_months[-need:]);state['earlier']=bool(need)
        if not current_gaps and not state['earlier']:
            blocked.append({'market':market,'symbol':symbol,'branch':branch,'reason':'NO_SAFE_MISSING_OR_NULL_MONTHS_OR_PRELISTING_HISTORY'})
    tasks=[]
    for (market,symbol),r in sorted(grouped.items()):
        if not r['months']:continue
        mn=min(r['months']);mx=max(r['months'])
        tasks.append({'kind':'valuation','dataset':DATASETS['valuation'],'market':market,'symbol':symbol,
                      'start_date':first_day(mn),'end_date':last_day(mx),'target_months':sorted(r['months']),
                      'branches':sorted(r['branches']),'listing_date':official[(market,symbol)].get('listing_date'),
                      'research_only':True,'reason':'MISSING_OR_NULL_MONTH_REVIEW'})
    # Only financial quarters relevant to the observed / requested valuation study interval;
    # don't infer missing data from absent published_at; don't request IPO-prelisting quarters.
    for (market,symbol,kind),qset in sorted(financial.items()):
        if (market,symbol) not in src01 or (market,symbol) not in official:continue
        base=src01[(market,symbol)]
        listing=official[(market,symbol)].get('listing_date')
        # Without IPO date, conservative earliest observed valuation month as lower bound.
        visible=base.get('first_observed_month') or meta.get('existing_first_month','')
        lower=(min(grouped[(market,symbol)]['months']) if (market,symbol) in grouped and grouped[(market,symbol)]['months'] else visible)
        start=ymonth(max(month_ord(first),month_ord(lower)-12)) # financial warmup
        valid=[]
        for q in sorted(qset):
            d=quarter_end(q)
            if d>last_day(asof): continue
            if month_ord(d[:7])<month_ord(start):continue
            if listing and d<listing:continue
            if not listing and visible and month_ord(d[:7])<month_ord(visible):continue
            valid.append(q)
        if not valid:continue
        tasks.append({'kind':kind,'dataset':DATASETS[kind],'market':market,'symbol':symbol,
                      'start_date':quarter_end(min(valid)),'end_date':quarter_end(max(valid)),
                      'target_quarters':valid,'listing_date':listing,
                      'research_only':True,'reason':'WHOLE_STATEMENT_QUARTER_ABSENT_SOURCE_CHECK'})
    return sorted(tasks,key=lambda r:(r['symbol'],r['dataset'],r['start_date'])),blocked

def task_id(task):
    x={k:task[k] for k in ('dataset','symbol','start_date','end_date')}
    return sha(json.dumps(x,sort_keys=True).encode())[:20]

def verify_receipt(root: Path, task):
    tid=task_id(task);receipt=root/'receipts'/f'{tid}.json';raw=root/'raw'/f'{tid}.json'
    if not receipt.is_file() or not raw.is_file():return None
    try:
        r=json.loads(receipt.read_text('utf-8'))
        if r['task_id']!=tid or r['dataset']!=task['dataset'] or r['symbol']!=task['symbol'] or r['raw_sha256']!=sha(raw.read_bytes()):return None
        if r.get('status') not in ('SUCCESS','EMPTY_SOURCE_RESPONSE'):return None
        j=json.loads(raw.read_bytes())
        if str(j.get('status'))!='200' or not isinstance(j.get('data'),list):return None
        return r
    except (ValueError,KeyError):return None

def response_kind(status_code, payload):
    if status_code in (401,403) or str(payload.get('status')) in ('401','403'):return 'ACCESS_DENIED'
    if status_code in (402,429) or str(payload.get('status')) in ('402','429'):return 'QUOTA_PAUSED'
    if status_code>=500:return 'RETRYABLE_HTTP'
    if status_code!=200:return 'ACCESS_OR_HTTP_ERROR'
    if not isinstance(payload,dict) or str(payload.get('status'))!='200' or not isinstance(payload.get('data'),list):return 'SCHEMA_OR_SOURCE_ERROR'
    return 'EMPTY_SOURCE_RESPONSE' if not payload['data'] else 'SUCCESS'

def safe_finmind_response(body:bytes, task):
    try:j=json.loads(body)
    except (ValueError,UnicodeDecodeError):return 'SCHEMA_OR_SOURCE_ERROR',0
    if not isinstance(j,dict):return 'SCHEMA_OR_SOURCE_ERROR',0
    if j.get('status') not in (200,'200'):
        return response_kind(200,{'status':int(j.get('status',0)) if str(j.get('status','')).isdigit() else 0}),0
    rows=j.get('data')
    if not isinstance(rows,list):return 'SCHEMA_OR_SOURCE_ERROR',0
    for item in rows:
        if not isinstance(item,dict) or str(item.get('stock_id','')).strip()!=task['symbol']:
            return 'SCHEMA_OR_SOURCE_ERROR',0
        if task['kind']=='valuation':
            date=item.get('date')
            if not date or not str(date)[:10].startswith(('19','20')):
                return 'SCHEMA_OR_SOURCE_ERROR',0
            if not ('PER' in item and 'PBR' in item):return 'SCHEMA_OR_SOURCE_ERROR',0
        else:
            if not {'date','type','value'}.issubset(item):return 'SCHEMA_OR_SOURCE_ERROR',0
    return ('SUCCESS' if rows else 'EMPTY_SOURCE_RESPONSE'),len(rows)

def persist_response(root, task, response, status, count):
    tid=task_id(task);raw=root/'raw'/f'{tid}.json';receipt=root/'receipts'/f'{tid}.json'
    atomic_bytes(raw,response)
    r={'task_id':tid,'status':status,'dataset':task['dataset'],'kind':task['kind'],
       'market':task['market'],'symbol':task['symbol'],'start_date':task['start_date'],
       'end_date':task['end_date'],'retrieved_at_utc':utc(),'raw_sha256':sha(response),
       'raw_bytes':len(response),'rows':count,'historical_pit_verified':False,
       'publication_allowed':False,'source_authorization':'REVIEW_REQUIRED',
       'month_end_official_verified':False,'request_auth':'BEARER_HEADER_NOT_PERSISTED'}
    atomic_json(receipt,r)
    return r

def run_fetch(root, tasks, *, token, max_calls_per_run=25, sleep_seconds=8.0,
              session=None, sleeper=time.sleep, retry_once=False):
    import requests
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if not token:raise RuntimeError('FinMind Token 未設定；無法發送補收請求')
    if not (1<=max_calls_per_run<=500):raise ValueError('MAX_CALLS_PER_RUN 必須在 1..500')
    if sleep_seconds < 7.2:raise ValueError('避免超出免費額度，請將請求間隔維持 >=7.2 秒')
    ses=session or requests.Session()
    actual=0;statuses=[];quota_stopped=False;last_call=None
    for task in tasks:
        cache=verify_receipt(root,task)
        if cache:
            statuses.append({'task_id':task_id(task),'status':'CACHED_'+cache['status']});continue
        if actual>=max_calls_per_run or quota_stopped: break
        # Avoid token in query / request URL. Do not log exception with request path.
        params={'dataset':task['dataset'],'data_id':task['symbol'],
                'start_date':task['start_date'],'end_date':task['end_date']}
        headers={'Authorization':'Bearer '+token,'User-Agent':'Janus-Valuation-04-Research-Backfill/2.1'}
        if last_call is not None:sleeper(max(0,sleep_seconds-(time.monotonic()-last_call)))
        attempts=2 if retry_once else 1
        for attempt in range(attempts):
            if actual>=max_calls_per_run:break
            last_call=time.monotonic();actual+=1
            try:
                r=ses.get(BASE_URL,params=params,headers=headers,timeout=(12,60))
                payload=r.content
                try: parsed=json.loads(payload)
                except (ValueError,UnicodeDecodeError):parsed={}
                if isinstance(parsed,dict) and str(parsed.get('status')) in ('402','429'):
                    kind='QUOTA_PAUSED'
                else:
                    kind=response_kind(r.status_code, parsed if isinstance(parsed,dict) else {})
                if kind in ('SUCCESS','EMPTY_SOURCE_RESPONSE'):
                    kind,n=safe_finmind_response(payload,task)
                    if kind in ('SUCCESS','EMPTY_SOURCE_RESPONSE'):
                        persist_response(root,task,payload,kind,n)
                if kind=='QUOTA_PAUSED':quota_stopped=True
            except requests.RequestException:
                kind='RETRYABLE_NETWORK' # never print potentially token-bearing URL
            statuses.append({'task_id':task_id(task),'dataset':task['dataset'],
                             'symbol':task['symbol'],'status':kind,'attempt':attempt+1})
            atomic_json(root/'last_progress.json',{'updated_at':utc(),'http_calls_this_run':actual,
                      'last_symbol':task['symbol'],'last_dataset':task['dataset'],
                      'last_status':kind,'quota_paused':quota_stopped,
                      'publication_allowed':False})
            if kind not in ('RETRYABLE_HTTP','RETRYABLE_NETWORK') or attempt==attempts-1:break
            sleeper(max(15.0,sleep_seconds));last_call=time.monotonic()
        if quota_stopped or actual>=max_calls_per_run: break
    return {'actual_http_calls_this_run':actual,'cached_verified':sum(1 for s in statuses if s['status'].startswith('CACHED_')),
            'success_or_empty_this_run':sum(1 for s in statuses if s['status'] in ('SUCCESS','EMPTY_SOURCE_RESPONSE')),
            'quota_paused':quota_stopped,'attempts':statuses[-60:]}

def generate_reports(root, tasks, base_data, *, run_summary=None):
    receipts=[verify_receipt(Path(root),t) for t in tasks]
    statuses=[{'task_id':task_id(t),'symbol':t['symbol'],'dataset':t['dataset'],
              'kind':t['kind'],'start_date':t['start_date'],'end_date':t['end_date'],
              'status':('FINISHED_'+r['status'] if r else 'PENDING_OR_ERROR'),
              'rows':(r.get('rows',0) if r else 0)} for t,r in zip(tasks,receipts)]
    atomic_csv(root/'01_task_status.csv',statuses,['task_id','symbol','dataset','kind','start_date','end_date','status','rows'])
    # Only candidate positive PE/PB, not verified true exchange month-end or safe-to-train PIT.
    base={(r['market'].lower().strip(),r['symbol'].strip()):r for r in base_data[REQUIRED[1]]}
    more=defaultdict(lambda:{'pe':set(),'pb':set()})
    allowed={(r['market'].lower().strip(),r['symbol'].strip(),r['branch'].strip().lower(),r['month'])
      for r in base_data[REQUIRED[2]] if r.get('gap_reason') in ('MISSING_MONTH_ROW','NULL_MULTIPLE')}
    val_rows=[];financial_rows=[]
    for t,r in zip(tasks,receipts):
        if not r or r.get('status')!='SUCCESS':continue
        blob=json.loads((root/'raw'/(task_id(t)+'.json')).read_bytes())['data']
        if t['kind']=='valuation':
            by_month=defaultdict(list)
            for x in blob:
                date=str(x.get('date',''))[:10]
                try:d=dt.date.fromisoformat(date)
                except ValueError: continue
                if not (t['start_date']<=date<=t['end_date']):continue
                if t.get('listing_date') and date<t['listing_date']:continue
                by_month[date[:7]].append((date,x))
            for month,pairs in sorted(by_month.items()):
                # use last actual observation from this HTTP response, no synthetic monthends
                date,x=max(pairs,key=lambda y:y[0])
                for branch,col in (('pe','PER'),('pb','PBR')):
                    v=x.get(col)
                    try:v=float(v)
                    except (ValueError,TypeError):v=math.nan
                    valid=math.isfinite(v) and v>0
                    candidate=(t['market'],t['symbol'],branch,month) in allowed or (month in t.get('target_months',[]) and month<base[(t['market'],t['symbol'])].get('first_observed_month','9999-99'))
                    if valid and candidate:more[(t['market'],t['symbol'])][branch].add(month)
                    val_rows.append({'market':t['market'],'symbol':t['symbol'],'month':month,'observed_date':date,
                                     'branch':branch,'multiple':v if math.isfinite(v) else '',
                                     'positive':valid,'candidate_month':candidate,'source_raw_sha256':r['raw_sha256'],
                                     'status':'RESEARCH_CANDIDATE_PIT_AND_MONTHEND_UNVERIFIED'})
        else:
            per_q=defaultdict(int)
            for row in blob:
                date=str(row.get('date',''))[:10]
                if date:
                    per_q[date[:7]]+=1
            for q in t['target_quarters']:
                financial_rows.append({'market':t['market'],'symbol':t['symbol'],'dataset':t['dataset'],
                                       'fiscal_quarter':q,'source_rows_with_same_quarter_end':per_q.get(quarter_end(q)[:7],0),
                                       'status':'RAW_RESPONSE_ONLY_SCOPE_UNIT_PIT_UNVERIFIED','source_raw_sha256':r['raw_sha256']})
    atomic_csv(root/'02_valuation_recovered_month_candidates.csv',val_rows,
       ['market','symbol','month','observed_date','branch','multiple','positive','candidate_month','source_raw_sha256','status'])
    atomic_csv(root/'03_financial_source_check.csv',financial_rows,
       ['market','symbol','dataset','fiscal_quarter','source_rows_with_same_quarter_end','status','source_raw_sha256'])
    scores=[]
    for key,v in sorted(base.items()):
        for branch in ('pe','pb'):
            n=int(float(v.get(f'{branch}_positive_months') or 0));additional=len(more[key][branch]);
            scores.append({'market':key[0],'symbol':key[1],'branch':branch,'existing_positive_months':n,
                           'additional_positive_month_candidates':additional,
                           'possible_positive_months_not_pit_verified':n+additional,
                           'precheck_30_positive_months':n+additional>=30,
                           'model_ready':False,'publication_allowed':False})
    atomic_csv(root/'04_postfetch_positive_coverage_precheck.csv',scores,
       ['market','symbol','branch','existing_positive_months','additional_positive_month_candidates',
        'possible_positive_months_not_pit_verified','precheck_30_positive_months','model_ready','publication_allowed'])
    summary={'status':'FETCH_ATTEMPTED_NOT_MODEL_READY','tasks_total':len(tasks),
      'tasks_success':sum(1 for r in receipts if r and r.get('status')=='SUCCESS'),
      'tasks_empty':sum(1 for r in receipts if r and r.get('status')=='EMPTY_SOURCE_RESPONSE'),
      'tasks_pending':sum(1 for r in receipts if not r),
      'candidate_positive_months_added':sum(len(x['pe'])+len(x['pb']) for x in more.values()),
      'run_stats':run_summary or {},'publication_allowed':False,
      'limitations':['FinMind daily last observed is not certified exchange month-end','positive multiples do not certify PIT, units or financial comparability','historical source versions are not reconstructed'],
      'updated_utc':utc()}
    atomic_json(root/'00_run_summary.json',summary)
    return summary
