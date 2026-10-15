from datetime import date
from decimal import Decimal
import pytest
from services.api.trade_calculation import transaction_result
from services.api.repository import OversellError


def trade(version, kind, quantity, price, **kwargs):
    return dict(user_id='owner', event_id=str(version), event_action='ORIGINAL', ledger_version=version,
                trade_date=date(2026, 10, 12), symbol='2330', currency='TWD',
                event_type=kind, shares=Decimal(quantity), price=Decimal(price), fee=Decimal(0), tax=Decimal(0), **kwargs)


def test_partial_sale_uses_actual_fees_and_moving_average_without_market_price():
    buy = trade(1, 'BUY', '1000', '100'); buy['fee'] = Decimal('20')
    sell = trade(2, 'SELL', '300', '120'); sell.update(fee=Decimal('30'), tax=Decimal('108'))
    result = transaction_result([buy, sell], sell, valuation_date=date(2026, 10, 12))
    assert result['transaction_realized_pnl'] == Decimal('5856')
    assert result['remaining_shares'] == 700 and result['remaining_cost_basis'] == Decimal('70014')
    assert result['net_cash_flow'] == Decimal('35862')


def test_full_sale_and_reversal_replay_preserve_actual_cost():
    buy = trade(1, 'BUY', '100', '20')
    canceled = trade(2, 'BUY', '100', '100')
    reversal = dict(canceled, event_id='3', ledger_version=3, event_action='REVERSAL', reverses_event_id='2')
    sell = trade(4, 'SELL', '100', '30')
    result = transaction_result([buy, canceled, reversal, sell], sell, valuation_date=date(2026, 10, 12))
    assert result['transaction_realized_pnl'] == 1000 and result['remaining_shares'] == 0


def test_backdated_sale_checks_chronological_available_shares():
    buy = trade(1, 'BUY', '100', '20')
    sell = trade(2, 'SELL', '100', '30'); sell['trade_date'] = date(2026, 10, 11)
    with pytest.raises(OversellError): transaction_result([buy, sell], sell, valuation_date=date(2026, 10, 12))


def test_correction_that_reduces_old_buy_cannot_leave_later_oversell():
    buy = trade(1, 'BUY', '100', '20')
    sell = trade(2, 'SELL', '100', '30')
    reversal = dict(buy, event_id='3', ledger_version=3, event_action='REVERSAL', reverses_event_id='1')
    replacement = dict(buy, event_id='4', ledger_version=4, event_action='REPLACEMENT', shares=Decimal(50))
    with pytest.raises(OversellError):
        transaction_result([buy, sell, reversal, replacement], replacement, valuation_date=date(2026, 10, 12))


def test_fractional_shares_stock_dividend_and_cash_dividend_keep_common_cost_rules():
    buy = trade(1, 'BUY', '0.5', '100')
    stock = trade(2, 'STOCK_DIV', '0.5', '0')
    cash = dict(trade(3, 'CASH_DIV', '0', '0'), cash_amount=Decimal(10), fee=Decimal(1), tax=Decimal(1))
    result = transaction_result([buy, stock, cash], cash, valuation_date=date(2026, 10, 12))
    assert result['remaining_shares'] == 1 and result['remaining_cost_basis'] == 50
    assert result['transaction_realized_pnl'] is None and result['net_cash_flow'] == 8
    with pytest.raises(OversellError):
        transaction_result([stock], stock, valuation_date=date(2026, 10, 12))


def test_fee_correction_preserves_same_day_original_trade_order_through_multiple_replacements():
    buy = trade(1, 'BUY', '100', '20')
    sell = trade(2, 'SELL', '30', '40')
    reverse_buy = dict(buy, event_id='3', ledger_version=3, event_action='REVERSAL', reverses_event_id='1')
    corrected = dict(buy, event_id='4', ledger_version=4, event_action='REPLACEMENT', replaces_event_id='1', fee=Decimal(20))
    rows = [buy, sell, reverse_buy, corrected]
    result = transaction_result(rows, sell, valuation_date=date(2026, 10, 12))
    assert result['transaction_realized_pnl'] == Decimal(594)
    assert result['remaining_cost_basis'] == Decimal(1414)
    rows += [dict(corrected, event_id='5', ledger_version=5, event_action='REVERSAL', reverses_event_id='4'),
             dict(corrected, event_id='6', ledger_version=6, replaces_event_id='4', fee=Decimal(40))]
    result = transaction_result(rows, sell, valuation_date=date(2026, 10, 12))
    assert result['transaction_realized_pnl'] == Decimal(588)
    assert result['remaining_cost_basis'] == Decimal(1428)
