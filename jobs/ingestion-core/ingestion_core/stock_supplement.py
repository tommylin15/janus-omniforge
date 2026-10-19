"""Drain de-identified stock demands on the existing ingestion Job."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from time import monotonic
from urllib.parse import urlencode
from uuid import uuid4
from zoneinfo import ZoneInfo

from packages.provenance import Provenance
from .supplement_sources import parse_prices, parse_revenue, parse_valuation, parse_eps_history


def revenue_months(today):
    latest = today.replace(day=1)-timedelta(days=1)
    if today.day <= 10:
        latest = latest.replace(day=1)-timedelta(days=1)
    n = latest.year*12+latest.month-1
    return {(i//12,i%12+1) for i in range(n-12,n+1)}


def claim(connection):
    token = uuid4()
    with connection.transaction(), connection.cursor() as cur:
        cur.execute('SELECT singleton FROM control.stock_supplement_dispatch WHERE singleton FOR UPDATE')
        cur.execute("""UPDATE control.stock_supplement_requests SET status='partial',lease_token=NULL,
            next_attempt_at=now(),updated_at=now() WHERE status='running'
            AND started_at<now()-interval '35 minutes'"""
        )
        cur.execute("""WITH candidate AS (SELECT symbol FROM control.stock_supplement_requests
            WHERE demanded AND status IN ('pending','partial') AND next_attempt_at<=now()
            ORDER BY next_attempt_at,symbol FOR UPDATE SKIP LOCKED LIMIT 1)
            UPDATE control.stock_supplement_requests q SET status='running',lease_token=%s,
              started_at=now(),attempts=attempts+1,updated_at=now()
            FROM candidate c WHERE q.symbol=c.symbol
            RETURNING q.symbol,q.generation,q.lease_token""", (token,))
        row = cur.fetchone()
        if row is None:
            cur.execute('UPDATE control.stock_supplement_dispatch SET reserved_at=NULL WHERE singleton')
        return row


def still_wanted(connection, request, *, lock=False):
    with connection.cursor() as cur:
        cur.execute("""SELECT 1 FROM control.stock_supplement_requests WHERE symbol=%s AND generation=%s
            AND lease_token=%s AND demanded AND status='running'""" + (' FOR UPDATE' if lock else ''), request)
        return cur.fetchone() is not None


def finish(connection, request, receipt):
    status = 'succeeded' if receipt['ready'] else 'partial'
    with connection.transaction(), connection.cursor() as cur:
        cur.execute("""UPDATE control.stock_supplement_requests SET status=%s,receipt=%s::jsonb,
            finished_at=now(),updated_at=now(),lease_token=NULL,
            next_attempt_at=now()+interval '24 hours'
            WHERE symbol=%s AND generation=%s AND lease_token=%s AND demanded AND status='running'""",
            (status,json.dumps(receipt,default=str),*request))


def publish_rows(core, projection, dataset, rows):
    snapshot = core.catalog.load_table(core.table_identifier(dataset)).current_snapshot()
    if snapshot is None:
        raise ValueError('missing_persisted_snapshot')
    groups = defaultdict(list)
    for row in rows:
        groups[(str(row['execution_id']),row['provenance_id'],row['source_id'])].append(row)
    for (eid,pid,sid), group in groups.items():
        projection.publish(dataset,group,execution_id=eid,provenance_id=pid,
            source_id=sid,core_snapshot_id=snapshot.snapshot_id)
    return snapshot.snapshot_id


def supplement_one(control, core, writer, projection, request, *, today, fetch):
    from .control import ExecutionStatus
    from .data_supplement import _rows
    from .valuation_history import publish_focus_profiles
    symbol = request[0]
    with control.connection.cursor() as cur:
        cur.execute("""SELECT sm.market,p.instrument_kind,
            EXISTS(SELECT 1 FROM control.market_universe_members u WHERE u.symbol=sm.symbol)
            FROM control.stock_master sm
            LEFT JOIN control.official_instrument_identity_provenance p USING(symbol)
            WHERE sm.symbol=%s AND sm.enabled AND sm.market IN ('TWSE','TPEX')""", (symbol,))
        identity = cur.fetchone()
    if identity is None:
        raise ValueError('supplement_identity_unavailable')
    market, kind, equity = identity
    if not equity and (kind is None or 'ETF' not in kind):
        raise ValueError('instrument_applicability_unknown')
    execution = control.enqueue_collection('first-batch',(symbol,),request_options={'operation':'stock-supplement'})
    control.transition_execution(execution.execution_id,ExecutionStatus.RUNNING)
    receipt = {'symbol':symbol,'ready':False,'datasets':{},'errors':[],
               'owner_mutation':False,'historical_pit_certified':False}
    staged = []
    try:
        for dataset, provider, parser in (
            ('ohlcv','TaiwanStockPrice',parse_prices),
            ('revenue','TaiwanStockMonthRevenue',parse_revenue),
            ('eps',None,parse_eps_history),
            ('valuation','TaiwanStockPER',parse_valuation)):
            if not still_wanted(control.connection,request):
                receipt['cancelled'] = True
                break
            if not equity and dataset != 'ohlcv':
                receipt['datasets'][dataset] = {'status':'not_applicable'}
                continue
            target = 'financials' if dataset in {'eps','revenue'} else dataset
            start = today-timedelta(days=400 if dataset=='ohlcv' else 450 if dataset=='revenue' else 760)
            try:
                source = 'finmind' if provider else 'yahoo-finance'
                if not control.source_is_approved(source):
                    raise ValueError('source_not_approved')
                # Reuse canonical values and their original lineage. Provider requests fill gaps.
                existing = _rows(core,target,(symbol,), **({'date_field':'trade_date' if target=='ohlcv' else 'observed_date',
                    'start_date':start.isoformat(),'end_date':today.isoformat()} if target!='financials' else {}))
                if dataset=='ohlcv':
                    dates = {str(r['trade_date'])[:10] for r in existing if r.get('close') is not None}
                    if len(dates)>=120 and max(dates)>=str(today-timedelta(days=7)):
                        publish_rows(core,projection,target,existing)
                        receipt['datasets'][dataset] = {'status':'ready','rows':len(dates),'reused':True}
                        continue
                if dataset=='revenue':
                    periods = {(int(r['fiscal_year']),int(r['fiscal_month'])) for r in existing
                        if str(r.get('metric','')).startswith('monthly_revenue') and r.get('period_basis')=='monthly'
                        and r.get('unit')=='TWD_thousands' and r.get('value') is not None and r.get('fiscal_month')}
                    if revenue_months(today)<=periods:
                        publish_rows(core,projection,target,[r for r in existing
                            if str(r.get('metric','')).startswith('monthly_revenue') and r.get('unit')=='TWD_thousands'])
                        receipt['datasets'][dataset] = {'status':'ready','rows':13,'reused':True}
                        continue
                url = ('https://api.finmindtrade.com/api/v4/data?'+urlencode({'dataset':provider,
                    'data_id':symbol,'start_date':start.isoformat(),'end_date':today.isoformat()}) if provider else
                    f"https://tw.stock.yahoo.com/quote/{symbol}.{'TW' if market=='TWSE' else 'TWO'}/eps")
                raw,_ = fetch(url)
                received = datetime.now(timezone.utc)
                provenance = Provenance(str(uuid4()),source,url,target,received,None,received,
                    'sha256:'+sha256(raw).hexdigest(),False,
                    quality_details={'source_kind':'third_party','dataset':dataset,'symbol':symbol,
                                     'price_basis':'provider_reported_not_official_certified' if dataset=='ohlcv' else None})
                entry = writer.write_raw(payload=raw,media_type='application/json' if provider else 'text/html',
                    extension='json' if provider else 'html',execution_id=execution.execution_id,
                    provenance=provenance,execution_scoped=True)
                options = {'received_at':received.isoformat()}
                if provider:
                    options.update(start=start,end=today)
                rows = (parser(raw,symbol,**options) if dataset=='revenue' else parser(raw,symbol,market,**options))
                if dataset=='revenue':
                    rows = [r for r in rows if (r['fiscal_year'],r['fiscal_month']) in revenue_months(today)]
                if not rows:
                    raise ValueError('provider_history_missing')
                if target=='financials':
                    known = {(int(r['fiscal_year']),int(r.get('fiscal_month') or r['fiscal_quarter'])) for r in existing
                        if r.get('value') is not None and r.get('provenance_id') and
                        (str(r.get('metric','')).startswith('monthly_revenue') and r.get('unit')=='TWD_thousands'
                         if dataset=='revenue' else r.get('metric')=='eps_single_quarter' and r.get('period_basis')=='single_quarter' and r.get('unit')=='TWD_per_share')}
                    rows = [r for r in rows if (r['fiscal_year'],r.get('fiscal_month') or r['fiscal_quarter']) not in known]
                else:
                    key = 'trade_date' if target=='ohlcv' else 'observed_date'
                    known = {str(r[key])[:10] for r in existing if r.get('provenance_id') and
                        (r.get('close') is not None if target=='ohlcv' else
                         any(r.get(k) is not None for k in ('pe_ratio','pb_ratio','dividend_yield_percent')))}
                    rows = [r for r in rows if str(r[key])[:10] not in known]
                for row in rows:
                    row['provenance_id'] = entry.idempotency_key
                    if target=='financials':
                        row['source_document_sha256'] = sha256(raw).hexdigest()
                # Do not hold a DB transaction across Core IO: owner mutations must stay responsive.
                if not still_wanted(control.connection,request):
                    receipt['cancelled'] = True
                    break
                if rows:
                    core.write(dataset_id=target,rows=rows,execution_id=execution.execution_id,
                        provenance_id=entry.idempotency_key,source_id=source,partition_date=today)
                    staged.append(entry)
                persisted = _rows(core,target,(symbol,), **({'date_field':'trade_date' if target=='ohlcv' else 'observed_date',
                    'start_date':start.isoformat(),'end_date':today.isoformat()} if target!='financials' else {}))
                persisted = [r for r in persisted if r.get('source_id') in {'twse','tpex','mops','finmind','yahoo-finance'} and r.get('provenance_id')]
                if target=='financials':
                    metric = 'monthly_revenue' if dataset=='revenue' else 'eps_single_quarter'
                    persisted = [r for r in persisted if str(r.get('metric','')).startswith(metric)
                        and r.get('unit')==('TWD_thousands' if dataset=='revenue' else 'TWD_per_share')]
                if not still_wanted(control.connection,request):
                    receipt['cancelled'] = True
                    break
                snapshot_id = publish_rows(core,projection,target,persisted)
                if dataset=='ohlcv':
                    dates = {str(r['trade_date'])[:10] for r in persisted}
                    ready = len(dates)>=120 and max(dates)>=str(today-timedelta(days=7))
                elif dataset=='revenue':
                    ready = revenue_months(today)<={(int(r['fiscal_year']),int(r['fiscal_month'])) for r in persisted}
                elif dataset=='eps':
                    periods = {int(r['fiscal_year'])*4+int(r['fiscal_quarter'])-1 for r in persisted}
                    ready = bool(periods) and set(range(max(periods)-11,max(periods)+1))<=periods
                else:
                    profiles = publish_focus_profiles(core,control,symbols=[symbol],as_of=today)
                    ready = profiles['two_year_ready']==2
                receipt['datasets'][dataset] = {'status':'ready' if ready else 'partial',
                    'rows':len(persisted),'core_snapshot_id':str(snapshot_id),
                    'source_ids':sorted({r['source_id'] for r in persisted})}
            except Exception as error:
                receipt['datasets'][dataset] = {'status':'partial','error_code':type(error).__name__}
                receipt['errors'].append({'dataset':dataset,'error_code':type(error).__name__})
        receipt['ready'] = (len(receipt['datasets'])==4 and
            all(r['status'] in {'ready','not_applicable'} for r in receipt['datasets'].values()) and not receipt.get('cancelled'))
        if not receipt['errors'] and not receipt.get('cancelled'):
            writer.mark_core_committed(execution.execution_id,stage_results=staged)
        control.complete_collection(execution.execution_id,None,partial=not receipt['ready'])
        return receipt
    except Exception:
        control.transition_execution(execution.execution_id,ExecutionStatus.FAILED,error_code='STOCK_SUPPLEMENT_FAILED')
        raise


def run_pending(*, daily=False):
    from .__main__ import _control_plane, _iceberg_core
    from .data_supplement import _fetch
    from .serving_projection import StockServingProjection
    from .stage import StageWriter, GcsObjectStore
    import os
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    control = _control_plane()
    core = None
    locked = False
    report = {'component':'stock-supplement','status':'idle','processed':0,'ready':0,'partial':0}
    started = datetime.now(timezone.utc)
    try:
        with control.connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(1835102836,8)')
            locked = cur.fetchone()[0]
        if not locked:
            return {**report,'status':'busy'}
        with control.connection.transaction(), control.connection.cursor() as cur:
            cur.execute('SELECT control.sync_stock_supplement_demand()')
            if daily:
                cur.execute("""UPDATE control.stock_supplement_requests SET status='pending',next_attempt_at=now()
                    WHERE demanded AND status IN ('succeeded','partial')
                    AND coalesce(finished_at,'epoch'::timestamptz)<%s""",
                    (datetime.combine(today,datetime.min.time(),tzinfo=ZoneInfo('Asia/Taipei')),))
        core = _iceberg_core(os.environ['CORE_BUCKET'])
        writer = StageWriter(GcsObjectStore(os.environ['STAGE_BUCKET']))
        projection = StockServingProjection.from_env()
        deadline = monotonic()+20*60
        for _ in range(50):
            if monotonic()>=deadline:
                break
            request = claim(control.connection)
            if request is None:
                break
            try:
                receipt = supplement_one(control,core,writer,projection,request,today=today,fetch=_fetch)
            except Exception as error:
                receipt = {'ready':False,'error_code':type(error).__name__}
            finish(control.connection,request,receipt)
            report['processed'] += 1
            report['ready' if receipt['ready'] else 'partial'] += 1
        report['status'] = 'partial' if report['partial'] else 'succeeded'
        return report
    finally:
        if locked:
            with control.connection.transaction(), control.connection.cursor() as cur:
                cur.execute('UPDATE control.stock_supplement_dispatch SET reserved_at=NULL WHERE singleton AND reserved_at<=%s',(started,))
                cur.execute('SELECT pg_advisory_unlock(1835102836,8)')
        if core:
            core.close()
        control.close()
