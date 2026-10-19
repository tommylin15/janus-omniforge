# Dev 批次總控與週維護 Runbook

更新：2026-10-19。本檔是可重跑操作程序；[資料治理統一入口](spec/data-governance.md) 保存**唯一人讀排程／任務表**。實際程式權威為 `jobs/ingestion-core/ingestion_core/batch_controller.py::BATCHES/effective_batches()`；完成與已部署配置依真實 Cloud Scheduler、Jobs、occurrence/執行收據。舊 [2026-10-13 盤點](archive/batch-inventory-2026-10-13.md) 是歷史證據，不能當現役 Cron。

## 唯一排程責任與週維護

- Cloud Scheduler 唯一業務定時入口目標 `janus-batch-controller:run`，既有 `30 * * * *`、`Asia/Taipei`。GitHub Actions 只保留備份清理的定時工作；其它 workflow_dispatch、CI、Release、診斷不是第二套業務 Cron。due 時段**不是** worker 真正啟動時間，每小時喚醒**不是**每小時重跑全業務。
- 日常 `ingestion` 07:30/14:30、`data-supplement` 08:30（依 07:30）、週一～五 `mart` 09:00、`market-screening` 16:30；每週六 `data-quality` 12:30；每月**第一個週六** `specialist-retrain` 10:30；`private`、`mobile-ledger`、`ledger-backup` 的具體 due 和依賴見 [總入口 §3](spec/data-governance.md)。新持股／關注股 demand 補收共用既有 ingestion Job，沒有新建第二個 Scheduler。
- **Stage-only 保留48小時**：每日 **18:30 Asia/Taipei** 由 Controller 派送既有 `janus-ingestion-core`，傳入 `ICEBERG_MAINTENANCE_MODE=stage-only-apply`。只掃/清 `gen-lang-client-0593591102-dev-stage`，查 PG active executions，保留有效引用並使用 GCS generation；不需要載入 Iceberg Core catalog。由 Controller busy/occurrence fence 管理，沒有新 Scheduler 或額外常駐 Job。模式 `stage-only-dry-run` 僅用於受控診斷；前後物件數/bytes、success/failure receipt 與實際部署要分開驗證。\n- `FINOPS_WEEKLY_MAINTENANCE=true` 時 `effective_batches()` 僅把三個維護操作改為**週六23:30 due**，依賴是 `iceberg-compaction → mart-cleanup → core-cleanup`；busy/lease、unique occurrence 和每小時 tick 可能使後續 Job 跨日。false 是 legacy daily branch，**不是**最新核准的週維護節奏。FINOPS-AB 2026-10-18 的既有收據記錄週維護開啟，但本次未重新查驗 current env 與自然 execution，不冒稱新的 live PASS。
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

**B7 排程口徑（以 `main` 程式為準）：** `jobs/ingestion-core/ingestion_core/batch_controller.py` 的 `specialist-retrain` 目前設定 `weekdays=(5,), month_days=1..7, hours=(10,), minute=30`，亦即**每月第一個週六 10:30（Asia/Taipei）** 才有 monthly due；`tests/test_batch_controller.py` 已有對應正／負向 deterministic 測試。既有 Cloud Scheduler 可維持每小時 `:30` 喚醒 controller，**並不是月度 Job 每小時啟動**。以上僅證明 `main` 的程式／test contract；部署映像、實際 Scheduler、當期自然 execution 及 retrain／OOS／cache artifact 仍須 B7 live readback 才能判 PASS。若需要補跑 missed slot，不得直接從外部 workflow 執行 Mart；使用 `BATCH_CONTROLLER_MODE=manual` 搭配唯一 `BATCH_CONTROLLER_MANUAL_REQUEST_ID` 執行既有 `janus-batch-controller`。manual mode 固定只允許 `specialist-retrain`，同一 request ID 對應同一 occurrence；它以最近 7 天 dependency occurrence 的最新台北日期作為 fence，綁定該日 ingestion／data-supplement 排程 identity，兩者未全數 `succeeded` 就只等待。若 pending 期間出現更新日期的 ingestion occurrence，dispatch 前會先改綁新日期並等待同日 data-supplement，避免跨日沿用舊 dependency；全程沿用 advisory lock、busy fence、dispatch intent、outbox 與 ambiguous 不重試規則。

GitHub 的 bounded 入口 `.github/workflows/run-dev-specialist-retrain.yml` 只接受 committed `ops/dev-specialist-retrain-request.json` 的 `operation=specialist-retrain`，並只對 `janus-batch-controller` 做 execution-level env override，不永久修改 controller／ingestion／Mart Job 設定。實際 retrain 仍由 controller 以固定 `MART_OPERATION=specialist-retrain`、`MART_OOS_EVALUATION=true`、`MART_AI_ENABLED=false` 派送；Mart 自身再驗最新 immutable Core snapshot freshness。manual request 成功派送不等於模型有效或 champion promotion，仍需 OOS artifact persist/readback 與 acceptance evidence。

