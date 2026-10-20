# D07-PRE｜2026-10-20 舊研究 GCP／BigQuery 退役結案（CLOSED）

- 專案 `gen-lang-client-0593591102`，region `us-central1`。GitHub Controller `specialist-retrain` 與 Mart 舊 fit 入口已移除；[完整 GHCR #39355867356](https://github.com/tommylin15/janus-omniforge/actions/runs/39355867356)、[四 Jobs rollout #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[獨立部署讀回 #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) PASS。
- [退役盤點／清理 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206)、[精確資源讀回 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801)：Cloud Run 共 8 Jobs，只有 1 個正式 `janus-ingestion-daily` Scheduler；沒有獨立舊研究重訓 Job／Scheduler。正式共用 Job 與 Life Jobs 保留。
- BigQuery 共 1 個空 dataset `_4b7fe31e8b2716c2c4242fa47f8ba327c90e9994`，0 tables／0 views；無舊 B5～B8 中介實體。**本次 GCP/BQ 實際刪除 0、釋放容量 0**；單次驗收已達成，無具體異常，不增加假設性追查或待辦。
- 清理完成後一次性工具與臨時 workflow 入口已自 `main` 移除。未來有具體異常時依 [PROJECT_RULES §1.1.1](../PROJECT_RULES.md#111-有界驗收與結案原則2026-10-20-使用者決策) 處理，不重開本結案工項。
