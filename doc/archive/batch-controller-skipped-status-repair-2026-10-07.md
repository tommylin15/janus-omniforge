# janus-batch-controller skipped status 修復（2026-10-07）

## 症狀

`janus-batch-controller` 在 GCP dev 連續多個每小時 `:30` active execution 以 exit code 1 結束；Cloud Run Job resource 本身維持 Ready。

## 根因

Controller 對兩種合法「本輪不需執行」情境會將 occurrence 寫成 `status=skipped`：

- mobile ledger queue 為空：`reason=queue_empty`
- market holiday：`reason=market_holiday`

但 migration `037_batch_controller` 建立的 `control.batch_occurrences` CHECK constraint 只允許：

`pending / dispatching / running / ambiguous / succeeded / failed`

因此 active controller 在 queue-empty 分支更新 occurrence 時觸發 PostgreSQL `CheckViolation`。精準 rollback probe execution `janus-batch-controller-fcmdw` 以 exit code 73 證明該更新命中 CheckViolation；`mobile-probe` execution `janus-batch-controller-9s25t` 與 `observe` execution `janus-batch-controller-fgvsp` 均成功，排除 image、基本 ADC、mobile queue reader、control DB / Iceberg observe 路徑的整體故障。

## 修復

新增 migration `049_batch_occurrence_skipped_status`：

- 以 catalog inspection 找到原 status CHECK constraint，不依賴舊匿名 constraint 名稱。
- 將允許狀態擴充為 `pending / dispatching / running / ambiguous / succeeded / failed / skipped`。
- 保留 active index 語意不變；`skipped` 不視為 active。
- migration acceptance 會確認新 constraint 含 `skipped`，並確認現有 rows 沒有未知 status。
- `serving_schema_migration.py`、allowlist workflow、Deploy dev path/filter 與 regression test 已同步。

沒有新增 GCP resource、沒有擴 IAM、沒有刪除 canonical data。

## 驗收證據

- Deploy dev workflow `37600433659`：**success**。
- `test-api`：success，包含 `tests/test_serving_schema_migration.py`。
- `test-ingestion`：success。
- `migrate-batch-occurrence-status / migrate` job `112725144699`：**success**。
- Scheduler 後續 execution `janus-batch-controller-cmdfr`：succeededCount=1，Completed success。
- 手動 bounded active acceptance workflow `37601633532`：**success**。
- active execution `janus-batch-controller-l5nkf`：succeededCount=1，failedCount=0，2026-10-07T09:35:52Z 開始，2026-10-07T09:37:34Z 完成。

因此本次 `janus-batch-controller` Error 已以 schema fix + migration + scheduler/runtime active evidence 收斂。
