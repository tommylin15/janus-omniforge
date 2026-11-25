"""Janus / OmniForge API + AI 個股分析 v2（StockInsightV2）三層資料契約。

嚴格區分：
1. AIAnalysisInput：後端確定性事實與核准外部資料（後端 → LLM，嚴禁含任何私人帳本欄位）。
2. LLMInsightDraft：LLM Structured Output 原始輸出（無系統 ID、無 review_status、無展開證據）。
3. StockInsightV2：後端驗證並展開 evidence_refs[] / secondary_insights / more_count 後之對外 API 與持久化契約。
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import re
from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def sanitize_prompt_text(text: str) -> str:
    """跳脫 <INPUT_DATA> 與 </INPUT_DATA> 標籤，防止外部文本夾帶 Prompt Injection。"""
    if not text:
        return ""
    cleaned = re.sub(r"<\s*/?\s*INPUT_DATA\s*>", "[INPUT_DATA_ESCAPED]", text, flags=re.IGNORECASE)
    return cleaned


class StrictContractModel(BaseModel):
    """禁用未定義欄位（防止誤傳 owner_id、成本或持股張數進入公共分析）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 第一層：AIAnalysisInput（後端 → LLM）
# ==============================================================================


class AnalysisMeta(StrictContractModel):
    canonical_symbol: str = Field(min_length=1, max_length=16)
    company_name: str = Field(min_length=1, max_length=80)
    market: Literal["TWSE", "TPEx"]
    security_type: Literal["common_stock", "financial", "etf", "reit", "ky_stock"]
    as_of_date: date
    price_as_of_date: date
    session: Literal["pre_market", "post_market", "holiday"]


class TriggeredRule(StrictContractModel):
    rule_id: Literal[
        "T1_DIVIDEND_CHANGE",
        "T2_COVERAGE_OR_PROFIT_DROP",
        "T3_CREDIT_OR_VOLATILITY_STRESS",
        "T4_MOPS_GOVERNANCE_EVENT",
        "T5_STRUCTURAL_REVENUE_DECLINE",
    ]
    severity: Literal["WARN", "REVIEW"]
    evidence_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=300)


class DeterministicReview(StrictContractModel):
    review_status: Literal["OK", "WARN", "REVIEW"]
    triggered_rules: list[TriggeredRule] = Field(default_factory=list)


class DeterministicFact(StrictContractModel):
    evidence_id: str = Field(min_length=1)
    category: Literal["price", "operation", "valuation", "risk"]
    metric: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value: float | None = None
    display_value: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    as_of: date
    deep_link: str = Field(min_length=1)


class RecentEvent(StrictContractModel):
    evidence_id: str = Field(min_length=1)
    category: Literal["event"] = "event"
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(max_length=300)
    source_name: str = Field(min_length=1)
    published_at: datetime
    source_url: str | None = None
    deep_link: str = Field(min_length=1)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _escape_prompt_tags(cls, value: Any) -> Any:
        if isinstance(value, str):
            return sanitize_prompt_text(value)
        return value


class ExternalEstimateItem(StrictContractModel):
    evidence_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    fiscal_period: str = Field(min_length=1)
    basis: Literal["reported", "adjusted", "unknown"]
    analyst_count: int | None = None
    display_value: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    vendor_as_of: date
    llm_input_allowed: Literal[True]


class ExternalEstimates(StrictContractModel):
    status: Literal["available", "stale", "not_covered", "blocked_basis", "blocked_rights"]
    items: list[ExternalEstimateItem] = Field(default_factory=list)


class PreviousInsight(StrictContractModel):
    insight_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    state: str = Field(min_length=1)
    as_of: date


class AIAnalysisInput(StrictContractModel):
    """後端傳入 Gemini Hydrogen 之安全結構化輸入（絕不含私人帳本資料）。"""

    meta: AnalysisMeta
    deterministic_review: DeterministicReview
    deterministic_facts: list[DeterministicFact] = Field(default_factory=list)
    recent_events: list[RecentEvent] = Field(default_factory=list, max_length=10)
    external_estimates: ExternalEstimates
    previous_insights: list[PreviousInsight] = Field(default_factory=list, max_length=5)


# ==============================================================================
# 第二層：LLMInsightDraft（僅供 LLM Structured Output 校驗）
# ==============================================================================


class Summary30s(StrictContractModel):
    current_state: str = Field(min_length=1, max_length=120)
    key_delta: str = Field(min_length=1, max_length=120)
    top_watch: str = Field(min_length=1, max_length=120)


