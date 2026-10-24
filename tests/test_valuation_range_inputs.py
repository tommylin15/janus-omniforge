"""RV-03 Core/Serving adapter tests; never calls external providers or writes data."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

import pytest

from ingestion_core.valuation_range_inputs import (
    MAX_CORE_ROWS, comparable_financial_facts, from_existing_rows,
    monthly_last_trading_observations, read_existing_inputs, _window_start,
)


AS_OF = date(2026, 10, 24)


def valuation_rows(count=24):
    rows = []
    for shift in range(count):
        n = 2024 * 12 + 10 + shift - 1
        year, month0 = divmod(n, 12)
        month = month0 + 1
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        day = month_end
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        rows.append({
            "symbol": "2330", "observed_date": day.isoformat(),
            "pe_ratio": str(10 + shift), "pb_ratio": str(2 + shift / 100),
            "source_id": "twse", "provenance_id": "existing-core-provenance",
        })
    return rows


def financial_rows(*, share_basis="same_reported_basis"):
    rows = []
    for quarter in range(1, 5):
        end = date(2025, quarter * 3, calendar.monthrange(2025, quarter * 3)[1])
        rows.append({
            "source_id": "mops", "provenance_id": "existing-financial-provenance",
            "metric": "eps_single_quarter", "fiscal_year": 2025,
            "fiscal_quarter": quarter, "fiscal_period_end": end.isoformat(),
            "unit": "TWD_per_share", "period_basis": "single_quarter",
            "report_scope": "consolidated", "share_basis": share_basis,
            "value": "1.5", "availability_at": "2026-01-01T01:00:00Z",
        })
    return rows


def test_true_month_end_last_trading_day_keeps_date_and_window():
    assert _window_start(AS_OF) == date(2021, 11, 1)
    raw = valuation_rows()
    points = monthly_last_trading_observations(raw, as_of=AS_OF, metric="pe_ratio")
    assert len(points) == 24
    assert points[-1]["observed_date"] == "2026-09-30"
    assert points[1]["observed_date"] == "2024-11-29"  # Sat Nov 30
    assert points[1]["month_end_date"] == "2024-11-30"
    assert points[1]["month_end_observation"] is True


def test_no_midmonth_gap_fill_and_no_current_unfinished_month():
    raw = valuation_rows()
    raw[0]["observed_date"] = "2024-10-10"
    raw.append({**raw[-1], "observed_date": "2026-10-23"})
    points = monthly_last_trading_observations(raw, as_of=AS_OF, metric="pe_ratio")
    assert len(points) == 23
    assert all(p["observed_date"] != "2026-10-23" for p in points)


def test_latest_day_conflict_excludes_month_without_fallback():
    raw = valuation_rows()
    raw.append({**raw[1], "pe_ratio": "99"})
    points = monthly_last_trading_observations(raw, as_of=AS_OF, metric="pe_ratio")
    assert len(points) == 23


def test_bad_provenance_and_future_values_not_counted():
    raw = valuation_rows()
    raw[0]["provenance_id"] = ""
    raw[1]["first_observed_at"] = "2026-10-25"
    raw[2]["source_id"] = "unknown"
    points = monthly_last_trading_observations(raw, as_of=AS_OF, metric="pe_ratio")
    assert len(points) == 21


def test_existing_core_financials_produce_range_without_fetch():
    result = from_existing_rows(
        symbol="2330", market="twse", security_type="ordinary_stock",
        is_financial=False, as_of=AS_OF, valuation_rows=valuation_rows(),
        financial_rows=financial_rows(), rights_status="approved",
        price="150", price_as_of="2026-10-23",
    )
    assert result["status"] == "available"
    assert result["valid_month_count"] == 24
    assert Decimal(result["lower"]) <= Decimal(result["mid"]) <= Decimal(result["upper"])
    assert result["input_refs"]["multiple_source"] == "core.valuation_v1/current"
    assert len(result["month_end_observation_dates"]) == 24


def test_missing_share_basis_is_not_guessed_and_financial_needs_bvps():
    result = from_existing_rows(
        symbol="2330", market="twse", security_type="ordinary_stock",
        is_financial=False, as_of=AS_OF, valuation_rows=valuation_rows(),
        financial_rows=financial_rows(share_basis=None), rights_status="approved",
    )
    assert result["status"] == "blocked_basis"
    bank = from_existing_rows(
        symbol="2882", market="twse", security_type="ordinary_stock",
        is_financial=True, as_of=AS_OF, valuation_rows=valuation_rows(),
        financial_rows=financial_rows(), rights_status="approved",
    )
    assert bank["status"] == "missing"
    assert bank["mid"] is None


def test_not_applicable_etf_and_source_rights():
    base = dict(
        symbol="0050", market="twse", is_financial=False,
        as_of=AS_OF, valuation_rows=valuation_rows(),
        financial_rows=financial_rows(), rights_status="approved",
    )
    assert from_existing_rows(**base, security_type="etf")["status"] == "not_applicable"
    assert from_existing_rows(**{**base, "rights_status": "unknown"},
                              security_type="ordinary_stock")["status"] == "blocked_rights"


def test_financial_ytd_and_unknown_source_never_promoted():
    original = financial_rows()
    original[0]["period_basis"] = "year_to_date"
    original[1]["source_id"] = "unknown"
    approved = comparable_financial_facts(original, as_of=AS_OF)
    assert len(approved) == 2


def test_unbounded_core_rows_fail_closed():
    with pytest.raises(ValueError, match="outside_bound"):
        monthly_last_trading_observations(
            valuation_rows() * (MAX_CORE_ROWS // 24 + 1),
            as_of=AS_OF, metric="pe_ratio",
        )


class Cursor:
    def __init__(self):
        self.query = ""
        self.values = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, values):
        self.query = query
        self.values = values

    def fetchone(self):
        if "stock_master" in self.query:
            return ("TWSE",)
        if "stock_serving_recent" in self.query:
            return ({"close": "150", "trade_date": "2026-10-23"}, "twse", "p")
        return None

    def fetchall(self):
        if "market_serving_recent" in self.query:
            return [
                ({k: v for k, v in r.items() if k not in {"source_id", "provenance_id"}},
                 r["source_id"], r["provenance_id"])
                for r in financial_rows()
            ]
        return []


class Connection:
    def cursor(self):
        return Cursor()


class Control:
    def __init__(self):
        self.connection = Connection()


class Scan:
    def __init__(self, rows):
        self.rows = rows

    def to_arrow(self):
        return self

    def to_pylist(self):
        return self.rows


class Snapshot:
    snapshot_id = 126


class Table:
    def current_snapshot(self):
        return Snapshot()

    def scan(self, **kwargs):
        assert kwargs["limit"] == MAX_CORE_ROWS + 1
        assert kwargs["selected_fields"][0] == "symbol"
        return Scan(valuation_rows())


class Catalog:
    def load_table(self, key):
        assert key == "core.valuation_v1"
        return Table()


class Core:
    catalog = Catalog()

    def table_identifier(self, key):
        assert key == "valuation"
        return "core.valuation_v1"


def test_real_core_and_serving_reader_contract_with_injected_stores():
    pytest.importorskip("pyiceberg.expressions")
    report = read_existing_inputs(
        Core(), Control(), symbol="2330", as_of=AS_OF,
        security_type="ordinary_stock", is_financial=False,
        rights_status="approved",
    )
    assert report["status"] == "available"
    assert report["input_refs"]["core_snapshot_id"] == "126"
    assert report["source_rows_scanned"] == {"valuation": 24, "financials": 4, "price": 1}


def test_invalid_scope_never_queries_core():
    with pytest.raises(ValueError, match="valuation_input_scope_invalid"):
        read_existing_inputs(
            Core(), Control(), symbol="2330", as_of=AS_OF,
            security_type="ordinary_stock", is_financial=False,
            rights_status="approved", max_core_rows=5000,
        )
