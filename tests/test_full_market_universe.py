import pytest
from ingestion_core.full_market import official_members, coverage_receipt, cached_coverage
from ingestion_core.__main__ import _market_universe


def test_membership_retains_all_equities_in_both_markets_without_price_ranking():
    profiles = [{'symbol': str(1000 + i), 'stock_name': f'股票{i}', 'market': 'TWSE' if i < 510 else 'TPEX'}
                for i in range(1010)]
    rows, identity = official_members(profiles)
    assert len(rows) == 1010
    assert official_members(list(reversed(profiles))) == (rows, identity)
    class Control:
        def full_market_snapshot(self):
            return {'status': 'available', 'items': rows, 'scope': 'all_listed_otc_equities'}
    universe, symbols = _market_universe(Control(), ('2330',))
    assert len(symbols) == 1010 and universe['scope'] == 'all_listed_otc_equities'


@pytest.mark.parametrize('profiles', [[], [{'symbol': '2330', 'stock_name': '台積電', 'market': 'TWSE'}],
    [{'symbol': '2330', 'stock_name': '', 'market': 'TWSE'}, {'symbol': '6488', 'stock_name': '環球晶', 'market': 'TPEX'}]])
def test_incomplete_or_invalid_official_profiles_cannot_publish(profiles):
    with pytest.raises(ValueError): official_members(profiles)


def test_missing_tolerance_is_inclusive_and_unknown_or_otc_failure_cannot_pass():
    expected = {str(i) for i in range(1000)}
    assert coverage_receipt(expected, sorted(expected)[:900])['coverage_accepted']
    assert not coverage_receipt(expected, sorted(expected)[:899])['coverage_accepted']
    assert not coverage_receipt([], [])['coverage_accepted']
    assert not coverage_receipt({'6488'}, [])['coverage_accepted']


def test_cached_receipt_uses_current_fixed_roster_and_rejects_other_date_or_unknown_snapshot():
    expected = set(str(i) for i in range(1000))
    receipt = {'date': '2026-10-13', 'snapshot_id': 1, 'dataset': 'ohlcv', 'market': 'TPEX',
               'received': sorted(expected)[:900]}
    cached = cached_coverage(receipt, expected, '2026-10-13')
    assert cached['coverage_accepted'] and cached['cache_hit']
    assert not cached_coverage(receipt, expected | {'new'}, '2026-10-13')['coverage_accepted']
    assert cached_coverage(receipt, expected, '2026-10-14') is None
    assert cached_coverage(dict(receipt, snapshot_id=None), expected, '2026-10-13') is None


def test_cursor_persists_same_source_snapshot_for_reuse_and_preserves_it_on_failed_fetch():
    from datetime import datetime, timezone
    from ingestion_core.control import SQLiteControlPlane
    with SQLiteControlPlane() as control:
        receipt = {'date': '2026-10-13', 'snapshot_id': 4, 'received': ['2330', '6488']}
        now = datetime(2026, 10, 13, tzinfo=timezone.utc)
        control.advance_cursor('tpex:ohlcv:market', now, successful=True, coverage=receipt)
        assert control.get_cursor('tpex:ohlcv:market').coverage == receipt
        control.advance_cursor('tpex:ohlcv:market', now, successful=False)
        assert control.get_cursor('tpex:ohlcv:market').coverage == receipt


@pytest.mark.parametrize('status', ['partial', 'failed', 'retrying'])
def test_container_cannot_report_success_for_incomplete_business_result(monkeypatch, status):
    from ingestion_core import __main__ as entry
    monkeypatch.delenv('QUEUE_CONSUMER', raising=False)
    monkeypatch.setattr(entry, 'run_scheduled_collection', lambda: {'status': status})
    with pytest.raises(SystemExit) as exit:
        entry.main()
    assert exit.value.code == 1


def test_full_market_ready_scope_is_readable_by_public_report_api(monkeypatch):
    import re
    from ingestion_core import __main__ as entry
    class Store:
        def __init__(self, bucket): pass
        def create(self, *args): return True
    monkeypatch.setattr(entry, 'GcsObjectStore', Store)
    symbols = tuple(str(i) for i in range(1000, 2010))
    event = entry._core_ready_event(core_bucket='test', execution_id='test', config_id='test',
        analysis_as_of='2026-10-14', iceberg_tables={'ohlcv': {'rows': 1010}},
        symbols=symbols, market='market')
    scope = event['scopes'][0]
    assert re.fullmatch(r'[\w.:-]{1,80}', scope['id'])
    assert scope['symbols'] == list(symbols)
