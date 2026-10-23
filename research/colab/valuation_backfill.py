"""Janus Valuation research-only, bounded, resumable source intake.

Never changes canonical/CURRENT.json, starts training, or publishes. The v1
candidate format is deliberately separate from canonical v3.1.0.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import socket
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DEFAULT = '/content/drive/MyDrive/給ai專用/janusChatGPT'
SCHEMA = 'valuation-research-v1'
SOURCE_URL = 'https://api.finmindtrade.com/api/v4/data'
SOURCE_DOC = 'https://finmind.github.io/tutor/TaiwanMarket/Fundamental/'
FINMIND = {'income':'TaiwanStockFinancialStatements',
           'balance':'TaiwanStockBalanceSheet',
           'cashflow':'TaiwanStockCashFlowsStatement',
           'revenue':'TaiwanStockMonthRevenue',
           'dividend':'TaiwanStockDividend', 'valuation':'TaiwanStockPER'}
STATEMENT = {'income','balance','cashflow'}
REQUIRED = {
 'income':['revenue','gross_profit','operating_profit','pretax_income','net_income','parent_net_income','basic_eps','diluted_eps'],
 'balance':['total_assets','total_liabilities','total_equity','parent_equity','cash_and_equivalents','current_assets','current_liabilities'],
 'cashflow':['cfo'], 'revenue':['monthly_revenue'],
 'valuation':['pe','pb'], 'corporate_actions':[], 'industry_membership':[]}
OPTIONAL = {
 'income':['interest_expense','rd_expense'],
 'balance':['short_term_debt','long_term_debt','current_portion_debt','bonds_payable','lease_liabilities','intangibles','goodwill','receivables','inventory'],
 'cashflow':['capex','depreciation','amortization'], 'revenue':['reported_yoy'],
 'valuation':['dividend_yield']}
# Only strong English taxonomy matches automatically; all other raw labels audited.
MAPPING = {
 'Revenue':'revenue','GrossProfit':'gross_profit','OperatingIncome':'operating_profit',
 'IncomeBeforeTax':'pretax_income','IncomeAfterTaxes':'net_income',
 'IncomeAttributableToOwnersOfParent':'parent_net_income',
 'Assets':'total_assets','Liabilities':'total_liabilities','Equity':'total_equity',
 'EquityAttributableToOwnersOfParent':'parent_equity',
 'CashAndCashEquivalents':'cash_and_equivalents',
 'CurrentAssets':'current_assets','CurrentLiabilities':'current_liabilities',
 'NetCashFlowsFromUsedInOperatingActivities':'cfo',
 'CostOfGoodsSold':'cost_of_goods_sold', 'EPS':'basic_eps',
 'ResearchAndDevelopmentExpenses':'rd_expense',
 'Goodwill':'goodwill','IntangibleAssets':'intangibles',
 'Inventories':'inventory','AccountsReceivableNet':'receivables'}
# No claim that these mappings identify accounting scope, unit, or revisions.
TASK_STATES = ('PENDING','RUNNING','SUCCESS','EMPTY_CONFIRMED','NOT_YET_AVAILABLE',
               'RETRYABLE_ERROR','ACCESS_DENIED','SCHEMA_ERROR','BUDGET_PAUSED')
REPORTS = ('inventory.csv','gap_plan.csv','collection_progress.csv',
           'coverage_by_market_period.csv','field_coverage.csv','financial_mapping_audit.csv',
           'source_conflicts.csv','quality_issues.csv','factor_readiness.csv')
FACTORS = {
 'gross_margin_ttm':('gross_profit','revenue'),
 'operating_margin_ttm':('operating_profit','revenue'),
 'net_margin_ttm':('net_income','revenue'),
 'roa_ttm':('net_income','average_total_assets'),
 'roe_ttm':('parent_net_income','average_parent_equity'),
 'asset_turnover_ttm':('revenue','average_total_assets'),
 'debt_ratio':('total_liabilities','total_assets'),
 'cash_to_assets':('cash_and_equivalents','total_assets'),
 'cfo_to_assets':('cfo','average_total_assets'),
 'accruals_to_assets':('net_income','cfo','average_total_assets'),
 'revenue_yoy_1m':('monthly_revenue',), 'revenue_yoy_3m':('monthly_revenue',),
 'revenue_yoy_12m':('monthly_revenue',),
 'revenue_growth_acceleration':('revenue_yoy_3m','revenue_yoy_12m'),
 'financial_age_days':('published_at',),
 'roe_change_yoy':('roe_ttm',),
 'operating_margin_change_yoy':('operating_margin_ttm',),
 'earnings_or_margin_volatility_8q':('operating_profit',),
 'log_total_assets':('total_assets',)}


# The v2 label catalog is dataset-scoped; semantic matches do not certify units/PIT.
def standard_item(dataset: str, raw: str) -> str:
    from valuation_mapping_p0p1 import mapping_label
    return mapping_label(dataset, raw)[0]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()


def checked_root(root: str | Path) -> Path:
    path=Path(root).expanduser().resolve()
    if path.name != 'janusChatGPT' or not path.is_dir():
        raise FileNotFoundError('ROOT 必須是已存在的 janusChatGPT 白名單根目錄：'+str(path))
    if not (path/'資料源'/'JanusDataset_v3_202610'/'canonical'/'CURRENT.json').is_file():
        raise FileNotFoundError('既有 canonical/CURRENT.json 不存在；不可自行建立第二套資料')
    return path


def dataset_root(root: Path) -> Path:
    return root/'資料源'/'JanusDataset_v3_202610'


def checked_current(root: Path) -> tuple[Path,dict,str]:
    base=dataset_root(root)
    current=base/'canonical'/'CURRENT.json'
    b=current.read_bytes(); pointer=json.loads(b)
    if pointer.get('format')!='parquet' or not re.fullmatch(r'release-[0-9a-zA-Z_-]+',str(pointer.get('release',''))):
        raise ValueError('CURRENT_POINTER_SCHEMA')
    rel=base/'canonical'/pointer['release']
    manifest=rel/'manifest.json'
    if not manifest.is_file(): raise FileNotFoundError(manifest)
    m=json.loads(manifest.read_text('utf-8'))
    if not isinstance(m.get('files'),dict): raise ValueError('MANIFEST_FILES_MISSING')
    # Fail closed on an invalid relative path or missing/mismatched raw inputs.
    for filename,meta in m['files'].items():
        p=(rel/filename).resolve()
        if not p.is_relative_to(rel.resolve()) or not p.is_file():
            raise ValueError('INVALID_REFERENCED_FILE:'+filename)
        if digest(p.read_bytes())!=meta.get('sha256'):
            raise ValueError('INPUT_SHA_MISMATCH:'+filename)
    return rel,m,digest(b)


def csv_write(path:Path, rows:list[dict], cols:list[str]|None=None)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    columns=cols or sorted(set().union(*(r.keys() for r in rows))) if rows else (cols or ['status'])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)


def json_write(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.part')
    temp.write_bytes(canonical_json(value));temp.replace(path)


def get_rows(release:Path, manifest:dict)->list[dict]:
    try: import pandas as pd
    except ImportError as exc: raise RuntimeError('pip install pandas pyarrow') from exc
    result=[]
    for filename,meta in sorted(manifest['files'].items()):
        if not filename.endswith('.parquet'):continue
        dataset=filename.split('/')[0]
        if dataset not in ('financials','revenue','valuation','ohlcv','corporate_actions'):continue
        p=release/filename
        try: frame=pd.read_parquet(p)
        except Exception as exc: raise ValueError('PARQUET_READ_FAILED:'+filename) from exc
        if len(frame)!=meta.get('rows'):raise ValueError('PARQUET_ROWCOUNT_MISMATCH:'+filename)
        for r in frame.to_dict('records'):
            # Keep original payload fields for mapping audit, never infer announcement date.
            v={k:(None if (not isinstance(x,(list,dict)) and pd.isna(x)) else x)
               for k,x in r.items()}
            v['_dataset']=dataset;v['_file']=filename;result.append(v)
    return result


def infer_period(row:dict)->str:
    return str(row.get('fiscal_quarter') or row.get('fiscal_month') or row.get('trade_date') or '')[:10]


def classify_existing(row:dict)->tuple[str,str]:
    dataset=str(row.get('dataset') or row.get('_dataset') or '')
    raw=str(row.get('item') or row.get('item_raw') or '')
    if row.get('_dataset')!='financials':
        keys={'revenue':['revenue','monthly_revenue'], 'valuation':['pe','pb'], 'ohlcv':['close']}
        measure=next((row.get(k) for k in keys.get(row.get('_dataset'),[]) if row.get(k) is not None), None)
        if measure is None and row.get('_dataset') in keys:
            return ('MAPPING_REQUIRED','VALUE_MISSING_OR_UNIDENTIFIED')
        return ('EXISTING_USABLE','PRESENT_RAW_NOT_PIT_VERIFIED')
    from valuation_mapping_p0p1 import disposition
    return disposition(mapped=bool(standard_item(dataset,raw)),value=row.get('value'),
       unit_basis=row.get('unit_basis'),period_basis=row.get('period_basis'),
       published_at=row.get('published_at'),statement_scope=row.get('statement_scope'))


def inventory(root:Path, run:Path, *, rows:list[dict]|None=None)->dict:
    release,m,current_sha=checked_current(root)
    rows=get_rows(release,m) if rows is None else rows
    inv=[]; idx={}
    for r in rows:
        dataset=str(r.get('dataset') or r.get('_dataset') or '')
        status,reason=classify_existing(r)
        raw=str(r.get('item') or r.get('item_raw') or '')
        item=standard_item(dataset,raw)
        v={'market':str(r.get('market','')),'symbol':str(r.get('symbol','')),
           'dataset':dataset,'period':infer_period(r), 'item_raw':raw,
           'item_standard':item,'statement_scope':r.get('statement_scope') or 'UNKNOWN',
           'period_basis':r.get('period_basis') or 'UNKNOWN',
           'unit':r.get('unit_basis') or 'UNKNOWN', 'currency':r.get('currency') or 'UNKNOWN',
           'published_at':r.get('published_at'),
           'first_observed_at':r.get('observed_at'),
           'source_id':r.get('source_id') or 'UNKNOWN',
           'revision_id':r.get('revision_id') or 'UNKNOWN',
           'file':r['_file'],'classification':status,'reason':reason}
        inv.append(v)
        idx.setdefault((v['market'],v['symbol'],dataset,v['period'],item),[]).append(v)
    csv_write(run/'inventory.csv',inv)
    old_snapshot=run/'input_snapshot.json'
    if old_snapshot.exists():
        previous=json.loads(old_snapshot.read_text('utf-8'))
        if previous.get('current_sha256')!=current_sha or previous.get('release')!=release.name:
            raise ValueError('INPUT_RELEASE_CHANGED_CREATE_NEW_RUN')
    json_write(old_snapshot,{'current_sha256':current_sha,
      'release':release.name,'manifest_sha256':digest((release/'manifest.json').read_bytes()),
      'referenced_files':len(m['files']),'raw_rows':len(rows), 'publication_allowed':False})
    return {'inventory':inv,'by_key':idx,'rows':rows,'release':release,'manifest':m}


def quarters(start:str,end:str)->list[str]:
    a=date.fromisoformat(start);b=date.fromisoformat(end)
    out=[]
    for y in range(a.year,b.year+1):
        for q in range(1,5):
            e=date(y,3*q+1,1)-timedelta(days=1) if q<4 else date(y,12,31)
            if a<=e<=b:out.append(f'{y}Q{q}')
    return out


def months(start:str,end:str)->list[str]:
    a=date.fromisoformat(start);b=date.fromisoformat(end);out=[]
    for y in range(a.year,b.year+1):
        for m in range(1,13):
            end_m=date(y+1,1,1)-timedelta(days=1) if m==12 else date(y,m+1,1)-timedelta(days=1)
            if a<=end_m<=b:out.append(f'{y}-{m:02d}')
    return out


def plan(root:Path,run:Path,records:dict,*, symbols:list[str],start:str,end:str,
         markets:dict[str,str],as_of:str|None=None)->list[dict]:
    # Exact bounded symbol allowlist, never default the entire market.
    if not symbols:raise ValueError('必須明確設定股票母體')
    if not all(re.fullmatch(r'[1-9]\d{3}',s) for s in symbols):raise ValueError('NOT_ORDINARY_STOCK_ID')
    if set(symbols)-set(markets):raise ValueError('SYMBOL_MARKET_UNKNOWN')
    if any(markets[s] not in ('twse','tpex') for s in symbols):raise ValueError('MARKET_INVALID')
    a=date.fromisoformat(start);b=date.fromisoformat(end)
    if a>b or (b-a).days>1827:raise ValueError('INVALID_RANGE_OR_GT_5_YEARS')
    today=date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date()
    period_spec={k:(quarters(start,end) if k in STATEMENT else months(start,end))
                 for k in ('income','balance','cashflow','revenue','valuation')}
    tasks=[];gaps=[]
    for s in sorted(set(symbols)):
        market=markets[s]
        for d,periods in period_spec.items():
            for period in periods:
                try:
                    p_end=(date(int(period[:4]),int(period[-1])*3+1,1)-timedelta(days=1)
                           if d in STATEMENT and period[-1]!='4'
                           else (date(int(period[:4]),12,31) if d in STATEMENT else
                           date(int(period[:4])+(period[-2:]=='12'),
                                int(period[-2:])%12+1,1)-timedelta(days=1)))
                except ValueError as exc: raise ValueError('PERIOD_BAD') from exc
                # Conservative planning hold. These lags are NOT published_at evidence.
                hold_days=60 if d in STATEMENT else 15 if d=='revenue' else 0
                not_due=p_end+timedelta(days=hold_days)>today
                needed=REQUIRED.get(d,[])
                statuses=[]
                for item in needed:
                    obs=records['by_key'].get((market,s,d,period,item),[])
                    klass=('EXISTING_USABLE' if any(v['classification'] in ('DERIVABLE','EXISTING_USABLE') for v in obs)
                           else 'MAPPING_REQUIRED' if obs else 'NOT_YET_AVAILABLE' if not_due else 'FETCH_REQUIRED')
                    gaps.append({'market':market,'symbol':s,'dataset':d,'period':period,
                                 'item_standard':item,'classification':klass,
                                 'source':'CURRENT' if obs else 'FinMind candidate',
                                 'reason':'PIT_NOT_VERIFIED' if obs else 'PENDING_PERIOD' if not_due else 'RAW_MISSING'})
                    statuses.append(klass)
                fetchable=not not_due and 'FETCH_REQUIRED' in statuses
                if fetchable:
                    identity={'source':'finmind','dataset':d,'market':market,'symbol':s,
                              'start':p_end.isoformat(),'end':p_end.isoformat()}
                    tasks.append(dict(identity,task_id=digest(canonical_json(identity))[:24],status='PENDING',estimated_requests=1))
    csv_write(run/'gap_plan.csv',gaps)
    json_write(run/'request_plan.json',{'tasks':tasks,'estimated_http_requests':len(tasks),
      'symbols':sorted(set(symbols)),'start':start,'end':end,'publication_allowed':False,
      'snapshot':json.loads((run/'input_snapshot.json').read_text('utf-8'))})
    return tasks


class SourceError(RuntimeError):
    def __init__(self,state,detail=''):
        super().__init__(state+(':'+detail if detail else ''));self.state=state


def redact(message:str,token:str|None=None)->str:
    text=str(message)
    if token:text=text.replace(token,'[REDACTED]')
    return re.sub(r'(?i)(bearer\s+)\S+',r'\1[REDACTED]',text)


def fetch_finmind(session,task:dict,token:str|None,*,max_retries:int=2,sleeper=time.sleep,on_request=None)->dict:
    dataset=FINMIND.get(task['dataset'])
    if not dataset:raise SourceError('SCHEMA_ERROR','UNSUPPORTED_DATASET')
    params={'dataset':dataset,'data_id':task['symbol'],
            'start_date':task['start'],'end_date':task['end']}
    headers={'User-Agent':'JanusValuationResearch/1.0'}
    if token:headers['Authorization']='Bearer '+token
    for attempt in range(max_retries+1):
        try:
            if on_request:on_request()
            response=session.get(SOURCE_URL,headers=headers,params=params,timeout=25)
            code=response.status_code
            if code in (401,403):raise SourceError('ACCESS_DENIED','HTTP_'+str(code))
            if code==429 or code in (500,502,503,504):
                if attempt==max_retries:raise SourceError('RETRYABLE_ERROR','HTTP_'+str(code))
                retry_after=response.headers.get('Retry-After','')
                try: wait=min(90,max(1,int(retry_after)))
                except(ValueError,TypeError):
                    from email.utils import parsedate_to_datetime
                    try: wait=min(90,max(1,int((parsedate_to_datetime(retry_after)-datetime.now(timezone.utc)).total_seconds())))
                    except (ValueError,TypeError,OverflowError):wait=min(30,2**attempt+1)
                sleeper(wait);continue
            if code!=200:raise SourceError('SCHEMA_ERROR','HTTP_'+str(code))
            try:payload=response.json()
            except ValueError as exc:raise SourceError('SCHEMA_ERROR','JSON_INVALID') from exc
            if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
                raise SourceError('SCHEMA_ERROR','DATA_SCHEMA_CHANGED')
            if payload.get('status') not in (None,200,200.0):
                msg=str(payload.get('msg',''))
                raise SourceError('ACCESS_DENIED' if 'permission' in msg.lower() else 'SCHEMA_ERROR','SOURCE_STATUS')
            data=payload['data'];needed={'date','stock_id'}
            if task['dataset'] in STATEMENT:needed|={'type','value'}
            if data and any(not isinstance(r,dict) or not needed.issubset(r) for r in data):
                raise SourceError('SCHEMA_ERROR','ROW_SCHEMA_CHANGED')
            body=response.content
            return {'rows':data,'raw_sha256':digest(body),'raw':body,
                    'source_id':'FinMind:'+dataset,'source_url':SOURCE_URL,
                    'fetched_at':now(),'status':'SUCCESS' if data else 'EMPTY_CONFIRMED',
                    'schema_status':'SCHEMA_COMPATIBLE','start_date':task['start'],'end_date':task['end']}
        except SourceError:raise
        except Exception as exc:
            if attempt==max_retries:raise SourceError('RETRYABLE_ERROR','NETWORK_TRANSIENT') from None
            sleeper(min(30,2**attempt+1))
    raise AssertionError('unreachable')


def valid_checkpoint(folder:Path,task:dict)->bool:
    marker=folder/'complete.json';raw=folder/'raw.json';rows=folder/'rows.json';response=folder/'response.bin'
    if not all(p.is_file() for p in (marker,raw,rows,response)):return False
    try:
        m=json.loads(marker.read_text('utf-8'))
        if m.get('task_id')!=task['task_id']:return False
        for name,p in (('raw.json',raw),('rows.json',rows),('response.bin',response)):
            if digest(p.read_bytes())!=m['files'][name]['sha256']:return False
        payload=json.loads(raw.read_text('utf-8'));parsed=json.loads(rows.read_text('utf-8'))
        return (isinstance(parsed,list) and payload.get('task_id')==task['task_id']
                and digest(response.read_bytes())==payload.get('raw_sha256')
                and len(parsed)==m['row_count'] and all(str(x.get('stock_id'))==task['symbol'] for x in parsed))
    except (OSError,ValueError,KeyError,TypeError):return False


def writer_lock(folder:Path,run_id:str,*,lease_seconds:int=7200)->Path:
    folder.mkdir(parents=True,exist_ok=True)
    lock=folder/'writer.lock'
    identity={'run_id':run_id,'writer':socket.gethostname()+':'+str(os.getpid()),'created_at':now(),
              'expires_epoch':time.time()+lease_seconds}
    try:
        fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        # Even expired lock is not auto-stolen; explicit operator review is required.
        raise RuntimeError('WRITER_LOCK_EXISTS_REVIEW_MANUALLY') from None
    with os.fdopen(fd,'w') as f:json.dump(identity,f)
    return lock


def finish_task(folder:Path,task:dict,response:dict)->None:
    if folder.exists() and (folder/'complete.json').is_file():
        if valid_checkpoint(folder,task):return
        raise ValueError('INCOMPLETE_OR_CORRUPT_EXISTING_CHECKPOINT')
    folder.mkdir(parents=True,exist_ok=True)
    raw=canonical_json({'task_id':task['task_id'],'raw_sha256':response['raw_sha256'],
                        'source_id':response['source_id'],'source_url':response['source_url'],
                        'fetched_at':response['fetched_at'],'raw_utf8':response['raw'].decode('utf-8','replace')})
    rows=canonical_json(response['rows'])
    for name,data in [('raw.json',raw),('rows.json',rows),('response.bin',response['raw'])]:
        temp=folder/(name+'.part');temp.write_bytes(data);temp.replace(folder/name)
    marker={'task_id':task['task_id'],'status':response['status'],'row_count':len(response['rows']),
            'source_id':response['source_id'],'fetched_at':response['fetched_at'],
            'files':{name:{'sha256':digest(data),'bytes':len(data)} for name,data in [('raw.json',raw),('rows.json',rows),('response.bin',response['raw'])]}}
    json_write(folder/'complete.json',marker)
    if not valid_checkpoint(folder,task):raise ValueError('COMMIT_READBACK_FAILED')


def fetch(root:Path,run:Path,*,run_fetch:bool=False,dry_run:bool=True,max_requests:int=3,
          max_symbols:int=3,max_runtime_minutes:int=5,max_retries:int=2,request_interval:float=1.0,
          token:str|None=None,session=None)->dict:
    req=json.loads((run/'request_plan.json').read_text('utf-8'))
    tasks=req['tasks'];state=[];count=0
    if dry_run or not run_fetch:
        state=[dict(t,status='PENDING',reason='FETCH_DISABLED') for t in tasks]
        csv_write(run/'collection_progress.csv',state)
        return {'status':'DRY_RUN','actual_requests':0,'remaining':len(tasks)}
    import requests
    session=session or requests.Session()
    lock=writer_lock(run,run.name)
    started=time.monotonic();processed=set();blocked=set();budget_symbols=set();actual_http=[0]
    def inc_http():
        if actual_http[0]>=max_requests:raise SourceError('BUDGET_PAUSED','HTTP_REQUEST_LIMIT')
        actual_http[0]+=1
    try:
        for t in tasks:
            folder=run/'tasks'/t['task_id']
            if valid_checkpoint(folder,t):
                saved_status=json.loads((folder/'complete.json').read_text('utf-8'))['status']
                state.append(dict(t,status=saved_status,reason='CHECKPOINT_VERIFIED'));processed.add(t['task_id']);continue
            if t['source'] in blocked:
                state.append(dict(t,status='ACCESS_DENIED',reason='SOURCE_BLOCKED'));continue
            if (actual_http[0]>=max_requests or time.monotonic()-started>=max_runtime_minutes*60 or
                (t['symbol'] not in budget_symbols and len(budget_symbols)>=max_symbols)):
                state.append(dict(t,status='BUDGET_PAUSED',reason='LIMIT_REACHED'));continue
            budget_symbols.add(t['symbol']);count+=1
            try:
                r=fetch_finmind(session,t,token,max_retries=max_retries,on_request=inc_http)
                finish_task(folder,t,r)
                state.append(dict(t,status=r['status'],reason='READBACK_OK'))
            except SourceError as exc:
                state.append(dict(t,status=exc.state,reason=redact(str(exc),token)))
                if exc.state=='ACCESS_DENIED':blocked.add(t['source'])
            if request_interval>0:time.sleep(request_interval)
    finally:
        lock.unlink(missing_ok=True)
        csv_write(run/'collection_progress.csv',state)
        json_write(run/'fetch_receipt.json',{'actual_task_attempts':count,
          'actual_http_requests':actual_http[0],
          'completed':sum(s['status']=='SUCCESS' for s in state),
          'remaining':sum(s['status'] not in ('SUCCESS','EMPTY_CONFIRMED') for s in state),
          'publication_allowed':False})
    return {'status':'BOUNDED_STOP','actual_task_attempts':count,'actual_http_requests':actual_http[0],'remaining':sum(s['status'] not in ('SUCCESS','EMPTY_CONFIRMED') for s in state)}


def unit_to_base(value,unit_raw,unit_multiplier=None):
    """Convert only documented units; never infer multiplier from magnitude."""
    x=numeric(value)
    if x is None:return None,'VALUE_MISSING'
    multipliers={'TWD':1,'TWD_THOUSAND':1000,'TWD_MILLION':1000000,'PERCENT':0.01,'DECIMAL':1}
    if unit_raw not in multipliers:return None,'UNIT_UNKNOWN'
    if unit_multiplier is not None and unit_multiplier!=multipliers[unit_raw]:
        return None,'UNIT_CONFLICT'
    return x*multipliers[unit_raw],'OK'


def numeric(raw)->float|None:
    try:
        x=float(str(raw).replace(',',''))
        return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None


def normalize(run:Path)->list[dict]:
    req=json.loads((run/'request_plan.json').read_text('utf-8'))
    observations=[];audit=[]
    for task in req['tasks']:
        folder=run/'tasks'/task['task_id']
        if not valid_checkpoint(folder,task):continue
        marker=json.loads((folder/'complete.json').read_text('utf-8'))
        source=marker['source_id']
        for raw in json.loads((folder/'rows.json').read_text('utf-8')):
            item_raw=str(raw.get('type') or raw.get('origin_name') or '')
            item_std=standard_item(task['dataset'],str(raw.get('type') or ''))
            endpoint=str(raw.get('date',''))
            # FinMind `date` is financial period, never a publication timestamp.
            scope='UNKNOWN';basis='UNKNOWN';unit='UNKNOWN'
            out={'market':task['market'],'symbol':task['symbol'],'dataset':task['dataset'],
                 'statement_type':task['dataset'],'statement_scope':scope,
                 'fiscal_period_start':None,'fiscal_period_end':endpoint,
                 'fiscal_year':int(endpoint[:4]) if re.match(r'^\d{4}-',endpoint) else None,
                 'fiscal_quarter':None,'period_basis':basis,
                 'item_raw':item_raw,'item_standard':item_std,'value_raw':raw.get('value'),
                 'value_numeric':numeric(raw.get('value')),
                 'currency':'UNKNOWN','unit_raw':unit,'unit_multiplier':None,
                 'published_at':None,'published_at_precision':'UNKNOWN',
                 'first_observed_at':None,'fetched_at':marker['fetched_at'],
                 'revision_id':None,'supersedes_id':None,'source_id':source,
                 'source_url':SOURCE_URL,'source_sha256':json.loads((folder/'raw.json').read_text('utf-8'))['raw_sha256'],
                 'mapping_version':'financial-mapping-v1','pit_status':'PIT_UNVERIFIED',
                 'quality_status':'MAPPING_REQUIRED' if item_std else 'UNMAPPED_RAW_ITEM'}
            observations.append(out)
            audit.append({'source_id':source,'raw_name':item_raw,'standard_name':item_std or 'UNMAPPED',
                          'unit_status':'UNKNOWN','scope_status':'UNKNOWN',
                          'classification':out['quality_status']})
    csv_write(run/'financial_mapping_audit.csv',audit)
    if observations:
        try:import pandas as pd
        except ImportError as exc:raise RuntimeError('pip install pandas pyarrow') from exc
        path=run/'observations.parquet';pd.DataFrame(observations).to_parquet(path,index=False)
    return observations


def safe_div(num:float|None,den:float|None,*,positive:bool=True)->tuple[float|None,str]:
    if num is None or den is None:return None,'MISSING_DEPENDENCY'
    if not math.isfinite(num) or not math.isfinite(den):return None,'NON_FINITE'
    if den==0:return None,'ZERO_DENOMINATOR'
    if positive and den<0:return None,'NON_POSITIVE_DENOMINATOR'
    return num/den,'OK'


def ytd_to_quarter(curr:dict,prev:dict|None,*,is_eps:bool=False)->tuple[float|None,str]:
    if is_eps or curr.get('item_standard') in ('basic_eps','diluted_eps'):
        return None,'EPS_CANNOT_DIFFERENCE'
    if curr.get('period_basis')!='YTD':return None,'NOT_YTD'
    if curr.get('fiscal_quarter')==1:return numeric(curr.get('value_numeric')),'OK'
    if not prev:return None,'PREVIOUS_YTD_MISSING'
    keys=('fiscal_year','statement_scope','currency','unit_multiplier','item_standard','revision_id')
    if any(curr.get(k) is None or curr.get(k)!=prev.get(k) for k in keys):
        return None,'INCOMPATIBLE_BASIS_OR_REVISION'
    p=numeric(prev.get('value_numeric'));c=numeric(curr.get('value_numeric'))
    if p is None or c is None:return None,'MISSING_VALUE'
    return c-p,'OK'


def derive(run:Path)->list[dict]:
    # Pure offline, fail closed until metadata/financial mapping are VERIFIED.
    fp=run/'observations.parquet'
    if not fp.is_file():
        csv_write(run/'factor_readiness.csv',[{'factor':k,'status':'BLOCKED','reason':'NO_OBSERVATIONS'} for k in FACTORS]);return []
    import pandas as pd
    data=pd.read_parquet(fp)
    approved=data.loc[(data.quality_status=='VERIFIED') & (data.pit_status.isin(['PIT_VERIFIED','PIT_UNVERIFIED']))]
    factors=[]
    if not approved.empty:
        # Only implement safe same-period balance ratios. TTM and windowed
        # factors are blocked until compatible versioned periods are verified.
        for (m,s,p),g in approved.groupby(['market','symbol','fiscal_period_end']):
            by={r['item_standard']:r for r in g.to_dict('records')}
            for f,a,b in [('debt_ratio','total_liabilities','total_assets'),
                          ('cash_to_assets','cash_and_equivalents','total_assets')]:
                x,y=by.get(a),by.get(b)
                if not x or not y:continue
                if any(x.get(k)!=y.get(k) for k in ('statement_scope','currency','unit_multiplier')):continue
                value,reason=safe_div(numeric(x.get('value_numeric')),numeric(y.get('value_numeric')))
                deps=[x.get('published_at'),y.get('published_at')]
                factors.append({'market':m,'symbol':s,'period':p,'factor':f,'value':value,
                                'reason':reason,'available_at':max(deps) if all(deps) else None,
                                'pit_status':'PIT_VERIFIED' if all(deps) and all(z['pit_status']=='PIT_VERIFIED' for z in (x,y)) else 'PIT_UNVERIFIED'})
    csv_write(run/'factors.csv',factors)
    ready=[{'factor':k,'status':'DERIVABLE' if any(f['factor']==k and f['value'] is not None for f in factors) else 'BLOCKED',
            'reason':'APPROVED_INPUTS_ONLY' if any(f['factor']==k and f['value'] is not None for f in factors) else 'MISSING_VERIFIED_DEPENDENCIES_OR_FORMULA_IMPLEMENTATION',
            'dependencies':'+'.join(v)} for k,v in FACTORS.items()]
    csv_write(run/'factor_readiness.csv',ready)
    return factors


def validate(root:Path,run:Path)->dict:
    # Create the human-readable report BEFORE immutable manifest-last closure.
    report(run)
    release,m,current_sha=checked_current(root)
    snap=json.loads((run/'input_snapshot.json').read_text('utf-8'))
    if current_sha!=snap['current_sha256'] or release.name!=snap['release']:
        raise ValueError('INPUT_CURRENT_CHANGED_CREATE_NEW_RUN')
    issues=[];conflicts=[]
    req=json.loads((run/'request_plan.json').read_text('utf-8')) if (run/'request_plan.json').exists() else {'tasks':[]}
    for task in req['tasks']:
        d=run/'tasks'/task['task_id']
        if (d/'complete.json').exists() and not valid_checkpoint(d,task):
            issues.append({'task_id':task['task_id'],'reason':'CHECKPOINT_CORRUPTED'})
    # Preserve conflicting observations; NEVER average or overwrite a version.
    if (run/'observations.parquet').is_file():
        import pandas as pd
        df=pd.read_parquet(run/'observations.parquet')
        keys=['market','symbol','dataset','statement_scope','fiscal_period_end','item_raw','revision_id','source_id']
        if all(k in df for k in keys):
            duplicates=df[df.duplicated(keys,keep=False)]
            for x in duplicates.to_dict('records'):
                conflicts.append({'symbol':x['symbol'],'period':x['fiscal_period_end'],'item_raw':x['item_raw'],
                                  'source_id':x['source_id'],'reason':'DUPLICATE_KEY_RETAINED'})
    csv_write(run/'quality_issues.csv',issues)
    csv_write(run/'source_conflicts.csv',conflicts)
    csv_write(run/'coverage_by_market_period.csv',[{'status':'NOT_VERIFIED','reason':'REAL_RELEASE_READBACK_REQUIRED'}])
    csv_write(run/'field_coverage.csv',[{'status':'NOT_VERIFIED','reason':'REAL_RELEASE_READBACK_REQUIRED'}])
    json_write(run/'pit_status_summary.json',{'PIT_VERIFIED':0,'PIT_UNVERIFIED':'UNCERTIFIED','publication_allowed':False})
    json_write(run/'source_capabilities.json',{'FinMind':{'url':SOURCE_URL,'terms_url':'https://finmindtrade.com/','documentation_url':SOURCE_DOC,
       'checked_at':'2026-10-23','datasets':FINMIND,'per_symbol':True,'market_batch':'NOT_AUTHORIZED',
       'training_and_redistribution_terms':'NOT_VERIFIED','research_use':'REVIEW_REQUIRED'},
       'MOPS/TWSE/TPEx':{'status':'REUSE_EXISTING_ADAPTERS_ONLY','authorization':'NOT_REVIEWED'}})
    files={}
    for p in sorted(run.iterdir()):
        if p.is_file() and p.name not in ('candidate_manifest.json','writer.lock'):
            files[p.name]={'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size}
    receipt={'schema_version':SCHEMA,'publication_allowed':False,'source_release':release.name,
             'source_current_sha256':current_sha,'run_id':run.name,'files':files,
             'quality_issues':len(issues),'source_conflicts':len(conflicts),
             'state':'RESEARCH_CANDIDATE_ONLY','model_training_executed':False}
    target=run/'candidate_manifest.json'
    if target.is_file():
        if json.loads(target.read_text('utf-8'))!=receipt:
            raise ValueError('CANDIDATE_IMMUTABLE_CHANGED_CREATE_NEW_RUN')
        return receipt
    json_write(target,receipt)
    if json.loads(target.read_text('utf-8'))!=receipt:
        raise ValueError('CANDIDATE_MANIFEST_READBACK_FAILED')
    return receipt


def report(run:Path)->str:
    snap=json.loads((run/'input_snapshot.json').read_text('utf-8'))
    req=json.loads((run/'request_plan.json').read_text('utf-8')) if (run/'request_plan.json').exists() else {'tasks':[]}
    prog=list(csv.DictReader((run/'collection_progress.csv').open(encoding='utf-8-sig'))) if (run/'collection_progress.csv').exists() else []
    text=(f'# Valuation 補收候選執行摘要\n\n- Run: `{run.name}`\n- Canonical input: `{snap["release"]}`\n'
          f'- 規劃請求: {len(req["tasks"])}；記錄工作: {len(prog)}\n- publication_allowed=false\n'
          '- HTTP/檔案成功不代表財務可用、PIT verified 或模型有效。\n'
          '- 財報單位、scope、period_basis、修訂與公告證據不明時預設 MAPPING_REQUIRED。\n'
          '- 本輪不會啟動模型訓練、部署或 canonical 發布。\n')
    (run/'執行摘要.md').write_text(text,encoding='utf-8')
    return text


def main(argv=None):
    ap=argparse.ArgumentParser(description='Janus Valuation research-only backfill')
    ap.add_argument('command',choices=['audit-p0p1','inventory','plan','fetch','normalize','derive','validate','report'])
    ap.add_argument('--root',default=ROOT_DEFAULT);ap.add_argument('--run-id',required=True)
    ap.add_argument('--symbols',default='');ap.add_argument('--markets',default='')
    ap.add_argument('--start',default='2025-01-01');ap.add_argument('--end',default='2026-09-30')
    ap.add_argument('--max-requests',type=int,default=3);ap.add_argument('--max-symbols',type=int,default=3)
    ap.add_argument('--max-runtime-minutes',type=int,default=5);ap.add_argument('--max-retries',type=int,default=2)
    ap.add_argument('--request-interval',type=float,default=1.0)
    ap.add_argument('--run-fetch',action='store_true');ap.add_argument('--no-dry-run',action='store_true')
    args=ap.parse_args(argv)
    root=checked_root(args.root)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{4,80}',args.run_id):raise ValueError('INVALID_RUN_ID')
    run=root/'模型研究'/'valuation'/'backfill_candidates'/args.run_id
    if args.command=='audit-p0p1':
        from valuation_mapping_p0p1 import live_canonical_audit
        summary=live_canonical_audit(root,run/'p0p1',verify_manifest=checked_current)
        print(json.dumps(summary,ensure_ascii=False,indent=2))
    elif args.command=='inventory':
        run.mkdir(parents=True,exist_ok=True);result=inventory(root,run)
        print('inventory rows:',len(result['inventory']))
    elif args.command=='plan':
        if not (run/'input_snapshot.json').is_file():raise ValueError('RUN_INVENTORY_FIRST')
        rec=inventory(root,run)
        markets=dict(v.split('=',1) for v in args.markets.split(',') if v)
        print('estimated requests:',len(plan(root,run,rec,symbols=[s for s in args.symbols.split(',') if s],start=args.start,end=args.end,markets=markets)))
    elif args.command=='fetch':
        print(fetch(root,run,run_fetch=args.run_fetch,dry_run=not args.no_dry_run,
          max_requests=args.max_requests,max_symbols=args.max_symbols,max_runtime_minutes=args.max_runtime_minutes,
          max_retries=args.max_retries,request_interval=args.request_interval,token=os.environ.get('FINMIND_TOKEN')))
    elif args.command=='normalize':print('normalized rows:',len(normalize(run)))
    elif args.command=='derive':print('derived factors:',len(derive(run)))
    elif args.command=='validate':print(validate(root,run)['state'])
    elif args.command=='report':print(report(run))


if __name__=='__main__':main()