class LLMPrimaryInsightDraft(StrictContractModel):
    previous_id: str | None = None
    statement_type: Literal[
        "confirmed_fact",
        "company_guidance",
        "external_consensus",
        "conditional_scenario",
        "ai_synthesis",
    ]
    category: Literal["event", "operation", "valuation", "price", "risk"]
    state: Literal[
        "new",
        "ongoing",
        "strengthened",
        "weakened",
        "resolved",
        "invalidated",
        "expired",
        "pending",
    ]
    rank_reason: Literal[
        "material_event",
        "earnings_or_revenue_shift",
        "valuation_extreme",
        "price_volume_anomaly",
        "risk_elevation",
        "consensus_revision",
    ]
    headline: str = Field(min_length=1, max_length=80)
    meaning: str | None = Field(default=None, max_length=160)
    next_check: str = Field(min_length=1, max_length=100)
    invalidation_condition: str = Field(min_length=1, max_length=100)
    evidence_ids: list[str] = Field(min_length=1)


class LLMInsightDraft(StrictContractModel):
    """LLM 原始輸出契約；不允許自填 insight_id、review_status、quality_gate 或 evidence_refs。"""

    summary_30s: Summary30s
    primary_insights: list[LLMPrimaryInsightDraft] = Field(default_factory=list, max_length=3)


# ==============================================================================
# 第三層：StockInsightV2（API 對外與持久化契約）
# ==============================================================================


class QualityGate(StrictContractModel):
    status: Literal["PASS", "WARN", "FALLBACK_ON_ERROR"]
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)


class GenerationMeta(StrictContractModel):
    mode: Literal["ai_synthesis", "deterministic_fallback"]
    model_id: str | None = None
    prompt_version: str = Field(min_length=1)
    facts_events_hash: str = Field(min_length=16)
    generated_at: datetime
    source_status: Literal["available", "stale", "partial", "not_covered"]
    quality_gate: QualityGate


class EvidenceRef(StrictContractModel):
    evidence_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    as_of: date
    label: str = Field(min_length=1)
    display_value: str = Field(min_length=1)
    source_url: str | None = None
    deep_link: str = Field(min_length=1)


class StockInsightItem(StrictContractModel):
    insight_id: str = Field(min_length=1)
    previous_id: str | None = None
    statement_type: Literal[
        "confirmed_fact",
        "company_guidance",
        "external_consensus",
        "conditional_scenario",
        "ai_synthesis",
    ]
    category: Literal["event", "operation", "valuation", "price", "risk"]
    state: Literal[
        "new",
        "ongoing",
        "strengthened",
        "weakened",
        "resolved",
        "invalidated",
        "expired",
        "pending",
    ]
    rank_reason: Literal[
        "material_event",
        "earnings_or_revenue_shift",
        "valuation_extreme",
        "price_volume_anomaly",
        "risk_elevation",
        "consensus_revision",
    ]
    headline: str = Field(min_length=1, max_length=80)
    meaning: str | None = Field(default=None, max_length=160)
    next_check: str = Field(min_length=1, max_length=100)
    invalidation_condition: str = Field(min_length=1, max_length=100)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)


class StockInsightV2(StrictContractModel):
    """對外 API（/changes 頂層 insight_v2）與 control.stock_insight_v2_snapshots 持久化契約。"""

    schema_version: Literal["insight.v2"] = "insight.v2"
    canonical_symbol: str = Field(min_length=1)
    as_of_date: date
    price_as_of_date: date
    review_status: Literal["OK", "WARN", "REVIEW"]
    triggered_rules: list[str] = Field(default_factory=list)
    generation_meta: GenerationMeta
    summary_30s: Summary30s
    primary_insights: list[StockInsightItem] = Field(default_factory=list, max_length=3)
    secondary_insights: list[dict[str, Any]] = Field(default_factory=list)
    more_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_more_count(self) -> StockInsightV2:
        if self.more_count != len(self.secondary_insights):
            raise ValueError("more_count must match len(secondary_insights)")
        return self


