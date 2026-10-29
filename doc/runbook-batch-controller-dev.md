# Dev 三大批次 Runbook

排程與驗收依[統一契約](spec/unified-batch-flow.md)§2／8.3／8.4；實作在`ingestion_core/batch_controller.py`。只走新排程，不保留舊時段補跑與需求緩衝。

1. 固定來源SHA，通過完整Release、同來源0%候選與Auth邊界。
2. 用現役固定映像及設定hash作安全回復基準，沿共用lease／Scheduler／在途fence更新既有四Jobs，驗8次canary。既有migration只驗必要marker，不重做已完成工程。
3. 透過既有VM安裝同來源備份／維護executor，不新增資源／IAM；備份checksum及隔離還原沿原守護工作流。
4. 執行`three-pipeline-acceptance-dev.yml`的`configure`：受控設定60分鐘timeout與新啟用點；Worker終態後有界退役舊操作緩衝、舊批次控制與舊需求，按目前持股／關注重建。超限或未知狀態停止，不偽造成功。
5. 分別執行`eod`、`compensation`、`backup`、`maintenance`。同一入口可controlled觸發，不等新週／週六；B驗一筆不改帳本的重算、防重複與空佇列，C驗Stage／Iceberg／PG維護及現役資料讀回。
6. 結果集中到Operations；全部有界條件通過即結案。失敗只處理具體項，保留執行身分，不盲目重派ambiguous，不開額外長期觀察。

回復只在實際部署／驗收失敗時沿既有映像與設定機制進行；不可雙Scheduler並行，不把基準保留當作恢復舊任務或需求緩衝。原始Owner資料、現役canonical與備份仍受保護。
