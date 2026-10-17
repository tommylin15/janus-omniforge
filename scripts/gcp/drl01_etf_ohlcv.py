#!/usr/bin/env python3
"""DRL-01 bounded TPEx official ETF 120-session price repair on existing dev Job.

Two versioned, approved ETF instruments only. Official TPEX dailyQuotes full raw
is staged before source-derived Core OHLCV; equity membership is not modified.
"""
import json,subprocess,sys,time
from datetime import date
from pathlib import Path
from ghcr_jobs_rollout import ROOT,cloud,job,terminal

PROBE=r"""
import json,os
from collections import defaultdict
from datetime import date,datetime,timezone
from hashlib import sha256
from urllib.parse import urlencode
from uuid import uuid4
from pyiceberg.expressions import And,GreaterThanOrEqual,In
from ingestion_core.__main__ import _control_plane,_iceberg_core
from ingestion_core.data_supplement import _fetch
from ingestion_core.first_batch import normalise_benchmark
from ingestion_core.sources import _date as official_date,_number
from ingestion_core.dq import validate_ohlcv
from ingestion_core.stage import StageWriter,GcsObjectStore
from packages.provenance import Provenance

req=json.loads(os.environ['DRL01_ETF_HISTORY_REQUEST'])
symbols=set(req['symbols'])
first=date.fromisoformat(req['start_date'])
as_of=date.fromisoformat(req['as_of'])
out={'component':'drl01_tpex_etf_120d_core','status':'PARTIAL','instrument_type':'ETF',
     'source':'tpex','expected':len(symbols),'before_qualified':0,'after_qualified':0,
     'month_receipts':[],'owner_mutation':False,'market_master_mutation':False,
     'job_template_mutation':False}
core=None
control=None
try:
    control=_control_plane()
    if not control.source_is_approved('tpex') or not control.source_is_approved('taiex'):
        raise RuntimeError('approved_sources_missing')
    # These source-confirmed ETF IDs must not be silently inserted into the equity master.
    core=_iceberg_core(os.environ['CORE_BUCKET'])
    writer=StageWriter(GcsObjectStore(os.environ['STAGE_BUCKET']))
    table=core.catalog.load_table(core.table_identifier('ohlcv'))
    def snapshot_coverage():
        t=core.catalog.load_table(core.table_identifier('ohlcv'))
        snap=t.current_snapshot()
        rows=t.scan(snapshot_id=snap.snapshot_id,
            row_filter=And(GreaterThanOrEqual('trade_date',first),In('symbol',sorted(symbols))),
            selected_fields=('symbol','market','trade_date','close','source_id','provenance_id')).to_arrow().to_pylist()
        out=defaultdict(set)
        for row in rows:
            day=date.fromisoformat(str(row['trade_date'])[:10])
            if (row.get('symbol') in symbols and row.get('market')=='TPEX'
                and row.get('source_id')=='tpex' and row.get('provenance_id')
                and row.get('close') is not None and day<=as_of):
                out[row['symbol']].add(day)
        return out,str(snap.snapshot_id)
    before,_=snapshot_coverage()
    out['before_qualified']=sum(len(before[s])>=120 for s in symbols)
    month=first.replace(day=1)
    months=[]
    while month<=as_of:
        months.append(month)
        month=date(month.year+int(month.month==12),month.month%12+1,1)
    # Official TAIEX trading-session calendar: weekend-only inference is forbidden.
    calendar=defaultdict(list)
    for month in months:
        url='https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?'+urlencode({
            'date':f"{month.year}{month.month:02d}01",'response':'json'})
        raw,_=_fetch(url)
        doc=json.loads(raw)
        days=normalise_benchmark(dict(zip(doc['fields'],cells)) for cells in doc.get('data',[]))
        calendar[month.strftime('%Y-%m')]=sorted({
            date.fromisoformat(r['trade_date']) for r in days
            if first<=date.fromisoformat(r['trade_date'])<=as_of})
    out['official_sessions']=sum(len(v) for v in calendar.values())
    if out['official_sessions']<120:raise RuntimeError('insufficient_official_market_sessions')
    for month in months:
        key=month.strftime('%Y-%m')
        item={'month':key,'official_sessions':len(calendar[key]),'source_days':0,
              'qualified_rows':0,'quarantined_rows':0,'missing_symbol_days':0}
        requested_days=[day for day in calendar[key] if any(day not in before[s] for s in symbols)]
        if not requested_days:
            out['month_receipts'].append(item)
            continue
        rows=[]
        staged=[]
        execution=str(uuid4())
        for day in requested_days:
            url='https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?'+urlencode({
                'date':day.strftime('%Y/%m/%d'),'id':'','response':'json'})
            try:
                raw,_=_fetch(url)
                doc=json.loads(raw)
                if not isinstance(doc,dict) or not doc.get('tables'):
                    raise ValueError('official_etf_archive_schema_missing')
                if official_date(doc.get('date'))!=day.isoformat():
                    raise ValueError('official_date_mismatch')
                selected=[]
                for tab in doc['tables']:
                    fields=tab.get('fields') or []
                    if '代號' not in fields:continue
                    for values in tab.get('data',[]):
                        record=dict(zip(fields,values))
                        if str(record.get('代號') or '').strip() in symbols:
                            selected.append(record)
                if len({str(v['代號']).strip() for v in selected})!=len(selected):
                    raise ValueError('duplicate_official_etf_symbol')
                if not selected:
                    item['missing_symbol_days']+=len(symbols)
                    continue
                possible=[]
                for rec in selected:
                    symbol=str(rec['代號']).strip()
                    if day in before[symbol]:continue
                    required=('名稱','成交股數','成交金額(元)','開盤','最高','最低','收盤')
                    if not all(f in rec for f in required):raise ValueError('official_etf_field_missing')
                    if not str(rec['名稱']).strip():raise ValueError('official_etf_name_missing')
                    possible.append({'symbol':symbol,'market':'TPEX','trade_date':day.isoformat(),
                        'open':_number(rec['開盤']),'high':_number(rec['最高']),
                        'low':_number(rec['最低']),'close':_number(rec['收盤']),
                        'volume_shares':_number(rec['成交股數']),
                        'turnover_twd':_number(rec['成交金額(元)']),
                        'change_percent':None,'source_id':'tpex',
                        'observed_at':day.isoformat()+'T00:00:00Z'})
                dq=validate_ohlcv(possible,analysis_as_of=as_of)
                item['quarantined_rows']+=len(dq.quarantined)
                if not dq.accepted:
                    item['missing_symbol_days']+=len(symbols)-sum(day in before[s] for s in symbols)
                    continue
                received=datetime.now(timezone.utc)
                provenance=Provenance(str(uuid4()),'tpex',url,'ohlcv',
                    received,None,received,'sha256:'+sha256(raw).hexdigest(),False,
                    quality_details={'request_identity':{'kind':'etf_historical_daily','date':day.isoformat()}})
                entry=writer.write_raw(payload=raw,media_type='application/json',extension='json',
                                       execution_id=execution,provenance=provenance,execution_scoped=True)
                staged.append(entry)
                rows.extend({**r,'provenance_id':entry.idempotency_key} for r in dq.accepted)
                item['source_days']+=1
            except Exception as error:
                error_name=type(error).__name__
                item.setdefault('errors',{})[error_name]=item.get('errors',{}).get(error_name,0)+1
        if rows:
            result=core.write(dataset_id='ohlcv',rows=rows,execution_id=execution,
                              provenance_id=rows[0]['provenance_id'],source_id='tpex',
                              partition_date=month)
            writer.mark_core_committed(execution,stage_results=staged)
            item.update(snapshot_id=str(result.snapshot_id),inserted=result.inserted,
                        updated=result.updated,reused=result.reused)
            item['qualified_rows']=len(rows)
            for r in rows:before[r['symbol']].add(date.fromisoformat(r['trade_date']))
        out['month_receipts'].append(item)
    after,snapshot=snapshot_coverage()
    out['final_snapshot_id']=snapshot
    out['after_qualified']=sum(len(after[s])>=120 for s in symbols)
    out['min_valid_dates']=min(len(after[s]) for s in symbols)
    out['max_valid_dates']=max(len(after[s]) for s in symbols)
    out['status']='PASS' if out['after_qualified']==len(symbols) else 'PARTIAL_ETF_HISTORY'
except Exception as error:
    out['status']='BLOCKED_'+type(error).__name__
finally:
    if core:
        try:core.close()
        except Exception:pass
    if control:
        try:control.close()
        except Exception:pass
    print(json.dumps(out,sort_keys=True,ensure_ascii=False),flush=True)
"""
def checked(path):
    req=json.loads(Path(path).read_text())
    if (req.get('intent')!='drl01-approved-official-tpex-etf-history'
        or req.get('approved') is not True or req.get('no_owner_mutation') is not True
        or req.get('no_equity_market_master_mutation') is not True
        or req.get('no_job_template_mutation') is not True
        or req.get('symbols')!=['00697B','00719B']
        or req.get('start_date')!='2026-04-01'
        or req.get('as_of')!='2026-10-16'):
        raise ValueError('out_of_scope_etf_history')
    return req
