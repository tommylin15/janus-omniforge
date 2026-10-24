import json
from pathlib import Path
import valuation_min30_v22 as v
import valuation_min30_real_backfill as base


def fixture():
    D={n:[] for n in base.REQUIRED if n.endswith('.csv')}
    D[base.REQUIRED[1]]=[{'market':'twse','symbol':'2330','has_any_valuation_evidence':'True',
        'first_observed_month':'2023-10','pe_positive_months':'28','pb_positive_months':'36'},
        {'market':'twse','symbol':'1101','has_any_valuation_evidence':'True',
        'first_observed_month':'2023-10','pe_positive_months':'2','pb_positive_months':'36'},
        {'market':'tpex','symbol':'9999','has_any_valuation_evidence':'True',
        'first_observed_month':'2026-04','pe_positive_months':'15','pb_positive_months':'15'}]
    D[base.REQUIRED[3]]=[{'market':'twse','symbol':'2330','branch':'pe','shortfall':'2',
       'may_need_pre_existing_history_before':''},
       {'market':'twse','symbol':'1101','branch':'pe','shortfall':'28','may_need_pre_existing_history_before':''},
       {'market':'tpex','symbol':'9999','branch':'pb','shortfall':'15','may_need_pre_existing_history_before':''}]
    D[base.REQUIRED[2]]=[{'market':'twse','symbol':'2330','branch':'pe','month':'2025-11','gap_reason':'NULL_MULTIPLE'},
       {'market':'twse','symbol':'2330','branch':'pe','month':'2025-12','gap_reason':'NONPOSITIVE_ECONOMIC_OR_BASIS'}]
    M={'as_of_month':'2026-09','existing_first_month':'2023-10',
      'input_sha256':{'x':'abc'},'source':{'release':base.EXPECTED_RELEASE}}
    official={('twse','2330'):{'listing_date':'1994-01-01'},
      ('twse','1101'):{'listing_date':'1962-01-01'},
      ('tpex','9999'):{'listing_date':'2026-04-01'}}
    return D,M,official


def test_targets_true_pre_release_and_skips_zero_or_ipo():
    D,M,official=fixture();tasks,holds,pairs=v.select_v22(D,M,official,{})
    assert len(tasks)==1 and tasks[0]['symbol']=='2330' and tasks[0]['branches']==['pe']
    assert tasks[0]['start_date']=='2023-04-01' and tasks[0]['end_date']=='2023-09-30'
    assert all(m<'2023-10' for m in tasks[0]['target_months'])
    assert not any(t['symbol']=='1101' for t in tasks)
    assert any(h['symbol']=='1101' and h['reason']=='LOW_POSITIVE_HISTORY_YIELD_AUDIT_FIRST' for h in holds)
    assert any(h['symbol']=='9999' and h['reason']=='NO_PRE_2023_POST_LISTING_MONTHS' for h in holds)


def test_legacy_read_only_sha_and_nonpositive(tmp_path):
    old=tmp_path/'old'; t={'dataset':'TaiwanStockPER','kind':'valuation','market':'twse',
            'symbol':'2330','start_date':'2024-11-01','end_date':'2024-12-31'}
    body=json.dumps({'status':200,'data':[{'date':'2024-11-29','stock_id':'2330','PER':0,'PBR':5.5},
               {'date':'2024-12-31','stock_id':'2330','PER':32,'PBR':5.4}]}).encode()
    base.persist_response(old,t,body,'SUCCESS',2)
    before=sorted((f.as_posix(),f.read_bytes()) for f in old.rglob('*') if f.is_file())
    a=v.inspect_legacy(old)
    assert a['receipts_valid']==1
    assert '2024-11' in a['nonpositive_by_symbol_branch'][('twse','2330','pe')]
    assert '2024-12' in a['positive_by_symbol_branch'][('twse','2330','pe')]
    assert before==sorted((f.as_posix(),f.read_bytes()) for f in old.rglob('*') if f.is_file())
    (old/'raw'/(base.task_id(t)+'.json')).write_text('{}')
    b=v.inspect_legacy(old)
    assert b['receipts_invalid']==1 and b['receipts_valid']==0


def test_immutable_plan_and_no_rerequest_on_resume(tmp_path):
    D,M,O=fixture();a=v.inspect_legacy(tmp_path/'legacy');tasks,holds,pairs=v.select_v22(D,M,O,a)
    root=tmp_path/'v22'
    plan=v.freeze(root,tasks,M,O,a,holds,pairs)
    assert plan['fingerprint'] == v.freeze(root,tasks,M,O,a,holds,pairs)['fingerprint']
    assert (root/'v22_tasks.csv').exists()
    payload=json.dumps({'status':200,'data':[
      {'date':'2023-05-31','stock_id':'2330','PER':16.5,'PBR':4},
      {'date':'2023-06-30','stock_id':'2330','PER':17.2,'PBR':4.5}]}).encode()
    base.persist_response(root,tasks[0],payload,'SUCCESS',2)
    result=v.yield_report(root,tasks,D,a)
    assert result['new_positive_month_candidate_count']==2
    assert result['tasks_success']==1
    class BlockSession:
        def get(self,*a,**k):raise AssertionError('cached receipt must not call HTTP')
    run=base.run_fetch(root,tasks,token='not-stored',max_calls_per_run=1,sleep_seconds=7.2,
           session=BlockSession(),sleeper=lambda x:None)
    assert run['actual_http_calls_this_run']==0 and run['cached_verified']==1
    changed=[dict(tasks[0],start_date='2023-03-01')]
    try:v.freeze(root,changed,M,O,a,holds,pairs)
    except RuntimeError:pass
    else:raise AssertionError('changed plan must fail')


def test_real_v20_corpus_simulated_roster_subset():
    path=Path('/mnt/data')
    if not (path/'00_summary.json').is_file():return
    D,M=base.read_sources(path)
    f=json.loads((path/'frozen_plan.json').read_text())
    roster={(t['market'],t['symbol']):{'listing_date':t.get('listing_date')} for t in f['plan']['tasks']}
    tasks,holds,pairs=v.select_v22(D,M,roster,{})
    assert len(pairs)==1018
    assert any(t['start_date']<'2023-10-01' for t in tasks)
    assert all(t['end_date']<'2023-10-01' for t in tasks)
    assert all(not any(b not in ('pe','pb') for b in t['branches']) for t in tasks)
    assert all(t['listing_date']<=t['end_date'] for t in tasks)