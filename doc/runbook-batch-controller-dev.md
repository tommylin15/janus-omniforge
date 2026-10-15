# Dev 批次總控

## 契約

現況 Cloud Scheduler 每小時 :30 喚醒 Cloud Run 總控；是否縮短需先量測 dispatch lag。所有業務定時工作以此總控為唯一入口，GitHub Actions 只保留備份清理 schedule。總控不等待子批次、不取消既有 execution。批次自身保留每日、每日多次或限定星期的排程，喚醒頻率不等於批次執行頻率。時區為 Asia/Taipei。

`ingestion` 由同一總控在 07:30 與 14:30 產生 occurrence；14:30 不建立第二支 Scheduler／Job，而是對既有 `janus-ingestion-core` 做 execution-level override，將 `INGESTION_DATE` 固定為該台北日期，且只收斂盤後價格／指數所需的 `twse-market-volume,tpex-market-volume,taiex`（TPEx 新需求，實際映像尚須驗證）。全上市櫃個股皆納入，首頁仍只用 TAIEX benchmark。07:30 維持原本完整 ingestion 契約。21:30 Private Pipeline 與晚間 retention 依賴同日最新的 14:30 ingestion occurrence。

### 23:30 夜間 Iceberg 壓縮（獨立 FinOps 事件）

2026-10-15 起的目標程式契約：每日 **23:30 Asia/Taipei** 由既有每小時 `:30` 喚醒的 `janus-batch-controller` 建立 `iceberg-compaction/YYYY-MM-DD/23` occurrence；沿用**現有** `janus-ingestion-core` Cloud Run Job，以 execution-level overrides 執行 `ICEBERG_MAINTENANCE_MODE=compact-nightly`（同次 execution 先執行 `compact-dry-run`、通過後再 `compact-apply`，並受控合併先前被遺漏的 `ops.batch_events_v1` 稽核事件表），不增開 Cloud Scheduler／Job，也不依賴 GitHub Actions 執行業務。

相依順序改為：**14:30 ingestion 成功 → iceberg-compaction → mart-cleanup → core-cleanup**。三項夜間工作維持同一個 23:30 邏輯時段，但因總控每小時喚醒且不得併發，後兩項的實際派送可能跨到翌日 00:30／01:30 或更晚；故 23:30 表示 **due 時段，不保證每支 Job 23:30 真正啟動**。compaction 在 ingestion 尚未成功、worker 忙碌、前一輪未終態或權限/資料異常時留 pending；不跳過依賴、不盲目重試 ambiguous dispatch。這是既有資料維護路徑，不計入產品 TODO／WBS。

`compact-apply` 會按月／年分區重寫可合併的有效 Parquet，驗證 row count 與舊 snapshot 可讀；**不代表同時刪除所有歷史 snapshot／孤兒檔，也不保證 GCS 課金立即下降**。既有 `core-cleanup` 的 retention 及引用保護仍獨立運作；本次不把「刪除全部舊 snapshot」變成每日無條件執行的破壞性 cron。Release 必須遵守完整 SHA CI／GHCR Jobs rollout gate，並從 GCP readback 真實 scheduler、controller／worker image、occurrence 及 Cloud Run execution；僅 GitHub commit 不代表 schedule 已生效。

GitHub 原本直派 `Maintain dev Core Iceberg` workflow、`ops/iceberg-maintenance-mode` 與 operations audit workflow 在本變更移除；保留 `iceberg-compaction-ci.yml` **純測試**。原有 GitHub run 歷史與獨立 FinOps Issue #2 保留作稽核。

總控使用 PostgreSQL advisory lock `(1835102836,3)`，同時間只有一支能決策。`control.batch_occurrences` 以批次、日期、排程時段唯一識別，先提交派送意圖才呼叫 Cloud Run。執行中與派送結果不明的紀錄持續阻擋相同 Job；Cloud Run 查詢失敗不解除阻擋。結果不明須人工核對 execution，不自動重新派送。