def main():
    req=checked(sys.argv[1])
    j=job('janus-ingestion-core')
    c=j['template']['template']['containers']
    if len(c)!=1 or c[0].get('command') not in (None,[],['python']):raise ValueError('job_template_drift')
    override={'args':(['python'] if not c[0].get('command') else [])+['-c',PROBE],
              'env':[{'name':'QUEUE_CONSUMER','value':'false'},
                     {'name':'DRL01_ETF_HISTORY_REQUEST','value':json.dumps(req,separators=(',',':'))}]}
    if c[0].get('name'):override['name']=c[0]['name']
    op=cloud(f'{ROOT}/jobs/janus-ingestion-core:run',{'etag':j['etag'],'overrides':{
        'taskCount':1,'timeout':'1600s','containerOverrides':[override]}},'POST')
    name=op.get('name','')
    if not name.startswith(ROOT+'/operations/'):raise RuntimeError('etf_operation_not_created')
    until=time.monotonic()+1660
    while not op.get('done') and time.monotonic()<until:
        time.sleep(8);op=cloud(name)
    if not op.get('done') or op.get('error'):raise RuntimeError('etf_operation_state_unknown')
    exe=op.get('response',{})
    if not terminal(exe) or exe.get('succeededCount')!=1 or exe.get('failedCount',0):
        raise RuntimeError('etf_core_execution_failed')
    ename=exe['name'].rsplit('/',1)[-1]
    if not ename.startswith('janus-ingestion-core-'):raise RuntimeError('etf_execution_identity_unknown')
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+ename+'"'
    receipt=None
    for _ in range(5):
        proc=subprocess.run(['gcloud','logging','read',filt,'--project=gen-lang-client-0593591102',
            '--limit=200','--format=json'],capture_output=True,text=True,timeout=45)
        if proc.returncode==0:
            for event in json.loads(proc.stdout):
                x=event.get('jsonPayload')
                if not isinstance(x,dict):
                    try:x=json.loads(event.get('textPayload',''))
                    except (TypeError,ValueError):continue
                if isinstance(x,dict) and x.get('component')=='drl01_tpex_etf_120d_core':
                    receipt=x;break
        if receipt:break
        time.sleep(5)
    if receipt is None:raise RuntimeError('etf_core_readback_missing')
    out={'execution':ename,'receipt':receipt}
    Path('/tmp/drl01-etf-history.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
    if receipt.get('status')!='PASS':raise RuntimeError('etf_core_120d_partial')
if __name__=='__main__':main()
