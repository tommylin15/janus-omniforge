# Janus Current Status

更新：2026-10-07

用途：只回答「現在在哪裡、下一步是什麼、哪些尚未完成」。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 2026-10-06 A 組：CLOSED

A 組已完成 implementation、tests／CI、dev deployment、runtime readback 與使用者人工驗收。

- `b360b51`：Ledger 首屏改為核心 request + 分頁 lazy load／頁內 request cache；使用者確認載入速度可接受。
- `1987590`：Stock Detail 個人持股改讀 latest-price valuation；`stock-header` 提供 `previous_close/change/change_percent`；未實現損益／報酬與最近收盤漲跌採台股正值紅、負值綠。
- Ledger「紀錄」按月份／按個股可收合，群組摘要只顯示 authoritative 已實現損益；年度 selector 同區顯示年度已實現損益；append-only correction 保留。
- 最終功能／測試 SHA `c311d4b`；Flutter workflow `37473733955` 為 **64/64 tests PASS**；Deploy dev workflow `37473734282` success；Cloud Run revision `janus-api-gc311d4b7242a-config` Ready 且 100% traffic。
- 2026-10-06 使用者明確確認兩項人工 gate 均驗收無誤：①交易佇列／真實 owner mutation／duplicate guard／transaction refresh；②`c311d4b` User App 手機畫面 readback。
- 完整證據見 [latest-price／Ledger UI 驗收紀錄](archive/latest-price-ledger-ui-acceptance-2026-10-06.md)。
- 2026-10-07 結案後補強亦完成：交易異動後 immediate owner-scoped PnL recalculation、pending 時才顯示手動「重新計算損益」、關注搜尋按鈕語意、13:30／14:30 latest-price handoff、User PnL 紅綠與負號格式，以及 annual PnL latest-ledger-version stale fence。Flutter run `37542658237` 為 **66/66 PASS**；Portfolio contract `37542950801` 與 Deploy dev `37542951194` 均 success，API revision `janus-api-gafa3e8214bb1-config` 100% traffic。使用者已完成手機人工 UI 驗收並明確要求回寫後結案。

**A 組及本次結案後 UI／PnL 補強均正式 CLOSED；下一個 active group 為 B。**
## 2026-10-07 Owner-scoped parallel Private Mart 重算：CLOSED

交易新增／更正／REVERSAL 後的即時損益重算已從 User API request thread 移出，改為 PostgreSQL owner queue + 既有 `janus-private-pipeline` Cloud Run Job 的 queue mode：

- migration `048_private_recalculation_queue` 已在 dev 成功套用；Deploy dev run `37556657369` 的 `migrate-private-recalc / migrate` job `112585424355` 為 **success**。
- 同 owner 只允許一筆 `QUEUED/RUNNING/CANCEL_REQUESTED`；active 期間 ledger version 前進時只提升同一 request 的 requested version，舊版本算完會重新排隊直到追上最新 ledger。
- 不同 owner 可由 2–8 個 Cloud Run task worker 平行計算；Admin setting `private_recalc_workers` 預設 2、硬限制 2–8。既有 `janus-private-pipeline` Job resource 保持 default `taskCount=1`、`parallelism=8`，只有 owner queue execution 用 task override。
- shared Private Iceberg commit 以 advisory lock 序列化；full scheduled reconciliation 與 owner queue 共用同一 write fence，避免 shared-table commit 競態。
- User App 在 active 狀態 disable「重新計算損益」，顯示 queued/running/cancelled/failed；FAILED/CANCELLED 顯示 safe reason 並可重試。Flutter run `37553539023` 為 **69/69 PASS**，含 User duplicate-disable／failure-retry 與 Admin worker/control UI。
- Admin「資料治理」可看去識別化 owner ref、request、execution、worker task、attempt、running／queued；可調 2–8 workers、owner-scoped cooperative cancel、強制回寫 FAILED + User-visible reason。不得因此 kill shared execution 或暴露交易／持股／symbol relation。
- API / Private Pipeline deploy：run `37557807555` success；Cloud Run API revision `janus-api-ga4e9660efbe7-config` Ready 且 **100% traffic**，immutable image `sha256:1cfa56a6b4aad5b695f17341820e9542ad4eef4cc2349892d0ff6a221734f507`；User/Admin Flutter workspace / PWA build readback 亦與該 SHA 一致。
- bounded live canary：workflow `Private recalculation live acceptance #37568678701` **PASS**。seed execution `janus-ingestion-core-ht6tf`、2-task queue execution `janus-private-pipeline-6ktlc`、DB verify execution `janus-ingestion-core-hkq7x` 均成功；驗證 `execution_tasks=2`、persistent `default_tasks=1`、`max_parallelism=8`、same-owner active unique fence、request `SUCCEEDED`、attempt=1、worker task/execution binding、requested ledger version catch-up、queue idle 與 dispatch release。
- 真實 private readback：最新 trade ledger version = **164**；positions 與 2026 annual PnL 皆已追到 **ledger_version 164**，valuation date = `2026-10-06`。
- failure watchdog：dispatch 5 分鐘未 claim → `DISPATCH_TIMEOUT/FAILED`；worker 35 分鐘無 heartbeat → `FAILED/CANCELLED`。User 不再無期限停在「待更新」。
- 沒有新增 GCP resource；只為既有 `janus-user-api` 增加既有 `janus-private-pipeline` 的 resource-scoped `roles/run.invoker`，符合本次已核准功能範圍。

