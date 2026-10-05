# Janus — TODO

版本：3.5（2026-10-05：A 組真實驗收與 Ledger acceptance 補強）
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

# 執行順序：A → B → C

依使用者 2026-10-05 指示，先完成上班族操作體驗／效能／Admin，再整合原 specialist 與 CEO 工作。執行細節與可貼給 Codex 的指令見 [Codex 執行指令](codex-execution-plan.md)。以下三組是唯一執行順序；後面的 1～8 是原 WBS acceptance 索引，不再代表先後順序，也不重複計工。

| 工作組 | 範圍與原待辦對應 | 主要模型 | 集中驗收 |
|---|---|---|---|
| A：操作體驗／效能／資料營運 | §6 Admin；§7 非 CEO 功能；§8 非 AI 相依版型；下列新增補強 | Sol | 一組 API／Flutter／資料營運回歸與一輪 dev browser/readback |
| B：specialist／增量快取 | §1 specialist + §2 rerun cache；Admin 對應狀態接線 | Sol | 一組引擎／cache 測試與 bounded dev 執行／reuse／OOS readback |
| C：CEO／權限／最終整合 | §3 provider + §4 CEO + §5 Admin profile；§7 AI 整合；§8 剩餘驗收 | Sol | 一組端到端安全／UI 測試與最少已授權 provider live calls |

同組先完成相關程式、migration、UI、tests、文件再集中驗收，不逐檔／逐 API／逐股票獨立部署。失敗僅補跑受影響範圍；原 acceptance、必要安全檢查及真實 dev 證據保留。A 不因尚無 CEO 而延後基本 UI；§8 整體結案仍須所有條件成立。跨組連續執行須使用者明確指定全部組，依 PROJECT_RULES 的本次例外處理。

預警／推播／警訊 outcome 增補已移至 [Parking Lot](parking-lot.md) 與其獨立未來文件，不是本次 active scope；既有 Event specialist 與 OOS 照原契約。

## A 組新增／明確化 acceptance

A 組目前狀態定義：**部分功能已完成並進入 GCP dev 真實驗收，仍可能由真實驗收發現 implementation gap；發現後必須回到實作修正。** 進入驗收不等於 implementation 已全部完成，也不等於只剩 acceptance。

