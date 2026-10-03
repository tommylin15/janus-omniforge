# Janus — TODO

版本：3.1
用途：**只保留確定要做的工作**。不確定、暫不做、純 observation、Production 才需要、已接受缺口與研究構想一律不放 active TODO；統一保存在 [`parking-lot.md`](parking-lot.md)，且不計入目前專案未完成度。

## 規則：只有「做／不做」

- 在本文件：**做**。代表 Janus 已確認最後需要完成，必須有明確 implementation／acceptance，依順序執行。
- 不在本文件而在 [`parking-lot.md`](parking-lot.md)：**不做**。保留資料供未來翻找，但不得自行開工，也不得把它當成目前欠著沒做。
- 已接受的 source-level missing、coverage threshold 內缺值、自然 observation 沒有新 evidence，都不建立 TODO checkbox。
- Active WBS 可以因外部核准或 runtime evidence 暫時呈 `partial`／`blocked`；這是執行狀態，不是第三種工作分類。
- 完成證據與歷史 checkpoint 移入 `archive/` 或 `spec/operations-and-testing.md`，不讓 TODO 永久累積歷史流水帳。

## 2026-10-03 Token-first 架構決策

**本次 active implementation 先讀：**

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

使用者已明確決定：

- 五 specialist production 主路徑改為 Python／SQL／ML；**不得再實作成每日 5 個生成式 LLM workers**。
- 約 500 檔只做便宜 market screening / discovery；完整 5 specialist 僅做 `active watchlist ∪ effective holdings`。
- Specialist inference event-driven / dirty dependency update；無 input change 就 reuse。
- 模型 retraining / calibration / reconciliation 第一版以月度為主，不代表 specialist data 每月才更新。
- 五 specialist 白話文預設以 structured outputs + SHAP/rules/templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 既有成果保留，改為 **授權使用者手動 On-demand CEO / rare escalation** runtime。
- User Stock Detail 讀保存的 CEO report；有權限帳號才可按「分析／重新分析」。重新分析建立新 immutable execution/report，不覆寫舊報告。
- Admin 需提供 DB-backed Google user capability（例如 `ceo_analysis.request`）、specialist/model/evaluation profile、CEO provider route、quota/cooldown 與 audit。
- 舊 `five-analyst-daily-operation-gate.md` 的「每日五 Codex workers」只作歷史規劃參考，不再是 active completion gate。

若舊 WBS／SPEC 文字仍與上述決策衝突，以本 TODO＋2026-10-03 decision 作**新需求**；但舊 implementation／runtime completion evidence 仍依 GitHub／runtime 如實保留，不能因文件更新假裝已完成重構。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。正式執行前，AI 先提醒建議模型與目標 WBS／工作組；使用者明確確認後開始。
- 一旦開始，以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面之間反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：partial。舊每日五角色已刪除，新確定性五分析師、去識別化覆蓋、不可變成果物與逐月 baseline evaluator 已實作；模型與真實 dev/OOS 整體驗收尚未完成。詳細限制見 [`spec/specialist-engines.md`](spec/specialist-engines.md)。使用者指定 1 CPU／1 GiB，失敗時先提出配置建議，不自行升級。500 檔缺失 ≤10% 可接受，超過先討論，不直接判失敗或建立複雜補資料。

- [ ] 依 [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md) 建立 500 檔低成本 market screening 與 Deep Coverage 五 specialist。
- [ ] Fundamental：deterministic financial features + LightGBM baseline；Valuation：deterministic DCF/reverse-DCF/relative valuation + LightGBM/CatBoost benchmark。
- [ ] Quant：Linear/LightGBM baseline + Qlib DoubleEnsemble challenger；以 Taiwan PIT walk-forward OOS 決定 champion，不照抄 upstream benchmark。
- [ ] Risk/Regime：Riskfolio-Lib + statsmodels/ML；Event：parser/rules + local multilingual Transformers classifier。
- [ ] 五 specialist 產出 structured artifact、SHAP/feature contribution、deterministic plain-language report；正常 path 0 LLM API token。
- [ ] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離 500 仍保留，清倉且不在 watchlist 才退出；500 screening 不自動升級 watchlist。
- [ ] 完成 PIT/provenance/missing-data/public-private isolation、tests、dev deployment、live data execution、artifact persist/readback 與 OOS benchmark acceptance。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [ ] 改成 dirty dependency graph：依 Core/PIT input hash、feature/engine/model version 只 invalidate 受影響 symbol/role。
- [ ] 新月營收／財報只更新受影響 Fundamental/Valuation；新 EOD price 更新 cheap valuation/Quant/Risk；新 event 只更新 Event；無變更直接 reuse。
- [ ] 每月 reconciliation 檢查 missed invalidation、orphan artifact、cache identity、model version；舊 artifact immutable。
- [ ] Specialist change 只標記 CEO report freshness/material delta，**不得自動觸發 CEO LLM**。

