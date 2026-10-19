"""Approved provider history. Receipt time is never historical publication time."""
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
import json
import re

from .dq import validate_ohlcv
from .yahoo_eps import _Text, parse_reported_quarter


def number(value, *, nonnegative=False):
    result = Decimal(str(value))
    if not result.is_finite() or nonnegative and result < 0:
        raise ValueError('invalid_provider_number')
    return str(result)


def finmind_rows(raw, symbol, start, end):
    document = json.loads(raw)
    if document.get('status') != 200 or not isinstance(document.get('data'), list):
        raise ValueError('finmind_unavailable')
    rows = document['data']
    if len(rows) > 2000:
        raise ValueError('provider_row_limit')
    for row in rows:
        if row.get('stock_id') != symbol or not start <= date.fromisoformat(row['date']) <= end:
            raise ValueError('provider_identity_or_date_mismatch')
    return rows


def parse_prices(raw, symbol, market, *, start, end, received_at):
    rows = []
    for row in finmind_rows(raw, symbol, start, end):
        rows.append({'symbol': symbol, 'market': market, 'trade_date': row['date'],
            **{key: number(row[field], nonnegative=True) for key, field in (
                ('open','open'), ('high','max'), ('low','min'), ('close','close'),
                ('volume_shares','Trading_Volume'), ('turnover_twd','Trading_money'))},
            'source_id': 'finmind', 'observed_at': received_at})
    checked = validate_ohlcv(rows, analysis_as_of=end)
    if checked.quarantined or not checked.accepted:
        raise ValueError('provider_ohlcv_not_qualified')
    return list(checked.accepted)


def parse_valuation(raw, symbol, market, *, start, end, received_at):
    rows, seen = [], set()
    for row in finmind_rows(raw, symbol, start, end):
        if row['date'] in seen:
            raise ValueError('duplicate_valuation_day')
        seen.add(row['date'])
        values = {}
        for key, field in (('pe_ratio','PER'), ('pb_ratio','PBR'), ('dividend_yield_percent','dividend_yield')):
            value = None if row.get(field) in (None, '') else number(row[field])
            values[key] = value if value is not None and Decimal(value) >= 0 else None
        rows.append({'symbol':symbol, 'market':market, 'observed_date':row['date'],
            'observed_at':received_at, 'source_id':'finmind', **values})
    return rows


def parse_revenue(raw, symbol, *, start, end, received_at):
    rows, seen = [], set()
    for row in finmind_rows(raw, symbol, start, end):
        year, month = int(row['revenue_year']), int(row['revenue_month'])
        period = date(year, month, monthrange(year,month)[1])
        if period >= date.fromisoformat(row['date']) or period > end or (year, month) in seen:
            raise ValueError('invalid_revenue_period')
        seen.add((year, month))
        rows.append({'symbol':symbol, 'fiscal_year':year, 'fiscal_quarter':(month-1)//3+1,
            'fiscal_month':month, 'fiscal_period_end':period.isoformat(),
            'statement_type':'monthly_revenue', 'metric':f'monthly_revenue_{month:02d}', 'period_basis':'monthly',
            'value':str(Decimal(number(row['revenue'], nonnegative=True))/1000),
            'unit':'TWD_thousands', 'currency':'TWD', 'source_id':'finmind',
            'availability_at':received_at, 'observed_at':received_at,
            'published_at':None, 'publication_time_authoritative':False,
            'availability_basis':'source_response_receipt', 'report_scope':'provider_reported',
            'historical_publication_status':'unknown'})
    return rows


def parse_eps_history(raw, symbol, market, *, received_at):
    parser = _Text()
    parser.feed(raw.decode('utf-8'))
    sections = ' '.join(parser.parts).split('單季每股盈餘',1)
    if len(sections) != 2:
        raise ValueError('missing_single_quarter_table')
    table = sections[1].split('單季每股盈餘',1)[0]
    periods = re.findall(r'\b(20\d{2})\s+Q([1-4])\b',table)
    if len(periods) != len(set(periods)):
        raise ValueError('duplicate_eps_quarter')
    today = datetime.fromisoformat(received_at.replace('Z','+00:00')).date()
    output = []
    for year, quarter in sorted(periods, reverse=True):
        year, quarter = int(year), int(quarter)
        period = date(year,quarter*3,monthrange(year,quarter*3)[1])
        if period >= today:
            raise ValueError('future_eps_period')
        output.append(parse_reported_quarter(raw,symbol,year=year,quarter=quarter,
            received_at=received_at,suffix='TW' if market=='TWSE' else 'TWO'))
        if len(output) == 12:
            break
    if not output:
        raise ValueError('missing_eps_history')
    return output
