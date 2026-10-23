import csv,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"/"colab"))
import valuation_mapping_p0p1 as p

def row(ds,item,value=123,market='twse',stock='2330'):
    return {'dataset':ds,'item':item,'value':value,'symbol':stock,'market':market,'fiscal_quarter':'2025Q4',
            'source_id':'mops','unit_basis':'RETAIN_SOURCE_HEADER_VERIFY_BEFORE_TRAINING',
            'period_basis':'QUERY_PERIOD_UNVERIFIED','observed_at':'2026-01-01T00:00:00Z','published_at':None,
            'historical_pit':'NOT_VERIFIED'}

def test_chinese_core_items_mapping():
    assert p.mapping_label('income','營業收入')==('revenue','LABEL_MATCH_ONLY')
    assert p.mapping_label('income','淨利（淨損）歸屬於母公司業主')[0]=='parent_net_income'
    assert p.mapping_label('balance','歸屬於母公司業主之權益合計')[0]=='parent_equity'
    assert p.mapping_label('cashflow','營業活動之淨現金流入（流出）')[0]=='cfo'

def test_no_unsafe_percentage_or_fuzzy_override():
    assert p.mapping_label('balance','TotalAssets_per')[0]==''
    assert p.mapping_label('income','模糊營業收入')[0]==''
    assert p.mapping_label('balance','Assets')==('total_assets','LABEL_MATCH_ONLY')
    assert p.mapping_label('cashflow','Assets')[0]==''

def test_mapping_never_promotes_unknown_unit_or_scope():
    assert p.disposition(mapped=True,value=5,unit_basis='RETAIN_SOURCE_HEADER_VERIFY_BEFORE_TRAINING',period_basis='YTD',published_at=None,statement_scope='CONSOLIDATED')[0]=='MAPPING_REQUIRED'
    assert p.disposition(mapped=True,value=5,unit_basis='TWD',period_basis='YTD',published_at=None,statement_scope=None)[1]=='STATEMENT_SCOPE_UNVERIFIED'
    assert p.disposition(mapped=True,value=-5,unit_basis='TWD',period_basis='YTD',published_at=None,statement_scope='CONSOLIDATED')[0]=='DERIVABLE'
    assert p.disposition(mapped=True,value=0,unit_basis='TWD',period_basis='YTD',published_at=None,statement_scope='CONSOLIDATED')[0]=='DERIVABLE'

def test_realistic_snapshot_does_not_mark_mapped_as_fetch_required(tmp_path):
    out=tmp_path/'research';records=[row('income','營業收入'),row('income','本期淨利（淨損）',-200),
     row('balance','資產總計'),row('balance','負債總計'),row('cashflow','營業活動之淨現金流入（流出）')]
    result=p.audit_financial_rows(records,out,source_release='release-fixture',source_manifest_sha256='hash-m',source_current_sha256='hash-c')
    assert result['source_records']==5 and result['mapped_raw_item_rows']==5
    with (out/'gap_plan.csv').open(encoding='utf-8-sig') as f:gap=list(csv.DictReader(f))
    x={(r['dataset'],r['item_standard']):r['classification'] for r in gap}
    assert x['income','revenue']=='MAPPING_REQUIRED'
    assert x['income','gross_profit']=='FETCH_REQUIRED'
    assert x['balance','total_assets']=='MAPPING_REQUIRED'
    assert (out/'inventory.csv.gz').exists()
    assert json.loads((out/'pit_status_summary.json').read_text())['PIT_VERIFIED']==0

def test_alias_collisions_retained_not_merged(tmp_path):
    out=tmp_path/'research'
    r=p.audit_financial_rows([row('income','營業毛利（毛損）',123),row('income','營業毛利（毛損）淨額',124)],out,
      source_release='release-test',source_manifest_sha256='m',source_current_sha256='c')
    assert r['mapped_alias_collision_groups']==0  # distinct gross variants stay distinct; no silent override
    assert 'gross_profit_before_adjustment' in (out/'financial_mapping_audit.csv').read_text(encoding='utf-8-sig')

def test_raw_vs_net_gross_profit_are_not_merged():
    assert p.mapping_label('income','營業毛利（毛損）')[0]=='gross_profit_before_adjustment'
    assert p.mapping_label('income','營業毛利（毛損）淨額')[0]=='gross_profit'


def test_actual_ambiguous_alias_same_standard_retained(tmp_path):
    out=tmp_path/'research'
    r=p.audit_financial_rows([row('balance','權益總額',111),row('balance','權益總計',112)],out,
       source_release='release-test',source_manifest_sha256='m',source_current_sha256='c')
    assert r['mapped_alias_collision_groups']==1
    with (out/'source_conflicts.csv').open(encoding='utf-8-sig') as f:
        assert next(csv.DictReader(f))['status']=='VALUE_CONFLICT_REQUIRES_REVIEW'
