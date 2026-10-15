from datetime import date
from decimal import Decimal

import pytest

from services.api.models import LedgerEventIn
from services.api.trade_fees import automatic_charges


def event(symbol='2330', kind='SELL', day=date(2026, 10, 15), **extra):
    return LedgerEventIn(event_type=kind, symbol=symbol, trade_date=day,
                         shares='1000', price='100', **extra)


PROFILE = {'version': 3, 'fee_discount_multiplier': Decimal('0.4'), 'minimum_fee': Decimal(20)}


@pytest.mark.parametrize('symbol,kind,day,tax', [
    ('2330', 'BUY', date(2026, 10, 15), 0),
    ('2330', 'SELL', date(2026, 10, 15), 300),
    ('9105', 'SELL', date(2026, 10, 15), 100),
    ('0050', 'SELL', date(2026, 10, 15), 100),
    ('006208', 'SELL', date(2026, 10, 15), 100),
    ('00719B', 'SELL', date(2026, 10, 15), 0),
    ('00719B', 'SELL', date(2027, 1, 1), 100),
])
def test_default_charges_use_profile_discount_and_dated_tax(symbol, kind, day, tax):
    fee, actual_tax, rule = automatic_charges(event(symbol, kind, day, fee='999', tax='999'), PROFILE)
    assert fee == 57 and actual_tax == tax
    assert rule['discount'] == '0.4' and rule['broker_profile_version'] == 3


def test_minimum_rounding_and_missing_profile_do_not_guess():
    value = event().model_copy(update={'shares': Decimal(1), 'price': Decimal('100.9')})
    fee, tax, _ = automatic_charges(value, PROFILE)
    assert fee == 20 and tax == 0
    with pytest.raises(ValueError, match='券商設定'):
        automatic_charges(value, None)
    with pytest.raises(ValueError, match='商品'):
        automatic_charges(event('ABC'), PROFILE)


def test_dividends_have_no_brokerage_or_securities_transaction_tax():
    value = LedgerEventIn(event_type='CASH_DIV', symbol='2330', trade_date=date(2026, 10, 15), cash_amount='1000')
    assert automatic_charges(value, None)[:2] == (0, 0)


def test_dividend_preview_keeps_profile_checkpoint():
    value = LedgerEventIn(event_type='CASH_DIV', symbol='2330', trade_date=date(2026, 10, 15), cash_amount=100)
    assert automatic_charges(value, PROFILE)[2]['broker_profile_version'] == 3


def test_repair_operator_keeps_owner_scope_and_existing_minimum_and_cash():
    from scripts.gcp.ledger_fee_repair import repair_owner_fees
    class Repo:
        profile = {'version': 4, 'fee_discount_multiplier': '1', 'minimum_fee': '10',
                   'cash_strategy': 'reserve', 'declared_cash': None, 'cash_as_of': None}
        version = 9
        corrected = False
        def broker_profile(self, owner):
            assert owner == 'authorized-owner'
            return self.profile
        def latest_ledger_version(self, owner):
            assert owner == 'authorized-owner'
            return self.version
        def save_broker_profile(self, owner, value, key):
            assert owner == 'authorized-owner' and value.expected_version == 4
            assert value.fee_discount_multiplier == Decimal('0.4') and value.minimum_fee == 10
            assert value.cash_strategy == 'reserve' and value.declared_cash is None
            self.profile = {**self.profile, 'version': 5, 'fee_discount_multiplier': '0.4'}
            return self.profile
        def reprice_ledger_fees(self, owner, *, expected_ledger_version, expected_profile_version, apply=False):
            assert owner == 'authorized-owner' and expected_ledger_version == self.version
            assert expected_profile_version == 5
            changes = 0 if self.corrected else 2
            if apply:
                self.version += changes * 2
                self.corrected = True
            return {'status': 'applied' if apply else 'preview', 'effective_events': 2, 'corrections': changes,
                    'based_on_ledger_version': expected_ledger_version, 'broker_profile_version': 5,
                    'ledger_version': self.version, 'fee_delta': 'private-amount'}
    repo = Repo()
    assert repair_owner_fees(repo, 'authorized-owner', expected_ledger_version=9, expected_profile_version=4)['status'] == 'profile_adjustment_required'
    result = repair_owner_fees(repo, 'authorized-owner', expected_ledger_version=9, expected_profile_version=4, apply=True)
    assert result['ledger_version'] == 13 and 'fee_delta' not in result and 'owner' not in result
