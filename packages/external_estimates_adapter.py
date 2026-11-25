"""統一外部市場／共識估算 API Adapter 與授權／口徑／last-success 防護。

任何外部 API 導入 AIAnalysisInput 前，必須通過：
1. JANUS_EXTERNAL_ESTIMATES_ENABLED 旗標檢查（預設關閉回傳 not_covered）。
2. llm_input_allowed == True 授權條款驗證（未授權者標 blocked_rights 禁止入 Prompt）。
3. basis 一致性檢查（禁止混用 adjusted 與 reported，違者標 blocked_basis）。
4. 失敗不覆蓋既有 last-success（遇 429/逾時/例外時安全回退 stale）。
"""
from __future__ import annotations

import os
from typing import Any, Callable, Mapping, Sequence

from packages.ai_insight_contracts import ExternalEstimateItem, ExternalEstimates


def is_external_estimates_enabled() -> bool:
    """讀取是否啟用外部預估 API Adapter（預設 false）。"""
    return os.getenv("JANUS_EXTERNAL_ESTIMATES_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _validate_and_build(raw_items: Sequence[Mapping[str, Any]]) -> ExternalEstimates:
    if not raw_items:
        return ExternalEstimates(status="not_covered", items=[])

    # 硬性檢查授權欄位：任何項目未明確允許進入 LLM，一律整包封鎖避免違約洩漏
    if any(item.get("llm_input_allowed") is not True for item in raw_items):
        return ExternalEstimates(status="blocked_rights", items=[])

    bases = {str(item.get("basis") or "unknown") for item in raw_items}
    if "adjusted" in bases and "reported" in bases:
        return ExternalEstimates(status="blocked_basis", items=[])

    validated_items = [ExternalEstimateItem.model_validate(item) for item in raw_items]
    return ExternalEstimates(status="available", items=validated_items)


def fetch_external_estimates_safe(
    symbol: str,
    *,
    fetcher: Callable[[str], Sequence[Mapping[str, Any]]] | None = None,
    last_success: ExternalEstimates | None = None,
    enabled: bool | None = None,
) -> ExternalEstimates:
    """安全擷取外部預估數據，遵守授權／口徑規範並保護 last-success 不被失敗覆蓋。"""
    use_external = is_external_estimates_enabled() if enabled is None else enabled
    if not use_external or fetcher is None:
        return ExternalEstimates(status="not_covered", items=[])

    try:
        raw_items = list(fetcher(symbol) or [])
        return _validate_and_build(raw_items)
    except Exception:
        # 發生 429、逾時或解析失敗時，絕不覆蓋既有合法之 last-success，僅降標為 stale
        if last_success is not None and last_success.items:
            return ExternalEstimates(status="stale", items=list(last_success.items))
        return ExternalEstimates(status="not_covered", items=[])
