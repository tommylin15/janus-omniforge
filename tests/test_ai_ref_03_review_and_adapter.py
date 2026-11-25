"""AI-REF-03 單元測試：T1–T5 台股確定性異常覆核引擎、外部 Adapter 與四模型停用旗標。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.ai_insight_contracts import ExternalEstimateItem, ExternalEstimates
from packages.external_estimates_adapter import fetch_external_estimates_safe
from packages.review_rules import evaluate_deterministic_review

ROOT = Path(__file__).resolve().parents[1]


def test_t1_dividend_flat_vs_cut_vs_etf():
    # 配息與前期持平且無其他異常 -> WARN（非惡化）
    flat = evaluate_deterministic_review(
        security_type="common_stock",
        dividend_info={
            "has_current_announcement": True,
            "prev_total_dividend": 2.0,
            "curr_total_dividend": 2.0,
            "current_total_dividend": 2.0,
        },
    )
    assert flat.review_status == "WARN"
    assert flat.triggered_rules[0].rule_id == "T1_DIVIDEND_CHANGE"
    assert flat.triggered_rules[0].severity == "WARN"

    # 配息減 >=20% -> REVIEW
    cut = evaluate_deterministic_review(
        security_type="common_stock",
        dividend_info={
            "has_current_announcement": True,
            "prev_total_dividend": 4.0,
            "current_total_dividend": 3.0,
        },
    )
    assert cut.review_status == "REVIEW"

    # ETF 排除 T1
    etf = evaluate_deterministic_review(
        security_type="etf",
        dividend_info={
            "has_current_announcement": True,
            "prev_total_dividend": 2.0,
            "current_total_dividend": 1.0,
        },
    )
    assert etf.review_status == "OK"
    assert etf.triggered_rules == []


def test_t2_financial_exception_and_margin_decline():
    # 金融股排除傳統毛利率/營益率，單季淨利 YoY <= -25% 觸發 WARN
    fin = evaluate_deterministic_review(
        security_type="financial",
        profit_info={
            "gross_margins": [40.0, 35.0, 30.0],
            "net_income_prev_year": 100.0,
            "net_income_current": 70.0,
        },
    )
    assert fin.review_status == "WARN"
    assert "金融股" in fin.triggered_rules[0].reason

    # 單季 EPS 轉虧 -> REVIEW
    loss = evaluate_deterministic_review(
        security_type="common_stock",
        profit_info={"prev_year_eps": 1.2, "current_eps": -0.3},
    )
    assert loss.review_status == "REVIEW"

    # 負 EPS 基期轉盈不誤判
    rebound = evaluate_deterministic_review(
        security_type="common_stock",
        profit_info={"prev_year_eps": -0.5, "current_eps": 0.2},
    )
    assert rebound.review_status == "OK"


def test_t3_financial_zero_debt_and_mdd():
    # 無負債公司（interest_expense = 0）不可除零，也不誤觸信用惡化
    zero_debt = evaluate_deterministic_review(
        security_type="common_stock",
        stress_info={
            "interest_expense": 0.0,
            "interest_coverage_ratio": 0.0,
            "net_debt_ratio_change_pp": 15.0,
            "adjusted_mdd_20d_pct": 5.0,
        },
    )
    assert zero_debt.review_status == "OK"

    # 金融股排除淨負債比與 ICR，但還原股價 MDD >= 18% 仍觸發 WARN
    fin_mdd = evaluate_deterministic_review(
        security_type="financial",
        stress_info={
            "interest_expense": 10.0,
            "interest_coverage_ratio": 1.2,
            "net_debt_ratio_change_pp": 20.0,
            "adjusted_mdd_20d_pct": 19.5,
        },
    )
    assert fin_mdd.review_status == "WARN"
    assert fin_mdd.triggered_rules[0].severity == "WARN"


def test_t4_governance_vs_clarification_notice():
    # 澄清媒體報導不應誤觸 T4 REVIEW
    clarify = evaluate_deterministic_review(
        security_type="common_stock",
        events=[
            {
                "evidence_id": "evt_1",
                "title": "本公司澄清媒體報導無大幅減資或處置計畫",
                "summary": "媒體報導純屬臆測，特此澄清並無此事。",
            }
        ],
    )
    assert clarify.review_status == "OK"
    assert clarify.triggered_rules == []

    # 實質處置公告觸發 REVIEW
    real_t4 = evaluate_deterministic_review(
        security_type="common_stock",
        events=[
            {
                "evidence_id": "evt_2",
                "title": "本公司經櫃買中心公告列為處置股票（分盤交易）",
                "summary": "自明日起採每二十分鐘撮合一次。",
            }
        ],
    )
    assert real_t4.review_status == "REVIEW"
    assert real_t4.triggered_rules[0].rule_id == "T4_MOPS_GOVERNANCE_EVENT"


def test_t5_lunar_new_year_cumulative_yoy():
    # 1 月單月暴跌但 1-2 月累計正成長，不可觸發連 3 月衰退
    lunar_safe = evaluate_deterministic_review(
        security_type="common_stock",
        revenue_info={
            "monthly_records": [
                {"month": 12, "yoy_pct": -12.0},
                {"month": 1, "yoy_pct": -35.0, "cumulative_yoy_pct": 5.0},
                {"month": 2, "yoy_pct": 40.0, "cumulative_yoy_pct": 5.0},
            ]
        },
    )
    assert lunar_safe.review_status == "OK"

    # 連 3 期（含 1-2 月累計）皆 <= -10% -> WARN
    decline = evaluate_deterministic_review(
        security_type="common_stock",
        revenue_info={
            "monthly_records": [
                {"month": 12, "yoy_pct": -11.0},
                {"month": 1, "yoy_pct": -20.0, "cumulative_yoy_pct": -12.5},
                {"month": 2, "yoy_pct": -5.0, "cumulative_yoy_pct": -12.5},
            ]
        },
    )
    assert decline.review_status == "WARN"
    assert decline.triggered_rules[0].rule_id == "T5_STRUCTURAL_REVENUE_DECLINE"


def test_external_estimates_adapter_guards():
    valid_item = ExternalEstimateItem(
        evidence_id="est_1",
        provider="TestConsensus",
        metric="EPS",
        fiscal_period="FY2026",
        basis="reported",
        analyst_count=8,
        display_value="35.0",
        currency="TWD",
        vendor_as_of=date(2026, 11, 20),
        llm_input_allowed=True,
    )
    last_ok = ExternalEstimates(status="available", items=[valid_item])

    # 未啟用旗標 -> not_covered
    disabled = fetch_external_estimates_safe("2330", fetcher=lambda _s: [], enabled=False)
    assert disabled.status == "not_covered"

    # 缺 llm_input_allowed=True -> blocked_rights
    blocked_r = fetch_external_estimates_safe(
        "2330",
        fetcher=lambda _s: [{**valid_item.model_dump(), "llm_input_allowed": False}],
        enabled=True,
    )
    assert blocked_r.status == "blocked_rights"
    assert blocked_r.items == []

    # 混用 adjusted 與 reported -> blocked_basis
    blocked_b = fetch_external_estimates_safe(
        "2330",
        fetcher=lambda _s: [
            valid_item.model_dump(),
            {**valid_item.model_dump(), "evidence_id": "est_2", "basis": "adjusted"},
        ],
        enabled=True,
    )
    assert blocked_b.status == "blocked_basis"
    assert blocked_b.items == []

    # 外部 API 例外 -> 不覆蓋 last-success，回傳 stale
    def _boom(_sym: str):
        raise TimeoutError("429 rate limited")

    stale = fetch_external_estimates_safe("2330", fetcher=_boom, last_success=last_ok, enabled=True)
    assert stale.status == "stale"
    assert len(stale.items) == 1
    assert stale.items[0].evidence_id == "est_1"


def test_four_model_serving_is_disabled_by_default_in_specialist_runtime():
    src = (ROOT / "jobs/intelligence-mart/intelligence_mart/specialist_runtime.py").read_text(encoding="utf-8")
    assert 'JANUS_FOUR_MODEL_SERVING_ENABLED' in src
    assert 'four_model_ref = None' in src
