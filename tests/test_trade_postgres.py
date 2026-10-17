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

from services.api.models import CashPositionIn, LedgerEventIn
from services.api.repository import ConflictError, NotFoundError, OversellError, PostgresWorkspaceRepository


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
            cash = (root/'infra/postgres/migrations/062_owner_cash_balance_snapshots.sql').read_text(encoding='utf-8')
            statement = re.search(r'CREATE TABLE IF NOT EXISTS private\.cash_balance_snapshots \(.*?\n\);', cash, re.S)
            assert statement is not None
            connection.execute(statement[0])
            connection.execute('ALTER TABLE private.ledger_events ADD COLUMN fee_rule_snapshot jsonb')
            projection = (root/'infra/postgres/migrations/059_ledger_automatic_charges.sql').read_text(encoding='utf-8')
            function = re.search(r'CREATE OR REPLACE FUNCTION private\.refresh_current_positions.*?\$\$;', projection, re.S)
            assert function is not None
            connection.execute(function[0])
            owners = (uuid4(), uuid4())
            for owner in owners:
                connection.execute('INSERT INTO private.users(user_id,google_sub,display_email) VALUES (%s,%s,%s)',
                                   (owner, str(owner), 'synthetic-ci@example.invalid'))
                connection.execute("INSERT INTO private.broker_profile_revisions(user_id,version,fee_discount_multiplier,minimum_fee,cash_strategy,idempotency_key) VALUES (%s,1,0,0,'balanced','ci-profile')", (owner,))
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
    saved = repo.add_ledger(owner, event(expected_ledger_version=0, expected_broker_profile_version=1), 'buy')
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
    assert sale['transaction_result']['transaction_realized_pnl'] == 991
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
    assert sold['transaction_result']['transaction_realized_pnl'] == 447
    assert sold['transaction_result']['remaining_cost_basis'] == 1750
    assert repo.positions(owner)[0]['cost_basis'] == 1750 and repo.positions(other) == []


def test_automatic_charges_and_atomic_historical_repair_preserve_originals(ledger):
    repo, (owner, other) = ledger
    buy = repo.add_ledger(owner, event(), 'buy')
    repo.add_ledger(owner, event('SELL', shares='30', price='40'), 'sell')
    with repo._connection() as connection:
        connection.execute("INSERT INTO private.broker_profile_revisions(user_id,version,fee_discount_multiplier,minimum_fee,cash_strategy,idempotency_key) VALUES (%s,2,0.4,20,'balanced','discount')", (owner,))
    preview = repo.preview_ledger(owner, event())
    assert preview['fee'] == 20 and preview['tax'] == 0
    assert preview['broker_profile_version'] == 2 and repo.latest_ledger_version(owner) == 2
    before = repo.ledger_history(owner, None, None)
    dry = repo.reprice_ledger_fees(owner, expected_ledger_version=2, expected_profile_version=2)
    assert dry['corrections'] == 2 and repo.latest_ledger_version(owner) == 2
    result = repo.reprice_ledger_fees(owner, expected_ledger_version=2, expected_profile_version=2, apply=True)
    assert result['ledger_version'] == 6 and repo.latest_ledger_version(other) == 0
    after = {row['event_id']: row for row in repo.ledger_history(owner, None, None)}
    assert all(after[row['event_id']] == row for row in before)
    assert repo.positions(owner)[0]['cost_basis'] == Decimal('1414')
    repeat = repo.add_ledger(owner, event(), 'buy')
    assert repeat['event_id'] == buy['event_id']  # A new profile cannot break a stored idempotent response.
    again = repo.reprice_ledger_fees(owner, expected_ledger_version=6, expected_profile_version=2, apply=True)
    assert again['corrections'] == 0 and again['ledger_version'] == 6
    with pytest.raises(ConflictError):
        repo.reprice_ledger_fees(owner, expected_ledger_version=2, expected_profile_version=2, apply=True)


