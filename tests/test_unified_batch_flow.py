"""Offline coverage for the unified flow; intentionally not run by the authoring turn."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import json
import pytest


def test_every_scheduled_slot_aligns_with_two_hour_tick():
    from ingestion_core.batch_controller import BATCHES
    assert all(b.minute == 30 and all(h % 2 == 0 for h in b.hours)
               for b in BATCHES if not b.manual_only)
    root = Path(__file__).parents[1]
    assert not (root / ".github/workflows/private-ledger-backup-retention.yml").exists()
    for path in (root / ".github/workflows").glob("*.yml"):
        assert "\n  schedule:" not in path.read_text()


def test_collection_finishes_canonical_after_supplement(monkeypatch):
    from ingestion_core import unified_collection, data_supplement, stock_supplement, __main__
    order = []
    monkeypatch.setenv("MART_JOB", "")
    monkeypatch.setattr(stock_supplement, "run_pending", lambda **k: order.append("demand") or {"status":"succeeded"})
    monkeypatch.setattr(data_supplement, "run_backfill", lambda **k: order.append("supplement") or {"status":"partial","failures":[]})
    monkeypatch.setattr(__main__, "run_scheduled_collection", lambda: order.append("core") or {"status":"succeeded"})
    assert unified_collection.run()["status"] == "succeeded"
    assert order == ["demand","supplement","core"]
    monkeypatch.setattr(data_supplement, "run_backfill", lambda **k: {"failures":[{"dataset":"financials"}]})
    assert unified_collection.run()["status"] == "partial"


def test_market_cycle_bounds_queue_without_claiming_empty_success_as_report(monkeypatch):
    from intelligence_mart import market_cycle, market_screening, runtime
    monkeypatch.setenv("SCREENING_DATE", "2026-10-24")
    screen = Mock(return_value={"screening_count":100})
    queue = Mock(side_effect=[{"claimed":True,"status":"succeeded","reports":1},
                              {"claimed":False,"status":"idle"}])
    monkeypatch.setattr(market_screening, "run_daily", screen)
    monkeypatch.setattr(runtime, "run_queued_analysis", queue)
    result = market_cycle.run()
    assert len(result["analyses"]) == 1
    assert queue.call_count == 2
    screen.assert_called_once()


def test_private_snapshot_records_inputs_without_copying_transaction_history():
    from services.api.private_pipeline import PrivatePipeline
    store = Mock()
    pipeline = PrivatePipeline(Mock(), store, lambda *_: {})
    prepared = {"user_id":"owner-a","valuation_date":"2026-10-23","ledger_version":4,
                "ledger":[{"secret_trade":"not duplicated"}],"watchlist":[{"version":2,"symbol":"2330"}],
                "profile":{"version":1},"marts":{"mart_user_positions":[]},"risk":{}}
    pipeline._write_prepared(prepared)
    name, rows = store.upsert.call_args.args
    assert name == "workspace_snapshots"
    snapshot = rows[0]
    assert snapshot["user_id"] == "owner-a"
    assert "secret_trade" not in snapshot["payload"]
    assert json.loads(snapshot["payload"])["ledger_version"] == 4
    pipeline._write_prepared(prepared)
    assert store.upsert.call_args.args[1][0]["snapshot_id"] == snapshot["snapshot_id"]


def test_dashboard_two_hour_grace_does_not_show_false_stale():
    from packages.admin_api.batch_dashboard import dashboard
    now = datetime(2026,10,24,4,30,tzinfo=timezone.utc)
    result = dashboard({"observed_at":"2026-10-24T02:30:00+00:00","definitions":[]}, {}, {}, now)
    assert result["controller_fresh"]
