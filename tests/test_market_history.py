from datetime import date
import pytest
from ingestion_core.market_history import archive_months


def test_history_window_includes_both_boundary_months_and_is_bounded():
    assert archive_months(date(2024, 12, 31), date(2025, 1, 1)) == [(2024, 11), (2025, 0)]
    with pytest.raises(ValueError):
        archive_months(date(2024, 1, 1), date(2023, 1, 1))
    with pytest.raises(ValueError):
        archive_months(date(2020, 1, 1), date(2026, 1, 1))


def test_long_history_retention_is_only_for_deep_prices_and_benchmark():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from ingestion_core.retention import retained_core_rows
    core = SimpleNamespace(PARTITIONS={"ohlcv": (("trade_date", "month"),), "benchmark": (("trade_date", "month"),)})
    rows = [{"symbol": "held", "trade_date": "2024-12-01"}, {"symbol": "screen", "trade_date": "2024-12-01"},
            {"symbol": "held", "trade_date": "2022-12-01"}]
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    assert retained_core_rows(core, "ohlcv", rows, now, frozenset({"held"})) == rows[:1]
    assert retained_core_rows(core, "benchmark", rows, now) == rows[:2]


@pytest.mark.parametrize("missing,otc_missing,expected_status", [(0, 0, "accepted"), (51, 0, "discussion_required"), (0, 100, "accepted"), (0, 151, "discussion_required")])
def test_monthly_fill_keeps_valid_prices_and_stops_for_poor_quality(monkeypatch, missing, otc_missing, expected_status):
    import json
    from types import SimpleNamespace
    from ingestion_core import market_history as module
    from ingestion_core import __main__ as entry
    symbols = [str(1000+i) for i in range(500)]
    otc_symbols = [str(2000+i) for i in range(500)]
    commits, finished, markers = [], [], []
    class Control:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def source_is_approved(self, source): return True
        def full_market_snapshot(self):
            return {'version': 1, 'items': [{'symbol': s, 'market': 'TWSE'} for s in symbols]
                    + [{'symbol': s, 'market': 'TPEX'} for s in otc_symbols]}
        def portfolio_coverage_symbols(self): return ()
        def enqueue_collection(self, *args, **kwargs): return SimpleNamespace(execution_id="ex", trace_id="trace")
        def transition_execution(self, *args, **kwargs): pass
        def complete_collection(self, identity, ready, *, partial):
            finished.append(partial)
            return SimpleNamespace(status=SimpleNamespace(value="partial" if partial else "succeeded")), None
    def commit(**kwargs):
        commits.append(kwargs)
        return SimpleNamespace(inserted=len(kwargs["rows"]), updated=0, reused=0)
    class Writer:
        def __init__(self, store): pass
        def write_raw(self, **kwargs): return SimpleNamespace(idempotency_key="provenance")
        def mark_core_committed(self, *args, **kwargs): markers.append(kwargs)
    def fetch(url):
        if "MI_5MINS_HIST" in url:
            month = "08" if "20260801" in url else "07"
            return json.dumps({"fields": ["日期", "收盤指數"], "data": [[f"115/{month}/03", "100"]]}).encode(), "utf-8"
        if 'tpex.org.tw' in url:
            return json.dumps([{'Date': '20260803', '代號': s, '名稱': s, '成交股數': '100',
                '成交金額(元)': '1000', '開盤': '10', '最高': '10', '最低': '10', '收盤': '10'}
                for s in otc_symbols[otc_missing:]+[str(8000+i) for i in range(otc_missing)]]).encode(), 'utf-8'
        return json.dumps([{"Date": "20260803", "證券代號": s, "證券名稱": s,
            "成交股數": "100", "成交金額": "1000", "開盤價": "10", "最高價": "10", "最低價": "10",
            "收盤價": "--" if i < missing else "10"} for i,s in enumerate(symbols)]).encode(), "utf-8"
    monkeypatch.setattr(entry, "_control_plane", Control)
    monkeypatch.setattr(entry, "_iceberg_core", lambda _: SimpleNamespace(write=commit, close=lambda: None))
    monkeypatch.setattr(entry, "_current_core_fences", lambda _: {"ohlcv": "fence"})
    monkeypatch.setattr(entry, "_core_ready_event", lambda **kwargs: kwargs)
    monkeypatch.setattr(module, "_fetch", fetch)
    monkeypatch.setattr(module, "StageWriter", Writer)
    monkeypatch.setattr(module, "GcsObjectStore", lambda _: None)
    for key,value in {"BACKFILL_START_DATE": "2026-08-01", "BACKFILL_END_DATE": "2026-08-31",
                      "CORE_BUCKET": "core", "STAGE_BUCKET": "stage"}.items():
        monkeypatch.setenv(key,value)
    result = module.run_market_history()
    assert not result["failures"]
    assert result["months"][0]["status"] == expected_status
    assert [commit['dataset_id'] for commit in commits] == [
        'ohlcv', 'ohlcv', 'market-volume', 'market-volume', 'benchmark']
    assert len(commits[0]["rows"]) == 500-missing
    assert len(commits[1]['rows']) == 500-otc_missing
    assert len(commits[2]['rows']) == 500-missing
    assert len(commits[3]['rows']) == 500-otc_missing
    assert all(row['provenance_id']=='provenance' and row['source_id']=='tpex' for row in commits[3]['rows'])
    assert result['months'][0]['market_volume_source_rows'] == {
        'TWSE':500-missing, 'TPEX':500-otc_missing}
    assert result['coverage_scope'] == 'current_members_price_history'
    assert result['months'][0]['missing_ratio_by_market']['TPEX'] == pytest.approx(otc_missing / len(otc_symbols))
    assert result['months'][0]['threshold_by_market'] == {'TWSE': .10, 'TPEX': .30}
    assert finished == [missing > 50 or otc_missing > 150]
    assert len(markers) == 1


def test_historical_market_volume_runner_is_bounded_and_immutable(tmp_path):
    import importlib.util
    import sys
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    script=root/"scripts"/"gcp"/"drl01_market_volume_replay.py"
    sys.path.insert(0,str(script.parent))
    spec=importlib.util.spec_from_file_location("drl01_market_volume_replay",script)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod.SLICES)==4
    assert mod.SLICES[0]==("2026-07-01","2026-07-31")
    assert mod.SLICES[-1]==("2026-10-01","2026-10-12")
    data={"intent":"drl01-existing-official-market-volume-history",
          "approved":True,"no_new_source":True,
          "no_owner_mutation":True,"no_job_template_mutation":True,
          "slices":[list(item) for item in mod.SLICES],
          "deployed_sha":"a"*40}
    path=tmp_path/"request.json"
    path.write_text(json.dumps(data))
    assert mod.checked(str(path))==data
    for bad in ({"approved":False},{"no_owner_mutation":False},
                {"deployed_sha":"main"},{"slices":[["2026-01-01","2026-12-31"]]}):
        path.write_text(json.dumps({**data,**bad}))
        with pytest.raises(ValueError,match="unapproved_market_continuity_scope"):
            mod.checked(str(path))
    source=script.read_text()
    assert 'wait_for_terminal_executions' in source
    assert '"etag":current["etag"]' in source
    assert 'if not digest_matches(request["deployed_sha"],current)' in source
    assert "PASS_BOUNDED_OFFICIAL_HISTORY_WRITTEN" in source
    assert "market_history_not_terminal_do_not_retry" in source
    assert ":update" not in source