- [ ] **四頁 Final Visual Contract 是 A 組正式結案 gate。** Today／Watchlist／Ledger／Stock Detail 必須在既有 GCP dev 的真實登入、真實使用者、真實資料、真實 API/runtime 下，非 AI 主體 UI 明顯收斂至 [`ui/reference/user-app-final/`](ui/reference/user-app-final/)；至少核對 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout、390px 寬度版面，以及 loading／empty／error／partial／stale／missing 不破壞主要 layout。若真實畫面仍明顯像 legacy UI、與四張 reference 差異很大，視為 A 組 acceptance failure／implementation gap，不是後續 cosmetic polish。
- [ ] **A 組不得把基本 UI convergence 延後到 B／C。** Specialist outputs、CEO analysis、AI-dependent content、capability/history/freshness 與最終 AI integration 可由 B／C 完成；AI-only 區塊未就緒時可 bounded unavailable／hidden／partial，但不得因此保留舊版非 AI layout。
- [ ] **A 組完成不得由單一技術成功條件推定。** API 200、migration、auth、backend deploy、Flutter/widget tests、build 或 Cloud Run revision 更新都不能單獨使 A 組 `done`；四頁非 AI 主體 UI 尚未在真實 GCP dev 明顯收斂，狀態維持 `partial`。
- [ ] **真實驗收失敗必須形成工程閉環。** 對 UI、data state 或功能缺陷完成「定位 → 修正 → 測試 → commit/push → dev 部署 → 使用同一 GCP dev URL 重驗」；驗收失敗是 implementation 工作輸入，不只留報告或修正建議。
- [ ] 修正個股頁 build 內建立 request future／整頁 Future.wait／無效 retry；section-first、進階按需載入；已訪問頁保留狀態，隱藏／背景停止輪詢，owner 切換清除私人 cache。
- [ ] 關注股離榜保留並標示；GET 不 retirement write／隱藏離榜股；同步核對 DB function／trigger、quota、Deep Coverage 及所有 caller。
- [ ] 重用已完成 042 serving projection，驗證 freshness／分頁／fallback；依 profiling 改善剩餘 Iceberg scan/filter、摘要、lock、DB connection、驗證憑證 cache 與重複 user upsert，不建立第二套 canonical store。
- [ ] Quote Router／persisted last quote／Broker Profile 完成；041 transaction position projection 重用並補剩餘整合驗收，不重做已完成 migration／backfill。
- [ ] 四頁 UI／formatter／中文搜尋與 partial 白話狀態收斂；修復可追溯的 PNG reference，缺原始資產時只保留受影響 visual blocker。
- [ ] **Ledger YTD realized P&L。** 查明是否已完整實作本年已實現損益、canonical source（transaction／position projection／DB aggregate／serving layer）、交易後更新時點與 refresh 方式；當年度確定無已實現交易時依正式 contract 顯示 `0`，資料不足／尚待刷新時用 empty／unavailable／pending 的明確語意，不得以假 `0` 補值；有已實現交易時不得長期缺值或完全不顯示。此功能不依賴 AI，若不完整即為 A 組 gap。
- [ ] **Ledger Holdings／Records／Reports summary 同步。** 三個 subview 上方 holdings summary 必須共用同一 canonical position/holdings semantics 或可追溯至同一 canonical position state；不得因 tab 各自 state、provider/repository、cache、refresh、舊 endpoint、不同 position source 或 valuation/as-of 語意而顯示不同版本的舊 snapshot。若「持股」已有新資料而「紀錄／報表」仍舊，直接列 A 組 UI/data-state acceptance failure，不以「整個批次尚未跑」概括。
- [ ] **Ledger Reports refresh／aggregation chain。** 明確追查 report API、transaction source、position projection、report aggregation、DB table/view/materialized projection、可能的 batch/job、scheduler/trigger、cache TTL/invalidation、valuation date/as-of 與 transaction 入帳後更新鏈路；最後依 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。root cause 未查明前不得寫成「正常等待批次」。
- [ ] **Ledger／Holdings canonical consistency。** 同一使用者、同一時間、同一資產的 shares、cost、market value、unrealized PnL、realized PnL、YTD realized PnL、valuation date、as-of/data freshness、pending transaction／pending Private Mart 必須一致或有可追溯的時間／freshness 差異說明；不得在持股／紀錄／報表出現無說明的不同版本摘要。
- [ ] **交易異動後 refresh/invalidation acceptance。** 新增／修改／同步交易或 position projection 更新後，驗證 Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 都會刷新，舊 cache 不長時間殘留，valuation/as-of 可判斷是否更新。若採 batch，文件與 runtime evidence 必須指出 Job、Scheduler/trigger、頻率、source table、target projection、freshness SLA、failure 行為；若非 batch，同樣寫清真正更新鏈路。
- [ ] Admin 以 backend effective jobs 呈現，資料治理取代 placeholder；容量區分 live／noncurrent／soft-deleted，未知不補零；本人缺價／coverage 與 Admin 去識別化摘要分離。
- [ ] 依既定資料容忍度顯示上市 500 範圍、缺值、時間與非嚴格 PIT 限制，保留價格／單位／身份／來源／交易正確性；現有報酬涉及 corporate action 時明示不可比，不新增完整調整價平台。
- [ ] 完成前後效能紀錄、Job duration／peak RSS／retry／cache／storage／可取得的成本證據；暖機核心資訊 p95 ≤2 秒、已訪問頁恢復 ≤300ms 作驗收目標，記錄樣本與裝置，未達列剩餘瓶頸。
- [ ] 檢查 cleanup 成本與回收效益、有效 GCS retention 設定；避免空轉／重複執行，不自行改 retention 時限、提高付費資源或新增 IAM／服務。
- [ ] 對齊舊 coverage inventory、status、batch 清單與已完成／待驗證工作；沿用既有 042 完成證據，041／compaction／retrain 依最新 evidence 判定，不把程式存在當 live 完成。