### B7 GHCR 現役路徑（不得重播舊 request）

- 2026-10-08 前的 `b7-monthly-live-20261008-v1` 已因舊 `dev-SHA` 比對失敗而**沒有由 Actions 派送**，僅保留歷史稽核，不重送、不修復舊映像。新的 bounded 驗收必須採全新 `request_id`。
- `ops/dev-specialist-retrain-request.json` 使用 `expected_release_sha`，且必須等於 `ops/ghcr-jobs-rollout-request.json` 已核准的 GHCR Jobs 完整 source SHA。workflow 從公開 GHCR tag 解析不可變 digest、核對 OCI revision label，再比對既有 controller／ingestion／Mart Job 的實際 image（允許 Cloud Run registry-import cache prefix，但**不**容許 mutable tag、舊 `dev-SHA` 或 digest 不符）。與 Jobs 發布共用 `janus-dev-runtime-writers` concurrency；不得更新映像或代替 release。
- 在任何手動 controller 派送前，利用現有唯讀權限列出 `us-central1` Scheduler，核對 `janus-ingestion-daily` 唯一、`ENABLED`、`30 * * * *`、`Asia/Taipei`、目標 `janus-batch-controller:run`。讀取被拒／值不符即 fail closed，不額外擴 IAM。
- `run-dev-specialist-retrain.yml` PASS 最多證明 workflow 與 controller 指令成功；若 dependency 未滿足，可能僅建立 pending occurrence。必須另外鎖定**新** `janus-intelligence-mart-...` execution，檢查 `Completed=True`、`MART_OPERATION=specialist-retrain` 與同次 execution 的 `specialist-manifest.json`／`oos-evaluation.json`／`monthly-reconciliation.json`。以 `ops/dev-mart-execution-inspect.json` 的 `execution` 與 `expect_monthly=true` 觸發 `inspect-dev-mart-execution.yml`，逐一核對 GCS bytes SHA-256、Core identity、cache reconciliation `pass/partial` 與零 CEO／promotion。缺任何證據維持 `NOT VERIFIED` 或 `PARTIAL`，不得將單純 Job success 標成 B7 完成。


### B7 衍生快取新鮮度獨立刷新（不重新訓練）

**歷史 B7 修復流程（2026-10-10 已結案，原 workflow 在 main 已不存在）：**若現役 B6 derived cache 新發生與舊 Core 的 identity 漂移，先依 [D07-PRE／D07 TODO](todo.md) 建立新合格的 bounded readback／修復工作；下述舊操作只供診斷參考，不可直接盲重播： [B7 歷史派送與結案](archive/group-b-b7-derived-cache-freshness-closure-2026-10-10.md) 所定義的 standalone PyIceberg 路徑，不派送 `specialist-retrain`、不重用舊 10/08 request，也不重開 B8 benchmark。對應 script 為 `scripts/gcp/b7-refresh-derived-cache.py`，只使用現有 dev buckets／GitHub WIF、已鎖定依賴及既有 B5/B6 schema。

1. 選最近七天的**最新 immutable Core snapshot**，驗證 `core-snapshot.json` 原始 bytes SHA-256、`core.ohlcv_v1` Iceberg metadata snapshot/pointer 與分析日期；月度原始 `specialist-manifest.json` 必須是**同一 Core identity**，否則 fail closed，不重訓補缺。
2. 以當次 pinned Core、版本、日期界線和 source authorization 產出 B5 格式 ML/OOS Parquet；相同 immutable cache 命中先核對 bytes/hash 才 reuse，cache miss 才以 PyIceberg 建立 `ml-oos-data/v1/<identity>/` 的 create-only shard／manifest。驗證前後 latest Core source 未改變。無 BigQuery／Storage Read API、無 canonical 寫入、無 CEO、無 champion promotion。
3. 從**原本已完成的月度** specialist manifest 讀取 active target 與 25 個 references，重新執行**唯讀** `reconcile_monthly_cache`。僅在 `status=pass`、derived cache `status=current`、`exact-core`、無 missed invalidation 且 independent Parquet bytes readback 通過時，才以 create-only 寫入 `acceptance/b7-cache-freshness/<hash>.json`；不能覆寫原來 `monthly-reconciliation.json`（可保留 `partial` 歷史）。
4. 以 GitHub Actions tests、dev GCS immutable readback 和 workflow receipt 判斷 B7 衍生快取的當次 source freshness；若 Core 已更新、metadata drift、月度 references 不匹配、GCS 權限被拒、寫入一半或驗收收據缺失，維持 `PARTIAL`／`BLOCKED`，只補修受影響範圍、不盲目重送月度 Job。

清理 worker 的啟用與完成狀態以目前 runtime／operations evidence 為準。清理報告必須保存 Core／Stage／Mart 各層刪除物件數與 bytes、前後 live 容量、受保護空間及非當前版本／soft delete 狀態。live bytes 減少不等於可計費空間立即釋放，未核對者標記 unknown。
