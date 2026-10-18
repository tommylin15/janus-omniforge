from pathlib import Path

import pytest

from ingestion_core.yahoo_eps import parse_eps, SOURCE
from packages.web_api.core import CoreQueryService, _comparable_single_quarter_eps


def page(value='2.08', *, symbol='1513', quarter='2025 Q4', heading='單季每股盈餘'):
    return (f'<title>士電({symbol}.TW) 財務報表 - 每股盈餘 - Yahoo股市</title>'
            f'<script>2025 Q4 9999</script><h2>{heading}</h2>年度/季別 每股盈餘'
            f'<li>{quarter}<span>{value}</span><span>10.00%</span></li>'
            '<h3>單季每股盈餘</h3>').encode()


def parsed(raw=None):
    return parse_eps(raw or page(), '1513', year=2025, quarter=4,
                     received_at='2026-10-18T12:00:00Z')


def test_provider_value_is_not_recalculated_or_mislabelled_as_official():
    row = parsed(page('-0.20'))
    assert row['value'] == '-0.20' and row['source_id'] == SOURCE
    assert row['unit'] == 'TWD_per_share' and row['period_basis'] == 'single_quarter'
    assert row['published_at'] is None and row['publication_time_authoritative'] is False
    assert row['fiscal_period_end'] == '2025-12-31'
    assert row['share_basis_status'] == 'provider_reported_unspecified'


@pytest.mark.parametrize('raw', [page(symbol='2327'), page(quarter='2025 Q3'),
                                page(heading='累季每股盈餘'), page(value='--'),
                                page().replace(b'</li>', b'</li><li>2025 Q4 2.09</li>'), b'<h1>captcha</h1>'])
def test_wrong_stock_period_table_missing_and_duplicate_are_rejected(raw):
    with pytest.raises(ValueError):
        parsed(raw)


def test_chart_publishes_yahoo_q4_without_weakening_cumulative_or_source_guards():
    yahoo = {**parsed(), 'provenance_id': 'stage-yahoo'}
    ytd = {**yahoo, 'metric': 'eps_year_to_date', 'period_basis': 'year_to_date'}
    assert not _comparable_single_quarter_eps([ytd])
    assert not _comparable_single_quarter_eps([{**yahoo, 'source_id': 'unapproved'}])
    assert not _comparable_single_quarter_eps([{**yahoo, 'provenance_id': None}])
    service = CoreQueryService(lambda *_: [], serving_series=lambda *_: [yahoo])
    report = service.visual_series('1513', 'eps')
    assert report['points'][0]['value'] == '2.08'
    assert report['source_ids'] == [SOURCE]
    assert report['calculation_version'] == 'eps-provider-reported-single-quarter-v3'
    official = {**yahoo, 'source_id': 'mops', 'value': '2.09'}
    for rows in ([yahoo, official], [official, yahoo]):
        assert _comparable_single_quarter_eps(rows)[0]['value'] == '2.09'


def test_yahoo_serving_migration_does_not_open_other_datasets_or_missing_fields():
    sql = Path('infra/postgres/migrations/065_yahoo_eps_serving.sql').read_text()
    assert "dataset_id='financials'" in sql
    assert "coalesce(payload_json->>'metric','')='eps_single_quarter'" in sql
    assert 'GRANT' not in sql and 'DELETE' not in sql