權威設計與 acceptance contract：[`decision-2026-10-07-owner-scoped-parallel-private-recalculation.md`](decision-2026-10-07-owner-scoped-parallel-private-recalculation.md)。

**2026-10-07 使用者已用真實 Admin Google 登入完成 Admin「資料治理」UI 人工 readback 並明確確認「通過」。因此 implementation／tests／CI／migration／deployment／2-task live runtime／authenticated Admin UI acceptance 均已有 evidence，本項正式 CLOSED。B 組 active 排序不變。**

## 2026-10-06 B 組優先架構決策（尚未實作完成）

使用者已核准 [Iceberg canonical + BigQuery analytics hybrid](decision-2026-10-06-bigquery-analytics-over-iceberg.md) 作為 B 組 specialist／cache 的優先資料運算架構：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；不改成 BigQuery native canonical warehouse。
- PostgreSQL serving projection 與 User／Admin request-time read 保持現行架構。
- BigQuery 只作 analytics compute；通過 fidelity gate 後優先承接每日盤後 liquid-500 screening、cross-sectional feature／ranking、OOS/evaluation preprocessing 與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；大量 training input 採 SQL 縮減後 export versioned GCS Parquet。
- B 組第一優先是抽出 exact-snapshot analytics reader、保留 PyIceberg reference/fallback，再做 BigQuery fidelity/cost/performance canary；未證明固定 Core snapshot 一致前不得切 default。
- Active cadence 已統一：每個交易日 EOD 做 500 檔低成本 screening；完整五 specialist 僅對 `active watchlist ∪ effective holdings` 依 dirty dependency 增量更新；retrain／calibration／OOS evaluation／reconciliation 的 target schedule 為每月第一個週六 10:30（Asia/Taipei）。
- **架構決策本身不代表 resource／IAM 授權。** B2 本輪的 dataset／connection／bucket-scoped IAM／固定 external tables 已另取得使用者明確授權並建立，詳見下方 B2 checkpoint；其他新增資源或權限仍依 PROJECT_RULES。

B 組架構決策不代表 specialist 已完成；A 組已於 2026-10-06 完成並結案，下一步進入 B 組。

### B0 Baseline — CLOSED（2026-10-07）

B0 已完成 implementation、deployment readback 與固定真實 dev Core snapshot 的 bounded baseline：

- baseline runtime code：`4dcb0309d9a8db525d8599e0c51d6b65bd856f45`；Deploy dev run `37488522467` 的 Mart tests／deploy／既有 smoke 成功。
- 第一次 baseline run `37490232648` 因 workflow 讀錯 Cloud Run Job env JSON path 而 fail closed；baseline workload 未執行。修正 commit `8b7fa5465f1516c00b63b2dad913f19d72a0dc18` 後再跑。
- 成功 baseline run `37490477263`、job `112361575980`、Cloud Run execution `janus-intelligence-mart-9bwkq`：固定 Core snapshot、輸入 **92,653 rows**、screening **500 symbols**、elapsed **725.726 s**、peak RSS **694.7 MiB**、LLM API tokens **0**。
- screening quality：EOD missing **1/500 = 0.2%**；5/20/60/120D history 均 missing **39/500 = 7.8%**，皆 accepted，`auto_fail=false`。
- `planned_scan_bytes` 與 `actual_gcs_read_bytes` 無可用量測，正式記為 `null`，不補成 0。
- B0 沒有建立／啟用 BigQuery／BigLake resource 或 API、沒有擴 IAM、沒有重做 A 組 migration／serving／UI。

