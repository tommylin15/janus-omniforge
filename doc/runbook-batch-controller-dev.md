# Dev 統一批次 Runbook

更新：2026-10-24。唯一排程與依賴表移至 [統一契約](spec/unified-batch-flow.md)，不在多份文件維護不同時段。
實作：`jobs/ingestion-core/ingestion_core/batch_controller.py::BATCHES/effective_batches()`。
本輪 CODE／文件修改；測試、CI、Dev部署、VM更新、Scheduler切換、自然觸發均 NOT VERIFIED。

## 執行

1. 依 [AI交接 WI](runbook-unified-batch-ai.md) 固定實際 commit SHA，完成必要離線測試。
2. 先 migration 069、備份 executor／policy 同版更新，再更新既有 ingestion／Mart／Private／Controller images。
3. 保存舊 cron／immutable image／VM檔；新Cron只改既有 `janus-ingestion-daily` 的兩小時節奏，先讀回其target必須是Controller。不得重建舊直接Mart／Private Scheduler。
4. 切換設定 `FINOPS_WEEKLY_MAINTENANCE=true`；新的 `BATCH_CONTROLLER_NOT_BEFORE` 防止新時段回補切換前工作。
5. 不取消健康running／ambiguous；待終態後再切換。Cloud Run response不明時不盲重送。
6. 既有durable occurrence／advisory lock／worker busy fence保留；五天外analysis／collection排除，不追查或補造成功。
7. Stage維持48h／有效租約與generation；Core/Mart每週依序compact→Mart retention→Core retention。
8. 備份由Controller產生日期request，VM領取；同次PG dump複用成日／週／月副本，備份與清理狀態分開讀回。GitHub無業務cron。

## 回復

暫停同一Scheduler，確認在途Job終態，恢復先前image／VM檔與cron，再恢復同一入口；不可新舊排程並行。
migration 069是加欄位，可留存供舊版忽略，不刪已存在備份／私人快照。
部署與故障診斷使用 recovering-stuck-ci-deploys：queued不是卡死；RUNNING未逾timeout不重派。
已結案FINOPS-AB／P0-2／OPS-P0-1收據保留在Operations及Git歷史，不因本次節奏改版重開來源稽核。
