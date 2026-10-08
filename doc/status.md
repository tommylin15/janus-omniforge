# Janus CI/CD GHCR cutover — 2026-10-08 進度（PARTIAL）

- **Actions／GHCR 發布 PASS：** [#37769572546](https://github.com/tommylin15/janus-omniforge/actions/runs/37769572546)，來源 SHA `0b93d99d42aaff662a3408d749d70aa9d04b1042`，Python **623 PASS / 2 deselected**、Flutter analyze／test／Web build PASS；四個 image build／push＋GHCR 匿名 digest readback PASS。另有五個已刪除的 legacy Web module 測試明確 ignore，不將它們包裝成 PASS。
- **Cloud Run API 0% 候選 PASS：** [#37771247779](https://github.com/tommylin15/janus-omniforge/actions/runs/37771247779)。現有 `janus-api` 新 Revision `janus-api-00446-luq` 已由 GitHub Actions 的固定 GHCR digest 部署，0% 正式流量；health、unauthenticated guard、Flutter SHA identity PASS。原 100% 仍為 `janus-api-g53d655ccb108-config`，尚未 promote。
- **GHCR Jobs／Scheduler 唯讀盤點 PASS，完整執行防護未完成：** [#37774702422](https://github.com/tommylin15/janus-omniforge/actions/runs/37774702422)：四個 GHCR digest verified public；五個現役 Job 最近各 20 筆 execution 檢查 `potentiallyActive=0`、映像仍是 AR。`us-central1` 全部 Scheduler readback 只有 `janus-ingestion-daily`：`ENABLED`、`30 * * * *`、`Asia/Taipei`、觸發 `janus-batch-controller:run`、retryCount=1；每小時 :30 會執行真實 workload。舊 `inspect-dev-runtime.yml` 假設四個 private Scheduler 存在，與此 region live 不符；不要直接建立或刪除排程。需另完成 pause/resume 權限、真正 active execution/mutex、回滾策略後才能切 Jobs。
- **OAuth／MCP 未登入安全邊界 PASS：**[#37773049093](https://github.com/tommylin15/janus-omniforge/actions/runs/37773049093) 於 GHCR 0% API candidate 驗證 OAuth metadata 200、Profile／Positions／PnL／績效與 Admin 私有端點全部 HTTP 401、MCP private tool 拒絕未授權並回 Bearer challenge；尚非真實 owner authenticated acceptance。
- **Scheduler WIF viewer 授權後 readback 已 PASS：** Cloud Shell 使用者已新增 `roles/cloudscheduler.viewer`；[#37774488086](https://github.com/tommylin15/janus-omniforge/actions/runs/37774488086) 證實 `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com` 的 jobs list／known describe／locations 全部可讀，Scheduler API ENABLED。專案 IAM policy 讀取仍 IAM_DENIED，但不阻擋 Scheduler viewer。詳細[授權後實測](archive/cicd-scheduler-post-grant-2026-10-08.md)。
- **Jobs 正式切換保護已實作，實際仍 BLOCKED：**[`inspect-dev-runtime` 真實 Scheduler 驗收 #37776046528](https://github.com/tommylin15/janus-omniforge/actions/runs/37776046528) PASS，已依 10/02 controller consolidation 修正原本要求四個退役 private schedulers 的錯誤測試；[GHCR Job guard #37777330780](https://github.com/tommylin15/janus-omniforge/actions/runs/37777330780) 的 guard-tests **19 PASS**，live-readback 因安全 gate 對未驗證項目以 **exit 78 / BLOCKED** 結束、`resource_writes=0`。原有五個 AR rollback image digest 均能 readback；掃描 201/243/216/91/24 筆 executions，`janus-private-pipeline` 有 9 筆 9 月舊 execution（`startTime=null`、`completionTime=null`、`runningCount=0`、`Completed=False`），不是正在運行的證據、也不是已完成。每小時 controller 在這輪另有 1 筆暫無終態；Scheduler 仍 ENABLED，跨 release mutex／owner auth／rollback rehearsal 仍未 PASS。**不能改 Jobs、升正式流量或停用舊 Trigger。** 詳見[正式 guard readback](archive/ghcr-jobs-safety-gate-2026-10-08.md)。
- **Jobs image-only dry-run 四項及回滾順序已實作、實際仍 BLOCKED：**[GitHub Actions #37778770806](https://github.com/tommylin15/janus-omniforge/actions/runs/37778770806) 在既有 guard＋image plan **28 tests PASS**，產出 4 個 pinned digest mappings／倒序 rollback，research Job 不動、`resource_writes=0`。實際 GCP readback 同時依設計 exit 78，尚有 5 個 blockers：Scheduler ENABLED、9 筆 Private Pipeline 歷史未終態、durable mutex、候選正式 owner authenticated acceptance、rollback drill。GCP 已有 `janusWebSchedulerOperator` 自訂角色可 pause／enable，但**其對 `janus-ci` 的 IAM binding 尚未驗證**，不視為已具權限。已連接 Janus Read-only MCP 的既有 owner annual-pnl／performance 可回覆 `available`，但這**不等於 GHCR 候選 Revision 的 OAuth／PnL parity PASS**。詳見 [reversible image plan](archive/ghcr-jobs-image-rollback-plan-2026-10-08.md)。
- **Scheduler 實際暫停／恢復及事後 readback PASS：**[#37780249969](https://github.com/tommylin15/janus-omniforge/actions/runs/37780249969) 先經 26 項 guard/contract tests PASS，後以 WIF `janus-ci` 對現役唯一排程執行 3 秒 `pause → PAUSED → resume → ENABLED`，並自動清除 GitHub drill lease；獨立 recovery job SUCCESS。[#37780525220](https://github.com/tommylin15/janus-omniforge/actions/runs/37780525220) 再次驗證 Scheduler `ENABLED`、台北每小時 `:30`、原 controller target 不變。僅證明 Scheduler 操作與 drill 恢復能力，**不等於 Cloud Run Jobs rollout 的 durable cross-system mutex、owner acceptance 或 rollback PASS**。詳見[驗收紀錄](archive/ghcr-scheduler-operator-drill-2026-10-08.md)。
- **2026-10-08 Private Pipeline 9 筆歷史未終態重新稽核：**[GitHub Actions #37787678921](https://github.com/tommylin15/janus-omniforge/actions/runs/37787678921) SUCCESS（修正先前 [#37787473813](https://github.com/tommylin15/janus-omniforge/actions/runs/37787473813) 的 jq `records=null` 問題）：92 筆 execution 全頁讀回，其中 9 筆逐一 describe `READABLE`，全部 `start_time=null`、`completion_time=null`、`running_count=0`、`Completed=False`；`resource_writes=0`。這證明**沒有已觀察到的執行活動**，但**不等於 9 筆已到 terminal state**；Job promotion fence 必須繼續 BLOCKED，不能自動取消、略過或重送。
- **GitHub Git-ref global deployment lease primitive live drill PASS（尚未跨系統接管發布）：**[#37796079169](https://github.com/tommylin15/janus-omniforge/actions/runs/37796079169) 在 GitHub 真實執行 **12 tests PASS**、原子建立 annotated tag lease／不同 run 身分搶鎖與解鎖拒絕／owner readback 及 release／獨立恢復三個 Job 均 SUCCESS。修正後 `inspect` 已將 GitHub ref 權限錯誤與 404 缺鎖分開，未知狀態 fail-closed；執行後獨立 GitHub ref readback 為 404、無殘留，`gcp_writes=0`。現有 **legacy Cloud Build、`deploy-dev.yml`、GHCR Candidate 等部署入口尚未全部取得同一 lease**，Git tag 演練不保證 GCP 跨系統互斥；真實 rollback/snapshot、owner authenticated E2E、9 筆歷史未終態仍 BLOCKED，**不可 promote／改 Job／刪舊資產**。GitHub-only drill 不取代實際 Release recovery acceptance。
- **GitHub GHCR API 0% 候選已真實接入部署鎖並成功驗收：**[Actions #37799529212](https://github.com/tommylin15/janus-omniforge/actions/runs/37799529212) SUCCESS；workflow 29 tests PASS，Git ref `janus-ghcr-deploy-global-v1` 依序 `CLAIMED→OWNED→SAFE_TO_RELEASE→RELEASED`，額外 GitHub ref readback 404；Cloud Run `janus-api` 原現役 `janus-api-g53d655ccb108-config` **100% 不變**，GHCR 0% candidate 真實部署／health／未登入 401／SHA identity gate PASS。Guard 在鎖內讀回現役流量與候選 digest、Ready、observedGeneration；未確認仍封鎖釋放。此為**API candidate + lock live acceptance**，並非 Google OAuth／owner PnL／MCP、Jobs／Scheduler 終態、100% promotion／rollback 已完成。後續 [CI #37799911001](https://github.com/tommylin15/janus-omniforge/actions/runs/37799911001) 30 tests PASS，`ghcr-candidate-dev.yml` 與 legacy `deploy-dev.yml` 已共用 GitHub Actions `janus-dev-runtime-writers` 序列化群組；**獨立 Cloud Build Trigger 與其他未接入 writer 不受此保護**。本輪未動正式 traffic、Jobs、備份或 GCS／AR。
- **未完成：**真正的 owner Google OAuth／MCP／PnL authenticated candidate acceptance、Jobs／Scheduler fence 與配置 rollback、Service 100% traffic promotion／rollback E2E、release mutex／state durability、10 Revision live retention、舊 Trigger 停用與 GCS／AR 清理。以上尚未執行，不得視為 CLOSED。
- **仍保留：**Janus `janus-dev-v2` Cloud Build Trigger、所有現役 AR digests、所有 GCS Buckets、PostgreSQL／GCS 備份、Iceberg 與應用資料。詳細 [GHCR acceptance evidence](archive/cicd-ghcr-acceptance-2026-10-08.md)／[五類清理 inventory](archive/cicd-cutover-cleanup-inventory-2026-10-08.md)。

---

# Janus Current Status

更新：2026-10-08

用途：只回答「現在在哪裡、下一步是什麼、哪些尚未完成」。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 2026-10-08 持股頁體驗與速度：ACTIVE

- 新需求：官方漲跌金額／幅度、持股每日價格變動、較大紅綠資訊、頁首次導覽、摘要只留持股，正確性優先。
- backend `53d655c`（正式昨收批次讀取／日漲跌）、Flutter `11ee66f`（頁首次導覽／卡片與非必要資料延後）、ACL migration wiring `6a5569c`、PostgreSQL DB-only 首屏快照 `b1f95ac` 均已提交。Flutter CI [#37713531543](https://github.com/tommylin15/janus-omniforge/actions/runs/37713531543) **SUCCESS**，Portfolio contract CI [#37713531544](https://github.com/tommylin15/janus-omniforge/actions/runs/37713531544) **SUCCESS**，migration CI [#37713115868](https://github.com/tommylin15/janus-omniforge/actions/runs/37713115868) **SUCCESS**（靜態／fixture，不代表 live）。完整 API targeted、migration 050 dev、最新 SHA deployment／runtime／User 手機驗收仍 **pending／unknown**，不得宣稱已可人工驗收。
- 使用既有 PostgreSQL operational/current quote projections 與 Private Mart，不增加另一份沒有明確失效規則的正式快照表。此次不影響 B7 進度，原 A 組保留 CLOSED。
- 完整追蹤見 [todo.md](todo.md)。

## 2026-10-08 B7 月度批次：ACTIVE（驗收中）

- 真實手動 acceptance 使用 request ID `b7-monthly-live-20261008-v1`，在 controller dispatch 之前必須驗證 Mart dev image 指向 `fb07979a...`（嚴格 SHA）；未命中則 bounded wait 後 **fail-closed**，不得用舊 Mart 映像結案。

- [獨立 Scheduler/Job readback #37711998105](https://github.com/tommylin15/janus-omniforge/actions/runs/37711998105)：第一次 execution **FAIL / blocked**，原因是既有 GitHub `janus-ci` 無 `cloudscheduler.jobs.get`，不能直接驗證 scheduler 設定。未擴張 IAM；後續 readback 需顯示 `unknown` 而非假裝 PASS，並繼續利用現有 Cloud Run job inspect 權限驗證部署。

- [實作 `6a2e76c`](https://github.com/tommylin15/janus-omniforge/commit/6a2e76c2916e72366c39abc27ff345508e283a11)：controller 從錯誤的每月 1 日改為每月第一個週六台北 10:30。沿用既有每小時 :30 Scheduler；當日 07:30 ingestion／08:30 data-supplement 成功才派送。
- 舊排程 pending 以 `schedule_superseded/skipped` 安全處理；manual 重跑仍建立獨立 occurrence。
- Mart 月度 reconciliation immutable receipt 驗證全 Deep Coverage 五 role cache pointer／source hash／model identity、盤點 B6 ML/OOS Parquet；歷史 candidate 不直接視為 orphan，缺少或舊 Core 證據維持 `partial`，不刪除、不 promotion、不觸發 CEO。
- CI：初版 [#37711002505](https://github.com/tommylin15/janus-omniforge/actions/runs/37711002505) SUCCESS，151 ingestion / 137 Mart PASS，ingestion/controller 與 Mart dev deploy + smoke PASS；修正版 [#37711737194](https://github.com/tommylin15/janus-omniforge/actions/runs/37711737194) 143 Mart tests PASS，最新 Mart deployment 尚需結案證據。
- [readback #37712126960](https://github.com/tommylin15/janus-omniforge/actions/runs/37712126960) 記錄 controller image=ingestion image TRUE、Mart Ready TRUE；Scheduler schedule/timeZone/state NULL (IAM blocked)，不算 runtime_config full PASS。
- 仍需最新 Mart image/live、真實 retrain + OOS/calibration/reconciliation immutable artifact readback；Scheduler 直接 readback 需受權 `cloudscheduler.jobs.get` 或其它可稽核替代證據。自然下一個首週六為 **2026-11-07 10:30（Asia/Taipei）**，人工執行不可冒充已觀察自然排程。

## 2026-10-07 `janus-batch-controller` Error：CLOSED

- 根因是 controller 合法寫入 `status=skipped`（mobile queue empty／market holiday），但 migration 037 的 `control.batch_occurrences` CHECK constraint 未允許 `skipped`，active execution 因 PostgreSQL `CheckViolation` 連續失敗。
- migration `049_batch_occurrence_skipped_status` 已將 status contract 擴充為 `pending / dispatching / running / ambiguous / succeeded / failed / skipped`；未新增 GCP resource、未擴 IAM、未刪 canonical data。
- Deploy dev `37600433659` success；`test-api`、`test-ingestion`、`migrate-batch-occurrence-status / migrate` job `112725144699` 均 success。
- Scheduler execution `janus-batch-controller-cmdfr` 與手動 bounded active execution `janus-batch-controller-l5nkf` 均 succeeded；active acceptance workflow `37601633532` success。
- 完整根因與 runtime evidence 見 [batch controller skipped-status repair](archive/batch-controller-skipped-status-repair-2026-10-07.md)。

**本次 controller Error 已修復並有 scheduler + active runtime evidence；B 組進度不因本次 incident 改變。**

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

Live readback 修正舊暫停文件：`janus_core_dev` 已於 2026-10-07 15:02（Asia/Taipei）建立，本輪復用；catalog primary location 為 US，storage region 為 us-central1。使用本機既有 principal 的 register 權限，無需提升 automation identity。PyIceberg 保持 default，shared catalog adapter/workload canary、fallback、FinOps 與 default cutover 留在後續 scope。見 [B2 結案](archive/group-b-b2-closure-2026-10-07.md) 與 [runbook](runbook-bigquery-compatibility.md)。

### B3 Daily liquid-500 screening — CLOSED / PASS（2026-10-07）

B3 已完成 targeted tests、dev deployment、fixed-snapshot PyIceberg／BigQuery deterministic canary、兩次 Cloud Run reuse acceptance 與 batch-controller 真實 occurrence readback。第二次 fixed-snapshot execution 為 `reused=true`、`artifact_growth_bytes=0`、500 symbols、0 specialist、0 LLM token、CEO 未觸發；BigQuery 不切 default，PyIceberg 維持預設 reader。

Controller recovery workflow `37628720592` **SUCCESS**；真實 occurrence `market-screening/2026-10-07/16` 為 `succeeded`，實際 Mart execution `janus-intelligence-mart-7f8jl`，dependencies 為 `ingestion/2026-10-07/14` 與 `data-supplement/2026-10-07/08`。完整 evidence 見 [B3 結案](archive/group-b-b3-closure-2026-10-07.md)。

**B3 正式 CLOSED。**

### B4 Deep Coverage specialists — CLOSED / PASS（2026-10-07）

B4 已完成 Deep Coverage universe、dependency-selective execution、immutable cache/reuse、targeted tests、Mart deployment/verify 與真實 Cloud Run acceptance。

- universe 僅為 `active watchlist ∪ effective holdings`；不把 B3 liquid-500 screening 混入。
- cache identity 納入 symbol/role、accepted + rejected PIT dependency state、feature/engine/model version；只有 dirty specialist 重算，其他 role reuse immutable artifact。
- 修正版 Deploy dev workflow `37634230788`：Mart targeted tests **116 PASS**，`deploy-mart` 與 `Verify intelligence-mart` 均 success。
- live acceptance workflow `37636276994` **SUCCESS**，確認 deployed runtime SHA `752e551110cc67e18403b2ce2f00774f5b2a0c7f`。
- 同一 Core snapshot hash `sha256:c81b476dfa9a2bade3e82c806f2f9bdfb04c5f97947265c08b0b44807955aac9` 連跑兩次：第一次 25 specialist = 25 computed / 0 reused；第二次 = **0 computed / 25 reused**。
- 第一次 elapsed 92.954 s、peak RSS 413.53 MiB；第二次 56.506 s、269.33 MiB；兩次皆 `screening_count=0`、`llm_api_tokens=0`。
- target artifact `private_fields_exposed=false`，manifest/target immutable readback PASS；rejected future/quality evidence 也會造成相應 role invalidation，不會誤 reuse。

完整 evidence 見 [B4 結案](archive/group-b-b4-deep-coverage-closure-2026-10-07.md)。

**B4～B6 CLOSED / PASS；B7 已啟動、驗收中，未 CLOSED。B8 效能／成本／fallback 與 B9 模型 OOS 品質依序後續執行；PyIceberg 維持 default。**

### B8 待辦：BigQuery vs PyIceberg 效能決策 — PARTIAL（B7 完成後執行）

- B5 data path 與 B6 zero-query reuse 已 CLOSED，但**不等於** BigQuery 在相同 workload 比 PyIceberg 有效益。2026-10-08 使用者確定維持 **B7 → B8 → B9**，B8 一次集中完成效能比較、成本／FinOps 與 fallback 驗收；B7 不以比較提前完成為前置條件。
- [B3 fixed-snapshot canary evidence](archive/group-b-b3-live-acceptance-2026-10-07.json)：B3 固定 snapshot 同一 screening 結果 `output_equal=true`；PyIceberg **30.2256 s**、BigQuery hybrid **36.0608 s**（慢約 **19.3%**）。此 canary 為單次觀測，BigQuery 只承接 benchmark/ohlcv、valuation 使用預先載入 PyIceberg rows（其讀取時間未計入 hybrid），未涵蓋公平的端到端相同負載與 RSS/GCS bytes。
- B3 BigQuery 兩個查詢合計 **20 MiB billed**（10 MiB 各一）；PyIceberg GCS read bytes 仍為 `null`，不能宣稱誰比較便宜。B5 首次 materialize 共 **30 MiB billed**，其中 export SQL script **5.84 s**；這是單段 SQL 執行時間，**不可與 B0/B1 的完整 Mart elapsed（725.726 / 800.966 s）相比**，也沒有相同 ML/OOS reduction 的 PyIceberg reference baseline。
- B8 必補可重跑 **同 fixed Core snapshot、同 symbol/date/feature/query/PIT/output** 的兩種 read + reduction/export 對照，區分 cold compute、warm cache、GCS payload readback；量測 elapsed、peak RSS、processed/billed bytes、Cloud Run/GCS bytes（可取得時），未知填 `null`。B8 同時驗證可稽核 fallback／FinOps，守住既有 1 GiB BQ execution budget／60 秒 query timeout／禁用 Storage Read API／不新增計費資源或權限。未完成比較前不做 BigQuery default cutover。

### B6 ML/OOS derived cache — CLOSED / PASS（2026-10-08）

- [B6 結案與 runtime evidence](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)：BigQuery-derived ML/OOS source-only identity、pre-query immutable verified reuse、dirty dependency selective invalidation，不修改 B4 五 specialist cache。
- [CI #37708769385](https://github.com/tommylin15/janus-omniforge/actions/runs/37708769385) **137 PASS / 7 warnings**；[live #37708769182](https://github.com/tommylin15/janus-omniforge/actions/runs/37708769182) **SUCCESS**，重用 10,978 rows／533,945 bytes，verified hash／0 BigQuery jobs／billed 0；Cloud Run Mart `janus-intelligence-mart-p8wjs` readback PASS。
- live 是同一 global Core 的 cache hit；無關 Core 修改及源資料／版本變更時 selective invalidation 由 targeted tests 驗證，未改 live canonical Core；B7～B9 未完成。

### B5 ML / OOS data path — CLOSED（2026-10-08）

- GitHub `main`：`c411fc0` 使用受控 BigQuery TEMP table 將 fixed Core snapshot 的 reduced SQL 結果匯出版本化 GCS Parquet，避開 shared Iceberg external table 直接 `EXPORT DATA` 的 HTTP 500；`051591e` 修正 Cloud Build `gcloud storage cp` entrypoint。
- [live acceptance #37706568819](https://github.com/tommylin15/janus-omniforge/actions/runs/37706568819) **SUCCESS**；B5 targeted 13 PASS、Mart regression 129 PASS（7 warnings）；Cloud Build export artifact 與 Cloud Run Mart execution `janus-intelligence-mart-bb25f` 真實讀回 PASS。
- Fixed Core snapshot `sha256:1eb49a2d...`；**10,978 rows / 499 symbols / 1 Parquet shard / 533,945 bytes**，row/content hash、source identity、manifest SHA256 驗收一致；Storage Read API false、LLM tokens 0、CEO 未觸發。最初 materialization BigQuery billed **30 MiB**；最終 immutable reuse run billed **0**。
- [B5 結案及 authoritative evidence](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)。**B5 僅 data path 結案**，B6 已另行 CLOSED；B7～B9、monthly scheduler、ML/OOS model quality 仍未完成；PyIceberg 維持 default。

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
- B3 每日 500 screening、B4 Deep Coverage、B5 ML/OOS data path、B6 derived cache 均已 CLOSED；尚未完成 B7～B9 的月度 retrain/reconciliation、BigQuery fallback/FinOps、完整模型 OOS 品質。
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