完整證據見 [B0 baseline 結案證據](archive/group-b-b0-baseline-closure-2026-10-07.md)。B0 不需再重跑。

### B1 Exact-snapshot reader — CLOSED（2026-10-07）

`AnalyticsSnapshotReader`／`IcebergSnapshotReader` 已接入 specialist runtime；保留 PyIceberg reference 與相容入口，沒有修改 canonical write path。最新 targeted CI `37572291941` **105 PASS**；既有 dev Mart deployment／smoke 通過。

固定 B0 Core snapshot 的真實 dev execution `janus-intelligence-mart-9krkb` success：92,653 rows、500 screening 與 25 specialist artifact hashes 均與 B0 一致。OOS raw hash 不同，逐欄比對僅有最大 `2.84e-14` 的浮點尾差，全部 input hashes 與非數值內容一致。Elapsed 800.966 s、peak RSS 688.98 MiB、LLM tokens 0；不宣稱效能提升或五 specialist 整體完成。

完整證據見 [B1 reader 驗收](archive/group-b-b1-reader-acceptance-2026-10-07.md)。**B2 compatibility 已 CLOSED / PASS**；沿用 adapter CI 20 PASS、Mart regression 106 PASS、deployment/smoke 與 320-row fidelity。本次三張 shared catalog exact-snapshot mapping、native DECIMAL(20,4)/schema evolution、真實 ohlcv partition pruning 全 PASS：窄日期 42,678 bytes，寬日期 1,602,600 bytes；整輪 9 jobs 共 60 MiB billed bytes，immutable GCS evidence SHA256 readback PASS。本輪沒有修改 IAM 或 canonical data。

Live readback 修正舊暫停文件：`janus_core_dev` 已於 2026-10-07 15:02（Asia/Taipei）建立，本輪復用；catalog primary location 為 US，storage region 為 us-central1。使用本機既有 principal 的 register 權限，無需提升 automation identity。PyIceberg 保持 default，shared catalog adapter/workload canary、fallback、FinOps 與 default cutover 留在後續 scope。下一步 **B3 liquid-500 screening**。見 [B2 結案](archive/group-b-b2-closure-2026-10-07.md) 與 [runbook](runbook-bigquery-compatibility.md)。

## 現行產品決策

Janus 採 **Token-first 五 specialist + On-demand CEO**：

- 五 specialist production 主路徑使用 Python／SQL／ML，不是每日五個生成式 LLM workers。
- 約 500 檔每個交易日 EOD canonical data ready 後做低成本 market screening／discovery；不做 500×5 深度分析。
- 完整五 specialist 只做 `active watchlist ∪ effective holdings`，依 input change／dirty dependency incremental update；無變化 reuse。
- retrain／calibration／OOS evaluation／reconciliation 第一版固定每月第一個週六 10:30（Asia/Taipei）。
- specialist 白話文由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只保留給 authorized manual On-demand CEO／approved rare escalation。
- CEO report 是 immutable symbol-level research artifact；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 DB-backed capability（例如 `ceo_analysis.request`）、specialist model/evaluation、CEO provider/profile、quota/cooldown、usage/cost/audit。

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

被取代的每日五 LLM／CIO 規劃只留在 `archive/`／Git history，不再是 active completion gate。

## Admin 現行範圍

唯一 active Admin frontend 是 Flutter／PWA。主導覽目標：

- 總覽
- 批次
- 個股
- 市場資訊
- AI 分析
- 資料治理

Admin operational convergence 不重做整個 shell；`資料治理` 是正式目標名稱。詳細 contract：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

## 已存在、可重用的能力

