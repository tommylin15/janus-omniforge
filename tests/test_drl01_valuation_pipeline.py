"""DRL-01D release guards: Core snapshot -> serving-only API; no false two-year."""
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from ingestion_core.valuation_history import publish_focus_profiles
from packages.web_api.core import CoreQueryService


def test_bounded_core_snapshot_makes_partial_profile_without_imputed_percentile():
    core=MagicMock()
    core.table_identifier.return_value="core.valuation_v1"
    snapshot=SimpleNamespace(snapshot_id=987654)
    table=core.catalog.load_table.return_value
    table.current_snapshot.return_value=snapshot
    table.scan.return_value.to_arrow.return_value.to_pylist.return_value=[
        {"symbol":"2327", "observed_date":"2026-10-16",
         "pe_ratio":"38.18","pb_ratio":"6.59",
         "source_id":"twse","provenance_id":"official-proof"}
    ]
    connection=MagicMock()
    control=SimpleNamespace(connection=connection)
    report=publish_focus_profiles(core,control,symbols=["2327"],as_of=date(2026,10,16))
    assert report["source_snapshot_id"]=="987654"
    assert report["profiles"]==2
    statement, records = connection.cursor.return_value.__enter__.return_value.executemany.call_args.args
    assert "ON CONFLICT(symbol,metric)" in statement
    assert "INSERT INTO control.stock_valuation_five_year" in statement
    assert "stock_valuation_two_year" not in statement
    assert len(records)==2
    for row in records:
        data=json.loads(row[4])
        assert data["historical_pit_certified"] is False
        assert data["status"]=="partial_history"
        assert data["percentile_midrank"] is None
        assert data["source_coverage"]=="source_observed_date_not_historical_publication"
        assert data["core_snapshot_id"]=="987654"


def test_public_pe_reads_only_one_published_profile_not_core():
    calls=[]
    def disallow_core(*args):
        raise AssertionError("PE/PB page must not access Iceberg")
    def series(dataset, symbol, limit):
        calls.append(("recent",dataset,symbol,limit))
        return [
            {"observed_date":"2026-10-16", "pe_ratio":"38.18","source_id":"twse",
             "provenance_id":"valid"},
            {"observed_date":"2026-10-15", "pe_ratio":"38.59","source_id":"twse",
             "provenance_id":"valid"},
        ]
    def two_year(symbol, metric):
        calls.append(("two_year",symbol,metric))
        return {"symbol":symbol, "metric":metric,"status":"partial_history", "window_years":2,
                "historical_pit_certified":False, "count":220, "percentile_midrank":None,
                "password":"must-not-expose"}
    client=CoreQueryService(disallow_core,serving_series=series,
                            serving_valuation_profile=two_year)
    report=client.visual_series("2327","pe",limit=12)
    assert report["data_status"]=="available"
    assert report["two_year_profile"]["status"]=="partial_history"
    assert "password" not in report["two_year_profile"]
    assert calls == [("recent","valuation","2327",12),("two_year","2327","pe_ratio")]
    empty=CoreQueryService(disallow_core,serving_series=series)
    assert empty.visual_series("2327","pb")["two_year_profile"]["status"]=="unavailable"
