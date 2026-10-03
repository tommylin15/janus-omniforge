# Janus WBS 5 — Token-first Specialist Engines

更新：2026-10-03
狀態：Partial implementation；未完成整體 acceptance

本 WBS 受 [`../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md) 約束。若舊 WBS-5／SPEC 仍描述「每日五個 Codex/LLM 分析師」，以 active TODO 與上述決策作為新需求；舊 implementation/runtime evidence 仍照實保留，不能假裝已完成本重構。

## 1. 目標

把五個 specialist 的 production 主路徑改為 Python／SQL／ML，日常不使用生成式 LLM：

1. Fundamental — deterministic financial features + LightGBM。
2. Valuation — deterministic valuation + LightGBM/CatBoost。
3. Quant Forecast — LightGBM baseline + Qlib DoubleEnsemble challenger。
4. Risk / Regime — Riskfolio-Lib + statsmodels/ML regime model。
5. Event / Catalyst — parser/rules + local multilingual encoder classifier。

五分析師輸出必須 structured、PIT、可重放、可回測、可版本化；白話說明使用 SHAP/rules/template，正常情況 0 API token。

## 2. Universe

### Market Coverage

約 500 檔保留低成本 screening 與全市場 cross-sectional Quant inference，目的為 discovery，不作 500×5 深度分析。

### Deep Coverage

`active watchlist ∪ effective holdings`，去重後執行完整 specialist engines。Watchlist 既有 50 distinct-symbol quota 保留；持股離榜仍在 deep coverage，清倉且不在 watchlist 才退出後續更新。

## 3. Incremental execution

禁止固定每日把所有 deep-covered symbols × 5 全重算。

每個 artifact 保存 input snapshot/content hash、feature/engine/model version、output hash、computed_at、freshness。Core/PIT data 更新後只 invalidate 受影響 dependency：

- monthly revenue / financials -> Fundamental；必要時 Valuation。
- EOD price -> cheap Valuation refresh、Quant、Risk。
- event -> Event。
- 無 input change -> cache hit / reuse。

CEO 不被 upstream change 自動觸發；只標記 report freshness/material delta。

## 4. Model cadence

- Specialist inference：有 input change 才跑。
- ML retraining/challenger：第一版月度；Event classifier 依新 labeled data 或 drift 才 retrain。
- Monthly reconciliation：檢查 missed invalidation、artifact identity、model version、orphan cache。
- 任何新模型先 walk-forward OOS / PIT / leakage guard；training success 不代表 promotion。

## 5. Evaluation

至少：Rank IC、ICIR、IC decay、top-decile future excess-return spread、hit rate、Brier/calibration、Sharpe、max drawdown、turnover、after-cost performance、regime stability。

GitHub framework benchmark 不等於台股 production evidence；champion 由 Janus Taiwan PIT OOS 結果決定。

## 6. 白話報告

五 specialist 產出 deterministic plain-language report：

- structured metrics / probability / score；
- SHAP or feature contribution；
- positive/negative drivers；
- missing/stale/partial；
- what changed since previous artifact。

LLM 不參與 canonical number 計算。只有 material + uncertain Event document 或使用者明確要求 CEO synthesis 才進 approved LLM runtime。

## 7. GitHub framework policy

Production candidates：

- `microsoft/qlib`
- `dcajasn/Riskfolio-Lib`
- `huggingface/transformers`
- `shap/shap`

Benchmark/challenger：

- `autogluon/autogluon`
- `ProsusAI/finBERT`（benchmark only）
- `AI4Finance-Foundation/FinGPT`（research only）

引入前必須 pin version/license、走 dependency/security review；不直接 fork 整套產品架構進 Janus。

## 8. Acceptance

完成必須至少證明：

- 500 screening 不產生 LLM calls；
- Deep Coverage watch-only/held-only/overlap/held-off-market/exit 語意正確；
- 五 specialist 至少一個 production baseline 可在真實 dev PIT data 執行並持久化；
- dirty dependency graph 只重算受影響 role；no-change 可 audit reuse；
- 月度 retrain/reconciliation 可重跑；champion promotion 有 OOS evidence；
- specialist plain-language output 不依賴 LLM API；
- canonical number、PIT、provenance、missing-data honesty、public/private isolation 保持；
- tests、deployment、live dev execution / persisted artifact / readback evidence 齊全。

本 WBS 完成不等於 On-demand CEO 完成；CEO provider/runtime、capability、User/Admin UI 由後續 WBS 驗收。