- GCP `dev` 是個人真實 parallel-live environment。
- WBS-3 full-market base coverage／data supplement 已有 500 market coverage、12Q／12M、fixed Core snapshots、Fact Packs、daily incremental、Saturday quality evidence。
- PostgreSQL serving projection migration `042_stock_serving_projection` 已在 dev 完成；`ohlcv`／`valuation`／`events` 共 `78,079 / 78,079` eligible rows 已 materialize，public API 以 `publication.stock_serving_recent` 為 stock-detail hot path、Iceberg 為 fallback，且 live Cloud Logging 已驗證 `source=serving_projection`。完成證據見 [`archive/stock-serving-projection-042-completed-2026-10-04.md`](archive/stock-serving-projection-042-completed-2026-10-04.md)。
- 既有 provider adapters／routing／auth／free-billing gate／validator 的 bounded dev evidence 可重用於 CEO provider path，但**不代表** specialist-engine 或 On-demand CEO 已完成。
- User API 已有 Google OIDC owner boundary；Admin 有獨立 Google admin allowlist。
- Stock Detail 已有 persisted report、positions、notes、Kline/events、analysis feedback 等 read-path basis，可供後續 specialist／CEO integration。
- Flutter Admin shell、Overview／Batch、Stock Workbench 的既有 acceptance 保留；新的 operational convergence 仍在 TODO。
- legacy static Admin 已退役，不再是 parity／release gate。

## Active 執行順序

唯一權威排序見 [`todo.md`](todo.md)：

1. **A：CLOSED** — 操作體驗／效能／資料營運已於 2026-10-06 結案。
2. **B：ACTIVE — specialist／增量快取／BigQuery analytics** — 合併 `WBS-5-MART-SPECIALIST-ENGINES` 與 `WBS-5-MART-RERUN-CACHE`。
3. **C：CEO／權限／最終整合** — 合併 provider、CEO synthesis（原 CIO tracking ID）、Admin profile、User AI integration 與 Final Visual 剩餘 acceptance。

執行指令見 [`codex-execution-plan.md`](codex-execution-plan.md)。同組先整合程式再集中驗收，原 WBS acceptance 不取消。預警與通知由 Parking Lot 管理，另存 [`future-market-alerts.md`](future-market-alerts.md)，目前不執行。

042 serving projection 重用已有完成證據；公開資料清理依 operations 已有 apply/readback 只補剩餘項，041／compaction／retrain 核對最新證據。此次只是待辦整合，不宣稱任何未完成 capability 已完成。

## 模型／framework 方向

- Fundamental：deterministic financial features + LightGBM。
- Valuation：deterministic valuation + LightGBM／CatBoost benchmark。
- Quant：LightGBM baseline + Microsoft Qlib DoubleEnsemble challenger。
- Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- Event／Catalyst：parser／rules + Hugging Face Transformers multilingual local classifier。
- Explanation：SHAP／feature contribution + deterministic templates。

AutoGluon、FinBERT、FinGPT 只作 benchmark／research challenger；production champion 必須由 Janus Taiwan PIT walk-forward OOS evidence 決定。

## 尚未完成的關鍵 acceptance

- A 組已完成 implementation／CI／deployment／runtime build 與使用者人工驗收，狀態 CLOSED。
- 五 specialist 的完整真實 dev／OOS、完整 ML baseline、dirty dependency、每日 500 screening 與每月第一個週六 10:30 retrain／reconciliation 尚未完成整體驗收。
- On-demand CEO command／capability／immutable report history 尚未完成。
- Admin specialist model/evaluation + CEO capability/profile controls 尚未完成。
- User Stock Detail manual Analyze/Re-analyze + freshness/history 尚未完成。

因此目前不得宣稱 Token-first 五 specialist production 已完整完成或 manual CEO 已可用；A 組已結案，B 組以 active TODO／SPEC／WBS 與真實 dev evidence 繼續驗收。

## Evidence 讀取順序

1. GitHub `main` code／schema／migration／workflow／tests。
2. 最新 CI／deployment／live runtime／trigger／workload／integration evidence。
3. [`todo.md`](todo.md) 看 active acceptance。
4. Active SPEC／WBS／UI contract。
5. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 `archive/` 查歷史 evidence。

文件修改、commit、build、upstream benchmark 或單次 bounded success 都不代表功能完成。
