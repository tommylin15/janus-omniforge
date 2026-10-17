"""DRL-01D valuation backfill windows must be bounded, explicit and replayable.

No two-year claim is made from a one-year serving window; this test only
certifies the 25-month historical retrieval envelope.
"""
import pytest
from ingestion_core.data_supplement import valuation_history_months, months_ending


def test_historical_valuation_pages_cover_exactly_61_calendar_months():
    windows = [
        valuation_history_months(2026, 10, count=12, offset=offset)
        for offset in (0, 12)
    ]
    windows.append(valuation_history_months(2026, 10, count=1, offset=24))
    buckets = [bucket for window in windows for bucket in window]
    assert len(buckets) == len(set(buckets)) == 25
    assert min(buckets) == (2024, 9)  # 2024-10 (zero-based month)
    assert max(buckets) == (2026, 9)  # 2026-10
    assert len(windows[0]) == 12
    assert windows[0][-1] == (2026, 9)


@pytest.mark.parametrize("count,offset", [
    (0, 0), (13, 0), (1, -1), (1, 25), (2, 24), (12, 14),
])
def test_valuation_slice_rejects_out_of_range_or_unbounded_scan(count, offset):
    with pytest.raises(ValueError, match="invalid bounded valuation"):
        valuation_history_months(2026, 10, count=count, offset=offset)


def test_normal_market_and_financial_months_remain_capped_at_36():
    with pytest.raises(ValueError, match="invalid bounded monthly"):
        months_ending(2026, 10, 61)
    assert months_ending(2026, 10, 8)[-1] == (2026, 9)