> **A 組不是「部署完成後做驗收」，而是「在真實 GCP dev 驗收中持續發現並關閉 implementation gap」；Today、Watchlist、Ledger、Stock Detail 的非 AI 主體 UI 必須在真實登入與真實資料下明顯收斂至 Final Visual Contract，且 Holdings／Records／Reports 必須共用一致、可追溯且可刷新之 canonical position state，否則 A 組維持 partial。**

# 原 WBS acceptance（依上方工作組整合執行）

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

先核對 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 已記錄的公開資料清理 apply/readback 與最新 runtime；依 [`spec/retention-governance.md`](spec/retention-governance.md) 只補尚缺的整合／排程證據，不為舊待辦重跑已完成刪除。其他治理／成本收斂併 A；不以文件過期阻擋 B。

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
- [ ] 以 backend effective batches／occurrences 呈現 ingestion、data-supplement、mart、specialist-retrain、data-quality、private、core-cleanup、mart-cleanup 等實際定義；區分 definition／deployment／observed execution，不在 Flutter 固定批次数或假造尚不存在的 CEO job。
- [ ] **資料治理**：單一精簡頁顯示 Stage/Core/Mart/必要 Private 摘要、active retention、coverage/freshness/DQ、live objects/active bytes、maintenance、protected references 與 anomaly；Public retention 依 [`spec/retention-governance.md`](spec/retention-governance.md)，Private 無核准 contract 時顯示 `未定義/unknown`。
- [ ] 第一版不導入 OpenMetadata／DataHub／Airflow／Kestra／Prefect、第二套 scheduler/control plane、metadata catalog、lineage graph、大型 chart 或新 canonical store。
- [ ] `個股`、`市場資訊`、`AI 分析` 保留；routing controls 放對應功能的進階設定，不另建高複雜度主頁。
- [ ] 完成 targeted tests、Admin auth/audience negative tests、deployment、GCP dev 真實 batch/retention/storage telemetry 與 authenticated browser acceptance。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。
- [ ] 【Sol／A 組】完成 Performance profiling/fix、Quote Router + persisted last quote、Broker Profile；重用既有 Transaction synchronous position projection，僅補未滿足的 contract／readback／UI 驗收。
- [ ] 【Sol／A 組】Ledger 的 Holdings／Records／Reports 共用可追溯 canonical position/valuation state；完成 YTD realized P&L、report refresh/aggregation chain、transaction → position → Ledger refresh/invalidation 的 implementation 與真實 GCP dev acceptance，未查明 root cause 前維持 `unknown/partial`，不得用「等待批次」代替判定。
- [ ] 【Luna】Journal／Watchlist／Stock Detail UX 與 typed numeric formatter 依 Final Visual Contract 收斂，不另建重複 recommendation 頁。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

- [ ] 依 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md` 完成 Today／Watchlist／Ledger／Stock Detail 四頁 final presentation convergence。
- [ ] 【A 組 gate】即使 specialist／CEO 尚未完成，四頁非 AI 主體 layout 也必須先在真實 GCP dev、authenticated owner、persisted real data 下明顯收斂；AI-only 區塊用 bounded unavailable／hidden／partial，不得保留 legacy layout。
- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] 四張 final PNG binary、Flutter targeted／golden／screenshot regression 與 GCP dev 真實 authenticated browser acceptance 完整；sample/mock data 不進 canonical runtime。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success 本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](archive/decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。
