"""Janus Valuation 04 research-only immutable v22 sidecar / coverage replay.

Input: existing research release reference, v22 frozen plan, unmodified FinMind raw JSON
and v20 monthly positive counts. This NEVER writes to the source release or registry.
No PE/PB price-derived features, no fabricated PIT or financial mapping.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
from collections import defaultdict, Counter
from pathlib import Path

EXPECTED_RELEASE='release-0bbae8d9c1ca7d8d'
EXPECTED_CURRENT='0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd'
EXPECTED_MANIFEST='7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542'
EXPECTED_PLAN_VERSION='VAL-MIN30-HIST-V22-20261024'


def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(p):return sha_bytes(Path(p).read_bytes())
def write_json(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def write_csv(p,fields,rows):
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def task_id(t):
    payload={k:t[k] for k in ('dataset','symbol','start_date','end_date')}
    return sha_bytes(json.dumps(payload,sort_keys=True).encode())[:20]

def last_day(month):
    y,m=map(int,month.split('-'))
    nxt=dt.date(y+1,1,1) if m==12 else dt.date(y,m+1,1)
    return nxt-dt.timedelta(days=1)

def is_positive(value):
    try:v=float(value)
    except (ValueError,TypeError):return False
    return math.isfinite(v) and v>0

def assemble(source:Path,out:Path):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((source/'frozen_plan_v22.json').read_text('utf-8'))
    if plan.get('version')!=EXPECTED_PLAN_VERSION or len(plan['tasks'])!=311:raise ValueError('V22_PLAN_VERSION_OR_TASK_COUNT')
    if plan['source'].get('release')!=EXPECTED_RELEASE or plan['source'].get('current_sha256')!=EXPECTED_CURRENT or plan['source'].get('manifest_sha256')!=EXPECTED_MANIFEST:
        raise ValueError('RESEARCH_RELEASE_MISMATCH')
    with (source/'01_普通股估值與季報逐股核對.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if len(rows)!=1980:raise ValueError('MASTER_ROWS_MISMATCH')
    present={ (r['market'],r['symbol']):r for r in rows}
    if len(present)!=len(rows):raise ValueError('DUPLICATE_MASTER')
    overlay=[];month_snapshots=[];provenance=[];rejected=Counter();counts=defaultdict(set)
    for t in plan['tasks']:
        tid=task_id(t);path=source/'raw'/(tid+'.json')
        if not path.exists():raise FileNotFoundError(str(path))
        raw=path.read_bytes();payload=json.loads(raw)
        if str(payload.get('status'))!='200' or not isinstance(payload.get('data'),list):raise ValueError(f'UNSUCCESSFUL_SOURCE_{tid}')
        if t['dataset']!='TaiwanStockPER' or t['kind']!='valuation':raise ValueError('OUT_OF_SCOPE_DATASET')
        if (t['market'],t['symbol']) not in present:raise ValueError('OUT_OF_SCOPE_SYMBOL')
        if not t.get('listing_date'):raise ValueError('MISSING_LISTING_BOUNDARY')
        if any(m>='2023-10' for m in t['target_months']):raise ValueError('OVERLAP_EXISTING_RELEASE')
        provenance.append({'task_id':tid,'market':t['market'],'symbol':t['symbol'],
          'start_date':t['start_date'],'end_date':t['end_date'],'source_raw_sha256':sha_bytes(raw),
          'source_raw_bytes':len(raw),'provider_rows':len(payload['data']),
          'source_path_in_original_drive':f'backfill_candidates/FINMIND_MIN30_HIST_V22_20261024/raw/{tid}.json',
          'receipt_crosschecked_by_integrator':'NOT_CHECKED_LOCAL_REPLAY'})
        bymonth=defaultdict(list)
        for x in payload['data']:
            s=str(x.get('date',''))[:10]
            try:d=dt.date.fromisoformat(s)
            except ValueError:rejected['INVALID_DATE']+=1;continue
            if x.get('stock_id')!=t['symbol'] or not t['start_date']<=s<=t['end_date'] or s<t['listing_date']:
                rejected['WRONG_SYMBOL_OR_OUTSIDE_RANGE_OR_PRELISTING']+=1;continue
            if s[:7] not in t['target_months']:
                rejected['NOT_TARGET_MONTH']+=1;continue
            bymonth[s[:7]].append((s,x))
        for month,grp in bymonth.items():
            # v22 rule: last real recorded day of requested month, never take earlier positive within month
            day,item=max(grp,key=lambda z:z[0])
            month_snapshots.append({'market':t['market'],'symbol':t['symbol'],'month':month,
              'trade_date':day,'pe_ratio':item.get('PER'),'pb_ratio':item.get('PBR'),
              'dividend_yield':item.get('dividend_yield'),'targeted_branches':','.join(t['branches']),
              'source_provider':'FinMind','source_dataset':t['dataset'],
              'source_task_id':tid,'source_raw_sha256':sha_bytes(raw),
              'last_actual_observation_not_certified_exchange_close':True,
              'historical_pit_verified':False,'publication_allowed':False})
            for branch in t['branches']:
                val=item.get('PER' if branch=='pe' else 'PBR')
                if not is_positive(val):rejected['LAST_OBSERVATION_NONPOSITIVE_OR_NULL']+=1;continue
                key=(t['market'],t['symbol'],branch)
                if month in counts[key]:raise ValueError('DUPLICATE_POSITIVE_MONTH')
                counts[key].add(month)
                overlay.append({'market':t['market'],'symbol':t['symbol'],'branch':branch,'month':month,
                  'trade_date':day,'multiple':float(val),'provider':'FinMind','dataset':t['dataset'],
                  'source_task_id':tid,'source_raw_sha256':sha_bytes(raw),
                  'listing_date_current_master':t['listing_date'],
                  'is_last_source_observation_of_month':True,
                  'official_last_market_session_verified':False,
                  'historical_listing_pit_verified':False,
                  'financial_source_pit_verified':False,
                  'research_candidate_only':True,'publication_allowed':False})
    overlay.sort(key=lambda x:(x['market'],x['symbol'],x['month'],x['branch']))
    month_snapshots.sort(key=lambda x:(x['market'],x['symbol'],x['month']))
    if len({(x['market'],x['symbol'],x['month']) for x in month_snapshots})!=len(month_snapshots):raise ValueError('DUPLICATE_MONTHLY_SNAPSHOT')

    # Assert exact equality with independently produced v22 counts; no silently accepted missing source rows.
    with (source/'v22_valid_month_gain.csv').open(encoding='utf-8-sig',newline='') as f:provider_gain=list(csv.DictReader(f))
    if len(provider_gain)!=311:raise ValueError('V22_GAIN_ROW_COUNT')
    for row in provider_gain:
        key=(row['market'],row['symbol'],row['branch'])
        if len(counts[key])!=int(row['new_candidate_positive_months']):
            raise ValueError(f'V22_ORIGINAL_GAIN_DISAGREE {key} {len(counts[key])} vs {row["new_candidate_positive_months"]}')
    if len(overlay)!=2672:raise ValueError('UNEXPECTED_CANDIDATE_COUNT')
    pair_path=source/'v22_pairs.csv'
    if not pair_path.is_file():raise FileNotFoundError(str(pair_path))
    with pair_path.open(encoding='utf-8-sig',newline='') as f:pair_rows=list(csv.DictReader(f))
    if len(pair_rows)!=1018:raise ValueError('V22_PAIR_REVIEW_COUNT')
    selected={ (t['market'],t['symbol'],b) for t in plan['tasks'] for b in t['branches'] }
    hold_reason={(x['market'],x['symbol'],x['branch']):x['reason'] for x in pair_rows if x['status']=='HOLD'}
    coverage=[];subthreshold=[]
    for row in rows:
        for branch in ('pe','pb'):
            key=(row['market'],row['symbol'],branch)
            n0=int(row[f'{branch}_positive_months']) if row[f'{branch}_positive_months'] else 0
            n1=len(counts[key]);n=n0+n1
            category=('REACHED_30_AFTER_V22' if n0<30<=n else
                      'STILL_BELOW_30_AFTER_V22' if n<30 else
                      'ALREADY_30_IN_ORIGINAL_RELEASE')
            record={'market':row['market'],'symbol':row['symbol'],'company_name':row['公司名稱'],
              'branch':branch,'original_positive_months':n0,'new_positive_month_candidates':n1,
              'combined_positive_precheck':n,'shortfall_to_30':max(0,30-n),
              'precheck_meets_30':n>=30,'category':category,
              'has_any_valuation_evidence':row['has_any_valuation_evidence'],
              'historical_pit_verified':False,'official_last_market_session_verified':False,
              'model_ready':False,'publication_allowed':False}
            coverage.append(record)
            if n<30:
                reason=('NO_EXISTING_VALUATION_EVIDENCE' if row['has_any_valuation_evidence']!='True' else
                    'V22_EXECUTED_BUT_NO_NEW_POSITIVE_MONTH' if key in selected and n1==0 else
                    'V22_EXECUTED_BUT_STILL_BELOW_30' if key in selected else
                    'V22_HOLD_'+str(hold_reason.get(key,'UNKNOWN_REASON')))
                subthreshold.append({**record,'disposition':reason,'automatic_further_backfill':False})
    metrics={}
    for branch in ('pe','pb'):
        old=[r for r in coverage if r['branch']==branch]
        metrics[branch]={'stocks':len(old),'before_30':sum(r['original_positive_months']>=30 for r in old),
         'after_30':sum(r['precheck_meets_30'] for r in old),
         'new_month_candidates':sum(r['new_positive_month_candidates'] for r in old),
         'remaining_branch_below30':sum(not r['precheck_meets_30'] for r in old)}
    union_before=sum(any(int(r[f'{branch}_positive_months'] or 0)>=30 for branch in ('pe','pb')) for r in rows)
    union_after=sum(any(next(x for x in coverage if x['market']==r['market'] and x['symbol']==r['symbol'] and x['branch']==branch)['precheck_meets_30'] for branch in ('pe','pb')) for r in rows)
    metrics.update({'unique_current_roster_symbols':len(rows),'tasks_replayed':len(provenance),
      'distinct_positive_recovered_months':len(overlay),'all_source_monthly_snapshots_including_nonpositive':len(month_snapshots),'original_union_stocks_30':union_before,
      'combined_union_stocks_30':union_after,'remaining_below_30_pairs_full_roster':len(subthreshold),
      'remaining_below_30_pairs_among_311':sum((int(r['existing_positive'])+int(r['new_candidate_positive_months']))<30 for r in provider_gain),
      'rejection_counts':dict(rejected), 'remaining_disposition_counts':dict(Counter(x['disposition'] for x in subthreshold))})
    expected={'pe':(1134,1325,2649,655),'pb':(1796,1799,23,181)}
    for branch,tuple_ in expected.items():
        vals=metrics[branch];v=(vals['before_30'],vals['after_30'],vals['new_month_candidates'],vals['remaining_branch_below30'])
        if v!=tuple_:raise ValueError(f'PRECHECK_COUNTS_DRIFT {branch} {v} != {tuple_}')
    if metrics['remaining_below_30_pairs_among_311']!=117 or len(subthreshold)!=836:raise ValueError('REMAINING_COUNTS_DRIFT')
    import hashlib
    data=io.StringIO(newline='');writer=csv.DictWriter(data,fieldnames=list(overlay[0]));writer.writeheader();writer.writerows(overlay)
    with open(out/'01_valuation_v22_monthly_overlay.csv.gz','wb') as output_fd:
        with gzip.GzipFile(filename='',mode='wb',fileobj=output_fd,mtime=0) as gz:
            gz.write(data.getvalue().encode('utf-8-sig'))
    full_snapshot=io.StringIO(newline='');w=csv.DictWriter(full_snapshot,fieldnames=list(month_snapshots[0]));w.writeheader();w.writerows(month_snapshots)
    with open(out/'01b_all_actual_prehistory_finmind_last_observations.csv.gz','wb') as output_fd:
        with gzip.GzipFile(filename='',mode='wb',fileobj=output_fd,mtime=0) as gz:
            gz.write(full_snapshot.getvalue().encode('utf-8-sig'))
    write_csv(out/'02_recalculated_PE_PB_30month_coverage.csv',list(coverage[0]),coverage)
    write_csv(out/'03_remaining_836_stock_branch_review.csv',list(subthreshold[0]),subthreshold)
    write_csv(out/'04_v22_source_raw_provenance.csv',list(provenance[0]),provenance)
    pit_evidence=json.loads((source/'evidence/pit_status_summary.json').read_text('utf-8'))
    with (source/'evidence/factor_readiness.csv').open(encoding='utf-8-sig') as f:factor_evidence=list(csv.DictReader(f))
    if not factor_evidence or pit_evidence.get('PIT_VERIFIED')!=0 or pit_evidence.get('published_at_populated')!=0:
        raise ValueError('P0_P1_FINANCIAL_GATE_EVIDENCE_CHANGED_RECHECK_MANUALLY')
    if any(r['status']!='BLOCKED' for r in factor_evidence):
        raise ValueError('P0_P1_FACTOR_GATE_EVIDENCE_CHANGED_RECHECK_MANUALLY')
    model_gate={'state':'BLOCKED_NOT_TRAINED','model_role':'valuation','publication_allowed':False,
        'requested_model':'04 XGBoost PE and PB; five-feature verified mapping',
        'financial_p0_p1_evidence':{'pit_verified_rows':pit_evidence.get('PIT_VERIFIED'),
         'pit_unverified_rows':pit_evidence.get('PIT_UNVERIFIED'),
         'published_at_populated':pit_evidence.get('published_at_populated'),
         'blocked_factor_count':len(factor_evidence),
         'evidence_sha256':{p.name:sha_file(p) for p in sorted((source/'evidence').iterdir())}},
        'checks':{
          'research_coverage_positive_month_precheck':'PASS_RESEARCH_ONLY',
          'direct_PARQUET_merge_into_canonical_release':'NOT_ATTEMPTED_READ_ONLY_SIDECAR',
          'financial_mapping_verified':'BLOCKED_UNVERIFIED_UNIT_PERIOD_SCOPE',
          'financial_historical_published_at':'BLOCKED_ZERO_PUBLISHED_AT_IN_PREVIOUS_P0_P1_AUDIT',
          'historical_pit':'NOT_VERIFIED',
          'actual_exchange_month_end_calendar':'NOT_VERIFIED',
          'historical_ordinary_share_pit':'NOT_VERIFIED',
          'valid_effective_dated_cohorts':'NOT_VERIFIED',
          'X_training_finite_5_features':'NOT_DEMONSTRATED'},
        'do_not_train_reason':'Current janus_precision.valuation_panel sets 4 financial X columns NaN and reason BLOCKED_VERIFIED_FINANCIAL_MAPPING_OR_COHORT until validated as-of mapping / cohorts. Historical PIT audit = 0 verified rows, published_at present = 0. Fit would be invalid or no eligible rows.',
        'safe_next_step':'Provide actual financial field mapping, units, period_basis, first availability as-of, cohort evidence; after approved research non-PIT fallback, train an explicitly marked RESEARCH_NON_PIT candidate with fixed time split and no publication.'}
    write_json(out/'05_model_training_gate.json',model_gate)
    write_json(out/'00_summary.json',{'status':'RESEARCH_OVERLAY_REPLAY_COMPLETED_MODEL_BLOCKED',
     'metrics':metrics,'source':plan['source'],'frozen_plan_fingerprint':plan['fingerprint'],
     'original_research_base':'JanusDataset_v3_202610/canonical/'+EXPECTED_RELEASE,
     'merge_semantics':'READ_ONLY_BASE_RELEASE_PLUS_VERSIONED_PRE_2023_10_OVERLAY_NOT_CANONICAL',
     'research_only':True,'publication_allowed':False,'model_ready':False,
     'raw_receipt_sha_crosscheck':'NOT_PERFORMED_BY_THIS_REPLAYER__RAW_HTTP_BODY_SHA_FROZEN',
     'data_quality':'POSITIVE_FINMIND_LAST_OBSERVATION_PRECHECK_ONLY_NOT_SESSION_CALENDAR_OR_PIT',
     'new_research_files_sha256':{p.name:sha_file(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return metrics

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--input',required=True,type=Path);a.add_argument('--output',required=True,type=Path)
    x=a.parse_args();print(json.dumps(assemble(x.input,x.output),ensure_ascii=False,indent=2))
