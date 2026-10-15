"""Read-only transaction estimates using the same rules as formal Private Mart."""
from datetime import date
from decimal import Decimal

from .private_pipeline import calculate_marts, ledger_net_cash_flow, effective_ledger_events
from .repository import OversellError


def transaction_result(events, event, *, valuation_date: date):
    rows = list(events)
    # Validate every effective sale, including later trades affected by a backdated entry.
    shares = {}
    for row in effective_ledger_events(rows):
        key = (row['symbol'], row['currency'])
        quantity = Decimal(str(row.get('shares') or 0))
        held = shares.get(key, Decimal(0))
        if row['event_type'] == 'SELL':
            if quantity > held:
                raise OversellError('sell exceeds shares available on the transaction date')
            shares[key] = held - quantity
        elif row['event_type'] in {'BUY', 'STOCK_DIV'}:
            if row['event_type'] == 'STOCK_DIV' and held <= 0:
                raise OversellError('stock dividend requires an existing position on the transaction date')
            shares[key] = held + quantity
    marts = calculate_marts(rows, {}, valuation_date)
    realized = next((row['realized_pnl'] for row in marts['mart_user_realized_pnl']
                     if str(row['event_id']) == str(event['event_id'])), None)
    position = next((row for row in marts['mart_user_positions']
                     if row['symbol'] == event['symbol'] and row['currency'] == event['currency']), {})
    return {'cost_basis_method': 'MOVING_AVERAGE', 'ledger_version': max((row['ledger_version'] for row in rows), default=0),
            'currency': event['currency'], 'net_cash_flow': ledger_net_cash_flow(event),
            'transaction_realized_pnl': realized, 'remaining_shares': position.get('shares', Decimal(0)),
            'remaining_cost_basis': position.get('average_cost', Decimal(0)) * position.get('shares', Decimal(0)),
            'remaining_average_cost': position.get('average_cost'), 'valuation_date': valuation_date}
