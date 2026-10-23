"""Valuation P1: immutable inventory-based raw label, period and source-lineage audit.

Research-only; no HTTP, no canonical writes, no source substitution, no publication.
A cross-source numerical match is NEVER a substitute for row-attached source evidence.
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
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = 'valuation-p1-source-lineage-v1.0.0'
RELEASE = 'release-0bbae8d9c1ca7d8d'
INVENTORY_SHA = 'f85fd1c16c286628e02d067088b0f9f473932596d83a098561537cc172bc376c'
P0_ZIP_MEMBER = 'P0_P1_實測報告/inventory.csv.gz'
P1_PAIR_MEMBER = '交叉驗證結果/unit_period_pairs.csv'
PAIR_STATUSES = ('VALUE_MISMATCH_REVIEW','AMBIGUOUS_SOURCE_OR_PREVIOUS_QUARTER')
ROW_FIELDS = ('market','symbol','fiscal_quarter','dataset','item_raw','source_id','value_raw')
# URLs point to later visible third-party mirrors. They are NOT the original API
# response and cannot independently prove canonical acquisition or revision.
EXTERNAL_CROSSCHECKS = {
 ('1103','2022Q4'): {
   'url':'https://tw.stock.yahoo.com/quote/1103.TW/balance-sheet',
   'kind':'PUBLIC_CURRENT_PAGE_WITH_HISTORICAL_TABLE',
   'unit':'TWD_THOUSAND',
   'values':{'total_assets':'36412314','total_liabilities':'14412887','total_equity':'21999427'},
   'first_publication':'NOT_PROVEN', 'scope':'NOT_PROVEN_FOR_CANONICAL'},
 ('1201','2022Q4'): {
   'url':'https://tw.stock.yahoo.com/news/%E5%85%AC%E5%91%8A-%E5%91%B3%E5%85%A8%E8%91%A3%E4%BA%8B%E6%9C%83%E9%80%9A%E9%81%8E111%E5%B9%B4%E5%BA%A6%E5%90%88%E4%BD%B5%E8%B2%A1%E5%8B%99%E5%A0%B1%E5%91%8A-094348507.html',
   'kind':'THIRD_PARTY_MIRROR_OF_2023_03_15_DISCLOSURE',
   'unit':'TWD_THOUSAND',
   'values':{'total_assets':'17608226','total_liabilities':'10375570'},
   'first_publication':'NOT_PROVEN', 'scope':'REPORT_DESCRIBED_AS_CONSOLIDATED_NOT_CANONICAL_ROW'},
}
MOPS_PROVIDER_TERM_URL='https://mopsfin.twse.com.tw/terms'
FINMIND_PROVIDER_DOC_URL='https://finmind.github.io/tutor/TaiwanMarket/Fundamental/'


def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()


def row_fingerprint(row:dict)->str:
    """Derived *inventory identity*, never call this original payload SHA."""
    src={x:str(row.get(x,'')) for x in ROW_FIELDS}
    return digest(json.dumps(src,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())


def to_decimal(v):
    try:
        d=Decimal(str(v));return d if d.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None


def fiscal_prior(q):
    if not re.fullmatch(r'\d{4}Q[1-4]',str(q)):return None
    y,qq=int(q[:4]),int(q[-1]);return (str(y-1)+'Q4') if qq==1 else (str(y)+'Q'+str(qq-1))


def normalized_concept(row):
    """Different economic statements do not become synonyms based on English words."""
    t=str(row.get('item_raw',''))
    if row.get('source_id')=='finmind' and row.get('dataset')=='income' and t=='TotalConsolidatedProfitForThePeriod':
        return 'OTHER_PROFIT_MEASURE_OR_COMPREHENSIVE_UNVERIFIED'
    return row.get('item_standard','')


def collapse_alias(rows:list[dict]):
    """Only equal-value, source-scoped CFO aliases are coalesced for comparison.

    Does not prove semantic equality, original publication, unit or scope.
    """
    if not rows:return None,'NO_ROWS'
    if len(rows)==1:return rows[0],'UNIQUE_RAW_FIELD'
    if all(r.get('dataset')=='cashflow' and r.get('source_id')=='finmind' and r.get('item_standard')=='cfo' for r in rows):
        values=[to_decimal(r.get('value_raw')) for r in rows]
        allowed={'CashFlowsFromOperatingActivities','NetCashInflowFromOperatingActivities'}
        if None not in values and len(set(values))==1 and {r.get('item_raw') for r in rows}==allowed and len(rows)==2:
            return next(r for r in rows if r['item_raw']=='CashFlowsFromOperatingActivities'),'EQUAL_CFO_ALIASES_CANDIDATE'
        return None,'CFO_ALIAS_VALUE_OR_FIELD_CONFLICT'
    return None,'MULTIPLE_SOURCE_ROWS_NO_ARBITRARY_CHOICE'


def proof_gate(row:dict,proof:dict|None,*,source_payload:bytes|None=None,
               disclosure_payload:bytes|None=None,as_of=None):
    """Two independent gates: accounting arithmetic and historical as-of.

    Only byte-backed, row-specific source evidence can activate a gate. The
    external display URLs in this module are NOT such proof.
    """
    result={'row_fingerprint':row_fingerprint(row),'arithmetic_ready':False,
            'historical_asof_ready':False,'reason':'PROOF_MISSING',
            'publication_allowed':False,'normalized_value_twd':None}
    if not isinstance(proof,dict):return result
    checks=(
      (proof.get('row_fingerprint')==result['row_fingerprint'],'ROW_HASH_MISMATCH'),
      (bool(re.fullmatch(r'[0-9a-f]{64}',str(proof.get('original_payload_sha256','')))),'ORIGINAL_PAYLOAD_SHA_MISSING'),
      (proof.get('row_anchor_verified') is True,'RAW_FIELD_ANCHOR_UNVERIFIED'),
      (proof.get('accounting_scope') in ('CONSOLIDATED','SEPARATE','INDIVIDUAL'),'SCOPE_UNVERIFIED'),
      (proof.get('period_basis') in ('INSTANT','YTD','QUARTER','ANNUAL'),'PERIOD_UNVERIFIED'),
      (proof.get('unit_basis') in ('TWD','TWD_THOUSAND','TWD_MILLION','TWD_PER_SHARE'),'UNIT_UNVERIFIED'),
      (proof.get('fiscal_quarter')==row.get('fiscal_quarter'),'QUARTER_MISMATCH'),
      (proof.get('source_id')==row.get('source_id'),'SOURCE_MISMATCH'),
      (bool(proof.get('source_revision_id')),'REVISION_MISSING'),
      (proof.get('currency')=='TWD','CURRENCY_UNVERIFIED'),
    )
    for valid,reason in checks:
        if not valid:result['reason']=reason;return result
    ds=row.get('dataset','')
    if (ds=='balance' and proof['period_basis']!='INSTANT') or (ds in ('income','cashflow') and proof['period_basis']=='INSTANT'):
        result['reason']='INCOMPATIBLE_ACCOUNTING_PERIOD';return result
    val=to_decimal(row.get('value_raw'))
    if val is None:result['reason']='VALUE_NOT_NUMERIC';return result
    if row.get('item_standard') in ('basic_eps','diluted_eps'):
        if proof['unit_basis']!='TWD_PER_SHARE':result['reason']='EPS_UNIT_INCOMPATIBLE';return result
        mul=Decimal(1)
    else:
        mul={'TWD':Decimal(1),'TWD_THOUSAND':Decimal(1000),'TWD_MILLION':Decimal(1000000)}.get(proof['unit_basis'])
        if mul is None:result['reason']='AMOUNT_UNIT_INCOMPATIBLE';return result
    # A caller-supplied 64-char hex hash or boolean flag alone is NOT evidence.
    # Bind to downloaded original bytes and exact source API row; require a
    # source-specific parser/adapter for all other formats, including MOPS HTML.
    if not isinstance(source_payload,bytes) or digest(source_payload)!=proof['original_payload_sha256']:
        result['reason']='ORIGINAL_BYTES_HASH_NOT_VERIFIED';return result
    if row.get('source_id')!='finmind':
        result['reason']='MOPS_RAW_ROW_ADAPTER_NOT_VERIFIED';return result
    try:
        payload=json.loads(source_payload)
        records=payload['data'] if isinstance(payload,dict) else []
        quarter_end={'1':'03-31','2':'06-30','3':'09-30','4':'12-31'}[str(row['fiscal_quarter'])[-1]]
        expected_date=str(row['fiscal_quarter'])[:4]+'-'+quarter_end
        same=[r for r in records if isinstance(r,dict) and
              str(r.get('stock_id'))==str(row.get('symbol')) and
              str(r.get('type'))==str(row.get('item_raw')) and
              str(r.get('date'))==expected_date and
              to_decimal(r.get('value'))==val]
    except (ValueError,KeyError,TypeError):
        same=[]
    if len(same)!=1:
        result['reason']='ORIGINAL_FINMIND_ROW_ANCHOR_UNVERIFIED';return result
    result['normalized_value_twd']=str(val*mul)
    result['arithmetic_ready']=True
    result['reason']='ARITHMETIC_ONLY_PIT_MISSING'
    # No inferred times and no fetch timestamp allowed in this step.
    pub=proof.get('first_publication_utc');ev=proof.get('original_disclosure_sha256')
    if not (isinstance(pub,str) and pub.endswith('Z') and re.fullmatch(r'[0-9a-f]{64}',str(ev or ''))):return result
    if not isinstance(disclosure_payload,bytes) or digest(disclosure_payload)!=ev:
        result['reason']='ORIGINAL_DISCLOSURE_BYTES_UNVERIFIED';return result
    if proof.get('disclosure_kind')!='EXCHANGE_OR_ISSUER_ORIGINAL_DISCLOSURE':
        result['reason']='DISCLOSURE_AUTHORITY_UNVERIFIED';return result
    if as_of and pub>as_of:result['reason']='PUBLISHED_AFTER_ASOF';return result
    result['historical_asof_ready']=True
    result['reason']='ACCOUNTING_AND_ASOF_READY_RESEARCH_ONLY'
    return result


def evidence_for_pair(pair,source_rows,prior_rows):
    sym,q,ds,item=pair['symbol'],pair['fiscal_quarter'],pair['dataset'],pair['item_standard']
    src=source_rows.get((pair['market'],sym,q,ds,item),[])
    mops=[r for r in src if r['source_id']=='mops']
    finmind=[r for r in src if r['source_id']=='finmind']
    prior=[r for r in prior_rows.get((pair['market'],sym,fiscal_prior(q),ds,item),[]) if r['source_id']=='mops']
    reasons=[]
    if len(mops)!=1:reasons.append('MOPS_DUPLICATE_OR_MISSING')
    if len(finmind)!=1:
        alias_row,alias_reason=collapse_alias(finmind)
        if alias_reason=='EQUAL_CFO_ALIASES_CANDIDATE':reasons.append('EQUAL_CFO_ALIASES_NOT_TWO_INDEPENDENT_REPORTS')
        elif item=='net_income' and {r['item_raw'] for r in finmind}=={'IncomeAfterTaxes','TotalConsolidatedProfitForThePeriod'}:
            reasons.append('FINMIND_TWO_DIFFERENT_PROFIT_CONCEPTS_MAPPED_TO_ONE')
        else:reasons.append('FINMIND_DUPLICATE_OR_DIFFERENT_CONCEPTS')
    if ds!='balance' and not q.endswith('Q1') and len(prior)!=1:
        reasons.append('SAME_YEAR_PRIOR_QUARTER_MISSING_OR_AMBIGUOUS')
    if pair['status']=='VALUE_MISMATCH_REVIEW':reasons.append('SOURCE_VALUES_CONFLICT_ACROSS_VERSIONS')
    matched=[]
    c=EXTERNAL_CROSSCHECKS.get((sym,q),{}) if ds=='balance' else {}
    for r in mops:
        x=c.get('values',{}).get(item)
        if x is not None and to_decimal(r['value_raw'])==to_decimal(x):matched.append('THIRD_PARTY_MIRROR_MOPS_VALUE_MATCH')
    return dict(symbol=sym,market=pair['market'],fiscal_quarter=q,dataset=ds,item_standard=item,
       prior_status=pair['status'],reasons=';'.join(reasons),
       mops_count=len(mops),finmind_count=len(finmind),prior_mops_count=len(prior),
       mops_labels='|'.join(r['item_raw'] for r in mops),
       finmind_labels='|'.join(r['item_raw'] for r in finmind),
       mops_amounts='|'.join(r['value_raw'] for r in mops),
       finmind_amounts='|'.join(r['value_raw'] for r in finmind),
       mops_inventory_row_ids='|'.join(row_fingerprint(r) for r in mops),
       finmind_inventory_row_ids='|'.join(row_fingerprint(r) for r in finmind),
       direct_raw_payload_hashes_present=False,direct_response_headers_present=False,
       statement_scope_verified=False,revision_matched=False,historical_pit_verified=False,
       external_crosscheck_url=c.get('url',''),external_crosscheck_type=c.get('kind',''),
       external_crosscheck_result='|'.join(matched) if matched else 'NO_EXACT_EXTERNAL_CROSSCHECK',
       external_is_original_raw=False,
       candidate_factor_status='BLOCKED_SOURCE_PROVENANCE',publication_allowed=False)


def csv_out(path, rows):
    if not rows:raise ValueError('NO_ROWS_TO_WRITE')
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)


def execute(p0zip:Path,p1zip:Path,out:Path):
    if out.resolve().is_relative_to(p0zip.resolve()) or out.resolve().is_relative_to(p1zip.resolve()):
        raise ValueError('NO_INPUT_OVERWRITE')
    z0=zipfile.ZipFile(p0zip);z1=zipfile.ZipFile(p1zip)
    frozen=z0.read(P0_ZIP_MEMBER)
    if digest(frozen)!=INVENTORY_SHA:raise ValueError('PINNED_INVENTORY_MISMATCH')
    pairs=list(csv.DictReader(io.StringIO(z1.read(P1_PAIR_MEMBER).decode('utf-8-sig'))))
    if len(pairs)!=504:raise ValueError('EXPECTED_504_PAIRS_MISMATCH')
    targets={(p['market'],p['symbol'],p['fiscal_quarter'],p['dataset'],p['item_standard']) for p in pairs}
    wanted=set(targets)
    for p in pairs:
        q=fiscal_prior(p['fiscal_quarter'])
        if q:wanted.add((p['market'],p['symbol'],q,p['dataset'],p['item_standard']))
    selected=collections.defaultdict(list)
    cnt=0
    for row in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(frozen)),encoding='utf-8-sig')):
        cnt+=1
        k=(row['market'],row['symbol'],row['fiscal_quarter'],row['dataset'],row['item_standard'])
        if k in wanted and row['source_id'] in ('mops','finmind'):
            selected[k].append(row)
    if cnt!=1181442:raise ValueError('INVENTORY_ROW_COUNT_MISMATCH')
    exception=[evidence_for_pair(p,selected,selected) for p in pairs if p['status'] in PAIR_STATUSES]
    if len(exception)!=113:raise ValueError('EXPECTED_113_EXCEPTIONS_MISMATCH')
    # All existing records are still blocked. Numeric match and external mirror
    # do not prove source byte hash, declaration revision, accounting scope, PIT.
    gate=[]
    for pair in pairs:
        key=(pair['market'],pair['symbol'],pair['fiscal_quarter'],pair['dataset'],pair['item_standard'])
        rr=selected[key]
        for row in rr:
            test=proof_gate(row,None)
            gate.append(dict(symbol=row['symbol'],fiscal_quarter=row['fiscal_quarter'],dataset=row['dataset'],
             item_raw=row['item_raw'],source_id=row['source_id'],
             inventory_row_id=test['row_fingerprint'],unit_candidate='NOT_ATTESTED',
             period_candidate='NOT_ATTESTED',source_payload_sha256='',
             accounting_scope='UNKNOWN',source_revision_id='',
             arithmetic_ready=test['arithmetic_ready'],historical_asof_ready=test['historical_asof_ready'],
             reason=test['reason'],publication_allowed=False))
    out.mkdir(parents=True,exist_ok=True)
    csv_out(out/'exception_evidence.csv',exception)
    csv_out(out/'source_record_links.csv',gate)
    kinds=collections.Counter()
    for ex in exception:
        for r in ex['reasons'].split(';'):
            if r:kinds[r]+=1
    # Every numeric mismatch has matched asset/liability delta, not independent
    # proof of a restatement. No attempt to synthesize an official revision ID.
    deltas=[]
    for sym in ('1103','1201'):
        pp=[p for p in pairs if p['symbol']==sym and p['fiscal_quarter']=='2022Q4' and p['dataset']=='balance']
        for p in pp:
            d=to_decimal(p['finmind_reported'])-to_decimal(p['mops_reported'])*Decimal(1000)
            deltas.append(dict(symbol=sym,item_standard=p['item_standard'],
                    mops_raw_thousand=p['mops_reported'],finmind_raw_twd=p['finmind_reported'],
                    finmind_minus_mops_twd=str(d),source_revision_explanation='UNKNOWN',
                    external_evidence_url=EXTERNAL_CROSSCHECKS[(sym,'2022Q4')]['url'],
                    publication_allowed=False))
    csv_out(out/'source_version_deltas.csv',deltas)
    summary=dict(version=VERSION,input_release=RELEASE,inventory_sha256=digest(frozen),
          financial_rows_checked=cnt,old_comparison_groups=len(pairs),
          exceptions=len(exception),exception_reasons=dict(sorted(kinds.items())),
          linked_inventory_rows=len(gate),raw_payloads_exactly_linked=0,
          arithmetic_ready_rows=0,historical_asof_ready_rows=0,
          source_unit_verified_rows=0,source_period_verified_rows=0,statement_scope_verified_rows=0,
          status='PARTIAL_SOURCE_EVIDENCE',publication_allowed=False,
          evidence_disclaimer='External mirrored pages prove displayed values/format, not original request payload, revision, row scope or historical PIT.',
          finmind_doc=FINMIND_PROVIDER_DOC_URL,mops_documented_period=MOPS_PROVIDER_TERM_URL)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'收斂紀錄.md').write_text('''# Valuation P1｜113 組例外來源證據鏈與安全因子輸入

- 固定來源 release：`release-0bbae8d9c1ca7d8d`；完整 1,181,442 rows 來源清冊讀回，與上期 504 組 cross-source pairing。
- 4 筆數值差異都在 1103／1201 2022Q4：各家公司資產與負債差額相同、權益差額為 0。可能是版本差異，**尚未取得原始 payload／revision ID 證據，不得宣稱已證實重編原因**。
- `TotalConsolidatedProfitForThePeriod` 與 `IncomeAfterTaxes` 金額不同，不再視為相同淨利概念；舊 v2 mapping 待拆分確認 `origin_name`。
- `CashFlowsFromOperatingActivities` 與 `NetCashInflowFromOperatingActivities` 在候選 45 組具有相同金額，可作單一候選排除重複計數，但未認證來源與期間。
- 2022Q4 無同年 2022Q3 MOPS 前季報表，不得跨年差分；EPS 不差分。
- 目前來源清冊無原始 request id、response bytes SHA、財報版本、合併／個體明示及首次發布證據，研究 arithmetic gate 和 historical PIT gate **均為 0**。第三方鏡像不能取代此證據。
- 本模組未發出 HTTP，未變更 canonical/CURRENT、Registry、Risk ACTIVE 或訓練輸入。`publication_allowed=false`。
''',encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--p0zip',type=Path,required=True);p.add_argument('--p1zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv);print(json.dumps(execute(a.p0zip,a.p1zip,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
