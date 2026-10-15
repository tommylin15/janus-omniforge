"""Tests for write-time aggregation and single-row home_market_snapshot projection."""

from datetime import date
from decimal import Decimal
import json
import pytest
from packages.web_api.core import CoreQueryService
from ingestion_core.serving_projection import StockServingProjection


class FakeCursor:
    def __init__(self, fetch_data=None):
        self.fetch_data = fetch_data or []
        self.executed_statements = []
        self.description = []

    def execute(self, statement, parameters=None):
        self.executed_statements.append((statement, parameters))

    def fetchall(self):
        return self.fetch_data

    def fetchone(self):
        return self.fetch_data[0] if self.fetch_data else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_core_query_service_uses_home_market_snapshot_fast_path():
    """Verify market_home uses single-key snapshot when available."""
    cached_payload = {
        "schema_version": "market-home.v1",
        "as_of": "2026-10-14",
        "status": "available",
        "sections": {
            "taiex": {"status": "available", "data": {"close": 23000}},
            "market-activity": {"status": "available", "data": {"day_trade_shares": 1000}},
            "institutional": {"status": "available", "data": {"foreign_net_shares": 500}},
        }
    }

    mock_query_called = False
    def mock_query(identifier, sql, params):
        nonlocal mock_query_called
        mock_query_called = True
        return []

    service = CoreQueryService(
        query=mock_query,
        serving_home_market_snapshot=lambda: cached_payload,
    )

    for section in cached_payload['sections'].values():
        section.update(as_of='2026-10-14', freshness_days=0)
    result = service.market_home(as_of_date=date(2026, 10, 14))
    assert result == cached_payload
    # Ensure expensive fallback query was NEVER called
    assert not mock_query_called


def test_core_query_service_falls_back_when_snapshot_empty():
    """Verify market_home gracefully falls back if snapshot is absent."""
    mock_query_called = False
    def mock_query(identifier, sql, params):
        nonlocal mock_query_called
        mock_query_called = True
        return []

    service = CoreQueryService(
        query=mock_query,
        serving_home_market_snapshot=lambda: None,
    )

    result = service.market_home()
    assert result["schema_version"] == "market-home.v1"
    assert mock_query_called


def test_materialize_home_market_snapshot_writes_single_pk():
    """Verify materialize_home_market_snapshot computes and upserts to control.home_market_snapshot."""
    cursor = FakeCursor(fetch_data=[
        (json.dumps({
            "benchmark_id": "TAIEX", "close": 23000.0, "trade_date": "2026-10-14",
            "source_id": "taiex", "provenance_id": "prov-1", "execution_id": "exec-1"
        }),)
    ])
    conn = FakeConnection(cursor)

    projection = StockServingProjection(lambda: conn)
    payload = projection.materialize_home_market_snapshot(as_of_date=date(2026, 10, 14))

    assert payload["schema_version"] == "market-home.v1"
    assert "taiex" in payload["sections"]
    assert any("INSERT INTO control.home_market_snapshot" in stmt for stmt, _ in cursor.executed_statements)


def test_snapshot_does_not_keep_yesterdays_freshness_or_allow_future_data():
    cached = {'schema_version': 'market-home.v1', 'status': 'available', 'sections': {
        name: {'as_of': '2026-10-13', 'freshness_days': 0, 'status': 'available', 'data': {'close': 999}}
        for name in ('taiex', 'institutional', 'market-activity')}}
    calls = []
    def query(identifier, *_):
        calls.append(identifier)
        return [{'benchmark_id': 'TAIEX', 'trade_date': '2026-10-13', 'close': '101',
                 'source_id': 'official', 'provenance_id': 'p'}] if identifier == 'core.benchmark_v1' else []
    service = CoreQueryService(query, serving_home_market_snapshot=lambda: cached)
    result = service.market_home(as_of_date=date(2026, 10, 14))
    assert calls and result['sections']['taiex']['freshness_days'] == 1
    assert result['sections']['taiex']['data']['close'] == '101'
    for part in cached['sections'].values():
        part['as_of'] = '2026-10-15'
    calls.clear()
    service.market_home(as_of_date=date(2026, 10, 14))
    assert calls  # A future cache cannot bypass the canonical date checks.


def test_materialized_home_uses_same_decimal_and_partial_semantics_as_api():
    class Cursor(FakeCursor):
        def execute(self, statement, parameters=None):
            super().execute(statement, parameters)
            if statement.lstrip().startswith('SELECT') and parameters[0] == 'benchmark':
                self.fetch_data = [(json.dumps({'benchmark_id': 'TAIEX', 'trade_date': '2026-10-13',
                    'close': '25000.123456', 'source_id': 'official', 'provenance_id': 'p'}),)]
                self.description = []
            elif statement.lstrip().startswith('SELECT'):
                self.fetch_data = []
                self.description = []
    cursor = Cursor()
    result = StockServingProjection(lambda: FakeConnection(cursor)).materialize_home_market_snapshot(date(2026, 10, 14))
    assert result['sections']['taiex']['data']['history_points'][0]['value'] == '25000.123456'
    assert result['sections']['taiex']['freshness_days'] == 1
    assert result['sections']['institutional']['status'] == 'missing'
    assert result['status'] == 'partial' and result['as_of'] is None
