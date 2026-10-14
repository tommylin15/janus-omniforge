"""Official listed/OTC membership; absence of prices never removes a member."""
from hashlib import sha256
import json
import re


def official_members(profiles):
    members = {}
    for row in profiles:
        symbol, market = str(row['symbol']), str(row['market'])
        if market not in {'TWSE', 'TPEX'} or not re.fullmatch(r'[1-9][0-9]{3}(?:[0-9]{2})?', symbol):
            raise ValueError('invalid official equity identity')
        name = str(row['stock_name']).strip()
        if not name or symbol in members:
            raise ValueError('missing name or duplicate official equity')
        members[symbol] = {'symbol': symbol, 'market': market, 'name': name}
    if {row['market'] for row in members.values()} != {'TWSE', 'TPEX'}:
        raise ValueError('both official company profiles are required')
    rows = tuple(members[key] for key in sorted(members))
    identity = sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return rows, identity


def coverage_receipt(expected, received):
    expected, received = set(expected), set(received)
    missing = expected - received
    return {'expected_count': len(expected), 'received_count': len(expected & received),
            'missing_count': len(missing), 'missing_ratio': len(missing) / len(expected) if expected else None,
            'coverage_accepted': bool(expected) and len(missing) * 10 <= len(expected),
            'missing': sorted(missing)}


def official_price_rows(rows, profiles, registered_holdings):
    allowed = {row['symbol'] for row in profiles} | set(registered_holdings)
    return tuple(row for row in rows if row['symbol'] in allowed)


def cached_coverage(receipt, expected, day):
    if (not isinstance(receipt, dict) or receipt.get('date') != day or not receipt.get('snapshot_id')
            or not isinstance(receipt.get('received'), list)):
        return None
    received = set(receipt['received'])
    return {**receipt, 'expected': sorted(expected), 'received': sorted(set(expected) & received),
            **coverage_receipt(expected, received), 'cache_hit': True}
