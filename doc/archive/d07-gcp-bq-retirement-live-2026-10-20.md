# D07-PRE｜2026-10-20 舊研究 GCP/BQ 實機盤點收據

- GCP project: `gen-lang-client-0593591102`；Cloud Run/Scheduler region: `us-central1`。
- [自動清理 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206)：GCP WIF 身分 PASS；已知舊研究專用 Jobs/Scheduler/BQ tables/datasets 均無符合候選，前後 readback PASS；**實刪 0**。
- [精確資源讀回 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801)：8 Cloud Run Jobs：`janus-batch-controller`、`janus-ceo-analysis`、`janus-ingestion-core`、`janus-intelligence-mart`、`janus-private-pipeline`、`life-assistant-db-migrate`、`life-assistant-free-events`、`life-assistant-gmail-onnx-smoke`。唯一 Scheduler：`janus-ingestion-daily`；因正式市場流程使用必須保留。
- BigQuery 列表：1 dataset `_4b7fe31e8b2716c2c4242fa47f8ba327c90e9994`、0 table、0 view；沒有已知 B5～B8／specialist-train 中介表。空 dataset 未證實來源，不做無依據刪除；BQ historical jobs/transfer configs 不在本輪查詢範圍。
- **未驗收**：GitHub main 已移除 Controller 舊 `specialist-retrain` due 與 Mart 舊 fit，但本輪僅驗證獨立 Cloud Run/Scheduler/BQ metadata；共用現役 Controller/Mart digest、實際自然 due／舊 pending 跳過收據仍須依 release/readback 驗證。不得將此備註視為全路徑 RUNTIME_DISABLED／DEPLOY PASS。
- One-shot 清理工具執行後從 active workflow/code 移除，避免在正式運維留下第二套研究刪除工作；歷史證據在上述 Github Actions artifacts/log 保存。
