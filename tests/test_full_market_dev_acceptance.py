from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/gcp'))
from full_market_dev_acceptance import CODE, VERIFY, payload, verified_terminal_business_success


def test_official_coverage_requires_both_markets_and_inclusive_fixed_denominators():
    namespace = {}
    exec(VERIFY,namespace)
    verify = namespace['verify_inventory']
    rows = [{'dataset':'ohlcv','market':market,'expected_count':1000,
             'received_count':900 if market == 'TWSE' else 700,
             'missing_count':100 if market == 'TWSE' else 300,
             'max_missing_ratio':0.1 if market == 'TWSE' else 0.3,
             'date':'2026-10-14','coverage_accepted':True,'snapshot_id':4,'stage_provenance_id':'official-proof'}
            for market in ('TWSE','TPEX')]
    inventory = {'scope':'all_listed_otc_equities','universe_status':'available',
                 'universe_version':1,'coverage_status':'complete','coverage_accepted':True,'items':rows}
    assert len(verify(inventory,'2026-10-14')) == 2
    holding = {'dataset':'outside_500_registered_portfolio_ohlcv','market':'ALL','date':'2026-10-14',
               'expected_count':1,'received_count':1,'missing_count':0,'max_missing_ratio':0.0,'coverage_accepted':True,
               'snapshot_ids':[4],'stage_provenance_ids':['official-proof']}
    assert len(verify(dict(inventory,items=rows+[holding]),'2026-10-14')) == 3
    with pytest.raises(AssertionError):
        verify(dict(inventory,items=rows+[dict(holding,snapshot_ids=[])]),'2026-10-14')
    with pytest.raises(AssertionError): verify(dict(inventory,items=rows[:1]),'2026-10-14')
    with pytest.raises(AssertionError): verify(inventory,'2026-10-15')
    rows[0]['missing_count'] = 101
    rows[0]['received_count'] = 899
    with pytest.raises(AssertionError): verify(inventory,'2026-10-14')
    rows[0]['missing_count'], rows[0]['received_count'] = 100, 900
    rows[1]['missing_count'], rows[1]['received_count'] = 301, 699
    with pytest.raises(AssertionError): verify(inventory,'2026-10-14')
    rows[1]['missing_count'], rows[1]['received_count'] = 300, 700
    with pytest.raises(AssertionError):
        verify(dict(inventory,items=rows+[dict(holding,received_count=0,missing_count=1)]),'2026-10-14')
    with pytest.raises(AssertionError):
        verify(dict(inventory,items=rows+[dict(holding,market='UNKNOWN')]),'2026-10-14')


def test_bootstrap_and_cache_requests_only_override_one_execution_and_never_trigger_mart():
    compile(CODE,'bounded-business-probe','exec')
    source = {'etag':'fence','template':{'template':{'containers':[{'command':['python']}]}}}
    bootstrap = payload(source,'bootstrap','2026-10-14')
    cached = payload(source,'cached','2026-10-14')
    assert set(bootstrap) == {'etag','overrides'}
    assert bootstrap['overrides']['taskCount'] == 1
    env = lambda request: {item['name']:item['value'] for item in request['overrides']['containerOverrides'][0]['env']}
    assert env(bootstrap)['FORCE_REFRESH'] == 'true'
    assert env(cached)['FORCE_REFRESH'] == 'false'
    assert env(bootstrap)['MART_JOB'] == ''
    assert env(bootstrap)['INGESTION_DATE'] == ''
    assert env(cached)['INGESTION_DATE'] == '2026-10-14'
    assert env(cached)['JANUS_ACCEPTANCE_TARGET_DAY'] == '2026-10-14'
    assert env(bootstrap)['JANUS_ACCEPTANCE_TARGET_DAY'] == ''
    assert not {'cpu','memory','serviceAccount'} & set(bootstrap['overrides'])
    with pytest.raises(ValueError): payload(source,'historical','2026-10-14')


def test_business_lease_release_requires_verified_terminal_pass():
    success = {'status':'PASS', 'business':{'status':'PASS', 'coverage':[]}}
    assert verified_terminal_business_success(success, True)
    assert not verified_terminal_business_success(success, False)
    assert not verified_terminal_business_success({'status':'FAIL', 'business':success['business']}, True)
    assert not verified_terminal_business_success({'status':'PASS', 'business':{'status':'FAIL'}}, True)
    assert not verified_terminal_business_success({'status':'PASS'}, True)
    assert not verified_terminal_business_success({'status':'UNKNOWN'}, False)


def test_one_shot_full_market_workflow_preserves_dispatch_and_no_schedule():
    workflow = (Path(__file__).parents[1] / '.github/workflows/full-market-dev-acceptance.yml').read_text()
    assert "workflow_dispatch:" in workflow
    assert "ops/full-market-acceptance-request.json" in workflow
    assert "janus-dev-runtime-writers" in workflow
    assert "one-shot-full-market-business-acceptance" in workflow
    assert "bootstrap_run" in workflow
    assert "schedule:" not in workflow
    source = (Path(__file__).parents[1] / 'scripts/gcp/full_market_dev_acceptance.py').read_text()
    assert "rollout.LEASE + ['release', '--safe-to-release']" in source


def test_cached_business_enforces_same_as_of_day_and_no_stage_recollection():
    assert "result['as_of']==os.environ['JANUS_ACCEPTANCE_TARGET_DAY']" in CODE
    assert "result['staged']==0 and all(r['cache_hit'] for r in receipts)" in CODE
    source = (Path(__file__).parents[1] / 'scripts/gcp/full_market_dev_acceptance.py').read_text()
    assert "os.environ.get('JANUS_BOOTSTRAP_DATE', '') if phase == 'cached'" in source
    wf = (Path(__file__).parents[1] / '.github/workflows/full-market-dev-acceptance.yml').read_text()
    assert "full-market-business-acceptance" in wf
    assert "JANUS_BOOTSTRAP_DATE" in wf
