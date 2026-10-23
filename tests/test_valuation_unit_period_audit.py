"""P1 unit/period agreement safety and ambiguity regression tests."""
import csv
import gzip
import hashlib
from pathlib import Path
import pytest
from valuation_unit_period_audit import compare, prior_quarter, run, verified_source_metadata


def r(src,item,q,v,ds='income',market='twse',symbol='2330'):
    return dict(market=market,symbol=symbol,dataset=ds,fiscal_quarter=q,
        item_standard=item,item_raw='revenue' if item=='revenue' else item,
        value_raw=str(v),source_id=src,unit_basis='UNVERIFIED',
        period_basis='UNVERIFIED',statement_scope='UNKNOWN',published_at='')


def test_quarter_rollover():
    assert prior_quarter('2025Q1')=='2024Q4'
    assert prior_quarter('2025Q3')=='2025Q2'
    assert prior_quarter('2025-Q1') is None


def test_balance_1000_does_not_verify_pit():
    s,p,c=compare([r('mops','total_assets','2025Q1',123,ds='balance'),
                     r('finmind','total_assets','2025Q1',123000,ds='balance')])
    assert p[0]['status']=='CONSISTENT_1000X_COHORT_ONLY'
    assert p[0]['source_unit_verified'] is False and p[0]['historical_pit_verified'] is False
    assert s['source_unit_verified_rows']==0


def test_q2_ytd_difference():
    _,p,_=compare([r('mops','revenue','2025Q1',30),r('mops','revenue','2025Q2',90),
                   r('finmind','revenue','2025Q2',60000)])
    assert p[0]['method']=='FLOW_YTD_DIFFERENCE'
    assert p[0]['mops_quarter_component']==60
    assert p[0]['status']=='CONSISTENT_1000X_COHORT_ONLY'


def test_q1_direct():
    _,p,_=compare([r('mops','revenue','2026Q1',30),r('finmind','revenue','2026Q1',30000)])
    assert p[0]['method']=='FLOW_Q1_DIRECT'


def test_missing_previous_quarter_blocks():
    _,p,_=compare([r('mops','revenue','2025Q2',90),r('finmind','revenue','2025Q2',60000)])
    assert p[0]['status']=='AMBIGUOUS_SOURCE_OR_PREVIOUS_QUARTER'


def test_duplicate_alias_blocks():
    _,p,_=compare([r('mops','total_assets','2025Q2',50,ds='balance'),
                   r('mops','total_assets','2025Q2',51,ds='balance'),
                   r('finmind','total_assets','2025Q2',50000,ds='balance')])
    assert p[0]['status']=='AMBIGUOUS_SOURCE_OR_PREVIOUS_QUARTER'


def test_mismatch_preserved():
    _,p,_=compare([r('mops','total_assets','2025Q2',50,ds='balance'),
                   r('finmind','total_assets','2025Q2',50500,ds='balance')])
    assert p[0]['status']=='VALUE_MISMATCH_REVIEW'


def test_zero_denominator_blocks():
    _,p,_=compare([r('mops','total_assets','2025Q2',0,ds='balance'),
                   r('finmind','total_assets','2025Q2',50000,ds='balance')])
    assert p[0]['status']=='ZERO_DENOMINATOR'


def test_non_finite_value_is_excluded():
    s,p,_=compare([r('mops','total_assets','2025Q2','NaN',ds='balance'),
                   r('finmind','total_assets','2025Q2',50000,ds='balance')])
    assert not p and s['candidate_pairs']==0


def test_eps_excluded_from_ytd_differencing():
    _,p,_=compare([r('mops','basic_eps','2025Q1',1),r('mops','basic_eps','2025Q2',3),
                   r('finmind','basic_eps','2025Q2',2)])
    assert not p


def test_pit_metadata_check():
    x=r('mops','revenue','2025Q1',123)
    assert not verified_source_metadata(x)
    x.update(unit_basis='TWD_THOUSAND',period_basis='YTD',statement_scope='CONSOLIDATED',published_at='2025-05-14T00:00:00Z')
    assert verified_source_metadata(x)


def test_integrity_pin_and_csv(tmp_path):
    gz=tmp_path/'inventory.csv.gz'
    rows=[r('mops','total_assets','2025Q1',123,ds='balance'),r('finmind','total_assets','2025Q1',123000,ds='balance')]
    with gzip.open(gz,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    digest=hashlib.sha256(gz.read_bytes()).hexdigest()
    result=run(gz,tmp_path/'out',expected_inventory_sha256=digest)
    assert result['candidate_pairs']==1
    assert (tmp_path/'out'/'unit_period_pairs.csv').exists()
    with pytest.raises(ValueError,match='PINNED_INVENTORY_SHA256_MISMATCH'):
        run(gz,tmp_path/'should_not_exist',expected_inventory_sha256='0'*64)
