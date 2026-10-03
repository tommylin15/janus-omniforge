# Janus — TODO

版本：3.3
用途：**只保留確定要做的 active work 與未完成 acceptance**。Deferred、Candidate、Observation、Production-only、已接受缺口與研究構想統一放 [`parking-lot.md`](parking-lot.md)；已完成／被取代內容放 `archive/`。

## 規則

- 在本文件：**做**。必須有 implementation／acceptance，依下列順序執行。
- 不在本文件而在 `parking-lot.md`：目前**不做**，不得自行開工或計入未完成度。
- active work 可因外部核准或 runtime evidence 呈 `partial`／`blocked`；partial 不等於完成。
- 完成證據移至 `archive/` 或 `spec/operations-and-testing.md`，TODO 不保存歷史流水帳。

## 現行架構決策

### Token-first specialists + On-demand CEO

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)

目前產品契約：

- 五 specialist production 主路徑為 Python／SQL／ML，正常 path 不使用生成式 LLM。
- 約 500 檔只做低成本 market screening／discovery；完整五 specialist 只做 `active watchlist ∪ effective holdings`。
- specialist 依 dirty dependency／input change 更新；無變更 reuse。
- retraining／calibration／reconciliation 第一版月度。
- plain-language output 由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只用於 authorized manual On-demand CEO／approved rare escalation。
- CEO report immutable；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 specialist model/evaluation、CEO provider/profile、DB-backed user capability、quota/cooldown、usage/cost/audit。

### Admin UI scope

權威文件：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

Admin operational convergence **不重做整個 Admin**。保留 `總覽 / 批次 / 個股 / 市場資訊 / AI 分析`，原 placeholder 收斂為 `資料治理`。第一版優先使用 Flutter Material，不導入第二套 metadata／orchestration control plane，也不要求大型 DAG／lineage graph／dashboard。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。
- 正式執行前依該項標示的【Sol】／【Luna】完成模型 gate；開始後以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

優先依 [`spec/retention-governance.md`](spec/retention-governance.md) 完成公開資料刪除治理批次的整合、deployment 與 dev 驗收，再繼續 specialist 整體 acceptance。既有治理程式／targeted tests 不等於 live cleanup 已完成。

- [ ] 完成約 500 檔低成本 market screening 與 Deep Coverage 五 specialist。
- [ ] Fundamental：deterministic financial features + LightGBM baseline。
- [ ] Valuation：deterministic DCF／reverse-DCF／relative valuation + LightGBM／CatBoost benchmark。
- [ ] Quant：LightGBM baseline + Qlib DoubleEnsemble challenger；以 Taiwan PIT walk-forward OOS 決定 champion。
- [ ] Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- [ ] Event／Catalyst：parser／rules + local multilingual Transformers classifier。
- [ ] 五 specialist 產出 structured artifact、SHAP／feature contribution、deterministic plain-language report；正常 path 0 LLM API token。
- [ ] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離開 500 仍保留，清倉且不在 watchlist 才退出。
- [ ] 完成 PIT／provenance／missing-data／public-private isolation、tests、dev deployment、live execution、artifact persist/readback 與 OOS benchmark acceptance。

目前 500 檔缺失 ≤10% 為使用者接受範圍；超過先討論，不直接判整體失敗或自行擴張補資料。Mart 資源維持使用者指定 1 CPU／1 GiB；需要提高時先提出 evidence，不自行升級。

使用者最新核准：歷史財報有資料就做 OOS，不再要求原始數值版次／當時公開時間已證明。採最新官方數值版本、優先官方公開／上傳時間，缺少時明示期末後 90 天假設；正式模型作法及結果標示見 specialist SPEC。價格標籤成熟與來源／品質／隔離檢查保留。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [ ] 建立 dirty dependency graph：依 Core/PIT input hash、feature/engine/model version 只 invalidate 受影響 symbol/specialist。
- [ ] monthly revenue／financials 只更新受影響 Fundamental／Valuation；EOD price 更新 cheap Valuation／Quant／Risk；event 只更新 Event。
- [ ] 無 input change 直接 reuse，保留可稽核 cache identity。
- [ ] 每月 reconciliation 檢查 missed invalidation、orphan artifact、cache identity、model version。
- [ ] specialist change 只標記 CEO report freshness／material delta，**不得自動觸發 CEO LLM**。

## 3. `WBS-5-MART-AI-PROVIDERS` — 【Sol】