## 3. `WBS-5-MART-AI-PROVIDERS` — 【Sol】— **scope 變更；既有成果保留**

- [ ] 保留已完成的 Codex CLI／OpenRouter／Gemini adapter、routing、free/billing gate、auth/secret/fallback/audit 成果；停止把「每日五 Codex role workers」當 completion target。
- [ ] 將 effective runtime 收斂為 On-demand CEO / rare escalation provider path；default approved route 仍為 `Codex CLI → OpenRouter → Gemini`，只有 approved/authorized/free-or-explicitly-approved-paid profile 可執行。
- [ ] 完成 manual CEO request 的 headless dispatch、cold-start auth/續期、timeout/cancel/retry、route snapshot/version/hash、attempt/fallback/usage/cost audit、zero-secret-leakage。
- [ ] 不新增未核准付費 provider/model/resource；舊 bounded provider execution evidence 保留為歷史/runtime capability evidence，不冒充新 On-demand CEO acceptance。

## 4. `WBS-5-MART-CIO-SYNTHESIS` — 【Sol】— **產品語意改為 CEO Analysis**

- [ ] CEO 只讀最新 validated specialist outputs／Fact Pack／provenance；不得計算或覆寫 canonical numbers，無 publication authority。
- [ ] 只由有權限使用者明確 request 觸發，不由 Scheduler、每日行情或 specialist dirty event 自動觸發。
- [ ] 產出 thesis、cross-role conflict resolution、bull/base/bear、risks、invalidation conditions、unknowns；validator failure 保持 structured partial/blocked。
- [ ] 每次分析／重新分析建立新 immutable execution/report；symbol-level report 可重用，保存 requester/trigger 作 audit metadata。

## 5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] Analysis Profile 改為 specialist champion/model/version/evaluation + CEO provider/model/profile；保留 locked guardrail、version history、rollback、audit、test symbols/compare。
- [ ] 加入 DB-backed Google user capability 管理，例如 `ceo_analysis.request`；backend enforce，Flutter visibility 不可代替 authorization。
- [ ] Admin 顯示 CEO provider approval/auth/health、latest model list、quota/cooldown、usage/cost；不得接收或顯示 raw token。
- [ ] Provider global default `Codex CLI → OpenRouter → Gemini` 只適用 On-demand CEO/approved escalation，不再代表五 specialist daily route。

## 6. Admin operational convergence — 【Sol】

- [ ] **Actionable exceptions**：首頁「需要處理的事項」可 drill-down 至 item/reason/last update/retryability/safe action。
- [ ] **Job Control Center**：顯示 ingestion/master controller、500 screening、dirty specialist updates、monthly retrain/reconciliation、Private Pipeline、maintenance、On-demand CEO executions；latest state/last success/近 3 天 timeline/更早歷史/manual rerun/audit。
- [ ] **Storage／Private Operations**：Stage/Core/Mart/Private Mart live objects/active bytes、snapshot/manifest/report references、retention/maintenance/anomaly、Private Pipeline checkpoint/backlog/valuation lag；未知顯示 `unknown`。
- [ ] **Routing controls**：versioned reorder/audit/optimistic lock；CEO AI route 如上；行情 source route 依既有 contract，僅 approved/authorized source 可進 effective route。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；authenticated user + `ceo_analysis.request` capability + symbol/profile/in-flight/quota/cooldown 檢查。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、報告後的新資料/dirty roles、immutable history，以及有權限帳號的「分析／重新分析」按鈕。
- [ ] 【Sol】Performance profiling + fix、Quote Router＋persisted last quote、Transaction synchronous position projection、操作池/Broker Profile 依既有 committed contract 繼續完成。
- [ ] 【Luna】Journal／Watchlist／Stock Detail UX 與 Typed numeric formatter 依現有 Final Visual Contract 收斂，不另建重複 recommendation 頁。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

- [ ] 依 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md` 完成 Today／Watchlist／Ledger／Stock Detail 四頁 final presentation convergence。
- [ ] Stock Detail 的 specialist/CEO 能力遵守 2026-10-03 decision：persisted first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] 四張 final PNG binary、Flutter targeted／golden／screenshot regression 與 GCP dev 真實 authenticated browser acceptance 完整；sample/mock data 不得進 canonical runtime。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance；文件勾選、commit、build、upstream GitHub benchmark 或單次 bounded success本身都不等於完成。

歷史／決策入口：

- [2026-10-03 Token-first 五分析師與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 決策總結](decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)
- 其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。