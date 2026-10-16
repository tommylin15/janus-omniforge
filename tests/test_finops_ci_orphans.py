from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('ci_orphans',Path('scripts/gcp/finops_ci_orphans.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_exact_old_unheld_generation_only():
    item={'name':'warehouse/batch_events_v1/data/old.parquet','generation':'123','bytes':10}
    actual={'generation':'123','size':'10','updated':'2026-10-01T00:00:00Z'}
    now=datetime(2026,10,16,tzinfo=timezone.utc)
    assert m.validate(item,actual,now) == False  # no hold
    assert m.validate(item,{**actual,'eventBasedHold':True},now) == True  # has hold, returns True
    for change in ({'generation':'124'},{'size':'11'},{'temporaryHold':True},
                   {'updated':'2026-10-15T00:00:00Z'}, {'retentionExpirationTime':'2026-11-01T00:00:00Z'}):
        with pytest.raises(ValueError,match='ci_orphan_generation_scope_changed'):m.validate(item,{**actual,**change},now)
    for name in ('private/owner.parquet','warehouse/ohlcv_v1/data/a.parquet','warehouse/batch_events_v1/metadata/a.metadata.json'):
        with pytest.raises(ValueError,match='ci_orphan_generation_scope_changed'):m.validate({**item,'name':name},actual,now)


@pytest.mark.parametrize('denied',[False,True])
def test_ci_deletion_uses_exact_generation_and_preserves_failure_receipt(monkeypatch,tmp_path,denied):
    import io,json
    from types import SimpleNamespace
    from urllib.error import HTTPError
    monkeypatch.chdir(tmp_path)
    item={'name':'warehouse/batch_events_v1/data/old.parquet','generation':'123','bytes':10}
    (tmp_path/'ops').mkdir();source=tmp_path/'.tmp/d06-ci-source';source.mkdir(parents=True)
    (tmp_path/'ops/finops-ci-orphan-generations.json').write_text(json.dumps({'bucket':m.BUCKET,'source_run':'1','source_execution':'run','objects':[item]}))
    (source/'d06-runtime-references.json').write_text(json.dumps({'results':[{'execution':'run','result':{'audit_cleanup_dry_run':{'applied':False,'candidate_generations':[item]}}}]}))
    calls=[]
    def request(req,**kw):
        calls.append((req.get_method(),req.full_url))
        if req.get_method()=='DELETE':
            if denied:raise HTTPError(req.full_url,403,'Forbidden',{},io.BytesIO(b'{"error":{"message":"denied"}}'))
            return io.BytesIO(b'')
        return io.BytesIO(json.dumps({'generation':'123','size':'10','updated':'2026-10-01T00:00:00Z'}).encode())
    monkeypatch.setattr(m,'urlopen',request)
    inventories=iter([{'under_1mib':1000},{'under_1mib':999}])
    args=(lambda *a:'token',lambda *a:{'status':'completed','conclusion':'success','workflowName':'D06 read-only runtime reference census'},lambda:next(inventories),SimpleNamespace(fence=lambda:None))
    if denied:
        with pytest.raises(RuntimeError):m.run(*args)
    else:m.run(*args)
    receipt=json.loads(Path('finops-unlinked-receipt.json').read_text())
    assert receipt['deleted_objects']==(0 if denied else 1)
    assert calls[-1][0]=='DELETE' and calls[-1][1].endswith('?ifGenerationMatch=123')
    assert 'token' not in Path('finops-unlinked-receipt.json').read_text()
