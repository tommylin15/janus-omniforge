# Janus Current Status

更新：2026-10-03

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 目前最重要的產品決策

2026-10-03 使用者已核准 **Token-first 五分析師 + On-demand CEO** 架構，詳見：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

新需求的核心是：

- 五 specialist production 主路徑使用 Python／SQL／ML，不再以 5 個每日生成式 LLM workers 為目標。
- 約 500 檔保留便宜 market screening/discovery；完整五 specialist 僅做 active watchlist + effective holdings。
- specialist 依 input change / dirty dependency incremental update，無變化 reuse；ML retrain/calibration/reconciliation 第一版月度。
- 五 specialist 白話文以 structured outputs + SHAP/rules/templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 既有 provider/router/validator/auth/free-gate 成果保留，但改為 authorized user 手動 On-demand CEO / rare escalation runtime。
- CEO report 保存成 immutable symbol-level research artifact；重新分析產生新 execution/report，不覆寫舊報告。
- Admin 需管理 DB-backed Google user capability（例如 `ceo_analysis.request`）；User Stock Detail 只有有權限帳號可按「分析／重新分析」。

**舊 `five-analyst-daily-operation-gate.md` 的「每日五 Codex workers」不再是 active completion gate，只保留歷史規劃參考。** 若舊 WBS／SPEC 尚未完全 convergence，以 active TODO + 2026-10-03 decision 作新需求；舊 implementation/runtime evidence 仍照實保留。

## 目前已存在、可重用的能力

- GCP `dev` 是 Janus 個人使用階段的真實 parallel-live environment。
- WBS-3 full-market base coverage 與 `WBS-3-DATA-SUPPLEMENT-V1` 已完成；500 檔資料網、12 季/12 月/行情補強、固定 Core snapshot、Fact Packs、每日增量與週六品質檢查已有既有 evidence。
- `WBS-5-MART-FACT-PACKS`、AI role contract、provider-neutral AI validation、mart.v1 additive compatibility 的既有完成歷史保持有效；不因新架構而回寫成未完成。
- Codex CLI 五角色 bounded GCP execution、provider routing、OpenRouter/Gemini free/billing probes、artifact lineage/validator 等既有成果保留為 provider/runtime capability evidence；它們**不等於新 specialist-engine 或 On-demand CEO 已完成**。
- User API 已有 Google OIDC owner boundary；Admin 有獨立 Google admin allowlist；Stock Detail 已有 persisted stock report、positions、notes、Kline/events、analysis feedback 等 read path，可作 CEO action/report integration 基礎。
- Flutter Admin shell、Overview/Batch、Stock Workbench 的舊 acceptance 保持；2026-10-02 新增的 operational convergence 尚在 active TODO。

## 目前執行順序

唯一權威排序見 [`todo.md`](todo.md)：

1. `WBS-5-MART-SPECIALIST-ENGINES` — 500 screening + Deep Coverage 5 Python/ML specialist + OOS champion/challenger + 0-token plain-language reports。
2. `WBS-5-MART-RERUN-CACHE` — dirty dependency graph、content-addressed reuse、incremental invalidation、monthly reconciliation。
3. `WBS-5-MART-AI-PROVIDERS` — scope 已改為 On-demand CEO / rare escalation provider runtime；保留 Codex CLI → OpenRouter → Gemini。
4. `WBS-5-MART-CIO-SYNTHESIS` — 產品語意改為 manual `CEO Analysis`，validated inputs only、immutable report、no publication authority。
5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — specialist model/evaluation + CEO route/profile + user capability/quota/cooldown。
6. Admin operational convergence。
7. User operational convergence — Stock Detail specialist/CEO/freshness/history/manual analyze integration，加上既有 quote/position/performance work。
8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE`。

## 模型／framework 方向

目前 approved production candidates：

- Fundamental：deterministic financial features + LightGBM。
- Valuation：deterministic valuation + LightGBM/CatBoost benchmark。
- Quant：LightGBM baseline + Microsoft Qlib DoubleEnsemble challenger。
- Risk/Regime：Riskfolio-Lib + statsmodels/ML。
- Event/Catalyst：parser/rules + Hugging Face Transformers multilingual local classifier。
- Explanation：SHAP/feature contribution + deterministic templates。

AutoGluon、FinBERT、FinGPT 可作 benchmark/research challenger，不直接取得 production authority。最終 champion 必須由 Janus Taiwan PIT walk-forward OOS evidence 決定，不能用 upstream benchmark 代替。

## 尚未完成的關鍵 acceptance

- 新五分析師確定性 adapters/contracts、覆蓋與 immutable persistence、逐月 baseline evaluator 已實作並通過 targeted tests；真實 dev／OOS、完整 ML baseline、dirty graph 與 monthly retrain/reconciliation 尚未完成整體驗收。舊每日五角色已刪除。
- On-demand CEO private command/capability/report history 尚未實作。
- Admin capability/model/evaluation controls 尚未實作。
- User Stock Detail 的 manual Analyze/Re-analyze + report freshness/history 尚未實作。
- 因此目前不得宣稱「五分析師已轉成 Python/ML production」、「CEO manual flow 已可用」或「新架構完成」。

## Evidence 讀取順序

需要判斷「是否完成」時依序看：

1. GitHub `main` code/schema/migration/workflow/tests。
2. 最新 CI/deployment/live runtime/trigger/workload/integration evidence。
3. [`todo.md`](todo.md) 看 active acceptance。
4. [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md) 看新分析架構。
5. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 `archive/` 查歷史 evidence。

文件修改、commit、build 或 upstream framework benchmark 本身都不代表功能已完成。