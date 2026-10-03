# 公開資料刪除治理

2026-10-03 使用者最新決策取代舊「未提交／未解決資料持續保留」規則。僅限既有 dev 公開 Stage、Core、Mart；私人交易、筆記與 production 不在此批次範圍。

- Stage 原始 API 回應、sidecar、提交證明與隔離資料超過 7 天刪除，不以 Core 是否提交成功作為保留條件。queued／running／retrying execution 及其共用 raw 引用暫時保護；狀態不明且已超過期限的 Stage 資料可清理。Core 資料列內必要的來源／PIT 欄位不移除。
- 每個股僅保留最新 3 代完整分析，每代包含當次五 specialist。依分析日期、成果物提交時間及 execution ID 排序；持股／自選名單變動時仍按個股獨立計數。共用內容雜湊檔案在仍有保留引用時不刪。
- 只保留最新仍使用的 OOS 結果；淘汰結果及未完成、無引用且超過 7 天的 OOS／specialist 成果物可刪。現有 evaluator 的訓練模型只在記憶體中，不產生持久化權重檔；未來新增模型登錄時須同時定義 active model 的保護與淘汰，不能對未知模型路徑盲刪。
- 淘汰 execution 的原 manifest、screening、targets、membership 與不再使用的 evaluation 一起清理。保留一份有界的現存成果物引用索引；部分個股仍有保留代數時，以該索引保存引用。小型 retirement marker 防止舊 execution 重跑重新產生已淘汰報告；retired execution 不再提供完整 historical replay。
- Mart 表的分析列沿用 90 天。Core 一般行情 365 天、深度價量與 benchmark 1096 天、財報 12 季；目前快照、最近 24 小時快照、最近 90 天每日最後快照與有效引用仍受保護。不是讀取一次就立即刪快照。
- Core execution manifest 超過 90 天且不再被有效成果物／作業引用才可淘汰。此步驟需 `CORE_RETENTION_FENCE_URI` 指定既有 dev Core `maintenance/retention-fences/` 下的新鮮引用清單，含 `created_at` 與 `core_snapshot_ids`；清單必須在 1 小時內產生，並與 queued／running／retrying 作業的 Core 引用合併。未提供清單時不淘汰 Core manifest，回報 `reference_fence_required`。
- 快照過期後，無存活快照引用且超過 7 天的 metadata／Avro／Parquet 孤立檔案才可清理。保留引用先讀回驗證；刪除使用 generation 條件。Mart 分析與清理共用 PostgreSQL mutation lock，避免新報告寫入時被清理。

批次沿用既有 ingestion `ICEBERG_MAINTENANCE_MODE=retention-dry-run|retention-apply` 與 Mart `MART_OPERATION=retention`、`MART_RETENTION_MODE=dry-run|apply`。Mart 必須先完成引用淘汰，再以保留索引產生 Core reference fence，最後清理 Core／Stage。實際刪除量、讀回結果、deployment 與排程證據記於 operations；程式已提交不代表已部署或已清理。
