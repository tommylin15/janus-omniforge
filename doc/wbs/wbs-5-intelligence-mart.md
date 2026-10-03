# Janus WBS 5 — Intelligence Mart

更新：2026-10-03
狀態：Active WBS index；執行順序以 `../todo.md` 為準

本文件只定義 WBS-5 的責任與驗收邊界。五 specialist 的現行實作契約見 [`wbs-5-specialist-engines.md`](wbs-5-specialist-engines.md) 與 [`../spec/specialist-engines.md`](../spec/specialist-engines.md)。舊「每日五個 Codex／LLM 分析師 + CIO」方案已被 2026-10-03 Token-first + On-demand CEO 決策取代，不再是 active WBS。

## 5.0 Runtime 與資料邊界

- `intelligence-mart` 只讀 `analysis_as_of` 可見的 versioned Core snapshot；不得即時補抓、呼叫 scraper 或改寫 Core。
- canonical data、PIT／future leakage、provenance、source authorization、missing-data honesty、immutable lineage、public/private isolation 與 publication boundary 必須維持。
- 每次 execution 保存 `execution_id`、`analysis_as_of`、Core snapshot identity、feature／engine／model version、input/output hash 與必要 governance version。
- PostgreSQL 只保存 catalog／control／publication／audit／bounded index；完整 feature、specialist artifact、evaluation、report 與大型 payload 存 GCS／Iceberg／Parquet。
- Mart 的已持久化成果可在 dev 真實使用；完成判定仍需 tests／deployment／live execution／readback evidence，不由文件或單次成功推定。

## 5.1 Coverage 與 Mart pipeline

### Market Coverage

約 500 檔只執行低成本 screening／discovery 與必要 cross-sectional Quant inference，不做 500×5 深度分析。

至少維持：

- `mart_screening_signals`
- `mart_market_regime_daily`
- `mart_sector_rotation_daily`
- `mart_topic_trends_daily`
- `mart_candidate_health`
- `mart_daily_brief`

這些資料集只能由已核准 Core／Mart inputs 產製；同一 Daily Brief 不得混用不同 `analysis_as_of` 的最新版拼裝。

### Deep Coverage

`active watchlist ∪ effective holdings` 去重後執行完整五 specialist。Watchlist 50 active distinct-symbol quota 保留；持股離開 500 仍保留 Deep Coverage，清倉且不在 watchlist 才退出後續更新。

Deep Coverage 既有／相容 Mart surface 可包含：

- `mart_core_alpha`
- `mart_risk_portfolio`
- `mart_alternative_sentiment`
- `mart_scoped_analysis`

相容 table name 不代表沿用舊每日 LLM role semantics；schema 演進須 additive／migration-safe，舊 immutable artifacts 不原地改寫。

## 5.2 五 specialist

Production 主路徑固定為：

1. Fundamental — deterministic financial features + LightGBM baseline。
2. Valuation — deterministic valuation + LightGBM／CatBoost benchmark。
3. Quant — LightGBM baseline + Qlib DoubleEnsemble challenger。
4. Risk／Regime — Riskfolio-Lib + statsmodels／ML。
5. Event／Catalyst — parser／rules + local multilingual classifier。

日常 specialist inference 不使用生成式 LLM。Plain-language report 由 structured outputs + SHAP／feature contribution／rules／templates 產生，正常 path 0 API token。

所有 specialist artifact 至少保存：

- symbol／coverage scope；
- `analysis_as_of`；
- Core／input snapshot or content hash；
- feature／engine／model version；
- structured metrics／score／probability（僅在該 specialist contract 有正式定義時）；
- positive／negative drivers；
- missing／stale／partial；
- contribution／explanation；
- output hash、computed_at、freshness；
- evidence／provenance references。

LLM 不得計算或改寫 canonical number，也不得持有 publication authority。

## 5.3 Dirty dependency／reuse

禁止固定每日將所有 Deep Coverage symbols × 5 全重算。

- monthly revenue／financials → Fundamental；必要時 Valuation。
- EOD price → cheap Valuation refresh、Quant、Risk。
- event → Event。
- input hash／feature／engine／model version 未變 → reuse。
- specialist artifact 更新只標記 CEO report freshness／material delta；不得自動觸發 CEO LLM。

`WBS-5-MART-RERUN-CACHE` 負責完成 dirty dependency graph、content-addressed reuse、incremental invalidation 與 monthly reconciliation。舊「單角色 LLM rerun → 自動 CIO」不再是 active dependency semantics。

