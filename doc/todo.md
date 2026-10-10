# Janus — TODO

版本：3.23（2026-10-10：CI/CD 結案；B7 月度執行 PASS／cache freshness PARTIAL；B8 ACTIVE／B9 待執行）
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
- 約 500 檔在每個交易日 EOD canonical data ready 後做低成本 market screening／cross-sectional discovery；BigQuery 通過 fidelity gate 後優先承接這條全市場計算，不做 500×5 深度 specialist。
- 完整五 specialist 只做 `active watchlist ∪ effective holdings`，依 dirty dependency／input change 更新；無變更 reuse，不固定每日全重算。
- retraining／calibration／OOS evaluation／cache reconciliation 第一版固定 **每月第一個週六 10:30（Asia/Taipei）** 執行；不另設每週六 500×5 全量深算排程。
- plain-language output 由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只用於 authorized manual On-demand CEO／approved rare escalation。
- CEO report immutable；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 specialist model/evaluation、CEO provider/profile、DB-backed user capability、quota/cooldown、usage/cost/audit。

### Iceberg canonical + BigQuery analytics hybrid

權威文件：

- [`decision-2026-10-06-bigquery-analytics-over-iceberg.md`](decision-2026-10-06-bigquery-analytics-over-iceberg.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

目前 B 組資料／運算契約：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；BigQuery 不取代 canonical store。
- PostgreSQL serving projection 與 User／Admin request-time hot path 保持不變。
- BigQuery 只作 B 組 analytics compute；通過 cutover gate 後，優先承接 **每日盤後 liquid-500 screening**、cross-sectional features、OOS/evaluation 前處理與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；小結果走一般 query/result API，大型 training data 走 versioned GCS Parquet export artifact。
- 不預設複製整套 Core 到 BigQuery native storage；temporary/TTL derived data 可用但不可升格 canonical。
- 資料角色固定：Iceberg/GCS 保存 canonical/PIT/history；BigQuery intermediate 是可重建 compute；大型 training/evaluation dataset 以 versioned GCS Parquet 保存；model/evaluation/specialist 成果依 Mart contract 保存。BigQuery 中間結果不要求再回寫一份 Iceberg。
- 先抽出 exact-snapshot analytics reader，再做 BigQuery compatibility/canary；無法證明與固定 Core snapshot 一致時保留 PyIceberg path。
- 本架構方向已核准；若 implementation 需啟用新付費 API／建立 BigLake/Lakehouse/BigQuery 計費資源或擴大 IAM，仍需另有明確授權。

### Admin UI scope

權威文件：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

Admin operational convergence **不重做整個 Admin**。保留 `總覽 / 批次 / 個股 / 市場資訊 / AI 分析`，原 placeholder 收斂為 `資料治理`。第一版優先使用 Flutter Material，不導入第二套 metadata／orchestration control plane，也不要求大型 DAG／lineage graph／dashboard。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。
- 正式執行前依該項標示的【Sol】／【Luna】完成模型 gate；開始後以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序：A（CLOSED）→ B → C

依使用者 2026-10-05 指示，先完成上班族操作體驗／效能／Admin，再整合原 specialist 與 CEO 工作。執行細節與可貼給 Codex 的指令見 [Codex 執行指令](codex-execution-plan.md)。以下三組是唯一執行順序；後面的 1～8 是原 WBS acceptance 索引，不再代表先後順序，也不重複計工。

| 工作組 | 範圍與原待辦對應 | 主要模型 | 集中驗收 |
|---|---|---|---|
| A：操作體驗／效能／資料營運 | §6 Admin；§7 非 CEO 功能；§8 非 AI 相依版型；下列新增補強 | Sol | 一組 API／Flutter／資料營運回歸與一輪 dev browser/readback |
| B：specialist／增量快取／BigQuery analytics | §1 specialist + §2 rerun cache；BigQuery analytics hybrid；Admin 對應狀態接線 | Sol | 一組 reader/fidelity／引擎／cache 測試與 bounded dev 執行／reuse／OOS／FinOps readback |
| C：CEO／權限／最終整合 | §3 provider + §4 CEO + §5 Admin profile；§7 AI 整合；§8 剩餘驗收 | Sol | 一組端到端安全／UI 測試與最少已授權 provider live calls |

同組先完成相關程式、migration、UI、tests、文件再集中驗收，不逐檔／逐 API／逐股票獨立部署。失敗僅補跑受影響範圍；原 acceptance、必要安全檢查及真實 dev 證據保留。A 不因尚無 CEO 而延後基本 UI；§8 整體結案仍須所有條件成立。跨組連續執行須使用者明確指定全部組，依 PROJECT_RULES 的本次例外處理。

預警／推播／警訊 outcome 增補已移至 [Parking Lot](parking-lot.md) 與其獨立未來文件，不是本次 active scope；既有 Event specialist 與 OOS 照原契約。

## A 組結案

A 組 implementation／CI／dev runtime 與兩項人工 gate 已於 2026-10-06 全部驗收完成。完成證據已移至：

- [非佇列結案紀錄](archive/group-a-nonqueue-live-closure-2026-10-06.md)
- [latest-price／Ledger UI 驗收紀錄](archive/latest-price-ledger-ui-acceptance-2026-10-06.md)

A 組不再列 active TODO；下一個 active work 為 B 組。
## 2026-10-08 持股頁 UX／首屏加速（獨立於已結案 A 組及進行中的 B7）

- [ ] 「持股／紀錄／報表／筆記」固定頁首、四格只顯示持股、字體放大，台股漲紅跌綠。
- [ ] 官方昨收／當日每股漲跌／幅度與現持股價格變動有缺值、stale／日期與 owner-scoped guard；migration 050 真實驗收。
- [ ] 首屏不等待年度交易歷史、PnL、重算狀態；版本、報價日期與狀態一致；量測 API latency P50／P95。
- [ ] Flutter／Python targeted CI、dev deployment/migration、真實 User UI／Owner 一致性驗收。未通過維持 ACTIVE，不更動原 A 組 CLOSED 判定。

## B 組：下一個執行入口（B7 → B8 → B9）

**B0～B6 CLOSED／PASS，不重跑。** 歷史驗收只留 [B0](archive/group-b-b0-baseline-closure-2026-10-07.md)、[B1](archive/group-b-b1-reader-acceptance-2026-10-07.md)、[B2](archive/group-b-b2-closure-2026-10-07.md)、[B3](archive/group-b-b3-closure-2026-10-07.md)、[B4](archive/group-b-b4-deep-coverage-closure-2026-10-07.md)、[B5](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)、[B6](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)。B7～B9 是下一階段，未達 live acceptance 不標完成。執行方法見 [B 組指令](codex-execution-plan.md)。

- [x] **B7 月度執行機制（PASS）**：先核對 `main` 的 retrain／calibration／OOS／reconciliation 實作與最新 CI、真實 Scheduler／controller 設定。目標 effective cadence 為**每月第一個週六 10:30 Asia/Taipei**；Scheduler 可以是現役 hourly controller trigger，但必須證明 controller 的 monthly due gate、依賴 fence、一次性／可重跑 semantics、Job execution、immutable model/evaluation artifacts 與 cache reconcile **真實**成立。只看到 workflow SUCCESS、code gate 或 Scheduler 字串不算 B7 PASS；缺實際月度 execution 時標 `NOT_VERIFIED`，不捏造。只補必要的 deployment／readback。
- [ ] **B7 derived cache freshness（PARTIAL；於 B8／B9 銜接更新，不重訓）**：舊 `b7-monthly-live-20261008-v1` 在 #37712457638 沒有派送，不重送。新版 `b7-ghcr-monthly-20261010-v1` 綁定已核准 GHCR SHA `038498c70e12488f345c3ca0fbe821846ddee4cc`；[#38025890942](https://github.com/tommylin15/janus-omniforge/actions/runs/38025890942) digest／Scheduler PASS，[#38026093638](https://github.com/tommylin15/janus-omniforge/actions/runs/38026093638) controller PASS，request 已 disabled。Mart `janus-intelligence-mart-xrlk5` **Completed=True／1 succeeded**，[#38027085666](https://github.com/tommylin15/janus-omniforge/actions/runs/38027085666) OOS／monthly reconciliation GCS bytes SHA-256 PASS，25/25 active specialist refs 正確、6 reused、無 missed invalidation、無 CEO／promotion。**唯一保留的 B7 衍生快取缺口（不撤銷月度執行 PASS）**：reconciliation `status=partial`，現有 B6 ML/OOS derived manifest `status=historical`、Core source fence 與 2026-10-10 當次不相符；不覆寫歷史產物、不把 historical 當 current，需將既有衍生資料流程銜接最新 Core 並取得新的 current-source reconciliation evidence。B7 月度執行機制已 PASS；derived cache freshness 保持 PARTIAL，銜接 B8/B9 更新，不重新訓練。B8/B9 各自獨立驗收。
- [ ] **B8（ACTIVE／PARTIAL）ML/OOS 已定案採用 PyIceberg 預設、BigQuery 選用／Typed fallback**：B8 500 screening 同源比對 [#38029803051 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051)、ML/OOS SQL／Parquet 同等工作量 [#38033560821](https://github.com/tommylin15/janus-omniforge/actions/runs/38033560821) **PASS**（10,978 rows、0 differences，BQ 2 輪 40 MiB billed）。使用者選定 Screening／Specialist／一般讀取永久維持 PyIceberg 預設，BigQuery 僅明確 opt-in 的 ML/OOS SQL／Parquet 路徑；無 BQ cutover。新增 `jobs/intelligence-mart/intelligence_mart/ml_oos_backend_policy.py` 並由 [synthetic outage + real fixed Core readback #38036167787](https://github.com/tommylin15/janus-omniforge/actions/runs/38036167787) **PASS**（19 tests；BQ 故障注入後 PyIceberg 真實掃 74,999 source rows→10,978 ML/OOS，0 differences；PIT/fidelity errors fail closed、無 data write／cache promotion）。**待結案：** typed fallback policy 尚未接線至舊 `scripts/gcp/b5-ml-oos-data.py` 的正式 materialization／已部署 Cloud Run Mart 服務；需用與當次 Core 相符的 immutable derived cache／現役 GHCR dev 工作負載完成整合驗收，不能因測試注入成功宣稱 live BQ outage 或已部署 fallback。B7 derived cache freshness 仍歷史，不為此重訓；B9 模型品質仍 NOT VERIFIED。參見 [B8 checkpoint](archive/group-b-b8-partial-checkpoint-2026-10-10.md)。
- [ ] **B9（B8 後）五 Specialist／OOS 整合驗收**：模型品質證據必須使用與當次 Core source fence、PIT、source authorization 相容的資料；不以 B7 historical cache 或 B8 舊 snapshot 直接代替。完成 Fundamental／Valuation／Quant／Risk-Regime／Event 的 deterministic／ML、Taiwan PIT walk-forward OOS、calibration／champion evidence、structured + plain-language artifacts、incremental reuse／provenance／source authorization／public-private isolation；正常 path 不呼叫生成式 LLM，不以模型訓練成功代替 live publication gate。
- [ ] **B 組跨階段安全底線**：PostgreSQL serving 與 A 組已驗證 read path 不回歸；BigQuery failure audit/fallback 不修改 canonical Iceberg；不使用 BigQuery Storage Read API；不自動呼叫 CEO；維持現有 1 CPU／1 GiB Mart 限制。新付費 API／資源、IAM 擴權或 catalog migration 需另取得授權，未授權部分單獨 `BLOCKED`，其餘可行項繼續。

# 原 WBS acceptance（依上方工作組整合執行）

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

先核對 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 已記錄的公開資料清理 apply/readback 與最新 runtime；依 [`spec/retention-governance.md`](spec/retention-governance.md) 只補尚缺的整合／排程證據，不為舊待辦重跑已完成刪除。其他治理／成本收斂併 A；不以文件過期阻擋 B。

- [x] 約 500 檔**每日盤後**低成本 market screening 已由 B3 CLOSED；Deep Coverage universe／selective execution／no-change reuse 已由 B4 CLOSED。兩者未混成 500×5 全量深算。
- [ ] Fundamental：deterministic financial features + LightGBM baseline。
- [ ] Valuation：deterministic DCF／reverse-DCF／relative valuation + LightGBM／CatBoost benchmark。
- [ ] Quant：LightGBM baseline + Qlib DoubleEnsemble challenger；以 Taiwan PIT walk-forward OOS 決定 champion。
- [ ] Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- [ ] Event／Catalyst：parser／rules + local multilingual Transformers classifier。
- [ ] 五 specialist 產出 structured artifact、SHAP／feature contribution、deterministic plain-language report；正常 path 0 LLM API token。
- [x] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離開 500 仍保留，清倉且不在 watchlist 才退出。B4 live acceptance 已驗 5 symbols × 5 roles。
- [ ] 完成 PIT／provenance／missing-data／public-private isolation、tests、dev deployment、live execution、artifact persist/readback 與 OOS benchmark acceptance。

目前 500 檔缺失 ≤10% 為使用者接受範圍；超過先討論，不直接判整體失敗或自行擴張補資料。Mart 資源維持使用者指定 1 CPU／1 GiB；需要提高時先提出 evidence，不自行升級。

使用者最新核准：歷史財報有資料就做 OOS，不再要求原始數值版次／當時公開時間已證明。採最新官方數值版本、優先官方公開／上傳時間，缺少時明示期末後 90 天假設；正式模型作法及結果標示見 specialist SPEC。價格標籤成熟與來源／品質／隔離檢查保留。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [x] 建立 dirty dependency graph：依 accepted/rejected PIT dependency state、feature/engine/model version 只 invalidate 受影響 symbol/specialist；B4 已有 regression + live evidence。
- [x] monthly revenue／financials、EOD price、event 依 specialist dependency mapping 選擇性 invalidation；event-only regression 已驗 1 computed / 4 reused。
- [x] 無 input change 直接 reuse，保留可稽核 cache identity；B4 live 第二輪 0 computed / 25 reused。
- [ ] 每月第一個週六 10:30（Asia/Taipei）執行 retrain／calibration／OOS evaluation／reconciliation，檢查 missed invalidation、orphan artifact、cache identity、model version。
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

## 6. Admin operational convergence — 已完成 A 組範圍

已移入 [A 組結案證據](archive/group-a-nonqueue-live-closure-2026-10-06.md)；B／C 的模型與 CEO 接線保留於其對應待辦。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。

非 AI Journal／Watchlist／Stock Detail UX、typed formatter 與四頁 390px browser gate 已完成 A 組驗證；交易驗收交接見上文。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

四頁非 AI presentation／PNG references／Flutter regression／authenticated dev browser 已完成 A 組驗證；本 WBS 整體仍保留 B／C 的 AI 整合驗收。

- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] specialist／CEO 接線後再驗四頁 AI-dependent state；不得把 A 組非 AI 結案當作此 WBS 全部完成。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success 本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](archive/decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。
