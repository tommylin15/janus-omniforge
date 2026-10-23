"""Janus Valuation financial item label mapping and audited existing-release inventory.
Research-only. Identifying a raw item does NOT certify its units, scope, period
basis, historical PIT, corporate identity, or suitability for financial factors.

Runs only on frozen CURRENT/manifest references. Never makes network calls or
writes canonical, no retraining and publication_allowed=False.
"""
from __future__ import annotations
import collections
import csv
import gzip
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Iterable

MAPPING_VERSION='valuation-financial-label-v2.0.0'
# Dataset-specific exact synonyms; no fuzzy matches and no substring fallback.
# Multiple raw labels mapping to one standard target are preserved separately.
RAW_ALIASES={
 'income':{
  'revenue':['營業收入','Revenue'],
  'cost_of_goods_sold':['營業成本','CostOfGoodsSold'],
  'gross_profit':['營業毛利（毛損）淨額','GrossProfit'],
  'gross_profit_before_adjustment':['營業毛利（毛損）'],
  'operating_profit':['營業利益（損失）','營業利益','OperatingIncome'],
  'pretax_income':['稅前淨利（淨損）','繼續營業單位稅前淨利（淨損）','繼續營業單位稅前損益','PreTaxIncome'],
  'net_income':['本期淨利（淨損）','本期稅後淨利（淨損）','IncomeAfterTaxes','TotalConsolidatedProfitForThePeriod'],
  'parent_net_income':['淨利（淨損）歸屬於母公司業主','淨利（損）歸屬於母公司業主'],
  'basic_eps':['基本每股盈餘（元）','EPS'],
  'diluted_eps':['稀釋每股盈餘（元）'],
  'interest_expense':['利息費用','InterestExpense'],
  'rd_expense':['研究發展費用','研究及發展費用','ResearchAndDevelopmentExpenses'],
 },
 'balance':{
  'total_assets':['資產總計','資產總額','TotalAssets','Assets'],
  'total_liabilities':['負債總計','負債總額','Liabilities'],
  'total_equity':['權益總計','權益總額','Equity'],
  'parent_equity':['歸屬於母公司業主之權益合計','歸屬於母公司業主權益合計','歸屬於母公司業主之權益','EquityAttributableToOwnersOfParent'],
  'cash_and_equivalents':['現金及約當現金','CashAndCashEquivalents'],
  'current_assets':['流動資產','CurrentAssets'],
  'current_liabilities':['流動負債','CurrentLiabilities'],
  'short_term_debt':['短期借款','ShortTermBorrowings'],
  'long_term_debt':['長期借款','LongTermBorrowings'],
  'current_portion_debt':['一年或一營業週期內到期長期負債','一年內到期長期借款'],
  'bonds_payable':['應付公司債','應付債券'],
  'lease_liabilities':['租賃負債','LeaseLiabilities'],
  'intangibles':['無形資產','無形資產－淨額','IntangibleAssets'],
  'goodwill':['商譽','Goodwill'],
  'receivables':['應收帳款淨額','應收款項－淨額','AccountsReceivableNet'],
  'inventory':['存貨','Inventories'],
 },
 'cashflow':{
  'cfo':['營業活動之淨現金流入（流出）','CashFlowsFromOperatingActivities','NetCashInflowFromOperatingActivities'],
  'capex':['購置不動產、廠房及設備','購置不動產廠房及設備'],
  'depreciation':['折舊費用','Depreciation'],
  'amortization':['攤銷費用','AmortizationExpense'],
 }
}
# Explicitly avoid treating the source-provided ratio/percentage suffix as an amount.
LOOKUP={(ds,alias):target for ds,groups in RAW_ALIASES.items() for target,aliases in groups.items() for alias in aliases}
assert len(LOOKUP)==sum(len(names) for groups in RAW_ALIASES.values() for names in groups.values()),'DUPLICATE_MAPPING_ALIAS'
CORE={
 'income':['revenue','cost_of_goods_sold','gross_profit','operating_profit','pretax_income','net_income','parent_net_income','basic_eps','diluted_eps'],
 'balance':['total_assets','total_liabilities','total_equity','parent_equity','cash_and_equivalents','current_assets','current_liabilities'],
 'cashflow':['cfo']}
OPTIONAL={
 'income':['interest_expense','rd_expense'],
 'balance':['short_term_debt','long_term_debt','current_portion_debt','bonds_payable','lease_liabilities','intangibles','goodwill','receivables','inventory'],
 'cashflow':['capex','depreciation','amortization']}

