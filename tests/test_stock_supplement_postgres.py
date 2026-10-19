"""Real outbox transactions in a disposable CI database; never the dev ledger."""
from contextlib import contextmanager
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from ingestion_core.stock_supplement import claim, finish, still_wanted


@pytest.fixture
def queue_db():
    source = os.getenv('ANALYSIS_TEST_DSN')
    if not source:
        pytest.skip('disposable PostgreSQL is required in Release CI')
    settings = conninfo_to_dict(source)
    assert settings['host'] in {'127.0.0.1','localhost'} and settings['dbname']=='janus_analysis_test'
    name = 'janus_supplement_'+uuid4().hex[:12]
    with psycopg.connect(source,autocommit=True) as admin:
        for role in ('janus_control','janus_private_api','janus_private_pipeline','janus_public_api','janus_web_control'):
            if not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(source,dbname=name)
    try:
        with psycopg.connect(dsn,autocommit=True) as connection:
            connection.execute('CREATE SCHEMA control AUTHORIZATION janus_control')
            connection.execute('CREATE SCHEMA private AUTHORIZATION janus_control')
            connection.execute('GRANT USAGE ON SCHEMA control,private TO janus_private_api')
            connection.execute('SET ROLE janus_control')
            connection.execute('CREATE TABLE control.stock_master(symbol text PRIMARY KEY,market text,enabled boolean)')
            connection.execute("INSERT INTO control.stock_master VALUES('1513','TWSE',true),('6488','TPEX',true)")
            connection.execute('CREATE TABLE control.schema_migrations(version text PRIMARY KEY)')
            connection.execute('CREATE TABLE control.market_serving_recent(source_id text,dataset_id text,payload_json jsonb)')
            connection.execute('CREATE TABLE private.watchlist(user_id uuid,symbol text,active boolean)')
            connection.execute('CREATE TABLE private.current_positions(user_id uuid,symbol text,shares numeric)')
            connection.execute('GRANT SELECT ON control.stock_master,private.watchlist,private.current_positions TO janus_private_api')
            connection.execute('RESET ROLE')
            migration = Path('infra/postgres/migrations/066_stock_supplement_queue.sql').read_text(encoding='utf-8')
            connection.execute('\n'.join(line for line in migration.splitlines() if not line.startswith('\\')))
        yield dsn
    finally:
        with psycopg.connect(source,autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def test_demand_is_transactional_deduplicated_and_last_owner_cancels(queue_db):
    owner, other = uuid4(),uuid4()
    with psycopg.connect(queue_db,autocommit=True) as connection:
        with pytest.raises(RuntimeError):
            with connection.transaction():
                connection.execute("INSERT INTO private.watchlist VALUES(%s,'1513',true)",(owner,))
                connection.execute('SELECT control.sync_stock_supplement_demand()')
                raise RuntimeError('rollback synthetic mutation')
        assert connection.execute('SELECT count(*) FROM control.stock_supplement_requests').fetchone()[0]==0
        connection.execute("INSERT INTO private.watchlist VALUES(%s,'1513',true)",(owner,))
        connection.execute("INSERT INTO private.current_positions VALUES(%s,'1513',10)",(other,))
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        request = claim(connection)
        assert request[0]=='1513'
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        assert claim(connection) is None
        connection.execute('DELETE FROM private.watchlist')
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        assert still_wanted(connection,request)
        connection.execute('DELETE FROM private.current_positions')
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        assert not still_wanted(connection,request)
        connection.execute("INSERT INTO private.watchlist VALUES(%s,'1513',true)",(owner,))
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        newer = claim(connection)
        assert newer[1]>request[1] and newer[2]!=request[2]
        finish(connection,request,{'ready':True})
        assert still_wanted(connection,newer)
        finish(connection,newer,{'ready':False})
        assert connection.execute('SELECT status,next_attempt_at>now() FROM control.stock_supplement_requests').fetchone()==('partial',True)


def test_expired_worker_retries_and_public_identity_cannot_read_queue(queue_db):
    with psycopg.connect(queue_db,autocommit=True) as connection:
        connection.execute("INSERT INTO private.watchlist VALUES(%s,'6488',true)",(uuid4(),))
        connection.execute('SELECT control.sync_stock_supplement_demand()')
        old = claim(connection)
        connection.execute("UPDATE control.stock_supplement_requests SET started_at=now()-interval '36 minutes'")
        new = claim(connection)
        assert new[2]!=old[2] and not still_wanted(connection,old)
        assert connection.execute("SELECT has_table_privilege('janus_public_api','control.stock_supplement_requests','SELECT')").fetchone()==(False,)
        columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='control' AND table_name='stock_supplement_requests'").fetchall()
        assert not {'user_id','shares','owner_id'} & {r[0] for r in columns}
