import importlib.util
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('unlinked',Path('scripts/gcp/finops_unlinked_small_files.py'))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW=datetime(2026,10,16,tzinfo=timezone.utc)


def test_only_old_listed_small_generation_inside_core_table_can_be_deleted(monkeypatch):
    old={'name':'warehouse/ohlcv_v1/data/old.parquet','size':'10','generation':'123','updated':'2026-10-01T00:00:00Z'}
    store=m.SmallStore([old],NOW,['warehouse/ohlcv_v1/'])
    calls=[]
    from io import BytesIO
    from urllib.error import HTTPError
    monkeypatch.setattr(m.GcsObjectStore,'_token',lambda self:'test-token')
    def request(req,**kwargs):
        calls.append((req.get_method(),req.full_url))
        if req.get_method()=='GET':
            if any(method=='DELETE' for method,_ in calls): raise HTTPError(req.full_url,404,'gone',{},BytesIO())
            return BytesIO(b'{}')
        return BytesIO()
    monkeypatch.setattr(m,'urlopen',request)
    from ingestion_core import stage
    monkeypatch.setattr(stage,'urlopen',request)
    with pytest.raises(ValueError):store.delete(old['name'],generation='124')
    with pytest.raises(ValueError):store.delete('private/owner.json',generation='123')
    store.delete(old['name'],generation='123')
    assert calls[1][0]=='DELETE' and calls[1][1].endswith('?generation=123&ifGenerationMatch=123')
    assert calls[2][0]=='GET' and calls[2][1].endswith('?generation=123')
    assert store.deleted==[{'name':old['name'],'generation':'123','bytes':10}]
    for change in ({'size':str(1024*1024)},{'updated':'2026-10-15T00:00:00Z'},{'name':'executions/id/core-snapshot.json'}):
        item={**old,**change};s=m.SmallStore([item],NOW,['warehouse/ohlcv_v1/'])
        with pytest.raises(ValueError):s.delete(item['name'],generation='123')


def test_large_core_manifests_remain_in_reference_listing(monkeypatch):
    items=({'name':'a','size':'1'},{'name':'b','size':str(2*1024*1024)})
    monkeypatch.setattr(m.GcsObjectStore,'objects',lambda self,prefix:items)
    store=m.SmallStore([],NOW,[])
    assert len(store.objects('executions/'))==2
    assert len(store.objects('warehouse/ohlcv_v1/'))==1


def test_audit_is_first_and_partial_table_receipt_survives_failure(monkeypatch):
    core=SimpleNamespace(IDENTIFIERS=['ohlcv'],table_identifier=lambda key:'core.ohlcv_v1',
                         catalog=SimpleNamespace(table_exists=lambda name:True))
    calls=[]
    def maintain(**kw):
        calls.append((kw['identifier'],kw['apply']))
        if kw['apply']: raise RuntimeError('blocked')
        return {'planned_expiration':2}
    monkeypatch.setattr(m,'maintain_financials',maintain)
    monkeypatch.setattr(m,'clean_orphans',lambda *args,**kw:{'planned_objects':3})
    reports=[]
    with pytest.raises(RuntimeError):m.cleanup(core,None,NOW,reports)
    assert calls==[('ops.batch_events_v1',False),('core.ohlcv_v1',False),('ops.batch_events_v1',True)]
    assert len(reports)==2 and reports[1]['orphan_preflight']['planned_objects']==3
    assert reports[0]['preflight']=={'planned_expiration':2} and reports[0]['phase']=='APPLYING'


def test_missing_explicit_worker_approval_stops_before_catalog(monkeypatch):
    monkeypatch.delenv('JANUS_APPROVED_UNLINKED_CLEANUP',raising=False)
    with pytest.raises(ValueError,match='authorization_required'):m.main()


def test_cleanup_reuses_reference_helpers_and_reads_current_rows(monkeypatch):
    calls=[]
    table=SimpleNamespace(scan=lambda **kw:SimpleNamespace(to_arrow=lambda:SimpleNamespace(num_rows=1)))
    core=SimpleNamespace(IDENTIFIERS=['ohlcv'],table_identifier=lambda key:'core.ohlcv_v1',
        catalog=SimpleNamespace(table_exists=lambda name:True,load_table=lambda name:table))
    monkeypatch.setattr(m,'maintain_financials',lambda **kw:calls.append(('metadata',kw['identifier'],kw['apply'])) or {'row_count':1})
    monkeypatch.setattr(m,'clean_orphans',lambda core,store,name,**kw:calls.append(('orphan',name,kw['apply'])) or {})
    reports=[]
    m.cleanup(core,None,NOW,reports)
    assert calls[:4]==[(kind,name,False) for name in ('ops.batch_events_v1','core.ohlcv_v1') for kind in ('metadata','orphan')]
    assert calls[4:]==[(kind,name,True) for name in ('ops.batch_events_v1','core.ohlcv_v1') for kind in ('metadata','orphan')]
    assert all(x['phase']=='READBACK_PASS' for x in reports)


def test_http_failure_emits_only_safe_diagnostics_without_retry(monkeypatch,capsys):
    import io,json
    from urllib.error import HTTPError
    from ingestion_core import __main__ as entry
    monkeypatch.setenv('JANUS_APPROVED_UNLINKED_CLEANUP','true')
    monkeypatch.setenv('CORE_BUCKET',m.BUCKET)
    calls=[]
    def fail(*args,**kw):
        calls.append(1)
        body=json.dumps({'error':{'message':'secret@example.test storage.objects.delete denied',
            'errors':[{'reason':'retentionPolicyNotMet'}]}}).encode()
        raise HTTPError('https://storage.googleapis.com/',403,'Forbidden',{},io.BytesIO(body))
    monkeypatch.setattr(entry,'_iceberg_core',fail)
    assert m.main()==0
    output=capsys.readouterr().out
    result=json.loads(output)
    assert calls==[1] and result['deleted_objects']==0
    assert result['http_reasons']==['retentionPolicyNotMet']
    assert result['denied_storage_permissions']==['storage.objects.delete']
    assert 'secret@example.test' not in output


def test_worker_source_preserves_gcloud_custom_argument_delimiter():
    code=Path('scripts/gcp/finops_unlinked_small_files.py').read_text()
    assert '|' not in code
    assert ('python|-c|'+code).split('|')==['python','-c',code]
