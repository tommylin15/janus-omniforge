"""True five-year PE/PB history vs. short, stale or untrusted records."""
from datetime import date, timedelta
from decimal import Decimal

from ingestion_core.valuation_history import five_year_profile


AS_OF = date(2026, 10, 16)


def _official_rows():
    current = AS_OF.replace(year=AS_OF.year - 5)
    rows = []
    while current <= AS_OF:
        if current.weekday() < 5:
            rows.append({
                "symbol": "2327", "market": "TWSE", "source_id": "twse",
                "provenance_id": "official-receipt", "observed_date": current.isoformat(),
                "pe_ratio": str(Decimal("20") + Decimal(len(rows) % 30) / 10),
                "pb_ratio": str(Decimal("2") + Decimal(len(rows) % 30) / 100),
            })
        current += timedelta(days=1)
    return rows


def test_true_five_year_history_has_a_real_observation_distribution():
    report = five_year_profile(_official_rows(), symbol="2327", metric="pe_ratio", as_of=AS_OF)
    assert report["status"] == "ready"
    assert report["count"] > 1200
    assert report["months_with_valid_observation"] >= 60
    assert Decimal(report["min"]) <= Decimal(report["latest_value"]) <= Decimal(report["max"])
    assert Decimal("0") <= Decimal(report["percentile_midrank"]) <= Decimal("100")
    assert report["historical_pit_certified"] is False


def test_retrospective_five_year_status_cannot_be_claimed_from_short_history():
    recent = [r for r in _official_rows() if r["observed_date"] >= "2025-11-01"]
    report = five_year_profile(recent, symbol="2327", metric="pe_ratio", as_of=AS_OF)
    assert report["status"] == "partial_history"
    assert report["percentile_midrank"] is None
    assert report["latest_value"] is not None


def test_loss_making_pe_does_not_hide_separately_valid_pb():
    rows = _official_rows()
    for row in rows:
        if row["observed_date"] < "2024-10-01":
            row["pe_ratio"] = "-1"
    pe = five_year_profile(rows, symbol="2327", metric="pe_ratio", as_of=AS_OF)
    pb = five_year_profile(rows, symbol="2327", metric="pb_ratio", as_of=AS_OF)
    assert pe["status"] == "partial_history"
    assert pe["percentile_midrank"] is None
    assert pb["status"] == "ready"


def test_untrusted_and_conflicting_revisions_never_count_as_history():
    rows = _official_rows()
    rows.append({**rows[-1], "pe_ratio": "999"})
    rows.append({**rows[-1], "observed_date": "2021-10-18", "source_id": "fake"})
    rows.append({**rows[-1], "observed_date": "2026-10-17"})
    report = five_year_profile(rows, symbol="2327", metric="pe_ratio", as_of=AS_OF)
    assert report["status"] == "ready"
    assert report["count"] == len(_official_rows()) - 1


def test_empty_and_bounded_scans_fail_closed():
    import pytest
    empty = five_year_profile([], symbol="2327", metric="pb_ratio", as_of=AS_OF)
    assert empty["status"] == "pending"
    assert empty["percentile_midrank"] is None
    with pytest.raises(ValueError, match="valuation_scan_limit_exceeded"):
        five_year_profile(_official_rows(), symbol="2327", metric="pb_ratio", as_of=AS_OF,
                          max_rows=100)
