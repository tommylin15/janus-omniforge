"""Fixed Core-date resolution: no stale/latest fallback and no fabricated business date."""
import json
from datetime import date, timedelta
import pytest

from scripts.gcp.risk_shadow_asof import select_latest, select_prior_completed


def item(i, stamp):
    return {"name": f"executions/{i}/core-snapshot.json", "updated": stamp}


def payload(i, day):
    return json.dumps({"execution_id": i, "snapshot_id": f"core-{i}",
                       "analysis_as_of": day, "iceberg_tables": {"core.ohlcv_v1": {"snapshot_id": 1}}}).encode()


def test_uses_latest_updated_core_date_not_fixed_previous_trading_date():
    today = date(2026, 10, 22)
    rows = [item("a", "2026-10-20T00:00:00Z"), item("b", "2026-10-22T01:00:00Z")]
    raw = {"a": payload("a", "2026-10-20"), "b": payload("b", "2026-10-21")}
    got = select_latest(rows, lambda name: raw[name.split("/")[1]], today)
    assert got["analysis_as_of"] == "2026-10-21"
    assert got["age_days"] == 1
    assert len(got["core_snapshot_hash"]) == 64


def test_latest_invalid_fails_without_falling_back_to_older():
    rows = [item("a", "2026-10-20T00:00:00Z"), item("b", "2026-10-22T00:00:00Z")]
    data = {"a": payload("a", "2026-10-20"), "b": payload("wrong_id", "2026-10-21")}
    with pytest.raises(ValueError, match="latest_core_snapshot_invalid"):
        select_latest(rows, lambda name: data[name.split("/")[1]], date(2026, 10, 22))


@pytest.mark.parametrize("business_date", ["2026-10-14", "2026-10-23"])
def test_rejects_out_of_bounds_core_asof(business_date):
    with pytest.raises(ValueError, match="latest_core_snapshot_out_of_age_bounds"):
        select_latest([item("a", "2026-10-22T00:00:00Z")],
                      lambda _: payload("a", business_date), date(2026, 10, 22))


def test_inventory_path_must_be_canonical_execution_manifest():
    with pytest.raises(ValueError, match="no_core_snapshot"):
        select_latest([{"name":"other/log.json","updated":"2026-10-22"}],
                      lambda _: b"{}", date(2026, 10, 22))


def test_manual_prefers_yesterday_over_newer_intraday_core_snapshot():
    today=date(2026,10,22)
    items=[item("yesterday","2026-10-22T00:30:00Z"),
           item("today","2026-10-22T03:00:00Z")]
    raw={"yesterday":payload("yesterday","2026-10-21"),
         "today":payload("today","2026-10-22")}
    got=select_prior_completed(items,lambda name:raw[name.split("/")[1]],today)
    assert got["analysis_as_of"]=="2026-10-21"
    assert got["event"]["coreSnapshotUri"].endswith("/executions/yesterday/core-snapshot.json")
    assert got["event"]["coreSnapshotHash"]=="sha256:"+got["core_snapshot_hash"]
    assert got["event"]["modelVersion"]=="deterministic-v1"


def test_manual_fails_if_no_prior_completed_core():
    with pytest.raises(ValueError,match="no_prior_completed_core_snapshot"):
        select_prior_completed([item("today","2026-10-22T03:00:00Z")],
                               lambda _:payload("today","2026-10-22"),date(2026,10,22))


def test_manual_fails_closed_on_malformed_prior_core():
    data=payload("wrong","2026-10-21")
    with pytest.raises(ValueError,match="prior_core_snapshot_invalid"):
        select_prior_completed([item("yesterday","2026-10-22T00:30:00Z")],
                               lambda _:data,date(2026,10,22))
