# Dev 批次總控與週維護 Runbook

更新：2026-10-20。本檔是可重跑操作程序；[資料治理統一入口](spec/data-governance.md) 保存**唯一人讀排程／任務表**。實際程式權威為 `jobs/ingestion-core/ingestion_core/batch_controller.py::BATCHES/effective_batches()`；完成與已部署配置依真實 Cloud Scheduler、Jobs、occurrence/執行收據。舊 [2026-10-13 盤點](archive/batch-inventory-2026-10-13.md) 是歷史證據，不能當現役 Cron。

## 唯一排程責任與週維護

- Cloud Scheduler 唯一業務定時入口目標 `janus-batch-controller:run`，既有 `30 * * * *`、`Asia/Taipei`。GitHub Actions 只保留備份清理的定時工作；其它 workflow_dispatch、CI、Release、診斷不是第二套業務 Cron。due 時段**不是** worker 真正啟動時間，每小時喚醒**不是**每小時重跑全業務。
- 日常 `ingestion` 07:30/14:30、`data-supplement` 08:30、週一～五 `mart` 09:00、`market-screening` 16:30；每週六 `data-quality` 12:30。`private`、`mobile-ledger`、`ledger-backup`、Stage48h、每週 Iceberg 的 due 見 [資料治理](spec/data-governance.md)。**舊月度 `specialist-retrain` 已移除。**
- **Stage-only 保留48小時**：每日 **18:30 Asia/Taipei** 由 Controller 派送既有 `janus-ingestion-core`，傳入 `ICEBERG_MAINTENANCE_MODE=stage-only-apply`。只掃/清 `gen-lang-client-0593591102-dev-stage`，查 PG `queued/running/retrying` 且 `claimed_until > now UTC` 的**有效租約**（過期/缺失的 `running` 不構成保護），apply 前重新讀取有效租約集合，若變動 fail closed；保留有效共用 raw 引用並使用 GCS generation；不需要載入 Iceberg Core catalog。由 Controller busy/occurrence fence 管理，沒有新 Scheduler 或額外常駐 Job。模式 `stage-only-dry-run` 僅用於受控診斷；前後物件數/bytes、success/failure receipt 與實際部署要分開驗證。\n- `FINOPS_WEEKLY_MAINTENANCE=true` 時 `effective_batches()` 僅把三個維護操作改為**週六23:30 due**，依賴是 `iceberg-compaction → mart-cleanup → core-cleanup`；busy/lease、unique occurrence 和每小時 tick 可能使後續 Job 跨日。false 是 legacy daily branch，**不是**最新核准的週維護節奏。FINOPS-AB 2026-10-18 的既有收據記錄週維護開啟，但本次未重新查驗 current env 與自然 execution，不冒稱新的 live PASS。
- `control.batch_occurrences` 先保留決策及 dispatch intent，再向 Cloud Run 派送；advisory lock `(1835102836,3)` 及 worker busy fence 保證單一控制面。Cloud Run dispatch ambiguous、unknown、active 不能取消後盲目再派，先讀 job/execution terminal 與 durable status。
- **current-only Iceberg**：依 [Retention SPEC](spec/retention-governance.md) 和 [10/18 決策](decision-2026-10-18-current-only-snapshots.md)，非 current Iceberg snapshot 不再要求 named/24h/外部研究引用 fence。舊 `CORE_RETENTION_FENCE_URI` 完整研究清冊不是非current過期 gate；但必須保護 current files、7日 orphan 年齡、generation、catalog pointer、lock／dev allowlist，逐項讀回。Private Owner 不在公開資料清理範圍。

## 操作／失敗恢復與驗收

