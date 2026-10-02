# Dev 批次總控

## 契約

初期 Cloud Scheduler 每小時 :30 喚醒一次 Cloud Run 總控；穩定後可調成每 10 分鐘。總控不等待子批次、不取消既有 execution。批次自身保留每日、每日多次或限定星期的排程，喚醒頻率不等於批次執行頻率。時區為 Asia/Taipei。

總控使用 PostgreSQL advisory lock `(1835102836,3)`，同時間只有一支能決策。`control.batch_occurrences` 以批次、日期、排程時段唯一識別，先提交派送意圖才呼叫 Cloud Run。執行中與派送結果不明的紀錄持續阻擋相同 Job；Cloud Run 查詢失敗不解除阻擋。結果不明須人工核對 execution，不自動重新派送。

`control.batch_event_outbox` 與狀態更新同一 transaction 提交；使用穩定 event ID 寫入 `ops.batch_events_v1`，讀回 payload 核對後才確認已輸出。Iceberg 不可用時 outbox 保留。歷史紀錄供後續 Admin UI 查詢，只有安全狀態、依賴與 execution 參照，不保存 secret 或原始私人 log。Cloud Run 成功不代表資料完整，應用的 partial／coverage 判定仍有效。

## 部署與切換條件

目前程式與 migration 是本機修改，尚未完成 GCP dev 驗收。Migration 為 `037_batch_controller`；controller entrypoint 為 `python -m ingestion_core.batch_controller`。新增 controller Job／所需 IAM 應依 PROJECT_RULES §1.3 完成核准。

須先驗收重複喚醒、長作業、派送後總控中斷與 Iceberg outbox 重送，再將既有 ingestion Scheduler 改為每小時 :30 指向總控，暫停其他直接啟動 worker 的 Scheduler。既有 Job 自動觸發下一批的路徑亦須收斂，避免雙重派送；切換前保存 Scheduler 設定供回復。

清理 worker 已加入 Core／Stage 與 Mart 入口，尚待 dev 固定快照保護、清理批次依賴與容量讀回驗收，不能視為已啟用正式清理。清理報告必須保存 Core／Stage／Mart 各層刪除物件數與 bytes、前後 live 容量、受保護空間及非當前版本／soft delete 狀態。live bytes 減少不等於可計費空間立即釋放，未核對者標記 unknown。