def mapping_label(dataset:str,raw:str)->tuple[str,str]:
    if raw.endswith('_per'):return '', 'DERIVED_SOURCE_PERCENTAGE_NOT_AMOUNT'
    item=LOOKUP.get((dataset,raw),'')
    return item, ('LABEL_MATCH_ONLY' if item else 'RAW_UNMAPPED_REVIEW')

def finite(value)->bool:
    try:return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError,OverflowError):return False

def disposition(*,mapped:bool,value,unit_basis,period_basis,published_at,statement_scope=None):
    if not finite(value):return 'MAPPING_REQUIRED','VALUE_NON_NUMERIC_OR_MISSING'
    if not mapped:return 'MAPPING_REQUIRED','RAW_ITEM_MAPPING_PENDING'
    # No source in this canonical version exposes verified scope/revisions/PIT.
    # Distinguish semantic mapping from all required data contract checks.
    if unit_basis not in ('TWD','TWD_THOUSAND','TWD_MILLION','TWD_ONES','CURRENCY_VERIFIED'):
        return 'MAPPING_REQUIRED','UNIT_BASIS_UNVERIFIED'
    if period_basis not in ('INSTANT','QUARTER','YTD','ANNUAL'):
        return 'MAPPING_REQUIRED','PERIOD_BASIS_UNVERIFIED'
    if statement_scope not in ('CONSOLIDATED','SEPARATE','INDIVIDUAL'):
        return 'MAPPING_REQUIRED','STATEMENT_SCOPE_UNVERIFIED'
    if published_at is None:return 'DERIVABLE','HISTORICAL_PIT_UNVERIFIED'
    return 'DERIVABLE','MAPPING_METADATA_OK_PIT_REQUIRES_PROVENANCE_REVIEW'

