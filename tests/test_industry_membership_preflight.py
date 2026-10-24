"""Offline PIT, overlap and industry-gate regression checks (no network/Parquet engine)."""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
import industry_membership as im
import janus_precision as jp
import label_four_models as lab

HASH = 'a' * 64


def row(**kw):
    r = dict(market='twse', symbol='2330', classification_system='TWSE_OFFICIAL',
             industry_id='semiconductor', membership_type='primary',
             valid_from='2025-01-01', valid_to=None,
             published_at='2024-12-31T04:00:00+00:00', source_id='TWSE-2024',
             source_url='https://www.twse.com.tw/example',source_sha256=HASH,
             evidence_status='VERIFIED')
    r.update(kw)
    return r


def fixture(tmp_path, monkeypatch, rows, *, auth='VERIFIED', pit='VERIFIED', mutate_manifest=None):
    root = tmp_path / 'JanusDataset'
    folder = root / im.RELATIVE_DIR
    folder.mkdir(parents=True)
    raw = b'fake-parquet-fixture'
    (folder / im.FILE_NAME).write_bytes(raw)
    manifest = dict(version=im.SCHEMA_VERSION, file=im.FILE_NAME,
                    status='RESEARCH_DATA_ONLY', publication_allowed=False,
                    sha256=hashlib.sha256(raw).hexdigest(), rows=len(rows),
                    source_authorization=auth, historical_pit=pit,
                    sources={'TWSE-2024': {'url':'https://www.twse.com.tw/example',
                      'sha256':HASH, 'authorization_status':'VERIFIED',
                      'rights_review_url':'https://data.gov.tw/license',
                      'authorized_uses':['COLLECT','RESEARCH_STORE','ML_TRAIN']}})
    if mutate_manifest:
        mutate_manifest(manifest)
    (folder/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(im.pd, 'read_parquet', lambda p: pd.DataFrame(rows))
    return root


def prices(*days):
    return pd.DataFrame([dict(market='twse',symbol='2330',trade_date=x) for x in days])


def test_missing_does_not_infer_current_classification(tmp_path):
    x=im.check_industry_membership(tmp_path,prices('2025-01-10'))
    assert x['status']=='MISSING' and x['industry_features_in_model_x'] is False


def test_valid_primary_and_overlapping_secondary(monkeypatch,tmp_path):
    rows=[row(), row(industry_id='AI-server',membership_type='theme',classification_system='RESEARCH_THEME'),
          row(industry_id='datacenter',membership_type='theme',classification_system='RESEARCH_THEME')]
    root=fixture(tmp_path,monkeypatch,rows)
    x=im.check_industry_membership(root,prices('2025-01-10','2025-01-13'))
    assert x['status']=='VERIFIED' and x['primary_matched_stock_days']==2
    assert x['overlapping_secondary_rows']==2
    assert x['industry_features_in_model_x'] is False


def test_valid_to_exclusive(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(valid_to='2025-01-10')])
    x=im.check_industry_membership(root,prices('2025-01-09','2025-01-10'))
    assert x['status']=='PARTIAL_COVERAGE'
    assert x['primary_matched_stock_days']==1


def test_publish_time_never_backdated(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(published_at='2025-01-10T05:00:00+00:00')])
    x=im.check_industry_membership(root,prices('2025-01-10','2025-01-13'))
    assert x['primary_matched_stock_days']==1
    assert x['status']=='PARTIAL_COVERAGE'


def test_overlapping_official_primary_is_blocked(monkeypatch,tmp_path):
    a=row(valid_to='2025-02-01')
    b=row(industry_id='electronics',valid_from='2025-01-15')
    root=fixture(tmp_path,monkeypatch,[a,b])
    x=im.check_industry_membership(root,prices('2025-01-20'))
    assert x['status']=='BLOCKED' and 'OVERLAPPING_OFFICIAL_PRIMARY' in x['reason']


def test_changing_primary_after_nonoverlap_is_valid(monkeypatch,tmp_path):
    a=row(valid_to='2025-02-01')
    b=row(industry_id='electronics',valid_from='2025-02-01',published_at='2025-01-29T04:00:00+00:00')
    root=fixture(tmp_path,monkeypatch,[a,b])
    x=im.check_industry_membership(root,prices('2025-01-15','2025-02-03'))
    assert x['status']=='VERIFIED'


def test_metadata_source_authorization_unknown_is_blocked(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row()],auth='NOT_VERIFIED')
    x=im.check_industry_membership(root,prices('2025-01-10'))
    assert x['status']=='BLOCKED' and x['historical_pit']=='VERIFIED'


def test_no_manifest_is_blocked(tmp_path):
    folder=tmp_path/im.RELATIVE_DIR
    folder.mkdir(parents=True)
    (folder/im.FILE_NAME).write_bytes(b'blob')
    assert im.check_industry_membership(tmp_path)['reason']=='IMMUTABLE_MEMBERSHIP_MANIFEST_MISSING'