`control.batch_event_outbox` 與狀態更新同一 transaction 提交，PostgreSQL 是即時且持久的事件稽核來源；Iceberg `ops.batch_events_v1` 只是供歷史查詢的**延遲鏡像**。2026-10-15 FinOps 觀察 5 分鐘級 Core 大量 `ReadObject`、`GetObjectMetadata` 集中在每小時 `:30～:40`，程式碼顯示舊版每小時無分區 Iceberg audit replay 掃描，為高度吻合的根因候選；不能單憑時段宣稱唯一呼叫來源。因此例行總控只在 **05:30、11:30、17:30、23:30 Asia/Taipei** 批次寫入 Iceberg，每輪最多 10 個 200-event batch；其餘時段 PostgreSQL outbox 保留並回報 `iceberg_audit_deferred=true`。最長正常延遲約六小時，若依賴／GCP 失敗則延後且不遺失、不能宣稱即時同步。每輪仍檢查 event ID／payload 並完成 Iceberg readback 後才更新 `exported_at`。與夜間稽核表 compact 合併，避免每小時重跑全部歷史 manifest。歷史紀錄供後續 Admin UI 查詢，只有安全狀態、依賴與 execution 參照，不保存 secret 或原始私人 log。Cloud Run 成功不代表資料完整，應用的 partial／coverage 判定仍有效。

完整現況／收斂清冊見 [批次盤點](batch-inventory-2026-10-13.md)，即時與快照責任見 [新契約](spec/full-market-batch-policy.md)。備份產生 timer 及研究 Actions 的遷移未完成；不得因本文件更新宣稱已收斂。

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

B7 月度 retrain／OOS／原始 reconciliation 已完成時，若 B6 ML/OOS derived cache 仍對舊 Core 顯示 `historical`，只執行 [B7 derived-cache workflow](../.github/workflows/b7-derived-cache-freshness.yml) 所定義的 standalone PyIceberg 路徑，不派送 `specialist-retrain`、不重用舊 10/08 request，也不重開 B8 benchmark。對應 script 為 `scripts/gcp/b7-refresh-derived-cache.py`，只使用現有 dev buckets／GitHub WIF、已鎖定依賴及既有 B5/B6 schema。

1. 選最近七天的**最新 immutable Core snapshot**，驗證 `core-snapshot.json` 原始 bytes SHA-256、`core.ohlcv_v1` Iceberg metadata snapshot/pointer 與分析日期；月度原始 `specialist-manifest.json` 必須是**同一 Core identity**，否則 fail closed，不重訓補缺。
2. 以當次 pinned Core、版本、日期界線和 source authorization 產出 B5 格式 ML/OOS Parquet；相同 immutable cache 命中先核對 bytes/hash 才 reuse，cache miss 才以 PyIceberg 建立 `ml-oos-data/v1/<identity>/` 的 create-only shard／manifest。驗證前後 latest Core source 未改變。無 BigQuery／Storage Read API、無 canonical 寫入、無 CEO、無 champion promotion。
3. 從**原本已完成的月度** specialist manifest 讀取 active target 與 25 個 references，重新執行**唯讀** `reconcile_monthly_cache`。僅在 `status=pass`、derived cache `status=current`、`exact-core`、無 missed invalidation 且 independent Parquet bytes readback 通過時，才以 create-only 寫入 `acceptance/b7-cache-freshness/<hash>.json`；不能覆寫原來 `monthly-reconciliation.json`（可保留 `partial` 歷史）。
4. 以 GitHub Actions tests、dev GCS immutable readback 和 workflow receipt 判斷 B7 衍生快取的當次 source freshness；若 Core 已更新、metadata drift、月度 references 不匹配、GCS 權限被拒、寫入一半或驗收收據缺失，維持 `PARTIAL`／`BLOCKED`，只補修受影響範圍、不盲目重送月度 Job。

清理 worker 的啟用與完成狀態以目前 runtime／operations evidence 為準。清理報告必須保存 Core／Stage／Mart 各層刪除物件數與 bytes、前後 live 容量、受保護空間及非當前版本／soft delete 狀態。live bytes 減少不等於可計費空間立即釋放，未核對者標記 unknown。