有效產品範圍只有 On-demand CEO／approved rare escalation provider runtime。

- [ ] 重用既有 Codex CLI／OpenRouter／Gemini adapter、routing、auth、free/billing gate、fallback/audit 能力。
- [ ] default approved route 為 `Codex CLI → OpenRouter → Gemini`；只有 approved／authorized／free-or-explicitly-approved-paid profile 可執行。
- [ ] 完成 manual CEO request 的 headless dispatch、cold-start auth／續期、timeout／cancel／retry、route snapshot/version/hash、attempt/fallback、usage/cost audit、zero-secret-leakage。
- [ ] 不新增未核准付費 provider／model／resource。

## 4. `WBS-5-MART-CIO-SYNTHESIS`（legacy tracking ID）— CEO Analysis — 【Sol】

產品名稱與語意一律使用 **CEO Analysis**；上述舊 ID 只為既有 WBS／artifact traceability 保留。

- [ ] CEO 只讀最新 validated specialist outputs／Fact Pack／provenance；不得計算或覆寫 canonical numbers，無 publication authority。
- [ ] 只由具 capability 的使用者明確 request；Scheduler、行情或 specialist dirty event 不自動觸發。
- [ ] 產出 thesis、cross-specialist conflict resolution、bull/base/bear、risks、invalidation conditions、unknowns；validator failure 保持 structured partial／blocked。
- [ ] 每次分析／重新分析建立新 immutable execution/report；保存 requester／trigger audit metadata。

## 5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] 管 specialist champion／model／version／evaluation 與 CEO provider／model／profile；保留 immutable version history、rollback、audit、test symbols／compare。
- [ ] 加入 DB-backed Google user capability 管理，例如 `ceo_analysis.request`；backend enforce，Flutter visibility 不可代替 authorization。
- [ ] Admin 顯示 CEO provider approval／auth／health、model list、quota/cooldown、usage/cost；不得接收或顯示 raw token。
- [ ] `Codex CLI → OpenRouter → Gemini` 只適用 On-demand CEO／approved escalation。

## 6. Admin operational convergence — 【Sol】

只精簡強化既有 Flutter Admin，不重做 shell、不取消既有功能。UI contract 見 [`ui/admin.md`](ui/admin.md)。

- [ ] **總覽**：維持 actionable-exceptions-first；只補今日批次、最近 DQ、storage/retention anomaly 與需要處理項目。
- [ ] **批次**：用簡單表格／清單讀 backend effective jobs／occurrences；顯示 schedule/trigger、latest state、duration/last update、latest success；預設最近 3 天並保留 bounded older history；只提供 `查看`、安全 `重試`／`手動執行`。
- [ ] 現行 controller 七個固定批次為 `ingestion`、`data-supplement`、`mart`、`data-quality`、`private`、`core-cleanup`、`mart-cleanup`；未來 specialist／retrain／CEO execution 只有 runtime 真正存在後才顯示。
- [ ] **資料治理**：單一精簡頁顯示 Stage/Core/Mart/必要 Private 摘要、active retention、coverage/freshness/DQ、live objects/active bytes、maintenance、protected references 與 anomaly；Public retention 依 [`spec/retention-governance.md`](spec/retention-governance.md)，Private 無核准 contract 時顯示 `未定義/unknown`。
- [ ] 第一版不導入 OpenMetadata／DataHub／Airflow／Kestra／Prefect、第二套 scheduler/control plane、metadata catalog、lineage graph、大型 chart 或新 canonical store。
- [ ] `個股`、`市場資訊`、`AI 分析` 保留；routing controls 放對應功能的進階設定，不另建高複雜度主頁。
- [ ] 完成 targeted tests、Admin auth/audience negative tests、deployment、GCP dev 真實 batch/retention/storage telemetry 與 authenticated browser acceptance。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。
- [ ] 【Sol】完成 Performance profiling/fix、Quote Router + persisted last quote、Transaction synchronous position projection、Broker Profile 既定 contract。
- [ ] 【Luna】Journal／Watchlist／Stock Detail UX 與 typed numeric formatter 依 Final Visual Contract 收斂，不另建重複 recommendation 頁。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

- [ ] 依 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md` 完成 Today／Watchlist／Ledger／Stock Detail 四頁 final presentation convergence。
- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] 四張 final PNG binary、Flutter targeted／golden／screenshot regression 與 GCP dev 真實 authenticated browser acceptance 完整；sample/mock data 不進 canonical runtime。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](archive/decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。
