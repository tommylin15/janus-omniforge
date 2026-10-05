"""Bounded MIS read-through cache; never writes canonical end-of-day marts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from threading import Lock
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TAIPEI = timezone(timedelta(hours=8))


class MisQuotes:
    def __init__(self):
        self.lock = Lock()
        self.cache = {}
        self.next_fetch = 0.0
        self.market_date = None

    def prices(self, identities):
        if os.getenv('JANUS_MIS_QUOTES_ENABLED', 'false').lower() != 'true':
            raise ValueError('MIS source authorization is pending')
        channels = {symbol: ('tse' if row.get('market') == 'TWSE' else 'otc') + '_' + symbol + '.tw'
                    for symbol, row in identities.items() if row.get('market') in {'TWSE', 'TPEX', 'TPEx'}}
        if not channels:
            return {}
        if len(channels) > 200:
            raise ValueError('holding quote limit exceeded')
        # ponytail: one process/batch cache for personal use; per-symbol/shared cache if multi-owner traffic matters.
        with self.lock:
            now = monotonic()
            if now >= self.next_fetch:
                self.next_fetch = now + 10  # Includes failures and rapid manual clicks.
                query = urlencode({'ex_ch': '|'.join(channels.values()), 'json': '1', 'delay': '0'})
                request = Request('https://mis.twse.com.tw/stock/api/getStockInfo.jsp?' + query,
                                  headers={'User-Agent': 'JanusPersonalHoldings/1.0',
                                           'Referer': 'https://mis.twse.com.tw/stock/index.jsp'})
                with urlopen(request, timeout=5) as response:
                    payload = json.load(response)
                if payload.get('rtcode') != '0000' or not isinstance(payload.get('msgArray'), list):
                    raise ValueError('MIS quote response unavailable')
                self.market_date = max((str(row.get('d', '')) for row in payload['msgArray']), default='')
                for row in payload['msgArray']:
                    symbol = str(row.get('c', ''))
                    if symbol not in channels or str(row.get('ex', '')) + '_' + symbol + '.tw' != channels[symbol]:
                        continue
                    trade = row.get('trade') or {}
                    raw_price = trade.get('z') if trade.get('z') not in {None, '-'} else row.get('z')
                    raw_time = trade.get('t') if trade.get('z') not in {None, '-'} else row.get('t')
                    try:
                        price = Decimal(str(raw_price))
                        at = datetime.strptime(str(row.get('d')) + ' ' + str(raw_time), '%Y%m%d %H:%M:%S').replace(tzinfo=TAIPEI)
                        if not price.is_finite() or price <= 0:
                            continue
                    except (InvalidOperation, ValueError):
                        continue
                    self.cache[symbol] = {'price': str(price), 'quote_at': at.isoformat(),
                                          'received_at': datetime.now(TAIPEI).isoformat()}
                self.cache = {symbol: row for symbol, row in self.cache.items() if symbol in channels}
            return {symbol: dict(self.cache[symbol]) for symbol in channels if symbol in self.cache}


def value_holdings(positions, quotes, now=None):
    now = now or datetime.now(TAIPEI)
    local = now.astimezone(TAIPEI)
    market_open = local.weekday() < 5 and 540 <= local.hour * 60 + local.minute < 810
    rows, totals = [], {}
    for position in positions:
        row = dict(position)
        quote = quotes.get(str(row['symbol']), {}) if row.get('currency') == 'TWD' else {}
        at = datetime.fromisoformat(quote['quote_at']) if quote else None
        fresh = at is not None and at.date() == now.astimezone(TAIPEI).date() and 0 <= (now-at).total_seconds() <= 120
        price = Decimal(quote['price']) if quote else None
        shares, average = Decimal(str(row['shares'])), Decimal(str(row['average_cost']))
        cost = shares * average
        value = price * shares if price is not None else None
        pnl = value - cost if value is not None else None
        row.update(market_price=str(price) if price is not None else None,
                   market_value=str(value) if value is not None else None,
                   unrealized_pnl=str(pnl) if pnl is not None else None,
                   unrealized_return=str(pnl/cost) if pnl is not None and cost else None,
                   price_status='available' if fresh else 'stale' if quote else 'missing',
                   quote_at=quote.get('quote_at'), received_at=quote.get('received_at'),
                   quote_session=quote.get('session'), freshness_seconds=(now-at).total_seconds() if at else None,
                   quote_route_version=quote.get('route_version'), price_date=at.date().isoformat() if at else None,
                   missing_reason=None if fresh else 'intraday_quote_stale' if quote else 'intraday_quote_missing', price_source='twse_mis', valuation_kind='intraday')
        rows.append(row)
        total = totals.setdefault(row['currency'], {'currency': row['currency'], 'market_value': Decimal(0),
                                                    'cost_basis': Decimal(0), 'affected_symbols': [],
                                                    'missing_price_count': 0, 'stale_price_count': 0})
        total['cost_basis'] += cost
        if not fresh:
            total['affected_symbols'].append(row['symbol'])
            total['missing_price_count' if not quote else 'stale_price_count'] += 1
        if value is not None:
            total['market_value'] += value
    summaries = []
    for total in totals.values():
        cost, value, affected = total['cost_basis'], total['market_value'], total['affected_symbols']
        missing = total['missing_price_count'] > 0
        summaries.append({**total, 'cost_basis': str(cost), 'market_value': None if missing else str(value),
                          'unrealized_pnl': None if missing else str(value-cost),
                          'unrealized_return': None if missing or not cost else str((value-cost)/cost),
                          'aggregate_status': 'withheld' if missing else 'stale' if affected else 'available',
                          'affected_symbol_count': len(affected), 'valuation_date': now.date().isoformat(),
                          'valuation_kind': 'intraday'})
    return {'positions': rows, 'items': summaries, 'source': 'twse_mis', 'checked_at': now.isoformat(),
            'market_open': market_open}
