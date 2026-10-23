"""Valuation P1 unit/period cross-source evidence from frozen audited inventory.

The source never claims unit or period certification. Numeric agreements establish
cohort-scoped corroboration, NOT authoritative per-record unit/PIT verification.
No canonical updates, fetching, model training or registry mutation.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import zipfile
from pathlib import Path

VERSION = 'valuation-unit-period-evidence-v1.0.0'
BALANCE_ITEMS = {'total_assets', 'total_liabilities', 'total_equity'}
FLOW_ITEMS = {'revenue', 'net_income', 'cfo'}
REQUIRED_COLUMNS = {'market', 'symbol', 'dataset', 'fiscal_quarter', 'item_raw',
                    'item_standard', 'value_raw', 'source_id', 'unit_basis',
                    'period_basis', 'published_at', 'statement_scope'}
TOLERANCE = 0.00001   # relative; candidate consistency, NOT a trust decision


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def as_number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def prior_quarter(quarter):
    if len(quarter) != 6 or quarter[4] != 'Q' or quarter[5] not in '1234':
        return None
    year, q = int(quarter[:4]), int(quarter[5])
    if q == 1:
        return f'{year-1}Q4'
    return f'{year}Q{q-1}'


def verified_source_metadata(row):
    """Check only row-specific source metadata, not values or generic source docs."""
    return (row.get('unit_basis') in ('TWD', 'TWD_ONES', 'TWD_THOUSAND', 'TWD_MILLION')
            and row.get('period_basis') in ('INSTANT', 'QUARTER', 'YTD', 'ANNUAL')
            and row.get('statement_scope') in ('CONSOLIDATED', 'SEPARATE', 'INDIVIDUAL')
            and bool(row.get('published_at')))


def add_inventory(rows):
    """Restrict to unique exact-mapped aggregate rows; don't merge aliased values.

    A mismatch/duplicate is an exception, not an arbitrary first/last value.
    """
    selected = collections.defaultdict(list)
    count = 0
    source_counts = collections.Counter()
    blockers = collections.Counter()
    for row in rows:
        count += 1
        src = str(row.get('source_id', '')).lower()
        source_counts[src] += 1
        if not verified_source_metadata(row):
            for name in ('unit_basis', 'period_basis', 'statement_scope', 'published_at'):
                if (name == 'unit_basis' and row.get(name) not in ('TWD', 'TWD_ONES', 'TWD_THOUSAND', 'TWD_MILLION') or
                    name == 'period_basis' and row.get(name) not in ('INSTANT', 'QUARTER', 'YTD', 'ANNUAL') or
                    name == 'statement_scope' and row.get(name) not in ('CONSOLIDATED','SEPARATE','INDIVIDUAL') or
                    name == 'published_at' and not row.get(name)):
                    blockers[(src, name)] += 1
        ds = row.get('dataset', '')
        item = row.get('item_standard', '')
        q = row.get('fiscal_quarter', '')
        if src not in ('finmind','mops') or not prior_quarter(q):
            continue
        if not ((ds == 'balance' and item in BALANCE_ITEMS) or
                (ds == 'income' and item in ('revenue', 'net_income')) or
                (ds == 'cashflow' and item == 'cfo')):
            continue
        val = as_number(row.get('value_raw'))
        if val is None:
            continue
        key = (row.get('market',''),row.get('symbol',''),q,ds,item,src)
        selected[key].append((val, row.get('item_raw','')))
    return selected, count, source_counts, blockers


def compare(rows):
    selected,total,source_counts,blockers=add_inventory(rows)
    result=[];duplicate_keys=sum(len(v)>1 for v in selected.values())
    for key, mops_values in sorted(selected.items()):
        market,sym,quarter,ds,item,src=key
        if src!='mops':
            continue
        other=(market,sym,quarter,ds,item,'finmind')
        if other not in selected:
            continue
        fm_values=selected[other]
        q=int(quarter[-1]); prior=prior_quarter(quarter)
        prior_mops=selected.get((market,sym,prior,ds,item,'mops'),[])
        if ds=='balance':
            method='BALANCE_INSTANT'
            valid=bool(len(mops_values)==len(fm_values)==1)
            mops_value=mops_values[0][0] if valid else None
        elif q==1:
            method='FLOW_Q1_DIRECT'
            valid=bool(len(mops_values)==len(fm_values)==1)
            mops_value=mops_values[0][0] if valid else None
        else:
            method='FLOW_YTD_DIFFERENCE'
            valid=bool(len(mops_values)==len(fm_values)==len(prior_mops)==1)
            mops_value=mops_values[0][0]-prior_mops[0][0] if valid else None
        fm_value=fm_values[0][0] if len(fm_values)==1 else None
        if not valid:
            status='AMBIGUOUS_SOURCE_OR_PREVIOUS_QUARTER'
            ratio=None
        elif not mops_value:
            status='ZERO_DENOMINATOR'
            ratio=None
        else:
            ratio=fm_value/mops_value
            status=('CONSISTENT_1000X_COHORT_ONLY'
                    if abs(ratio/1000.0-1) <= TOLERANCE else 'VALUE_MISMATCH_REVIEW')
        result.append(dict(market=market,symbol=sym,fiscal_quarter=quarter,dataset=ds,
             item_standard=item,method=method,mops_reported=mops_values[0][0] if len(mops_values)==1 else '',
             mops_quarter_component=mops_value if valid else '',finmind_reported=fm_value if fm_value is not None else '',
             finmind_over_mops_component_ratio=ratio if ratio is not None else '',
             status=status,unit_inference='MOPS_THOUSANDS_FINMIND_ONES_HYPOTHESIS' if status=='CONSISTENT_1000X_COHORT_ONLY' else 'NOT_INFERRED',
             period_inference=('MOPS_YTD_FINMIND_QUARTER_HYPOTHESIS' if method=='FLOW_YTD_DIFFERENCE' and status=='CONSISTENT_1000X_COHORT_ONLY' else 'NOT_INFERRED'),
             source_unit_verified=False,source_period_verified=False,historical_pit_verified=False,
             publication_allowed=False))
    status_counts=collections.Counter(x['status'] for x in result)
    by_item=collections.defaultdict(list)
    for x in result:by_item[(x['dataset'],x['item_standard'],x['method'])].append(x)
    cohorts=[]
    for (ds,item,method),rr in sorted(by_item.items()):
        valid=[float(v['finmind_over_mops_component_ratio']) for v in rr if v['finmind_over_mops_component_ratio']!='']
        cohorts.append(dict(dataset=ds,item_standard=item,method=method,total_pairs=len(rr),
             consistent_1000x=sum(x['status']=='CONSISTENT_1000X_COHORT_ONLY' for x in rr),
             exceptions=sum(x['status']!='CONSISTENT_1000X_COHORT_ONLY' for x in rr),
             median_ratio=statistics.median(valid) if valid else '',
             source_metadata_status='NOT_VERIFIED',pit_status='NOT_VERIFIED'))
    summary={'audit_version':VERSION,'rows_examined':total,'source_counts':dict(source_counts),
             'metadata_blockers':{f'{a}/{b}':n for (a,b),n in sorted(blockers.items())},
             'candidate_pairs':len(result),'status_counts':dict(status_counts),
             'duplicate_source_keys_excluded':duplicate_keys,
             'source_unit_verified_rows':0,'source_period_verified_rows':0,
             'historical_pit_verified_rows':0,'publication_allowed':False,
             'scope':'ONLY_OVERLAPPING_EXACT_MAPPED_SOURCE_COHORTS',
             'limitations':['1000X ratios are cross-source corroboration, not row-level unit evidence',
                 'MOPS unit header/raw response is not attached to canonical row',
                 'FinMind financial date is a fiscal period end, not announcement timestamp',
                 'Income/cashflow YTD differencing only creates candidate quarter flow; do not diff EPS',
                 'No conversion written to canonical or trainable factor store']}
    return summary,result,cohorts


def read_inventory(fp):
    with gzip.open(fp,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not REQUIRED_COLUMNS.issubset(set(reader.fieldnames or [])):
            raise ValueError('INVENTORY_SCHEMA_MISMATCH')
        yield from reader


def csv_dump(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)


def run(inventory_path,output,*,expected_inventory_sha256=None):
    inventory_path=Path(inventory_path);output=Path(output)
    if expected_inventory_sha256:
        actual=hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        if actual != expected_inventory_sha256:
            raise ValueError('PINNED_INVENTORY_SHA256_MISMATCH')
    summary,pairs,cohorts=compare(read_inventory(inventory_path))
    summary['input_inventory_gzip_sha256']=hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    (output/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    csv_dump(output/'unit_period_pairs.csv',pairs,list(pairs[0]) if pairs else ['status'])
    csv_dump(output/'unit_period_cohorts.csv',cohorts,list(cohorts[0]) if cohorts else ['dataset'])
    (output/'P1_單位期間驗證收據.md').write_text(
       '# Valuation P1｜單位／會計期間交叉驗證\n\n'
       '研究限定；無補收、訓練、canonical/Registry 修改。\n\n'
       f'- 原始財報 rows：{summary["rows_examined"]:,}；比較組合：{summary["candidate_pairs"]:,}。\n'
       f'- 1,000 倍交叉一致：{summary["status_counts"].get("CONSISTENT_1000X_COHORT_ONLY",0):,} 組；'
       f'不一致／歧義：{summary["candidate_pairs"]-summary["status_counts"].get("CONSISTENT_1000X_COHORT_ONLY",0):,} 組。\n'
       '- MOPS Balance 候選為仟元、FinMind 為元；損益表營收有 MOPS 累季、FinMind 單季交叉證據。現金流不具足夠的唯一配對證據，維持待核對；以上均非整個來源的自動認證。\n'
       '- EPS 不進行累季差分；金融業需個別會計模板。\n'
       '- 缺來源逐列單位／合併別／期間標記及公告首次時間，不准提升為 UNIT_VERIFIED／PIT_VERIFIED。\n'
       '- 文件中的一致性是有界數值對照，不代表所有股票、全部 318 個原始科目完成驗證。\n'
       '- `publication_allowed=false`。\n',encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--inventory-gz',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--expected-sha256',default=None)
    a=p.parse_args(argv)
    s=run(a.inventory_gz,a.out,expected_inventory_sha256=a.expected_sha256)
    print(json.dumps(s,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