def audit_financial_rows(rows:Iterable[dict],output:Path,*,source_release:str,source_manifest_sha256:str,source_current_sha256:str,include_detail=True):
    """Consume flat existing canonical financial rows. No invented timestamps/units.
    Each row keys: market,symbol,dataset,fiscal_quarter,item,value,source_id,unit_basis,
    period_basis,published_at,observed_at[,historical_pit,statement_scope].
    """
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    inv_cols=['market','symbol','dataset','statement_type','fiscal_quarter','fiscal_year','period','item_raw','item_standard','value_raw','value_parseable','statement_scope','period_basis','unit_basis','currency','source_id','published_at','first_observed_at','historical_pit','mapping_version','mapping_status','classification','reason']
    inv_file=output/'inventory.csv.gz'
    fout=gzip.open(inv_file,'wt',encoding='utf-8-sig',newline='') if include_detail else None
    writer=csv.DictWriter(fout,fieldnames=inv_cols) if fout else None
    if writer:writer.writeheader()
    summaries=collections.Counter();by_raw=collections.Counter();symbol_period=collections.defaultdict(set)
    # Dataset/market/quarter item coverage at the source record level, not PIT verified.
    field_symbol=collections.defaultdict(set);mapped_key=collections.defaultdict(list)
    errors=[];n=0;seen=collections.Counter();srcs=collections.Counter();units=collections.Counter();periods=collections.Counter();publish=0
    try:
        for r in rows:
            ds=str(r.get('dataset') or '');raw=str(r.get('item') or '')
            if ds not in CORE:continue
            market=str(r.get('market') or '');sym=str(r.get('symbol') or '');quarter=str(r.get('fiscal_quarter') or '')
            standard,mapping_status=mapping_label(ds,raw)
            klass,reason=disposition(mapped=bool(standard),value=r.get('value'),unit_basis=r.get('unit_basis'),period_basis=r.get('period_basis'),published_at=r.get('published_at'),statement_scope=r.get('statement_scope'))
            source=str(r.get('source_id') or 'UNKNOWN')
            value=r.get('value');val_valid=finite(value)
            n+=1;srcs[source]+=1;units[str(r.get('unit_basis') or 'UNKNOWN')]+=1;periods[str(r.get('period_basis') or 'UNKNOWN')]+=1
            publish+=r.get('published_at') is not None
            key=(market,sym,ds,quarter)
            symbol_period[(market,ds,quarter)].add(sym)
            if val_valid and standard:field_symbol[(market,ds,quarter,standard)].add(sym)
            by_raw[(ds,raw,source,mapping_status,standard,klass,reason)]+=1
            summaries[(ds,klass)]+=1
            seen[(market,sym,ds,quarter,raw,source)]+=1
            if standard and val_valid:
                mapped_key[(market,sym,ds,quarter,standard)].append((raw,source,value))
            if writer:
                writer.writerow({'market':market,'symbol':sym,'dataset':ds,'statement_type':ds,'fiscal_quarter':quarter,
                   'fiscal_year':quarter[:4] if len(quarter)==6 else '', 'period':quarter,
                   'item_raw':raw,'item_standard':standard,'value_raw':value,
                   'value_parseable':val_valid,'statement_scope':r.get('statement_scope') or 'UNKNOWN',
                   'period_basis':r.get('period_basis') or 'UNKNOWN','unit_basis':r.get('unit_basis') or 'UNKNOWN',
                   'currency':r.get('currency') or 'UNKNOWN','source_id':source,
                   'published_at':r.get('published_at') or '', 'first_observed_at':r.get('observed_at') or '',
                   'historical_pit':r.get('historical_pit') or 'NOT_VERIFIED',
                   'mapping_version':MAPPING_VERSION,'mapping_status':mapping_status,'classification':klass,'reason':reason})
    finally:
        if fout:fout.close()
    def output_csv(name,rows,headers):
        with (output/name).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
    audits=[dict(dataset=ds,item_raw=raw,source_id=src,mapping_status=ms,item_standard=std or '',classification=cl,reason=reason,rows=count)
            for (ds,raw,src,ms,std,cl,reason),count in sorted(by_raw.items())]
    output_csv('financial_mapping_audit.csv',audits,['dataset','item_raw','source_id','mapping_status','item_standard','classification','reason','rows'])
    coverage=[];gaps=[]
    for (market,ds,quarter),universe in sorted(symbol_period.items()):
        den=len(universe)
        for standard in CORE[ds]+OPTIONAL[ds]:
            actual=field_symbol.get((market,ds,quarter,standard),set())
            coverage.append(dict(market=market,dataset=ds,period=quarter,item_standard=standard,
                  symbols_with_raw=len(actual),symbols_in_financial_dataset=den,raw_coverage_ratio=round(len(actual)/den,6),
                  usable_symbols=0,usable_coverage_ratio=0,
                  unit_status='NOT_VERIFIED',period_basis_status='NOT_VERIFIED',statement_scope_status='NOT_VERIFIED',pit_status='PIT_UNVERIFIED',
                  denominator_basis='EXISTING_RELEASE_FINANCIAL_DATASET_SYMBOLS_ONLY'))
            for sym in sorted(universe):
                exists=sym in actual
                gaps.append(dict(market=market,symbol=sym,dataset=ds,period=quarter,item_standard=standard,
                  priority='P1' if standard in CORE[ds] else 'P2',classification='MAPPING_REQUIRED' if exists else 'FETCH_REQUIRED',
                  reason='RAW_PRESENT_METADATA_UNVERIFIED' if exists else 'NO_MATCHED_RAW_ITEM_IN_RELEASE_CHECK_UNMAPPED_LABELS_BEFORE_FETCH',
                  source='CURRENT' if exists else 'SOURCE_NOT_SELECTED',estimated_http_requests=0))
    output_csv('field_coverage.csv',coverage,['market','dataset','period','item_standard','symbols_with_raw','symbols_in_financial_dataset','raw_coverage_ratio','usable_symbols','usable_coverage_ratio','unit_status','period_basis_status','statement_scope_status','pit_status','denominator_basis'])
    output_csv('gap_plan.csv',gaps,['market','symbol','dataset','period','item_standard','priority','classification','reason','source','estimated_http_requests'])
    conflicts=[]
    for key,aliases in mapped_key.items():
        if len(aliases)<2:continue
        distinct={(raw,src) for raw,src,val in aliases}; values={str(val) for raw,src,val in aliases}
        if len(distinct)>1:
            conflicts.append(dict(market=key[0],symbol=key[1],dataset=key[2],period=key[3],item_standard=key[4],observations=len(aliases),different_raw_source_pairs=len(distinct),distinct_value_count=len(values),status='VALUE_CONFLICT_REQUIRES_REVIEW' if len(values)>1 else 'ALIAS_DUPLICATE_SAME_VALUE_RETAINED'))
    duplicates=[dict(market=k[0],symbol=k[1],dataset=k[2],period=k[3],item_raw=k[4],source_id=k[5],rows=v,reason='DUPLICATE_SOURCE_KEY') for k,v in seen.items() if v>1]
    output_csv('source_conflicts.csv',conflicts,['market','symbol','dataset','period','item_standard','observations','different_raw_source_pairs','distinct_value_count','status'])
    output_csv('quality_issues.csv',duplicates,['market','symbol','dataset','period','item_raw','source_id','rows','reason'])
    pit={'PIT_VERIFIED':0,'PIT_UNVERIFIED':n,'published_at_populated':publish,'publication_allowed':False,'as_of_release':source_release}
    (output/'pit_status_summary.json').write_text(json.dumps(pit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    output_csv('factor_readiness.csv',[{'factor':x,'status':'BLOCKED','reason':'FINANCIAL_UNIT_SCOPE_PERIOD_BASIS_NOT_VERIFIED','publication_allowed':False} for x in ('gross_margin_ttm','operating_margin_ttm','net_margin_ttm','roa_ttm','roe_ttm','asset_turnover_ttm','debt_ratio','cash_to_assets','cfo_to_assets','accruals_to_assets','log_total_assets','revenue_yoy_1m','revenue_yoy_3m','revenue_yoy_12m','revenue_growth_acceleration','roe_change_yoy','operating_margin_change_yoy','earnings_or_margin_volatility_8q','financial_age_days')],['factor','status','reason','publication_allowed'])
    rows_report=[]
    for (ds,cl),count in sorted(summaries.items()):rows_report.append(dict(dataset=ds,classification=cl,rows=count))
    output_csv('coverage_by_dataset_status.csv',rows_report,['dataset','classification','rows'])
    summary={'source_release':source_release,'source_manifest_sha256':source_manifest_sha256,'source_current_sha256':source_current_sha256,'source_records':n,'observed_stock_codes':len({s for us in symbol_period.values() for s in us}),
        'distinct_raw_items':len({(ds,raw) for ds,raw,src,ms,std,klass,reason in by_raw}),
        'mapped_raw_item_rows':sum(c for (ds,raw,src,ms,std,klass,reason),c in by_raw.items() if std),
        'source_counts':dict(srcs),'unit_basis_counts':dict(units),'period_basis_counts':dict(periods),
        'published_at_present':publish,'per_dataset_status':rows_report,'mapped_alias_collision_groups':len(conflicts),'duplicate_source_keys':len(duplicates),
        'gap_plan_rows':len(gaps),'field_coverage_rows':len(coverage),'pit_status':'PIT_UNVERIFIED',
        'publication_allowed':False,'HTTP_requests_executed':0,'estimated_http_requests':0,
        'known_limitations':['All units and period bases unverified in current financial release','No period publication timestamps; historical PIT cannot be reconstructed from fetched_at','Statement scope and revisions absent from current schema','Current stock membership is not a historical as-of denominator','Additional non-financial parquet must be checked separately']}
    (output/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'執行摘要.md').write_text('''# Valuation P0＋P1｜真實財報 inventory／mapping（研究限定）\n\n輸入 release：`{release}`，財報 {n:,} 筆。\n\n- 已對原始財務科目完成**候選名稱映射** {mapped:,} 筆（不等於已驗證可計算）。\n- `published_at` 真實非空：{published:,} 筆；PIT 均維持 UNVERIFIED。\n- `financial_mapping_audit.csv` 為原科目逐來源聚合；`inventory.csv.gz` 為原始長表逐列盤點；`field_coverage.csv` 分市場、財報季度、資料集、標準欄位；`gap_plan.csv` 的 `FETCH_REQUIRED` 須二次排除未收錄的同義字及時點問題**才可執行補收**。\n- 文件全部 `publication_allowed=false`；無連網、無訓練、無 canonical 或 Registry 寫入。\n- 不含月營收／估值逐列內容驗證；財務 release 在此已逐檔 HASH 與 row-count 比對。\n'''.format(release=source_release,n=n,mapped=summary['mapped_raw_item_rows'],published=publish),encoding='utf-8')
    return summary


def live_canonical_audit(root:Path,output:Path,*,verify_manifest):
    """Colab full data read. verify_manifest returns (release,manifest,current_hash)."""
    import pandas as pd
    release,manifest,current_sha=verify_manifest(root)
    manifest_sha=hashlib.sha256((release/'manifest.json').read_bytes()).hexdigest()
    def rows():
        for relative,meta in sorted(manifest['files'].items()):
            if not (relative.startswith('financials/') and relative.endswith('.parquet')):continue
            df=pd.read_parquet(release/relative)
            if len(df)!=meta['rows']:raise ValueError('FINANCIAL_PARQUET_ROWS_MISMATCH:'+relative)
            # verify_manifest already verified all referenced SHA256.
            for r in df.to_dict('records'):
                yield {k:(None if (not isinstance(v,(list,dict)) and pd.isna(v)) else v) for k,v in r.items()}
    return audit_financial_rows(rows(),output,source_release=release.name,source_manifest_sha256=manifest_sha,source_current_sha256=current_sha)
