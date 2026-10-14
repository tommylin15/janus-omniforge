"""Real ledger transactions in a disposable CI database, never the dev ledger."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import re
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from services.api.models import LedgerEventIn
from services.api.repository import ConflictError, OversellError, PostgresWorkspaceRepository


@pytest.fixture
def ledger():
    source = os.getenv('ANALYSIS_TEST_DSN')
    if not source:
        pytest.skip('isolated CI PostgreSQL not configured')
    settings = conninfo_to_dict(source)
    assert settings['host'] in {'127.0.0.1', 'localhost'} and settings['dbname'] == 'janus_analysis_test'
    name = 'janus_trades_' + uuid4().hex[:12]
    root = Path(__file__).parents[1]
    with psycopg.connect(source, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(source, dbname=name)
    try:
        with psycopg.connect(dsn) as connection:
            connection.execute('CREATE SCHEMA private')
            original = (root/'infra/postgres/migrations/014_private_workspace.sql').read_text(encoding='utf-8')
            projection = (root/'infra/postgres/migrations/041_operational_position_projection.sql').read_text(encoding='utf-8')
            profile = (root/'infra/postgres/migrations/044_quotes_broker_profile.sql').read_text(encoding='utf-8')
            for table, source_sql in [('users', original), ('ledger_events', original), ('change_log', original),
                                      ('current_positions', projection), ('broker_profile_revisions', profile)]:
                statement = re.search(r'CREATE TABLE IF NOT EXISTS private\.' + table + r' \(.*?\n\);', source_sql, re.S)
                assert statement is not None
                connection.execute(statement[0])
            function = re.search(r'CREATE OR REPLACE FUNCTION private\.refresh_current_positions.*?\$\$;', projection, re.S)
            assert function is not None
            connection.execute(function[0])
            owners = (uuid4(), uuid4())
            for owner in owners:
                connection.execute('INSERT INTO private.users(user_id,google_sub,display_email) VALUES (%s,%s,%s)',
                                   (owner, str(owner), 'synthetic-ci@example.invalid'))
        repo = PostgresWorkspaceRepository(dsn)
        @contextmanager
        def connect():
            with psycopg.connect(dsn, row_factory=dict_row) as connection:
                with connection.transaction():
                    yield connection
        repo._connection = connect
        yield repo, owners
    finally:
        with psycopg.connect(source, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def event(kind='BUY', shares='100', price='20', **extra):
    return LedgerEventIn(event_type=kind, symbol='6488', shares=shares, price=price,
                         trade_date=date(2026, 10, 12), fee=0, tax=0, **extra)


def test_preview_is_read_only_and_save_returns_cost_and_rejects_stale_version(ledger):
    repo, (owner, other) = ledger
    preview = repo.preview_ledger(owner, event())
    assert preview['remaining_cost_basis'] == 2000 and preview['based_on_ledger_version'] == 0
    assert repo.latest_ledger_version(owner) == 0 and repo.positions(owner) == []
    saved = repo.add_ledger(owner, event(expected_ledger_version=0, expected_broker_profile_version=0), 'buy')
    assert saved['transaction_result']['remaining_shares'] == 100
    assert repo.positions(owner)[0]['cost_basis'] == Decimal(2000)
    assert repo.positions(other) == []
    repeated = repo.add_ledger(owner, event(expected_ledger_version=0), 'buy')
    assert repeated['event_id'] == saved['event_id'] and repo.latest_ledger_version(owner) == 1
    with pytest.raises(ConflictError):
        repo.add_ledger(owner, event(shares='101'), 'buy')
    with pytest.raises(ConflictError):
        repo.add_ledger(owner, event(expected_ledger_version=0), 'stale')
    assert repo.latest_ledger_version(owner) == 1


def test_correction_cannot_erase_cost_required_by_a_later_sale_and_rolls_back(ledger):
    repo, (owner, _) = ledger
    buy = repo.add_ledger(owner, event(), 'buy')
    sale = repo.add_ledger(owner, event('SELL', shares='100', price='30'), 'sell')
    assert sale['transaction_result']['transaction_realized_pnl'] == 1000
    with pytest.raises(OversellError):
        repo.correct_ledger(owner, buy['event_id'], 1, event(shares='50'), 'bad-correction')
    assert repo.latest_ledger_version(owner) == 2 and len(repo.ledger_history(owner, None, None)) == 2
    assert repo.positions(owner) == []


def test_corrected_buy_and_partial_sale_have_one_cost_rule_and_owner_boundary(ledger):
    repo, (owner, other) = ledger
    buy = repo.add_ledger(owner, event(), 'buy')
    replacement = repo.correct_ledger(owner, buy['event_id'], 1, event(price='25'), 'correction')
    assert replacement['transaction_result']['remaining_cost_basis'] == 2500
    sold = repo.add_ledger(owner, event('SELL', shares='30', price='40'), 'sale')
    assert sold['transaction_result']['transaction_realized_pnl'] == 450
    assert sold['transaction_result']['remaining_cost_basis'] == 1750
    assert repo.positions(owner)[0]['cost_basis'] == 1750 and repo.positions(other) == []
