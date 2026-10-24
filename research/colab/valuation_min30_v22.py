"""V22: evidence-gated historical Valuation research backfill, read-only old receipts.
No canonical writes; FinMind fetch only via an explicit bounded call.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import valuation_min30_real_backfill as base

VERSION='VAL-MIN30-HIST-V22-20261024'
# Minimum positive observation months to prioritize a historical query, not model eligibility.
MIN_OBSERVED_POSITIVE_FOR_FETCH=12
MAX_HIST_MONTHS_PER_TASK=24


def digest_json(x):
    return base.sha(json.dumps(x,ensure_ascii=False,sort_keys=True, separators=(',',':')).encode())


def positive(v):
    try:
        x=float(v)
        return math.isfinite(x) and x>0
    except (ValueError,TypeError):
        return False


def inspect_legacy(legacy_root:Path):
    """Never modifies v21. SHA-check every completed receipt before inspecting its raw."""
    legacy_root=Path(legacy_root)
    out={'receipts_valid':0,'receipts_invalid':0,'raw_positive_months':0,
         'raw_nonpositive_months':0,'validated':[],'positive_by_symbol_branch':defaultdict(set),
         'nonpositive_by_symbol_branch':defaultdict(set)}
    if not (legacy_root/'receipts').is_dir():return out
    for file in sorted((legacy_root/'receipts').glob('*.json')):
        try:
            rec=json.loads(file.read_text('utf-8'))
            if rec.get('dataset')!=base.DATASETS['valuation'] or rec.get('status') not in ('SUCCESS','EMPTY_SOURCE_RESPONSE'):
                continue
            raw=legacy_root/'raw'/file.name
            if rec.get('task_id')!=file.stem or not raw.is_file() or rec.get('raw_sha256')!=base.sha(raw.read_bytes()):
                out['receipts_invalid']+=1;continue
            payload=json.loads(raw.read_bytes())
            if str(payload.get('status'))!='200' or not isinstance(payload.get('data'),list):
                out['receipts_invalid']+=1;continue
            sym=str(rec['symbol']); monthly=defaultdict(list)
            for row in payload['data']:
                if str(row.get('stock_id'))!=sym:
                    raise ValueError('v21 mismatched stock_id')
                date=dt.date.fromisoformat(row['date'])
                if not rec['start_date']<=date.isoformat()<=rec['end_date']:continue
                monthly[date.strftime('%Y-%m')].append((date,row))
            for month,rows in monthly.items():
                date,last=max(rows,key=lambda x:x[0])
                for branch,col in (('pe','PER'),('pb','PBR')):
                    key=(str(rec['market']).lower(),sym,branch)
                    dest='positive_by_symbol_branch' if positive(last.get(col)) else 'nonpositive_by_symbol_branch'
                    out[dest][key].add(month)
            out['receipts_valid']+=1
            out['validated'].append({'task_id':file.stem,'symbol':sym,'raw_sha256':rec['raw_sha256'],
                                      'start_date':rec['start_date'],'end_date':rec['end_date']})
        except (ValueError,KeyError,TypeError,UnicodeError):
            out['receipts_invalid']+=1
    out['raw_positive_months']=sum(map(len,out['positive_by_symbol_branch'].values()))
    out['raw_nonpositive_months']=sum(map(len,out['nonpositive_by_symbol_branch'].values()))
    return out


def select_v22(data:dict, meta:dict, official:dict, legacy:dict, *,
               months_back:int=60, min_positive:int=MIN_OBSERVED_POSITIVE_FOR_FETCH,
               historical_cap:int=MAX_HIST_MONTHS_PER_TASK):
    """Select only pre-release valuation dates; never retry a known PE=0 in-place.

    Current official listing date is an upper-bound eligibility guard only; no historical PIT claim.
    """
    if months_back<36 or months_back>120:raise ValueError('months_back must be 36..120')
    if historical_cap<1 or historical_cap>48:raise ValueError('cap must be 1..48')
    end=base.month_ord(meta['as_of_month'])
    existing_start=base.month_ord(meta['existing_first_month'])
    earliest=end-months_back+1
    if existing_start<=earliest:raise ValueError('no pre-release history inside lookback')
    universe={(r['market'].strip().lower(),r['symbol'].strip()):r for r in data[base.REQUIRED[1]]}
    grouped=defaultdict(lambda:{'months':set(),'branches':set(),'branch_detail':[]})
    holds=[]
    pairs=[]
    for r in data[base.REQUIRED[3]]:
        market,symbol,branch=r['market'].strip().lower(),r['symbol'].strip(),r['branch'].lower().strip()
        if branch not in ('pe','pb'):continue
        short=int(float(r['shortfall']))
        if short<=0:continue
        baseline=universe.get((market,symbol)); ordinary=official.get((market,symbol))
        n=int(float((baseline or {}).get(branch+'_positive_months') or 0))
        k=(market,symbol,branch)
        decision={'market':market,'symbol':symbol,'branch':branch,'baseline_positive_months':n,
                  'shortfall':short,'status':'','historical_months':0,'reason':''}
        if not baseline or str(baseline.get('has_any_valuation_evidence')).lower()!='true' or not ordinary:
            decision.update(status='HOLD',reason='UNVERIFIED_ORDINARY_OR_NO_VALUATION')
        elif not ordinary.get('listing_date'):
            decision.update(status='HOLD',reason='UNKNOWN_LISTING_DATE_FOR_PRE_2023')
        elif n<min_positive:
            decision.update(status='HOLD',reason='LOW_POSITIVE_HISTORY_YIELD_AUDIT_FIRST')
        else:
            listing=ordinary['listing_date']
            historic=[base.ymonth(i) for i in range(earliest,existing_start)
                    if base.last_day(base.ymonth(i))>=listing]
            # For low probability PE=0 stretches, cap to shortfall+4 and then measure.
            need=min(len(historic),short+4,historical_cap)
            selected=historic[-need:] if need>0 else []
            if not selected:
                decision.update(status='HOLD',reason='NO_PRE_2023_POST_LISTING_MONTHS')
            else:
                decision.update(status='FETCH_CANDIDATE',reason='EARLIER_UNOBSERVED_MONTHS',historical_months=len(selected))
                group=grouped[(market,symbol)]
                group['months'].update(selected)
                group['branches'].add(branch)
                group['branch_detail'].append({'branch':branch,'baseline':n,'shortfall':short,'historical_months':len(selected)})
        pairs.append(decision)
        if decision['status']=='HOLD':holds.append(decision)
    tasks=[]
    for (market,symbol),g in sorted(grouped.items()):
        months=sorted(g['months']);listing=official[(market,symbol)]['listing_date']
        if months[-1]>=meta['existing_first_month']:raise ValueError('v22 would re-fetch v21 range')
        tasks.append({'dataset':base.DATASETS['valuation'],'kind':'valuation', 'market':market,'symbol':symbol,
                'start_date':base.first_day(months[0]), 'end_date':base.last_day(months[-1]),
                'target_months':months,'branches':sorted(g['branches']),
                'listing_date':listing,'reason':'PRE_RELEASE_MIN30_TARGETED_HISTORY',
                'branch_detail':sorted(g['branch_detail'],key=lambda x:x['branch']),
                'publication_allowed':False,'research_only':True,'plan_version':VERSION})
    # Highest near-target probability first; avoid waste on chronic PER=0.
    tasks.sort(key=lambda t:(-max(x['baseline'] for x in t['branch_detail']),
                             min(x['shortfall'] for x in t['branch_detail']),t['market'],t['symbol']))
    return tasks,holds,pairs


def fingerprint(tasks, meta, official, legacy):
    official_fingerprint=[{'market':k[0],'symbol':k[1],'listing_date':v.get('listing_date')}
                          for k,v in sorted(official.items())]
    return digest_json({'version':VERSION,'tasks':tasks,'source':meta['input_sha256'],
                        'source_release':meta['source'],'master':official_fingerprint})


def freeze(root:Path,tasks,meta,official,legacy,holds,pairs):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    token=fingerprint(tasks,meta,official,legacy)
    path=root/'frozen_plan_v22.json'
    if path.exists():
        j=json.loads(path.read_text('utf-8'))
        if j.get('fingerprint')!=token:raise RuntimeError('immutable v22 plan drift; use a new versioned folder')
        return j
    # Existing v22 receipts without a plan would create an unsafe partial resume.
    if (root/'receipts').exists() and any((root/'receipts').glob('*.json')):
        raise RuntimeError('v22 receipts exist without a frozen plan')
    plan={'version':VERSION,'fingerprint':token,'tasks':tasks,
          'input_hashes':meta['input_sha256'],'source':meta['source'],
          'legacy_sha_verified':legacy['receipts_valid'], 'legacy_sha_invalid':legacy['receipts_invalid'],
          'hold_pairs':len(holds),'pairs_reviewed':len(pairs),'publication_allowed':False}
    base.atomic_json(path,plan)
    base.atomic_csv(root/'v22_pairs.csv',pairs,['market','symbol','branch','baseline_positive_months',
       'shortfall','status','historical_months','reason'])
    base.atomic_csv(root/'v22_tasks.csv',[
        {'task_id':base.task_id(t),'symbol':t['symbol'],'market':t['market'],'start_date':t['start_date'],
         'end_date':t['end_date'],'target_months':len(t['target_months']),
         'branches':','.join(t['branches'])} for t in tasks],
         ['task_id','symbol','market','start_date','end_date','target_months','branches'])
    base.atomic_json(root/'v21_reuse_index.json',{'status':'SHA_VERIFIED_READ_ONLY','count_valid':legacy['receipts_valid'],
        'count_invalid':legacy['receipts_invalid'],'prior_raw_positive_months':legacy['raw_positive_months'],
        'prior_raw_nonpositive_months':legacy['raw_nonpositive_months'], 'receipts':legacy['validated'],
        'note':'V21 receipts are preserved and are not copied into V22 output; no current-range refetch.'})
    return plan


def yield_report(root:Path,tasks:list,existing:dict,legacy:dict,run_stats=None):
    """Positive month-end candidates only in requested prehistory; never certifies PIT or official closing date."""
    gained=defaultdict(set)
    taskrows=[]
    for task in tasks:
        r=base.verify_receipt(Path(root),task)
        row={'task_id':base.task_id(task),'symbol':task['symbol'],'status':'PENDING_OR_ERROR' if r is None else r['status'],
             'rows':0 if r is None else r['rows'],'candidate_positive_months':0}
        if r and r['status']=='SUCCESS':
            payload=json.loads((Path(root)/'raw'/(base.task_id(task)+'.json')).read_bytes())
            by_month=defaultdict(list)
            for x in payload['data']:
                day=str(x.get('date',''))[:10];m=day[:7]
                if m not in task['target_months'] or day<task['listing_date'] or not task['start_date']<=day<=task['end_date']:continue
                by_month[m].append(x)
            for m,rows in by_month.items():
                item=max(rows,key=lambda x:x['date'])
                for branch in task['branches']:
                    if positive(item.get('PER' if branch=='pe' else 'PBR')):
                        gained[(task['market'],task['symbol'],branch)].add(m)
            row['candidate_positive_months']=sum(len(gained[(task['market'],task['symbol'],b)]) for b in task['branches'])
        taskrows.append(row)
    base.atomic_csv(Path(root)/'v22_task_status.csv',taskrows,['task_id','symbol','status','rows','candidate_positive_months'])
    gain_rows=[]
    for task in tasks:
        for q in task['branch_detail']:
            key=(task['market'],task['symbol'],q['branch'])
            n=len(gained[key])
            gain_rows.append({'market':key[0],'symbol':key[1],'branch':key[2],
                'existing_positive':q['baseline'],'new_candidate_positive_months':n,
                'combined_positive_precheck':q['baseline']+n, 'precheck_at_least_30':q['baseline']+n>=30,
                'model_ready':False,'publication_allowed':False})
    base.atomic_csv(Path(root)/'v22_valid_month_gain.csv',gain_rows,
       ['market','symbol','branch','existing_positive','new_candidate_positive_months','combined_positive_precheck','precheck_at_least_30','model_ready','publication_allowed'])
    positive_count=sum(len(x) for x in gained.values())
    succeeded=sum(1 for r in taskrows if r['status']=='SUCCESS')
    overall={'version':VERSION,'status':'RESEARCH_PRECHECK_NOT_MODEL_READY','plan_tasks':len(tasks),
        'tasks_success':succeeded,'tasks_pending':sum(1 for r in taskrows if r['status']=='PENDING_OR_ERROR'),
        'new_positive_month_candidate_count':positive_count,'legacy_receipts_sha_verified':legacy['receipts_valid'],
        'legacy_receipts_sha_invalid':legacy['receipts_invalid'],'run':run_stats or {},
        'publication_allowed':False,'source_pit_verified':False,
        'recommendation':('CONTINUE_BOUNDED' if positive_count>0 else 'CHECK_FIRST_BATCH_YIELD_BEFORE_EXPANDING'),
        'updated_at_utc':base.utc()}
    base.atomic_json(Path(root)/'00_run_summary_v22.json',overall)
    return overall