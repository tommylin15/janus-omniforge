"""T1–T5 台股確定性異常覆核引擎（供 AI-REF-03 與 AIAnalysisInput 使用）。

嚴格使用後端確定性計算與台股專屬例外規則，絕不依賴 LLM 判斷嚴重度。
多條規則觸發時保留所有 TriggeredRule，最終 review_status 取 REVIEW > WARN > OK。
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from packages.ai_insight_contracts import DeterministicReview, TriggeredRule

_CLARIFICATION_RE = re.compile(
    r"(澄清媒體報導|澄清報導|並無此事|並無|否認|無此計畫|無此規劃|特此澄清|絕無此事|媒體臆測)"
)

_T4_GOVERNANCE_KEYWORDS = (
    "處置股票",
    "處置有價證券",
    "分盤交易",
    "全額交割",
    "變更交易方法",
    "暫停交易",
    "停止買賣",
    "終止上市",
    "終止上櫃",
    "財報重編",
    "重編財務報告",
    "會計師保留意見",
    "會計師否定意見",
    "無法表示意見",
    "大幅減資",
    "彌補虧損減資",
    "重大訴訟",
    "大額訴訟",
    "假扣押",
    "經營權異動",
    "掏空",
    "檢調搜索",
)


def _severity_rank(severity: str) -> int:
    return {"OK": 0, "WARN": 1, "REVIEW": 2}.get(severity, 0)


def _is_clarification_notice(title: str, summary: str) -> bool:
    """檢查標題或首句是否屬澄清媒體報導／否認類重訊，避免誤判為實質異常。"""
    head = (title or "").strip()
    first_sentence = re.split(r"[。！？\n]", (summary or "").strip(), maxsplit=1)[0]
    return bool(_CLARIFICATION_RE.search(head) or _CLARIFICATION_RE.search(first_sentence))


def _eval_t1_dividend(
    security_type: str,
    dividend_info: Mapping[str, Any] | None,
) -> TriggeredRule | None:
    """T1：股利異常變動檢核（季配／半年配採 YoY 同期或 TTM 合計；ETF 與虧損股排除）。"""
    if security_type == "etf" or not dividend_info:
        return None
    if dividend_info.get("loss_no_dividend"):
        return None
    if not dividend_info.get("has_current_announcement"):
        return None

    prev_total = dividend_info.get("prev_total_dividend")
    curr_total = dividend_info.get("current_total_dividend")
    evidence_ids = list(dividend_info.get("evidence_ids") or ["fact_div_1"])

    if dividend_info.get("suspended"):
        return TriggeredRule(
            rule_id="T1_DIVIDEND_CHANGE",
            severity="REVIEW",
            evidence_ids=evidence_ids,
            reason="當期公告停止配發股利，建議人工優先覆核盈餘與配息政策。",
        )

    if prev_total is None or curr_total is None or prev_total <= 0:
        return None

    change_ratio = (curr_total - prev_total) / prev_total
    if change_ratio <= -0.20:
        return TriggeredRule(
            rule_id="T1_DIVIDEND_CHANGE",
            severity="REVIEW",
            evidence_ids=evidence_ids,
            reason=f"公告總股利較去年同期或前期合計減少 {abs(change_ratio) * 100:.1f}%（達 ≥20% 門檻）。",
        )
    if abs(change_ratio) <= 1e-6:
        return TriggeredRule(
            rule_id="T1_DIVIDEND_CHANGE",
            severity="WARN",
            evidence_ids=evidence_ids,
            reason="當期股利金額與前期同期持平，標記 WARN 供確認配息週期（非基本面惡化）。",
        )
    return None


def _eval_t2_profit(
    security_type: str,
    profit_info: Mapping[str, Any] | None,
) -> TriggeredRule | None:
    """T2：獲利轉虧／毛利營益率連降檢核（金融股排除營益率、改採單季淨利 YoY；ETF 排除）。"""
    if security_type == "etf" or not profit_info:
        return None
    evidence_ids = list(profit_info.get("evidence_ids") or ["fact_eps_1"])

    curr_eps = profit_info.get("current_eps")
    prev_eps = profit_info.get("prev_year_eps")
    if prev_eps is not None and curr_eps is not None and prev_eps > 0 and curr_eps < 0:
        return TriggeredRule(
            rule_id="T2_COVERAGE_OR_PROFIT_DROP",
            severity="REVIEW",
            evidence_ids=evidence_ids,
            reason=f"單季 EPS 由前期 {prev_eps:g} 元轉虧為 {curr_eps:g} 元（差額 {curr_eps - prev_eps:g} 元）。",
        )

    if security_type == "financial":
        ni_curr = profit_info.get("net_income_current")
        ni_prev = profit_info.get("net_income_prev_year")
        if ni_prev is not None and ni_curr is not None and ni_prev > 0:
            yoy = (ni_curr - ni_prev) / ni_prev
            if yoy <= -0.25:
                return TriggeredRule(
                    rule_id="T2_COVERAGE_OR_PROFIT_DROP",
                    severity="WARN",
                    evidence_ids=evidence_ids,
                    reason=f"金融股單季稅後淨利年減 {abs(yoy) * 100:.1f}%（達 ≥25% 警示門檻）。",
                )
        return None

    # 非金融／非 ETF：檢查毛利率或營業利益率是否連 2 季下滑且累計降幅 >= 3.0pp
    for key, label in (("gross_margins", "毛利率"), ("operating_margins", "營業利益率")):
        series = list(profit_info.get(key) or [])
        if len(series) >= 3:
            q0, q1, q2 = series[-3], series[-2], series[-1]
            if q1 < q0 and q2 < q1 and (q0 - q2) >= 3.0:
                return TriggeredRule(
                    rule_id="T2_COVERAGE_OR_PROFIT_DROP",
                    severity="WARN",
                    evidence_ids=evidence_ids,
                    reason=f"{label}連續 2 季下滑（累計降幅 {q0 - q2:.2f} 個百分點 ≥ 3pp）。",
                )
    return None


def _eval_t3_stress(
    security_type: str,
    stress_info: Mapping[str, Any] | None,
) -> TriggeredRule | None:
    """T3：還原股價 20 日回撤或信用／償債壓力檢核（金融股排除負債比率指標；無負債不除零）。"""
    if not stress_info:
        return None
    evidence_ids = list(stress_info.get("evidence_ids") or ["fact_risk_1"])

    if security_type != "financial":
        icr = stress_info.get("interest_coverage_ratio")
        interest_expense = stress_info.get("interest_expense")
        net_debt_change_pp = stress_info.get("net_debt_ratio_change_pp")
        # 利息費用為 0 或負值代表無有息負債壓力，略過利息保障倍數
        if (
            (interest_expense is None or interest_expense > 0)
            and icr is not None
            and icr < 2.0
            and net_debt_change_pp is not None
            and net_debt_change_pp >= 10.0
        ):
            return TriggeredRule(
                rule_id="T3_CREDIT_OR_VOLATILITY_STRESS",
                severity="REVIEW",
                evidence_ids=evidence_ids,
                reason=f"非金融股利息保障倍數降至 {icr:.2f}x（<2.0x）且淨負債比上升 {net_debt_change_pp:.1f}pp。",
            )

    mdd_20d_pct = stress_info.get("adjusted_mdd_20d_pct")
    if mdd_20d_pct is not None and mdd_20d_pct >= 18.0:
        return TriggeredRule(
            rule_id="T3_CREDIT_OR_VOLATILITY_STRESS",
            severity="WARN",
            evidence_ids=evidence_ids,
            reason=f"還原股價近 20 個交易日最大回撤達 {mdd_20d_pct:.1f}%（≥18% 警示線）。",
        )
    return None


def _eval_t4_governance(events: Sequence[Mapping[str, Any]]) -> TriggeredRule | None:
    """T4：MOPS 治理與交易異動重大事件檢核（含澄清媒體報導降級過濾）。"""
    matched_titles: list[str] = []
    evidence_ids: list[str] = []
    for ev in events:
        title = str(ev.get("title") or "")
        summary = str(ev.get("summary") or "")
        if _is_clarification_notice(title, summary):
            continue
        text = f"{title} {summary}"
        if ev.get("governance_flag") or any(kw in text for kw in _T4_GOVERNANCE_KEYWORDS):
            matched_titles.append(title or "治理/交易重大公告")
            if ev.get("evidence_id"):
                evidence_ids.append(str(ev["evidence_id"]))

    if not matched_titles:
        return None
    return TriggeredRule(
        rule_id="T4_MOPS_GOVERNANCE_EVENT",
        severity="REVIEW",
        evidence_ids=evidence_ids or ["evt_mops_1"],
        reason=f"偵測到重大治理或交易管制公告：{matched_titles[0][:60]}。",
    )


def _eval_t5_revenue(
    security_type: str,
    revenue_info: Mapping[str, Any] | None,
) -> TriggeredRule | None:
    """T5：結構性營收衰退與展望下修檢核（1–2 月採累計 YoY 防農曆年錯月；ETF 排除）。"""
    if security_type == "etf" or not revenue_info:
        return None
    evidence_ids = list(revenue_info.get("evidence_ids") or ["fact_rev_1"])

    if revenue_info.get("guidance_downgraded"):
        return TriggeredRule(
            rule_id="T5_STRUCTURAL_REVENUE_DECLINE",
            severity="REVIEW",
            evidence_ids=evidence_ids,
            reason="公司法說會或正式公告下修全年營收／毛利率展望。",
        )

    monthly_records = list(revenue_info.get("monthly_records") or [])
    effective_yoys: list[float] = []
    for rec in monthly_records:
        month = int(rec.get("month") or 0)
        if month in (1, 2):
            # 1–2 月必須採「1–2 月累計營收 YoY」，防農曆年天數與假期錯位誤判
            yoy_val = rec.get("cumulative_yoy_pct")
        else:
            yoy_val = rec.get("yoy_pct")
        if yoy_val is not None:
            effective_yoys.append(float(yoy_val))

    if len(effective_yoys) >= 3 and all(val <= -10.0 for val in effective_yoys[-3:]):
        return TriggeredRule(
            rule_id="T5_STRUCTURAL_REVENUE_DECLINE",
            severity="WARN",
            evidence_ids=evidence_ids,
            reason="排除農曆年 1–2 月錯月效應後，仍連續 3 期月營收 YoY ≤ -10%。",
        )
    return None


def evaluate_deterministic_review(
    *,
    security_type: str,
    dividend_info: Mapping[str, Any] | None = None,
    profit_info: Mapping[str, Any] | None = None,
    stress_info: Mapping[str, Any] | None = None,
    events: Sequence[Mapping[str, Any]] = (),
    revenue_info: Mapping[str, Any] | None = None,
) -> DeterministicReview:
    """執行 T1–T5 全套確定性異常覆核，回傳合併後之 DeterministicReview。"""
    triggered: list[TriggeredRule] = []
    for candidate in (
        _eval_t1_dividend(security_type, dividend_info),
        _eval_t2_profit(security_type, profit_info),
        _eval_t3_stress(security_type, stress_info),
        _eval_t4_governance(events),
        _eval_t5_revenue(security_type, revenue_info),
    ):
        if candidate is not None:
            triggered.append(candidate)

    final_status = "OK"
    for rule in triggered:
        if _severity_rank(rule.severity) > _severity_rank(final_status):
            final_status = rule.severity

    return DeterministicReview(
        review_status=final_status,  # type: ignore[arg-type]
        triggered_rules=triggered,
    )
