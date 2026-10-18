# 公開資料刪除治理

## 2026-10-18 最新覆蓋決策：只保留 current snapshot

使用者明確核准每張 Core／Mart Iceberg 表只保留目前 snapshot，其餘可清理；取消24小時、named tag／branch、研究／模型／報告／publication引用的歷史保護。`CORE_RETENTION_FENCE_URI`／external研究清冊／PG `core_snapshot_id` 讀權不再是歷史snapshot清理gate。先移除指向舊snapshot的named refs、過期非current snapshot，再以7日檔齡、current實際檔案集合、catalog pointer與generation清理孤立檔，讀回current資料不變。舊研究／報告／歷史snapshot可能無法重播；未來機制另訂。Private Owner與current必要檔不得刪除。詳見 [決策](../decision-2026-10-18-current-only-snapshots.md) 與 [PROJECT_RULES §1.6](../PROJECT_RULES.md)。

以下較早政策中「current以外snapshot／historical引用保護／完整reference fence」已由本節取代；row TTL、Stage期限與其餘generation／安全邊界維持。

## 2026-10-16 D06 當次小檔清理授權

使用者指定 Core 的 8,335 個 `<1 MiB` 物件（其中稽核表 1,175 個）為首批整理對象，要求實際降低物件與 I/O，並明確指示「不用太嚴謹，找不到關連就砍」。本輪因此以已查得的有效引用判定舊小檔是否可刪，不因完整外部研究清冊缺位而阻擋整批作業；不得把這項人工決定偽裝成 `COMPLETE_VERIFIED` 引用 fence。

本次沿既有 dev Core warehouse，先合併可重建的稽核鏡像，再清理無保留快照引用、超過七日且 `<1 MiB` 的 metadata／Avro／Parquet；保留 current／named／最近24小時快照、已知 Core execution／報告引用與新檔，按 generation 刪除並讀回。私人 bucket、交易、Core canonical rows 與 execution manifests 不在這次刪除範圍。記錄實刪物件、bytes、保護與新舊快照讀取，不以 compact 或乾跑冒稱已減量。以下一般 row／manifest retention 的完整 fence 契約維持適用原範圍。

關於各因子適用 **全市場（M）／觀察與持股（D）／私人（P）** 的收錄分母、容量估算、期限及「到期刪除≠搬至歷史區」的差異，請見 [因子收錄與保存矩陣](factor-coverage-retention-ledger.md)。矩陣是規格與容量預估，不會單憑文件變更觸發新的資料清理。

## 一般保留政策

2026-10-03 使用者最新決策取代舊「未提交／未解決資料持續保留」規則。僅限既有 dev 公開 Stage、Core、Mart；私人交易、筆記與 production 不在此批次範圍。

- Stage 原始 API 回應、sidecar、提交證明與隔離資料超過 7 天刪除，不以 Core 是否提交成功作為保留條件。queued／running／retrying execution 及其共用 raw 引用暫時保護；狀態不明且已超過期限的 Stage 資料可清理。Core 資料列內必要的來源／PIT 欄位不移除。
- 每個股僅保留最新 3 代完整分析，每代包含當次五 specialist。依分析日期、成果物提交時間及 execution ID 排序；持股／自選名單變動時仍按個股獨立計數。共用內容雜湊檔案在仍有保留引用時不刪。
- 只保留最新仍使用的 OOS 結果；淘汰結果及未完成、無引用且超過 7 天的 OOS／specialist 成果物可刪。現有 evaluator 的訓練模型只在記憶體中，不產生持久化權重檔；未來新增模型登錄時須同時定義 active model 的保護與淘汰，不能對未知模型路徑盲刪。
- 淘汰 execution 的原 manifest、screening、targets、membership 與不再使用的 evaluation 一起清理。保留一份有界的現存成果物引用索引；部分個股仍有保留代數時，以該索引保存引用。小型 retirement marker 防止舊 execution 重跑重新產生已淘汰報告；retired execution 不再提供完整 historical replay。
- Mart 表的分析列沿用 90 天。Core 一般行情 365 天、深度價量／估值與 benchmark 1096 天、財報 12 季；目前快照、最近 24 小時快照、named branch／tag 及**實際研究／模型／PIT／publication／execution 有效引用**受保護；未被引用的「最近 90 天每日最後快照」不再自動保留。這依 2026-10-15 使用者 FinOps 決策取代原本無差別 90 天 daily snapshot 保護；必須先確實退休沒有活躍分析用途的舊 manifest 與成果物，才能讓引用保護解除。
- Core execution manifest 超過 90 天且不再被有效成果物／作業引用才可淘汰。此步驟需 `CORE_RETENTION_FENCE_URI` 指定既有 dev Core `maintenance/retention-fences/` 下的新鮮引用清單，含 `created_at` 與 `core_snapshot_ids`；清單必須在 1 小時內產生，並與 queued／running／retrying 作業的 Core 引用合併。未提供清單時不淘汰 Core manifest，回報 `reference_fence_required`。
- 快照過期後，無存活快照引用且超過 7 天的 metadata／Avro／Parquet 孤立檔案才可清理。未加入 Core canonical dataset 清單的 `ops.batch_events_v1` 稽核事件表也須在夜間 `core-cleanup` 完成 snapshot expiration 與 orphan 清理；不能只合併稽核 Parquet 而讓舊 manifest 不斷堆積。保留引用先讀回驗證；刪除使用 generation 條件。Mart 分析與清理共用 PostgreSQL mutation lock，避免新報告寫入時被清理。

批次沿用既有 ingestion `ICEBERG_MAINTENANCE_MODE=retention-dry-run|retention-apply` 與 Mart `MART_OPERATION=retention`、`MART_RETENTION_MODE=dry-run|apply`。Mart 必須先完成引用淘汰，再以保留索引產生 Core reference fence，最後清理 Core／Stage。實際刪除量、讀回結果、deployment 與排程證據記於 operations；程式已提交不代表已部署或已清理。