## 5.4 Model evaluation／promotion

第一版 ML retrain／calibration／reconciliation 以月度為主；不代表 specialist data 每月才更新。

至少評估：

- Rank IC／ICIR／IC decay；
- top-decile future excess-return spread；
- hit rate；
- Brier／calibration；
- Sharpe／max drawdown／turnover／after-cost performance；
- regime stability。

任何 challenger 必須用 Janus Taiwan PIT walk-forward OOS evidence 決定 promotion；GitHub upstream benchmark、training success 或單次 dev run 都不能直接取得 champion authority。

## 5.5 On-demand CEO boundary

Codex CLI／OpenRouter／Gemini provider/runtime 不屬五 specialist 日常 production path，只保留給 authorized manual On-demand CEO／rare escalation。

CEO：

- 只讀最新 validated specialist outputs／Fact Pack／provenance；
- 只由具有 backend capability 的使用者明確 request；
- 不由 Scheduler、price、event 或 dirty update 自動觸發；
- 每次建立新的 immutable execution／report；
- validator failure 保持 structured partial／blocked；
- 不覆寫 canonical numbers、不擁有 publication authority。

`WBS-5-MART-AI-PROVIDERS` 目前責任是 On-demand CEO provider path 的 auth lifecycle、route snapshot、timeout／cancel／retry、fallback、usage／cost 與 zero-secret-leakage；不再驗收每日五 specialist LLM workers。

`WBS-5-MART-CIO-SYNTHESIS` 的產品語意已改為 **CEO Analysis**；舊 `CIO` 名稱只可出現在歷史 artifact／schema compatibility 或 archive，不作新的 UI／API／WBS 名稱。

## 5.6 Publication／governance

- specialist／CEO 只能使用可定位 evidence；future data、未授權來源、缺必要 publication time 的資料不得被默認成合格 evidence。
- `insufficient_data` 是 analysis outcome／reason，不是 publication lifecycle state。
- blocked／review-required／invalid 不得進 publishable public index。
- 只有 deterministic governance／publication gate 擁有發布決策權；specialist、CEO、Flutter 都不能自行發布。
- historical artifact immutable；重新計算或重新分析建立新 artifact／execution，不原地改寫。

## 5.7 Mart writer／storage

- GCS／Iceberg 保存 versioned feature、specialist、evaluation、aggregation／report artifacts 與完整 structured payload。
- PostgreSQL 保存 bounded metadata、snapshot／artifact reference、hash、version、publication／audit state。
- retention 依 `../spec/retention-governance.md`；有效引用、目前 snapshot 與 reference fence 必須先保護再清理。
- private holdings／cost／PnL／owner mapping 不得寫入 public Mart specialist artifacts；必要的 Deep Coverage membership 僅保存去識別化 symbol demand／effective scope。

## 5.8 Active WBS slices

目前執行順序只看 `../todo.md`。WBS-5 active slices 為：

| WBS | 現行責任 |
|---|---|
| `WBS-5-MART-SPECIALIST-ENGINES` | 500 screening + Deep Coverage 五 Python／SQL／ML specialist + PIT/OOS + immutable artifacts |
| `WBS-5-MART-RERUN-CACHE` | dirty dependency、reuse、incremental invalidation、monthly reconciliation |
| `WBS-5-MART-AI-PROVIDERS` | On-demand CEO／rare escalation provider runtime、auth、route、fallback、usage/cost |
| `WBS-5-MART-CIO-SYNTHESIS` | **CEO Analysis**：validated specialist inputs only、immutable report、no publication authority |

舊 `WBS-5-MART-AI-ROLE-CONTRACT`、每日五 provider worker、per-role LLM prompt routing 等若只剩歷史證據，應由 archive／operations 查閱，不再作 active execution target。

## 5.9 Acceptance

WBS-5 的相關 capability 宣稱完成時，至少需有與範圍相稱的：

- deterministic／PIT replay；
- source authorization／provenance／missing-data negative cases；
- public/private isolation；
- targeted tests／CI；
- dev deployment；
- 真實 data execution；
- immutable artifact persistence／readback；
- OOS／evaluation evidence（模型相關）；
- dirty dependency／reuse evidence（cache 相關）；
- provider auth／fallback／usage/cost／secret-redaction evidence（CEO provider 相關）。

任何 partial、單次 bounded success、credential probe、router existence 或文件完成都不得包裝成整體 WBS 完成。