"""Telemetry must be optional, bounded, owner-bound and retry safe."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.usage import UsageBatch


def event(**changes):
    return dict(event_id=str(uuid4()), session_id=str(uuid4()), feature_id='journal',
                event_type='page_view', client_time=datetime.now(timezone.utc).isoformat(), **changes)


def batch(events=None, **changes):
    return dict(batch_id=str(uuid4()),events=events or [event()],**changes)


@pytest.mark.parametrize('changes',[
    {'user_id':str(uuid4())}, {'symbol':'2330'}, {'payload':{'body':'private'}},
    {'feature_id':'trade:2330'}, {'action_key':'search text'},
    {'client_time':'2026-01-01T00:00:00Z'}, {'client_time':'2026-10-18T00:00:00'},
    {'active_duration_ms':True}, {'active_duration_ms':100},
])
def test_rejects_identity_free_text_and_invalid_time(changes):
    value=event()
    value.update(changes)
    with pytest.raises(ValidationError):
        UsageBatch.model_validate(batch([value]))


def test_cross_midnight_oversized_and_repeated_events_rejected():
    now=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    midnight=now.replace(hour=0,minute=0,second=0,microsecond=0)
    value=event(); value.update(event_type='active_interval',active_duration_ms=2000,
                                client_time=(midnight+timedelta(seconds=1)).isoformat())
    with pytest.raises(ValidationError): UsageBatch.model_validate(batch([value]))
    value=event()
    with pytest.raises(ValidationError): UsageBatch.model_validate(batch([value,value]))
    with pytest.raises(ValidationError): UsageBatch.model_validate(batch([event() for _ in range(21)]))
    assert UsageBatch.model_validate(batch()).events[0].feature_id=='journal'


def test_api_binds_identity_and_admin_audience(monkeypatch):
    from tests.test_user_api import Repository,Store,Core,auth,admin_auth,USER_ID
    from services.api.app import create_app
    from fastapi.testclient import TestClient
    from services.api.usage import UsageService
    calls=[]
    monkeypatch.setattr(UsageService,'ingest',lambda self,owner,value: calls.append(owner) or {'accepted':1})
    monkeypatch.setattr(UsageService,'read',lambda self,**values: {'items':[], 'status':'no_data'})
    repo=Repository()
    def verify(token,audience):
        return {'iss':'https://accounts.google.com','aud':'admin-client' if token=='valid-admin-token' else 'user-client',
                'sub':'synthetic','email':'admin@example.com','email_verified':True,'exp':1900000000}
    api=TestClient(create_app(repo,Store(),verify,audience='user-client',core=Core(),
        admin_verifier=verify,admin_audience='admin-client',admin_emails=frozenset({'admin@example.com'})))
    assert api.post('/api/v1/me/usage/batches',json=batch(),headers=auth()).status_code==200
    assert calls==[USER_ID]
    spoof=event(); spoof['feature_id']='admin_overview'
    assert api.post('/api/v1/me/usage/batches',json=batch([spoof]),headers=auth()).status_code==422
    assert api.post('/api/v1/admin/usage/self/batches',json=batch(),headers=admin_auth()).status_code==422
    assert api.get('/api/v1/admin/usage/overview',headers=auth()).status_code==401
    assert api.get('/api/v1/me/usage/preference',headers=admin_auth()).status_code==401
    assert api.get('/api/v1/admin/usage/overview?days=10000',headers=admin_auth()).status_code==422
    assert api.get('/api/v1/admin/usage/overview',headers=admin_auth()).status_code==200
    assert api.post('/api/v1/me/usage/batches',content=b' '*16385,headers=auth()).status_code==413


def test_postgres_idempotency_retention_and_opt_out():
    import os,re
    from contextlib import contextmanager
    from pathlib import Path
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    from services.api.repository import PostgresWorkspaceRepository
    from services.api.usage import UsageService
    source=os.getenv('ANALYSIS_TEST_DSN')
    if not source: pytest.skip('isolated CI PostgreSQL not configured')
    settings=conninfo_to_dict(source)
    assert settings['host'] in ('127.0.0.1','localhost') and settings['dbname']=='janus_analysis_test'
    name='janus_usage_'+uuid4().hex[:12]
    with psycopg.connect(source,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn=make_conninfo(source,dbname=name)
    try:
        with psycopg.connect(dsn) as db:
            db.execute('CREATE SCHEMA private')
            ddl=(Path(__file__).parents[1]/'infra/postgres/migrations/064_usage_analytics.sql').read_text()
            for statement in re.findall(r'CREATE (?:TABLE|INDEX) IF NOT EXISTS .*?;',ddl,re.S): db.execute(statement)
            db.execute('CREATE TABLE private.users(user_id uuid PRIMARY KEY,display_email text)')
            owner,other=uuid4(),uuid4()
            db.execute("INSERT INTO private.users VALUES (%s,'synthetic@example.invalid'),(%s,'other@example.invalid')",(owner,other))
        repo=PostgresWorkspaceRepository(dsn)
        @contextmanager
        def connect():
            with psycopg.connect(dsn,row_factory=dict_row) as db:
                yield db
        repo._connection=connect
        service=UsageService(repo)
        value=UsageBatch.model_validate(batch())
        assert service.ingest(owner,value)['status']=='disabled'
        service.preference(owner,True)
        assert service.ingest(owner,value)['accepted']==1
        assert service.ingest(owner,value)['status']=='duplicate'
        repeated=value.model_copy(update={'batch_id':uuid4()})
        assert service.ingest(owner,repeated)['accepted']==0
        assert service.read(actor='admin',user_id=other)['status']=='no_data'
        assert service.read(actor='admin',user_id=owner)['items'][0]['page_views']==1
        assert service.read(actor='admin',user_id=owner)['items'][0]['sessions']==1
        broken=event(); broken['event_type']='feature_action'
        atomic=UsageBatch.model_validate(batch([broken]))
        with connect() as db:
            db.execute('ALTER TABLE private.usage_monthly_summary ADD CONSTRAINT reject_actions CHECK(actions=0)')
        with pytest.raises(psycopg.errors.CheckViolation):
            service.ingest(owner,atomic)
        with connect() as db:
            assert db.execute('SELECT count(*) AS n FROM private.usage_ingest_receipts WHERE batch_id=%s',(atomic.batch_id,)).fetchone()['n']==0
            db.execute('ALTER TABLE private.usage_monthly_summary DROP CONSTRAINT reject_actions')
        assert service.ingest(owner,atomic)['accepted']==1
        with connect() as db:
            db.execute("UPDATE private.usage_recent_events SET received_at=now()-interval '8 days' WHERE event_id=%s", (value.events[0].event_id,))
            db.execute("INSERT INTO private.usage_user_feature_daily(user_id,day,feature_id,last_event_at) VALUES (%s,current_date-181,'today',now())",(owner,))
        service.purge()
        with connect() as db:
            assert db.execute('SELECT count(*) AS n FROM private.usage_recent_events WHERE event_id=%s',(value.events[0].event_id,)).fetchone()['n']==0
            assert db.execute('SELECT count(*) AS n FROM private.usage_user_feature_daily WHERE day<current_date-180').fetchone()['n']==0
        service.preference(owner,False)
        assert service.ingest(owner,UsageBatch.model_validate(batch()))['status']=='disabled'
        service.delete(owner)
        assert service.read(actor='admin',user_id=owner)['status']=='no_data'
        with connect() as db:
            db.execute('DELETE FROM private.users WHERE user_id=%s',(owner,))
        from services.api.repository import NotFoundError
        with pytest.raises(NotFoundError): service.preference(owner,True)
        service.purge()
    finally:
        with psycopg.connect(source,autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
