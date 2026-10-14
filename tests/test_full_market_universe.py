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


def test_market_specific_missing_tolerance_boundaries_and_unknown_market_fail_closed():
    expected = {str(i) for i in range(1000)}
    listed = coverage_receipt(expected, sorted(expected)[:900], 'TWSE')
    assert listed['coverage_accepted'] and listed['max_missing_ratio'] == 0.1
    assert not coverage_receipt(expected, sorted(expected)[:899], 'TWSE')['coverage_accepted']
    otc = coverage_receipt(expected, sorted(expected)[:700], 'TPEX')
    assert otc['coverage_accepted'] and otc['max_missing_ratio'] == 0.3
    assert not coverage_receipt(expected, sorted(expected)[:699], 'TPEX')['coverage_accepted']
    assert not coverage_receipt([], [], 'TPEX')['coverage_accepted']
    assert not coverage_receipt({'6488'}, [], 'TPEX')['coverage_accepted']
    assert not coverage_receipt({'00719B', '6488'}, {'6488'}, 'ALL')['coverage_accepted']
    with pytest.raises(ValueError, match='unknown coverage market'):
        coverage_receipt(expected, expected, 'UNKNOWN')


def test_cached_receipt_uses_current_fixed_roster_and_rejects_other_date_or_unknown_snapshot():
    expected = set(str(i) for i in range(1000))
    receipt = {'date': '2026-10-13', 'snapshot_id': 1, 'dataset': 'ohlcv', 'market': 'TPEX',
               'received': sorted(expected)[:700]}
    cached = cached_coverage(receipt, expected, '2026-10-13')
    assert cached['coverage_accepted'] and cached['cache_hit']
    assert cached['max_missing_ratio'] == 0.3
    assert not cached_coverage(receipt, expected | {'new'}, '2026-10-13')['coverage_accepted']
    assert cached_coverage(dict(receipt, market='UNKNOWN'), expected, '2026-10-13') is None
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


def test_registered_etf_prices_survive_the_ordinary_equity_filter_and_cache():
    from ingestion_core.full_market import official_price_rows
    rows = [{'symbol':symbol,'close':'10'} for symbol in ('6488','00719B','00870B')]
    assert [row['symbol'] for row in official_price_rows(rows,[{'symbol':'6488'}],{'00719B'})] == ['6488','00719B']
    receipt = {'date':'2026-10-14','snapshot_id':4,'stage_provenance_id':'official', 'market':'TPEX',
               'received':['6488'],'portfolio_received':['00719B']}
    cached = cached_coverage(receipt,{'6488'},'2026-10-14')
    assert cached['portfolio_received'] == ['00719B'] and cached['coverage_accepted']


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
        analysis_as_of='2026-10-13', iceberg_tables={'ohlcv': {'rows': 1010}},
        symbols=symbols, market='market', scope_as_of='2026-10-14')
    scope = event['scopes'][0]
    assert re.fullmatch(r'[\w.:-]{1,80}', scope['id'])
    assert scope['symbols'] == list(symbols)
    assert event['analysisAsOf'] == '2026-10-14'


def test_collection_reports_missing_financials_against_each_fixed_market_roster(monkeypatch):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from ingestion_core import __main__ as entry
    from ingestion_core.adapters import SourceResponse
    control = MagicMock()
    control.get_collection_config.return_value = SimpleNamespace(source_ids=('twse',))
    control.config_symbols.return_value = ('2330', '6488', '6147')
    control.enabled_stock_symbols.return_value = ('2330', '6488', '6147')
    control.portfolio_coverage_symbols.return_value = ()
    control.get_admin_setting.return_value = None
    control.full_market_snapshot.return_value = {'status': 'available', 'version': 1,
        'items': [{'symbol': '2330', 'market': 'TWSE'}, {'symbol': '6488', 'market': 'TPEX'},
                  {'symbol': '6147', 'market': 'TPEX'}]}
    inventory = {}
    class Store:
        def __init__(self, bucket): pass
        def create(self, name, payload, media_type):
            inventory.update(json.loads(payload))
            return True
    monkeypatch.setattr(entry, 'GcsObjectStore', Store)
    monkeypatch.setattr(entry, '_iceberg_core', lambda _: MagicMock())
    monkeypatch.setattr(entry, 'dataset_adapters', lambda: {'twse-events':
        SimpleNamespace(source_id='twse', dataset_id='events', market='TWSE')})
    monkeypatch.setattr(entry, '_fetch_source', lambda *_: SourceResponse())
    for key, value in {'STAGE_BUCKET':'stage', 'CORE_BUCKET':'core', 'INGESTION_DATE':'2026-10-13',
        'INGESTION_DATASETS':'twse-events', 'FORCE_REFRESH':'true', 'STAGE_EXECUTION_SCOPED':'false',
        'STOCK_SERVING_PROJECTION_ENABLED':'false'}.items():
        monkeypatch.setenv(key, value)
    result = entry.collect_stage(control=control)
    financials = [r for r in inventory['items'] if r['dataset'] == 'financials']
    assert {(r['market'], r['expected_count'], r['missing_count']) for r in financials} == {
        ('TWSE', 1, 1), ('TPEX', 2, 2)}
    assert result['coverage_status'] == 'partial' and not inventory['coverage_accepted']
