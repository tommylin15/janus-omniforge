"""Versioned TWD default charges; broker discounts never discount transaction tax."""
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import re

RULE_VERSION = 'tw-default-fees.v1'


def automatic_charges(value, profile):
    if value.currency != 'TWD':
        raise ValueError('自動費稅僅支援 TWD')
    if value.event_type not in {'BUY', 'SELL'}:
        return Decimal(0), Decimal(0), {'rule_version': RULE_VERSION, 'tax_rate': '0',
                                        'broker_profile_version': profile['version'] if profile else 0}
    if not profile or 'fee_discount_multiplier' not in profile:
        raise ValueError('請先在券商設定保存手續費折扣與最低費用')
    discount = Decimal(str(profile['fee_discount_multiplier']))
    minimum = Decimal(str(profile['minimum_fee']))
    if not discount.is_finite() or not minimum.is_finite() or not 0 <= discount <= 1 or minimum < 0:
        raise ValueError('券商費率設定無效')
    symbol = value.symbol
    if re.fullmatch(r'00\d{2,4}[A-Z]?', symbol):
        rate = Decimal('0.001')
        if symbol.endswith('B') and date(2017, 1, 1) <= value.trade_date <= date(2026, 12, 31):
            rate = Decimal(0)
    elif re.fullmatch(r'91\d{2,4}', symbol):
        rate = Decimal('0.001')
    elif re.fullmatch(r'[1-9]\d{3}', symbol):
        rate = Decimal('0.003')
    else:
        raise ValueError('商品缺少已核實的預設證交稅規則')
    if value.event_type == 'BUY':
        rate = Decimal(0)
    gross = value.shares * value.price
    fee = max(minimum, gross * Decimal('0.001425') * discount).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    tax = (gross * rate).quantize(Decimal(1), rounding=ROUND_DOWN)
    return fee, tax, {
        'rule_version': RULE_VERSION, 'broker_profile_version': profile['version'],
        'fee_rate': '0.001425', 'discount': str(discount), 'minimum_fee': str(minimum),
        'tax_rate': str(rate), 'fee_rounding': 'HALF_UP_TWD', 'tax_rounding': 'DOWN_TWD',
        'tax_policy': 'regular-sale-default',
    }