def test_source_sha_required(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(source_sha256='unknown')])
    assert 'SOURCE_SHA256_REQUIRED' in im.check_industry_membership(root)['reason']


def test_hash_mismatch_is_blocked(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row()],mutate_manifest=lambda m:m.update(sha256='deadbeef'))
    x=im.check_industry_membership(root)
    assert 'MEMBERSHIP_HASH_MISMATCH' in x['reason']


def test_unverified_industry_no_silent_primary(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(evidence_status='UNVERIFIED',published_at=None)])
    x=im.check_industry_membership(root,prices('2025-01-10'))
    assert x['status']=='BLOCKED' and x['usable_primary_rows']==0


def test_primary_market_mismatch_block(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(market='tpex')])
    assert 'PRIMARY_OFFICIAL_MARKET_MISMATCH' in im.check_industry_membership(root)['reason']


def test_strict_require_industry_fails_before_export(monkeypatch,tmp_path):
    root=tmp_path/'input';(root/'canonical').mkdir(parents=True)
    (root/'canonical/CURRENT.json').write_text('{}')
    monkeypatch.setattr(lab,'load_release',lambda *a,**k:({'ohlcv':prices('2025-01-10')},{'release':'fixture'}))
    with pytest.raises(ValueError,match='INDUSTRY_MEMBERSHIP_NOT_VERIFIED'):
        lab.run(root,tmp_path/'output',verify_only=True,require_industry=True)
    monkeypatch.setattr(lab, 'check_industry_membership', lambda *a, **k: (_ for _ in ()).throw(AssertionError('default must not audit')))
    x=lab.run(root,tmp_path/'output',verify_only=True)
    assert x['industry_membership_precheck']['status']=='NOT_REQUESTED'
    assert not (tmp_path/'output').exists()


def test_export_manifest_records_industry_precheck_no_block_nonindustry(monkeypatch,tmp_path):
    monkeypatch.setattr(jp,'load_release',lambda *a,**k:({
        'ohlcv':pd.DataFrame(),'revenue':pd.DataFrame(),'valuation':pd.DataFrame(),
        'financials':pd.DataFrame()}, {'release':'release-test','publication_allowed':False}))
    status=im.check_industry_membership(tmp_path)
    out,manifest=jp.export_dataset(tmp_path,output_root=tmp_path/'research',industry_preflight_fn=lambda data:status)
    assert (out/'industry_membership_precheck.json').exists()
    ready=json.loads((out/'readiness.json').read_text())
    assert ready['industry_membership_precheck']['status']=='MISSING'
    assert 'NOT_IN_MODEL_X' in ready['industry']
    assert manifest['publication_allowed'] is False
    assert (out/'manifest.json').exists()
    assert jp.export_dataset(tmp_path,output_root=tmp_path/'research',industry_preflight_fn=lambda data:status)[0]==out


def test_output_path_guard(tmp_path):
    with pytest.raises(ValueError,match='OUTPUT_MUST_NOT'):
        lab.run(tmp_path,tmp_path/'derived')


def test_preflight_before_export_non_strict(monkeypatch,tmp_path):
    root=tmp_path/'input';(root/'canonical').mkdir(parents=True)
    (root/'canonical/CURRENT.json').write_text('{}')
    seen=[]
    def fake_export(*a,**kw):
        seen.append(kw['industry_preflight_fn']({'ohlcv':prices('2025-01-10')})['status'])
        out=tmp_path/'output-result';out.mkdir()
        (out/'industry_membership_precheck.json').write_text('{"status":"MISSING"}')
        return out,{'state':'RESEARCH_DERIVED_NOT_PROMOTABLE','input':{'release':'fake'},'version':'3.8.2','files':{}}
    monkeypatch.setattr(lab,'export_dataset',fake_export)
    result=lab.run(root,tmp_path/'output')
    assert seen==['NOT_REQUESTED']
    assert result['publication_allowed'] is False


def test_naive_published_at_is_rejected(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row(published_at='2024-12-31 12:00:00')])
    assert 'PUBLISHED_AT_REQUIRES_EXPLICIT_TIMEZONE' in im.check_industry_membership(root)['reason']


def test_source_registry_provenance_required(monkeypatch,tmp_path):
    root=fixture(tmp_path,monkeypatch,[row()],mutate_manifest=lambda m:m.pop('sources'))
    assert 'SOURCE_REGISTRY_MISSING' in im.check_industry_membership(root)['reason']


def test_source_registry_authorized_scopes_required(monkeypatch,tmp_path):
    def mutate(m):
        m['sources']['TWSE-2024']['authorized_uses']=['COLLECT']
    root=fixture(tmp_path,monkeypatch,[row()],mutate_manifest=mutate)
    assert 'SOURCE_REGISTRY_NOT_AUTHORIZED_OR_MISMATCH' in im.check_industry_membership(root)['reason']
