from datetime import date, datetime, timedelta, timezone

import pytest

from ingestion_core.__main__ import _market_universe
from ingestion_core.liquid_500 import rank_week
from packages.admin_api import AdminConflictError, AdminService


def test_weekly_ranking_requires_both_markets_each_day_and_stable_tie_break():
    day = date(2026, 9, 24)
    rows = [
        {"symbol": str(symbol), "market": "TWSE", "trade_date": day.isoformat(),
         "volume_shares": 10, "turnover_twd": "100"}
        for symbol in range(1000, 1500)
    ]
    rows.extend({"symbol": str(symbol), "market": "TPEX", "trade_date": day.isoformat(),
                 "volume_shares": 10, "turnover_twd": "100"}
                for symbol in range(2000, 2500))
    approved = {row["symbol"] for row in rows}
    result = rank_week(rows, [day], approved)
    assert len(result) == 500
    assert result[0]["symbol"] == "1000"
    assert result[-1]["symbol"] == "1499"
    with pytest.raises(ValueError, match="incomplete market batch"):
        rank_week(rows[:-1], [day], approved)
    with pytest.raises(ValueError, match="missing a trading day"):
        rank_week(rows[:500], [day], approved)


def test_market_batch_uses_only_the_complete_effective_500():
    symbols = tuple(f"{value:04}" for value in range(1000, 1500))

    class Control:
        def liquid_500_snapshot(self):
            return {"status": "available", "items": [{"symbol": symbol} for symbol in symbols]}

    universe, selected = _market_universe(Control(), ("2330",))
    assert universe["status"] == "available"
    assert len(selected) == 500
    assert selected[0] == "1000"
    assert selected[-1] == "1499"

    class Partial:
        def liquid_500_snapshot(self):
            return {"status": "available", "items": [{"symbol": "2330"}]}

    with pytest.raises(ValueError, match="exactly 500"):
        _market_universe(Partial(), ("2330",))


def test_admin_swap_previews_future_version_without_activating_it():
    effective = datetime.now(timezone.utc) + timedelta(days=2)
    items = [{"rank": rank, "symbol": f"{rank:04}", "volume_shares": rank,
              "turnover_twd": "100", "manual_override": False}
             for rank in range(1, 501)]

    class Control:
        def __init__(self):
            self.current = {"status": "missing", "version": 0, "items": []}
            self.upcoming = {"status": "available", "version": 1, "items": items,
                             "week_start": "2026-09-21", "effective_from": effective.isoformat(),
                             "source_snapshot": {"source": "weekly"}}
            self.published = None

        def liquid_500_snapshot(self, *, upcoming=False):
            return self.upcoming if upcoming else self.current

        def publish_liquid_500(self, rows, **kwargs):
            self.published = (rows, kwargs)
            self.upcoming = {**self.upcoming, "version": 2, "items": list(rows),
                             "effective_from": kwargs["effective_from"].isoformat()}

    control = Control()
    admin = AdminService(control)
    assert admin.liquid_500_snapshot()["current"]["status"] == "missing"
    with pytest.raises(AdminConflictError):
        admin.swap_liquid_500(remove_symbol="0001", add_symbol="0600", reason="調整",
                              expected_version=0, actor="operator")
    assert control.published is None

    result = admin.swap_liquid_500(remove_symbol="0001", add_symbol="0600", reason="調整",
                                   expected_version=1, actor="operator")
    rows, options = control.published
    assert result["current"]["status"] == "missing"
    assert result["upcoming"]["version"] == 2
    assert options["effective_from"] > effective
    assert options["expected_version"] == 1
    assert options["reason"] == "調整" and options["actor"] == "operator"
    assert options["source_snapshot"]["manual_swap"] == {"removed": "0001", "added": "0600"}
    assert len(rows) == 500 and rows[0]["symbol"] == "0600" and rows[0]["manual_override"]
