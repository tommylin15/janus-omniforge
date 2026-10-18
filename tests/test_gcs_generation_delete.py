from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from ingestion_core import stage


def test_generation_delete_removes_the_version_not_only_the_live_name(monkeypatch):
    calls = []
    monkeypatch.setattr(stage.GcsObjectStore, '_token', lambda self: 'test-token')
    monkeypatch.setattr(stage, 'urlopen', lambda request, **kwargs: calls.append(request) or BytesIO())
    store = stage.GcsObjectStore('dev')
    store.delete('warehouse/table/data/file.parquet', generation='123')
    assert calls[0].get_method() == 'DELETE'
    assert parse_qs(urlsplit(calls[0].full_url).query) == {'generation': ['123'], 'ifGenerationMatch': ['123']}
    store.delete('stage/uncommitted.json')
    assert not urlsplit(calls[1].full_url).query


def test_core_cleanup_clears_only_event_hold_with_metadata_precondition(monkeypatch):
    import json
    import pytest
    calls=[]
    monkeypatch.setattr(stage.GcsObjectStore,'_token',lambda self:'test-token')
    def request(req,**kwargs):
        calls.append(req)
        return BytesIO(json.dumps({'eventBasedHold':True,'metageneration':'9'}).encode())
    monkeypatch.setattr(stage,'urlopen',request)
    store=stage.GcsObjectStore('gen-lang-client-0593591102-dev-core',release_event_based_hold=True)
    with pytest.raises(ValueError,match='exact generation'):store.delete('warehouse/table/data/file.parquet')
    assert not calls
    store.delete('warehouse/table/data/file.parquet',generation='123')
    assert [r.get_method() for r in calls]==['GET','PATCH','DELETE']
    assert parse_qs(urlsplit(calls[1].full_url).query)=={'generation':['123'],'ifGenerationMatch':['123'],'ifMetagenerationMatch':['9']}
    assert json.loads(calls[1].data)=={'eventBasedHold':False}
    with pytest.raises(ValueError,match='restricted'):stage.GcsObjectStore('private',release_event_based_hold=True)
    calls.clear()
    monkeypatch.setattr(stage,'urlopen',lambda req,**kw:calls.append(req) or BytesIO(b'{"temporaryHold":true}'))
    with pytest.raises(RuntimeError,match='temporary hold'):store.delete('warehouse/table/data/file.parquet',generation='123')
    assert [r.get_method() for r in calls]==['GET']
