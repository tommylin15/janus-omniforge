"""Fail-closed P1 lineage and accounting/PIT gates."""
import importlib.util
from pathlib import Path
import pytest
import json

P=Path(__file__).resolve().parents[1]/'research'/'colab'/'valuation_p1_source_lineage.py'
if not P.is_file():
    P=Path(__file__).with_name('valuation_p1_source_lineage.py')
spec=importlib.util.spec_from_file_location('valuation_p1_source_lineage',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def row(**kwargs):
    base=dict(market='twse',symbol='1201',fiscal_quarter='2022Q4',dataset='balance',
              item_raw='TotalAssets',item_standard='total_assets',source_id='finmind',value_raw='17659407000.0')
    base.update(kwargs);return base

def src_bytes(r):
    return json.dumps({'data':[{'stock_id':r['symbol'],'date':r['fiscal_quarter'][:4]+'-12-31',
                    'type':r['item_raw'],'value':float(r['value_raw'])}]}).encode()

def proof(r,**kwargs):
    p=dict(row_fingerprint=m.row_fingerprint(r),original_payload_sha256=m.digest(src_bytes(r)),
           row_anchor_verified=True,accounting_scope='CONSOLIDATED',period_basis='INSTANT',
           unit_basis='TWD',fiscal_quarter=r['fiscal_quarter'],source_id=r['source_id'],
           source_revision_id='report-hash-pinned',currency='TWD')
    p.update(kwargs);return p

def test_no_proof_does_not_promote():
    r=row();assert not m.proof_gate(r,None)['arithmetic_ready']

def test_fake_row_hash_does_not_promote():
    r=row();assert m.proof_gate(r,proof(r,row_fingerprint='0'*64))['reason']=='ROW_HASH_MISMATCH'

def test_cross_source_similarity_cannot_certify():
    r=row();assert m.proof_gate(r,{'ratio':1000})['reason']=='ROW_HASH_MISMATCH'

def test_missing_raw_sha_blocks():
    r=row();assert m.proof_gate(r,proof(r,original_payload_sha256=''))['reason']=='ORIGINAL_PAYLOAD_SHA_MISSING'

def test_missing_revision_blocks():
    r=row();assert m.proof_gate(r,proof(r,source_revision_id=''))['reason']=='REVISION_MISSING'

def test_scope_is_required():
    r=row();assert m.proof_gate(r,proof(r,accounting_scope='UNKNOWN'))['reason']=='SCOPE_UNVERIFIED'

def test_period_stock_vs_flow():
    r=row();assert m.proof_gate(r,proof(r,period_basis='YTD'))['reason']=='INCOMPATIBLE_ACCOUNTING_PERIOD'

def test_fiscal_quarter_binding():
    r=row();assert m.proof_gate(r,proof(r,fiscal_quarter='2024Q4'))['reason']=='QUARTER_MISMATCH'

def test_valid_accounting_but_not_pit():
    r=row();a=m.proof_gate(r,proof(r),source_payload=src_bytes(r));assert a['arithmetic_ready'] and not a['historical_asof_ready'] and not a['publication_allowed']

def test_source_publication_is_asof_scoped():
    r=row();p=proof(r,first_publication_utc='2023-03-15T09:43:00Z',original_disclosure_sha256='f'*64)
    assert not m.proof_gate(r,p,source_payload=src_bytes(r),as_of='2023-03-14T23:00:00Z')['historical_asof_ready']
    assert not m.proof_gate(r,p,source_payload=src_bytes(r),as_of='2023-03-16T00:00:00Z')['historical_asof_ready']
    receipt=b'original exchange disclosure with 1201 and fiscal quarter'
    p['original_disclosure_sha256']=m.digest(receipt)
    p['disclosure_kind']='EXCHANGE_OR_ISSUER_ORIGINAL_DISCLOSURE'
    assert m.proof_gate(r,p,source_payload=src_bytes(r),disclosure_payload=receipt,as_of='2023-03-16T00:00:00Z')['historical_asof_ready']

def test_eps_never_scaled_by_thousands():
    r=row(dataset='income',item_standard='basic_eps',item_raw='EPS',value_raw='0.47')
    p=proof(r,period_basis='QUARTER',unit_basis='TWD_THOUSAND')
    assert m.proof_gate(r,p)['reason']=='EPS_UNIT_INCOMPATIBLE'
    p['unit_basis']='TWD_PER_SHARE';assert m.proof_gate(r,p,source_payload=src_bytes(r))['normalized_value_twd']=='0.47'

def test_net_income_concepts_split():
    r=row(dataset='income',item_standard='net_income',item_raw='TotalConsolidatedProfitForThePeriod')
    assert m.normalized_concept(r)=='OTHER_PROFIT_MEASURE_OR_COMPREHENSIVE_UNVERIFIED'
    r['item_raw']='IncomeAfterTaxes';assert m.normalized_concept(r)=='net_income'

def test_cfo_equal_aliases_only_one_candidate():
    r=row(dataset='cashflow',item_standard='cfo',item_raw='CashFlowsFromOperatingActivities')
    r2=dict(r,item_raw='NetCashInflowFromOperatingActivities')
    x,status=m.collapse_alias([r,r2]);assert x['item_raw']==r['item_raw'] and status=='EQUAL_CFO_ALIASES_CANDIDATE'
    r2['value_raw']='111';assert m.collapse_alias([r,r2])[0] is None

def test_fourth_quarter_prerequisite():
    assert m.fiscal_prior('2022Q4')=='2022Q3'
    assert m.fiscal_prior('2023Q1')=='2022Q4'
    assert m.fiscal_prior('2022Q5') is None

def test_mirror_not_original_raw():
    assert all(c['first_publication']=='NOT_PROVEN' for c in m.EXTERNAL_CROSSCHECKS.values())

def test_forged_sha_with_no_bytes_never_passes():
    r=row()
    assert m.proof_gate(r,proof(r))['reason']=='ORIGINAL_BYTES_HASH_NOT_VERIFIED'

def test_hash_valid_but_wrong_row_rejected():
    r=row()
    payload=json.dumps({'data':[{'stock_id':'1103','date':'2022-12-31',
         'type':'TotalAssets','value':17659407000.0}]}).encode()
    assert m.proof_gate(r,proof(r,original_payload_sha256=m.digest(payload)),source_payload=payload)['reason']=='ORIGINAL_FINMIND_ROW_ANCHOR_UNVERIFIED'