def compute_facts_events_hash(input_data: AIAnalysisInput) -> str:
    """計算正規化事實／事件／外部預估／覆核雜湊（刻意排除 as_of_date、price_as_of_date、session）。"""
    payload = {
        "canonical_symbol": input_data.meta.canonical_symbol,
        "deterministic_review": {
            "review_status": input_data.deterministic_review.review_status,
            "triggered_rules": sorted(
                (rule.model_dump(mode="json") for rule in input_data.deterministic_review.triggered_rules),
                key=lambda r: (r["rule_id"], r["severity"]),
            ),
        },
        "deterministic_facts": sorted(
            (fact.model_dump(mode="json") for fact in input_data.deterministic_facts),
            key=lambda f: f["evidence_id"],
        ),
        "recent_events": sorted(
            (ev.model_dump(mode="json") for ev in input_data.recent_events),
            key=lambda e: e["evidence_id"],
        ),
        "external_estimates": {
            "status": input_data.external_estimates.status,
            "items": sorted(
                (item.model_dump(mode="json") for item in input_data.external_estimates.items),
                key=lambda x: x["evidence_id"],
            ),
        },
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_evidence_catalog(input_data: AIAnalysisInput) -> dict[str, EvidenceRef]:
    """從 AIAnalysisInput 建立所有允許引用之 EvidenceRef 查找表。"""
    catalog: dict[str, EvidenceRef] = {}
    for fact in input_data.deterministic_facts:
        catalog[fact.evidence_id] = EvidenceRef(
            evidence_id=fact.evidence_id,
            source_name=fact.source_name,
            as_of=fact.as_of,
            label=fact.label,
            display_value=fact.display_value,
            source_url=None,
            deep_link=fact.deep_link,
        )
    for ev in input_data.recent_events:
        catalog[ev.evidence_id] = EvidenceRef(
            evidence_id=ev.evidence_id,
            source_name=ev.source_name,
            as_of=ev.published_at.date(),
            label=ev.title,
            display_value=ev.event_type,
            source_url=ev.source_url,
            deep_link=ev.deep_link,
        )
    for est in input_data.external_estimates.items:
        catalog[est.evidence_id] = EvidenceRef(
            evidence_id=est.evidence_id,
            source_name=est.provider,
            as_of=est.vendor_as_of,
            label=f"{est.metric} ({est.fiscal_period})",
            display_value=f"{est.display_value} {est.currency}".strip(),
            source_url=None,
            deep_link=f"/stock/{input_data.meta.canonical_symbol}?tab=valuation",
        )
    return catalog


def deterministic_insight_id(canonical_symbol: str, as_of_date: date, idx: int) -> str:
    """依 (canonical_symbol, as_of_date, idx) 確定性生成 insight_id。"""
    raw = f"{canonical_symbol}|{as_of_date.isoformat()}|{idx}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"ins_{canonical_symbol}_{as_of_date:%Y%m%d}_{idx}_{digest}"


def build_stock_insight_v2(
    input_data: AIAnalysisInput,
    draft: LLMInsightDraft,
    *,
    mode: Literal["ai_synthesis", "deterministic_fallback"],
    model_id: str | None,
    prompt_version: str,
    generated_at: datetime,
    source_status: Literal["available", "stale", "partial", "not_covered"],
    quality_gate: QualityGate,
    secondary_insights: Sequence[dict[str, Any]] = (),
) -> StockInsightV2:
    """由後端驗證 evidence_ids 並展開為完整的 StockInsightV2 契約。"""
    catalog = build_evidence_catalog(input_data)
    expanded: list[StockInsightItem] = []
    for idx, item in enumerate(draft.primary_insights):
        missing = [eid for eid in item.evidence_ids if eid not in catalog]
        if missing:
            raise ValueError(f"unknown evidence_ids rejected: {','.join(missing)}")
        refs = [catalog[eid] for eid in item.evidence_ids]
        expanded.append(
            StockInsightItem(
                insight_id=deterministic_insight_id(
                    input_data.meta.canonical_symbol,
                    input_data.meta.as_of_date,
                    idx,
                ),
                previous_id=item.previous_id,
                statement_type=item.statement_type,
                category=item.category,
                state=item.state,
                rank_reason=item.rank_reason,
                headline=item.headline,
                meaning=item.meaning,
                next_check=item.next_check,
                invalidation_condition=item.invalidation_condition,
                evidence_refs=refs,
            )
        )
    sec_list = [dict(x) for x in secondary_insights]
    return StockInsightV2(
        canonical_symbol=input_data.meta.canonical_symbol,
        as_of_date=input_data.meta.as_of_date,
        price_as_of_date=input_data.meta.price_as_of_date,
        review_status=input_data.deterministic_review.review_status,
        triggered_rules=[r.rule_id for r in input_data.deterministic_review.triggered_rules],
        generation_meta=GenerationMeta(
            mode=mode,
            model_id=model_id,
            prompt_version=prompt_version,
            facts_events_hash=compute_facts_events_hash(input_data),
            generated_at=generated_at,
            source_status=source_status,
            quality_gate=quality_gate,
        ),
        summary_30s=draft.summary_30s,
        primary_insights=expanded,
        secondary_insights=sec_list,
        more_count=len(sec_list),
    )


def to_today_preview(insight: StockInsightV2) -> dict[str, Any]:
    """產生 /api/v1/me/today-changes 專用的輕量版 insight_v2_preview。"""
    return {
        "schema_version": insight.schema_version,
        "review_status": insight.review_status,
        "summary_30s": insight.summary_30s.model_dump(mode="json"),
        "primary_insight": (
            insight.primary_insights[0].model_dump(mode="json")
            if insight.primary_insights
            else None
        ),
        "more_count": insight.more_count,
    }
