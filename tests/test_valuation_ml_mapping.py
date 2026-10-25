"""Valuation v26 accounting mapping never uses proxy ratios or unverified versions."""
import math
from intelligence_mart.valuation_ml_mapping import build_v26_features, FEATURES


def _rows():
    metrics = {"total_assets_snapshot": ("balance", "snapshot", 20000000),
               "total_liabilities_snapshot": ("balance", "snapshot", 8000000),
               "total_equity_snapshot": ("balance", "snapshot", 12000000),
               "net_income_year_to_date": ("income", "year_to_date", 1200000),
               "revenue_year_to_date": ("income", "year_to_date", 6000000)}
    rows = [{"symbol": "2330", "market": "twse", "source_id": "mops",
             "report_scope": "consolidated", "unit": "TWD", "currency": "TWD",
             "metric": metric, "statement_type": spec[0], "period_basis": spec[1],
             "fiscal_year": 2026, "fiscal_quarter": 2, "value": spec[2],
             "availability_at": "2026-08-14"} for metric, spec in metrics.items()]
    return rows + [{**rows[-1], "fiscal_year": 2025, "value": 3000000,
                    "availability_at": "2025-08-14"}]


def test_five_slots_from_core_xbrl_twd_and_prior_year_ytd():
    got = build_v26_features(_rows(), symbol="2330", market="twse", as_of="2026-10-25")
    assert got["feature_order"] == list(FEATURES) and got["feature_ready"]
    v = got["values"]
    assert v["roe_proxy"] == .1 and v["debt_ratio"] == .4
    assert math.isclose(v["log_total_assets"], math.log(20000000))
    assert v["revenue_yoy"] == 1 and v["market_code"] == 0


def test_missing_prior_year_future_or_ambiguous_basis_fails_closed():
    base = _rows()
    for rows in (base[:-1],
                 [{**base[0], "unit": "TWD_thousands"}, *base[1:]],
                 base + [{**base[0], "value": 21000000}],
                 [{**base[0], "report_scope": "separate"}, *base[1:]]):
        got = build_v26_features(rows, symbol="2330", market="twse", as_of="2026-10-25")
        assert not got["feature_ready"] and got["values"]["roe_proxy"] is None
    assert not build_v26_features(base, symbol="2330", market="twse",
                                  as_of="2026-06-01")["feature_ready"]