def test_fee_repair_rolls_back_all_corrections_if_second_write_fails(ledger, monkeypatch):
    repo, (owner, _) = ledger
    repo.add_ledger(owner, event(), 'buy')
    repo.add_ledger(owner, event('SELL', shares='30', price='40'), 'sell')
    with repo._connection() as connection:
        connection.execute("INSERT INTO private.broker_profile_revisions(user_id,version,fee_discount_multiplier,minimum_fee,cash_strategy,idempotency_key) VALUES (%s,2,0.4,20,'balanced','discount')", (owner,))
    before = repo.ledger_history(owner, None, None)
    positions = repo.positions(owner)
    original = repo._correct_ledger
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError('injected failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(repo, '_correct_ledger', fail_second)
    with pytest.raises(RuntimeError, match='injected failure'):
        repo.reprice_ledger_fees(owner, expected_ledger_version=2, expected_profile_version=2, apply=True)
    assert repo.latest_ledger_version(owner) == 2
    assert repo.ledger_history(owner, None, None) == before and repo.positions(owner) == positions


def test_cash_anchor_dividend_correction_reversal_and_replay(ledger):
    repo, (owner, other) = ledger
    buy = repo.add_ledger(owner, event(), 'buy-before-anchor')
    repo.set_cash_position(owner, CashPositionIn(amount='1000', expected_version=0), 'cash-anchor')
    assert repo.cash_position(other)['cash_status'] == 'not_configured'
    dividend = LedgerEventIn(event_type='CASH_DIV', symbol='6488', cash_amount='100',
                             trade_date=date(2026, 10, 12))
    paid = repo.add_ledger(owner, dividend, 'dividend')
    assert repo.cash_position(owner)['cash_balance'] == 1100
    repo.add_ledger(owner, dividend, 'dividend')
    assert repo.cash_position(owner)['cash_balance'] == 1100
    corrected = repo.correct_ledger(owner, paid['event_id'], 1,
                                    dividend.model_copy(update={'cash_amount': Decimal('150')}), 'correct-dividend')
    assert repo.cash_position(owner)['cash_balance'] == 1150
    repo.reverse_ledger(owner, corrected['event_id'], 1, 'void-dividend')
    repo.reverse_ledger(owner, corrected['event_id'], 1, 'void-dividend')
    assert repo.cash_position(owner)['cash_balance'] == 1000
    # Reversing a pre-anchor purchase refunds its original persisted cash flow once.
    repo.reverse_ledger(owner, buy['event_id'], 1, 'void-old-buy')
    cash = repo.cash_position(owner)
    assert cash['cash_balance'] == 3000
    assert cash['anchor_ledger_version'] == 1
    assert cash['current_ledger_version'] == repo.latest_ledger_version(owner)
    assert repo.cash_position(other)['cash_balance'] is None


def test_cash_reset_versions_owner_boundary_and_failed_trade_are_atomic(ledger):
    repo, (owner, other) = ledger
    setting = CashPositionIn(amount='100', expected_version=0)
    repo.set_cash_position(owner, setting, 'set-cash')
    repo.set_cash_position(other, setting, 'set-cash')
    buy = repo.add_ledger(owner, event(), 'buy')
    assert repo.cash_position(owner)['cash_balance'] == -1900
    # A retry of the original reset must not reset away subsequent trading flows.
    assert repo.set_cash_position(owner, setting, 'set-cash')['cash_balance'] == -1900
    with pytest.raises(ConflictError):
        repo.set_cash_position(owner, setting, 'stale-reset')
    with pytest.raises(ConflictError):
        repo.set_cash_position(owner, CashPositionIn(amount='200', expected_version=0), 'set-cash')
    with pytest.raises(NotFoundError):
        repo.reverse_ledger(other, buy['event_id'], 1, 'foreign-reversal')
    before = repo.cash_position(owner)
    with pytest.raises(OversellError):
        repo.add_ledger(owner, event('SELL', shares='101', price='30'), 'oversell')
    assert repo.cash_position(owner) == before
    assert repo.cash_position(other)['cash_balance'] == 100
    reset = repo.set_cash_position(owner, CashPositionIn(amount='500', expected_version=1), 'reset')
    assert reset['cash_balance'] == 500
    assert reset['anchor_ledger_version'] == repo.latest_ledger_version(owner)


def test_concurrent_cash_resets_commit_only_one_expected_version(ledger):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    repo, (owner, other) = ledger
    barrier = Barrier(2)
    def reset(amount):
        barrier.wait(timeout=10)
        try:
            return repo.set_cash_position(owner,
                CashPositionIn(amount=amount, expected_version=0), 'cash-' + amount)
        except ConflictError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reset, ('100', '200')))
    committed = [result for result in results if result is not None]
    assert len(committed) == 1
    assert repo.cash_position(owner)['cash_balance'] == committed[0]['cash_balance']
    assert repo.cash_position(owner)['cash_version'] == 1
    assert repo.latest_ledger_version(owner) == 0
    assert repo.cash_position(other)['cash_status'] == 'not_configured'
