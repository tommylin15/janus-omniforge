"""Fundamental abstention: only uses known-month revenue features, NEVER future Y.
Research contract; publication_allowed=False. Actual PIT/ACTIVE validation is external.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

@dataclass(frozen=True)
class GateResult:
    decision: str
    reason_codes: tuple[str,...]
    analyst_note: str
    model_prediction_allowed_by_this_gate: bool
    publication_allowed: bool = False

def classify(prior_target_revenue: float | None,
             revenue_mean12m: float | None,
             current_yoy_m: float | None,
             thresholds: Mapping[str, float]) -> GateResult:
    """Use strictly available X; caller verifies publication times/source/revisions."""
    keys = ('base_twd_max', 'ratio_min', 'abs_known_yoy_min_pp')
    if any(k not in thresholds for k in keys):
        raise ValueError('MISSING_GATE_THRESHOLD')
    t = [float(thresholds[k]) for k in keys]
    if any(not isfinite(v) or v <= 0 for v in t):
        raise ValueError('INVALID_GATE_THRESHOLD')
    if any(v is None for v in (prior_target_revenue, revenue_mean12m, current_yoy_m)):
        return GateResult('DATA_UNVERIFIED', ('MISSING_REVENUE_FEATURE',),
                          '營收或基期資料不完整；請先核對來源和公告時點。', False)
    try:
        base, mean, yoy = map(float, (prior_target_revenue, revenue_mean12m, current_yoy_m))
    except (ValueError, TypeError):
        return GateResult('DATA_UNVERIFIED', ('NON_NUMERIC_REVENUE_FEATURE',),
                          '營收或成長率資料格式異常，暫不預測。', False)
    if not all(map(isfinite, (base, mean, yoy))):
        return GateResult('DATA_UNVERIFIED', ('NONFINITE_REVENUE_FEATURE',),
                          '資料含無效數值，暫不預測。', False)
    if base <= 0:
        return GateResult('ANALYST_ONLY', ('ZERO_OR_NEGATIVE_PRIOR_BASE',),
                          '去年對應月份營收基期為零或非正值，YoY 不具穩健可比性。', False)
    if mean < 0 or yoy < -100 - 1e-9:
        return GateResult('DATA_UNVERIFIED', ('INCONSISTENT_REVENUE_FEATURE',),
                          '營收欄位不一致，需核對原始來源。', False)
    why = []
    descriptions = []
    if base <= t[0]:
        why.append('TINY_PRIOR_YEAR_TARGET_REVENUE')
        descriptions.append('去年對應月份營收基期偏低')
    if mean / base >= t[1]:
        why.append('UNUSUAL_TRAILING_REVENUE_TO_BASE_RATIO')
        descriptions.append('近期營收相對去年基期放大')
    if abs(yoy) >= t[2]:
        why.append('EXTREME_KNOWN_CURRENT_YOY')
        descriptions.append('已公告月份 YoY 變動極端')
    if why:
        return GateResult('ANALYST_ONLY', tuple(why),
                          '、'.join(descriptions) + '；本期不提供模型數值，原因仍須核實。', False)
    return GateResult('MODEL_ELIGIBLE_BY_TAIL_GATE', (),
                      '未觸發極端規則；仍須通過 PIT、模型 ACTIVE 與資料檢核。', True)
