# Dev 批次總控

## 契約

初期 Cloud Scheduler 每小時 :30 喚醒一次 Cloud Run 總控；穩定後可調成每 10 分鐘。總控不等待子批次、不取消既有 execution。批次自身保留每日、每日多次或限定星期的排程，喚醒頻率不等於批次執行頻率。時區為 Asia/Taipei。

`ingestion` 由同一總控在 07:30 與 14:30 產生 occurrence；14:30 不建立第二支 Scheduler／Job，而是對既有 `janus-ingestion-core` 做 execution-level override，將 `INGESTION_DATE` 固定為該台北日期，且只收斂盤後價格／指數所需的 `twse-market-volume,taiex`。TPEx／櫃買已退出 active scope，不再排程或發布。07:30 維持原本完整 ingestion 契約。21:30 Private Pipeline 與晚間 retention 依賴同日最新的 14:30 ingestion occurrence。

總控使用 PostgreSQL advisory lock `(1835102836,3)`，同時間只有一支能決策。`control.batch_occurrences` 以批次、日期、排程時段唯一識別，先提交派送意圖才呼叫 Cloud Run。執行中與派送結果不明的紀錄持續阻擋相同 Job；Cloud Run 查詢失敗不解除阻擋。結果不明須人工核對 execution，不自動重新派送。

`control.batch_event_outbox` 與狀態更新同一 transaction 提交；使用穩定 event ID 寫入 `ops.batch_events_v1`，讀回 payload 核對後才確認已輸出。Iceberg 不可用時 outbox 保留。歷史紀錄供後續 Admin UI 查詢，只有安全狀態、依賴與 execution 參照，不保存 secret 或原始私人 log。Cloud Run 成功不代表資料完整，應用的 partial／coverage 判定仍有效。

## 部署與操作

Schema baseline 為 `037_batch_controller`；`049_batch_occurrence_skipped_status` 將 controller 已使用的終態 `skipped` 納入 `control.batch_occurrences` status CHECK。新增或調整 controller status 時，必須同步提供版本化 migration 與 live schema acceptance，避免 runtime 合法狀態被舊 DB constraint 拒絕。controller entrypoint 為 `python -m ingestion_core.batch_controller`。既有 dev controller Job 與限定 IAM 由 deployment／runtime evidence 驗證；新增 Job、擴張權限或付費資源仍依 PROJECT_RULES 的授權邊界處理。Scheduler cutover 或回復前都先保存現況，避免與舊直接 worker Scheduler 雙重派送。

**B7 排程口徑（以 `main` 程式為準）：** `jobs/ingestion-core/ingestion_core/batch_controller.py` 的 `specialist-retrain` 目前設定 `weekdays=(5,), month_days=1..7, hours=(10,), minute=30`，亦即**每月第一個週六 10:30（Asia/Taipei）** 才有 monthly due；`tests/test_batch_controller.py` 已有對應正／負向 deterministic 測試。既有 Cloud Scheduler 可維持每小時 `:30` 喚醒 controller，**並不是月度 Job 每小時啟動**。以上僅證明 `main` 的程式／test contract；部署映像、實際 Scheduler、當期自然 execution 及 retrain／OOS／cache artifact 仍須 B7 live readback 才能判 PASS。若需要補跑 missed slot，不得直接從外部 workflow 執行 Mart；使用 `BATCH_CONTROLLER_MODE=manual` 搭配唯一 `BATCH_CONTROLLER_MANUAL_REQUEST_ID` 執行既有 `janus-batch-controller`。manual mode 固定只允許 `specialist-retrain`，同一 request ID 對應同一 occurrence；它以最近 7 天 dependency occurrence 的最新台北日期作為 fence，綁定該日 ingestion／data-supplement 排程 identity，兩者未全數 `succeeded` 就只等待。若 pending 期間出現更新日期的 ingestion occurrence，dispatch 前會先改綁新日期並等待同日 data-supplement，避免跨日沿用舊 dependency；全程沿用 advisory lock、busy fence、dispatch intent、outbox 與 ambiguous 不重試規則。

GitHub 的 bounded 入口 `.github/workflows/run-dev-specialist-retrain.yml` 只接受 committed `ops/dev-specialist-retrain-request.json` 的 `operation=specialist-retrain`，並只對 `janus-batch-controller` 做 execution-level env override，不永久修改 controller／ingestion／Mart Job 設定。實際 retrain 仍由 controller 以固定 `MART_OPERATION=specialist-retrain`、`MART_OOS_EVALUATION=true`、`MART_AI_ENABLED=false` 派送；Mart 自身再驗最新 immutable Core snapshot freshness。manual request 成功派送不等於模型有效或 champion promotion，仍需 OOS artifact persist/readback 與 acceptance evidence。

清理 worker 的啟用與完成狀態以目前 runtime／operations evidence 為準。清理報告必須保存 Core／Stage／Mart 各層刪除物件數與 bytes、前後 live 容量、受保護空間及非當前版本／soft delete 狀態。live bytes 減少不等於可計費空間立即釋放，未核對者標記 unknown。
