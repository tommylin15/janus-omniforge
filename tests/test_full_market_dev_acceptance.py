from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/gcp'))
from full_market_dev_acceptance import CODE, VERIFY, payload


def test_official_coverage_requires_both_markets_and_inclusive_fixed_denominators():
    namespace = {}
    exec(VERIFY,namespace)
    verify = namespace['verify_inventory']
    rows = [{'dataset':'ohlcv','market':market,'expected_count':1000,'received_count':900,'missing_count':100,
             'date':'2026-10-14','coverage_accepted':True,'snapshot_id':4,'stage_provenance_id':'official-proof'}
            for market in ('TWSE','TPEX')]
    inventory = {'scope':'all_listed_otc_equities','universe_status':'available',
                 'universe_version':1,'coverage_status':'complete','coverage_accepted':True,'items':rows}
    assert len(verify(inventory,'2026-10-14')) == 2
    holding = {'dataset':'outside_500_registered_portfolio_ohlcv','market':'ALL','date':'2026-10-14',
               'expected_count':1,'received_count':1,'missing_count':0,'coverage_accepted':True,
               'snapshot_ids':[4],'stage_provenance_ids':['official-proof']}
    assert len(verify(dict(inventory,items=rows+[holding]),'2026-10-14')) == 3
    with pytest.raises(AssertionError):
        verify(dict(inventory,items=rows+[dict(holding,snapshot_ids=[])]),'2026-10-14')
    with pytest.raises(AssertionError): verify(dict(inventory,items=rows[:1]),'2026-10-14')
    with pytest.raises(AssertionError): verify(inventory,'2026-10-15')
    rows[1]['missing_count'] = 101
    rows[1]['received_count'] = 899
    with pytest.raises(AssertionError): verify(inventory,'2026-10-14')


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
    assert not {'cpu','memory','serviceAccount'} & set(bootstrap['overrides'])
    with pytest.raises(ValueError): payload(source,'historical','2026-10-14')
