"""AI-REF-04 單元測試：Gemini Hydrogen 分析引擎、5 道防線、快取轉態與降級。"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json

from packages.ai_insight_contracts import (
    AIAnalysisInput,
    AnalysisMeta,
    DeterministicFact,
    DeterministicReview,
    ExternalEstimates,
    RecentEvent,
    TriggeredRule,
)
from packages.ai_insight_engine import (
    DailyLLMBudget,
    PROMPT_VERSION,
    synthesize_stock_insight,
)


def _make_input(
    *,
    as_of: date = date(2026, 11, 25),
    price_date: date = date(2026, 11, 25),
    with_t4: bool = False,
    summary_text: str = "大股東申報賣出 5,000 張，公告日交易正常。",
) -> AIAnalysisInput:
    rules = []
    events = [
        RecentEvent(
            evidence_id="evt_mops_1",
            event_type="mops_major_holder",
            title="大股東申報轉讓公告",
            summary=summary_text,
            source_name="MOPS",
            published_at=datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc),
            deep_link="/stock/2330?tab=event",
        )
    ]
    if with_t4:
        rules.append(
            TriggeredRule(
                rule_id="T4_MOPS_GOVERNANCE_EVENT",
                severity="REVIEW",
                evidence_ids=["evt_t4_1"],
                reason="經櫃買中心公告列為處置股票。",
            )
        )
        events.append(
            RecentEvent(
                evidence_id="evt_t4_1",
                event_type="mops_disposition",
                title="公告列為處置股票",
                summary="分盤交易處置 10 個營業日。",
                source_name="MOPS",
                published_at=datetime(2026, 11, 25, 8, 30, tzinfo=timezone.utc),
                deep_link="/stock/2330?tab=event",
            )
        )
    return AIAnalysisInput(
        meta=AnalysisMeta(
            canonical_symbol="2330",
            company_name="台積電",
            market="TWSE",
            security_type="common_stock",
            as_of_date=as_of,
            price_as_of_date=price_date,
            session="post_market",
        ),
        deterministic_review=DeterministicReview(
            review_status="REVIEW" if with_t4 else "OK",
            triggered_rules=rules,
        ),
        deterministic_facts=[
            DeterministicFact(
                evidence_id="fact_price_1",
                category="price",
                metric="close",
                label="還原收盤價",
                value=1050.0,
                display_value="1,050.0 元",
                currency="TWD",
                source_name="TWSE_CORE",
                as_of=date(2026, 11, 25),
                deep_link="/stock/2330?tab=price",
            )
        ],
        recent_events=events,
        external_estimates=ExternalEstimates(status="not_covered", items=[]),
        previous_insights=[],
    )


def _valid_llm_json(*, headline: str = "收盤價 1,050.0 元", meaning: str | None = "大股東申報賣出 5,000 張屬於事實揭露。", eid: str = "fact_price_1") -> str:
    return json.dumps(
        {
            "summary_30s": {
                "current_state": "收盤報 1,050.0 元",
                "key_delta": "申報轉讓 5,000 張",
                "top_watch": "後續成交量與月營收",
            },
            "primary_insights": [
                {
                    "previous_id": None,
                    "statement_type": "confirmed_fact",
                    "category": "price",
                    "state": "new",
                    "rank_reason": "material_event",
                    "headline": headline,
                    "meaning": meaning,
                    "next_check": "觀察下一次月營收公告",
                    "invalidation_condition": "股價跌破前波支撐",
                    "evidence_ids": [eid],
                }
            ],
        },
        ensure_ascii=False,
    )


def test_ai_synthesis_passes_all_gates_and_exempts_neutral_news(monkeypatch):
    monkeypatch.setenv("JANUS_LLM_MODEL", "gemini-hydrogen")
    inp = _make_input()
    calls: list[tuple[str, str]] = []

    def _caller(_sys: str, _usr: str, model: str) -> str:
        calls.append((model, PROMPT_VERSION))
        return _valid_llm_json()

    res = synthesize_stock_insight(inp, llm_caller=_caller, secondary_insights=[{"headline": "補充"}])
    assert len(calls) == 1
    assert calls[0][0] == "gemini-hydrogen"
    assert res.generation_meta.mode == "ai_synthesis"
    assert res.generation_meta.quality_gate.status == "PASS"
    assert res.more_count == 1
    assert res.primary_insights[0].evidence_refs[0].evidence_id == "fact_price_1"


def test_ghost_evidence_id_triggers_deterministic_fallback():
    inp = _make_input()
    res = synthesize_stock_insight(
        inp,
        llm_caller=lambda *_args: _valid_llm_json(eid="ghost_999"),
    )
    assert res.generation_meta.mode == "deterministic_fallback"
    assert res.generation_meta.quality_gate.status == "FALLBACK_ON_ERROR"


def test_ungrounded_numeric_triggers_fallback():
    inp = _make_input()
    # 捏造輸入不存在的「營收年增 99.9%」與「500億」
    res = synthesize_stock_insight(
        inp,
        llm_caller=lambda *_args: _valid_llm_json(headline="營收估大增 99.9% 達 500億"),
    )
    assert res.generation_meta.mode == "deterministic_fallback"
    assert res.generation_meta.quality_gate.status == "FALLBACK_ON_ERROR"


def test_forbidden_directive_triggers_fallback():
    inp = _make_input()
    res = synthesize_stock_insight(
        inp,
        llm_caller=lambda *_args: _valid_llm_json(meaning="建議賣出並逢低承接其他標的。"),
    )
    assert res.generation_meta.mode == "deterministic_fallback"
    assert res.generation_meta.quality_gate.status == "FALLBACK_ON_ERROR"


def test_cache_hit_skips_llm_and_transitions_new_to_ongoing():
    day1_inp = _make_input(as_of=date(2026, 11, 25), price_date=date(2026, 11, 25))
    llm_count = {"n": 0}

    def _caller(*_args) -> str:
        llm_count["n"] += 1
        return _valid_llm_json()

    day1_out = synthesize_stock_insight(day1_inp, llm_caller=_caller)
    assert llm_count["n"] == 1
    assert day1_out.primary_insights[0].state == "new"

    # 隔日事實與事件雜湊不變，必須命中快取（LLM 呼叫數 = 0）且自動轉 ongoing
    day2_inp = _make_input(as_of=date(2026, 11, 26), price_date=date(2026, 11, 26))
    day2_out = synthesize_stock_insight(day2_inp, cached_insight=day1_out, llm_caller=_caller)
    assert llm_count["n"] == 1
    assert day2_out.as_of_date == date(2026, 11, 26)
    assert day2_out.primary_insights[0].state == "ongoing"
    assert day2_out.primary_insights[0].previous_id == day1_out.primary_insights[0].insight_id


def test_llm_timeout_on_new_t4_event_writes_fresh_fallback_without_stale_masking():
    day1_inp = _make_input(as_of=date(2026, 11, 24), with_t4=False)
    day1_out = synthesize_stock_insight(day1_inp, llm_caller=lambda *_args: _valid_llm_json())

    # 隔日發生 T4 處置重訊（facts_events_hash 改變不命中快取），模擬 LLM 逾時
    day2_inp = _make_input(as_of=date(2026, 11, 25), with_t4=True)

    def _timeout(*_args) -> str:
        raise TimeoutError("upstream timeout")

    day2_out = synthesize_stock_insight(day2_inp, cached_insight=day1_out, llm_caller=_timeout)
    assert day2_out.as_of_date == date(2026, 11, 25)
    assert day2_out.review_status == "REVIEW"
    assert day2_out.generation_meta.mode == "deterministic_fallback"
    assert day2_out.generation_meta.quality_gate.status == "FALLBACK_ON_ERROR"
    assert "T4_MOPS_GOVERNANCE_EVENT" in day2_out.primary_insights[0].headline


def test_disabled_flag_and_daily_budget_exceeded_fallback(monkeypatch):
    inp = _make_input()
    called = {"n": 0}

    def _caller(*_args) -> str:
        called["n"] += 1
        return _valid_llm_json()

    # 1. 配額耗盡
    exhausted = DailyLLMBudget(max_calls=1, used_calls=1)
    r_budget = synthesize_stock_insight(inp, llm_caller=_caller, budget=exhausted)
    assert called["n"] == 0
    assert r_budget.generation_meta.mode == "deterministic_fallback"

    # 2. AI_SYNTHESIS_ENABLED=false
    monkeypatch.setenv("AI_SYNTHESIS_ENABLED", "false")
    r_disabled = synthesize_stock_insight(inp, llm_caller=_caller)
    assert called["n"] == 0
    assert r_disabled.generation_meta.mode == "deterministic_fallback"
    assert r_disabled.generation_meta.quality_gate.status == "PASS"