1. 檢查當前 GitHub 完整 SHA、controller 與 ingestion/Mart jobs immutable digest，Scheduler cron/timezone/target/state，當前 `FINOPS_WEEKLY_MAINTENANCE`、active executions、schema/migration 與共用 lease。沒有 live 權限時標 `NOT_VERIFIED`，不以 GitHub 文件取代 readback。
2. 週維護依 **current Core 確認 → compaction → Mart retirement/retention → Core row/Stage/noncurrent snapshot/orphan cleanup → current Core/Mart readback**。所有刪除都先符合適用時限與 generation；歷史 snapshot 不因研究引用保護，但活躍 Writer/當前檔案必須安全。
3. 必須分開記錄候選與**實際**刪除 Core、Stage、Mart 各層 `objects/bytes`、實際 row count、active bytes 前後、已保留 current 數值、錯誤與未驗證費用。Dry-run/compaction/job success 不是 GCS 計費節省證據。
4. 補收 `daily|demand|quality`、來源治理、去識別化 demand lease、部分成功與 Ledger publication 分開驗；步驟詳見 [補資料 Runbook](runbook-data-supplement.md)。遇 source stale、Job 失敗、週批依賴未終態，維持 partial/pending 並從唯一總控復原，不透過外部 Cron 重送。
5. 改變 Cron、worker env 或啟用 retention apply 屬工程作業，另依 [TODO](todo.md)、PROJECT_RULES、Release 與真實驗收授權；本次文件整理沒有進行上述 mutation。

## 部署與操作

Schema baseline 為 `037_batch_controller`；`049_batch_occurrence_skipped_status` 將 controller 已使用的終態 `skipped` 納入 `control.batch_occurrences` status CHECK。新增或調整 controller status 時，必須同步提供版本化 migration 與 live schema acceptance，避免 runtime 合法狀態被舊 DB constraint 拒絕。controller entrypoint 為 `python -m ingestion_core.batch_controller`。既有 dev controller Job 與限定 IAM 由 deployment／runtime evidence 驗證；新增 Job、擴張權限或付費資源仍依 PROJECT_RULES 的授權邊界處理。Scheduler cutover 或回復前都先保存現況，避免與舊直接 worker Scheduler 雙重派送。

## 舊模型工作已退役（2026-10-20）

原 B7 手動月度重訓 workflow、Controller `specialist-retrain`、BigQuery ML/OOS 前置中轉與對應接線都不再是 active 作業。新研究使用 [官方API→Colab→Drive月資料夾](spec/research-collection-gas-drive-colab.md)。對資料庫內**沒有現役 batch 定義**的歷史 pending 工作採通用 `schedule_superseded` 結案；正在 running/ambiguous 的既有 execution 必須查終態，不盲取消重送。

舊研究GCP/BQ範圍已依2026-10-20實機收據結案，不重開inventory；未來部署仍須新版本readback，不能以歷史成功替代。正式 ingestion、market-screening、Owner/Private、Stage48h、每週 Iceberg、備份保留。已有現役引用的共享 Mart 或 BQ 不應因模型架構改版整支刪除。

清理報告仍要保存 Core／Stage／Mart 各層實際刪除 objects/bytes、前後容量與保護集，區分 dry-run、實刪與計費空間。安全與驗收請依 [PROJECT_RULES](PROJECT_RULES.md)、[Retention](spec/retention-governance.md)、[TODO](todo.md)。

### 2026-10-20 Stage 過期 running 控制紀錄清理收據

- 只在 dev Stage bucket 進行：受控乾跑 #39354898619 定位 24 筆過期/無租約 `running` 對應 4,927 個超過7天 Stage execution 物件；GCP #39355428497 在 Scheduler 暫停、全部 Cloud Run execution 終態、全球部署 lease 下以固定 generation 實刪 **4,927 objects／96,321,204 bytes**。Stage before 6,384／415,180,394 → after 1,457／318,859,190；Core/Mart/Private 刪除零。操作過程未清除控制表內的歷史紀錄。相關真實執行證據以 [Operations](spec/operations-and-testing.md) 為準。
- 日常 Stage 48h 清理**不**改為七天；七天僅此歷史失效執行的專項清理範圍。清理失敗需保存部分刪除收據並 fail closed，不得以單純 `running` 狀態長期持有失效資料；不得為 MD5 猜測容量直接刪除仍被有效租約引用的副本。每次要確認實際 Scheduler ENABLED、Cloud Run terminal、generation readback 和週六 Iceberg cadence 不變。


## D07模型分析／回收擴充（設計，未啟用）
[模型生命週期](spec/model-lifecycle.md)定義盤前08:30目標due、盤後接既有screening、每週成熟outcome及每月首週evaluation。現行BATCHES尚未因此改動；09:00 mart可能09:30派送，不能當盤前。實作沿原Controller/既有Mart/occurrence/鎖，模型按批載入，按股票輸出，不新增每股Job或Colab自動訓練。具體模式/參數實作後才回寫可執行命令。

