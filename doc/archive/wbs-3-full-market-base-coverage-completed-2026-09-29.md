# WBS-3-FULL-MARKET-BASE-COVERAGE 驗收結案（2026-09-29）

範圍是有效 TWSE 上市週量 500 檔，不是全部上市股票。使用者指定各必要資料集缺值率嚴格低於 10% 即可通過缺值驗收；原始 runtime `partial`、逐檔 `missing` 與來源限制仍照實保留。

## 整批資料與品質

- 2026-09-24 資料日的既有 dev Job `janus-ingestion-core-8xhlx` 於 2026-09-28 完成，GCP task 1/1 成功，11 個 request、9 個 staged、1 個合法 empty、0 個 source failure；Core created 4,384／updated 14,826／reused 4,630。應用耗時 119,032 ms，Cloud Run wall time 242.38 秒。Job Ready，1 task／1 parallelism／1 vCPU／2 GiB／1800 秒 timeout／最多 1 次 retry。
- 不可變 inventory：`gs://gen-lang-client-0593591102-dev-core/executions/21830a1b-709f-421d-84ed-036700764182/coverage-inventory.json`，SHA-256 `39f155a6e48de955bde02ed555ab9a60cd754a5f7a8ec09f100200ab8dc1ec4e`。逐項為 OHLCV 499/500（0.2% 缺）、TAIEX 1/1（0%）、valuation 498/500（0.4%）、institutional 499/500（0.2%）、MOPS financials 499/500（0.2%）、financing 498/500（0.4%）、securities lending／short 499/500（0.2%）、day trading 482/500（3.6%）。每項必要資料集均嚴格低於 10%；inventory 原狀仍是 `partial`，缺檔名單與 provenance 不變。
- 官方同日批次唯讀核對支持 `2601`／`9105` 等缺檔是報表來源缺值，不從其他 dataset 推補。FinMind financials 因無合規 market batch endpoint 繼續標 `blocked`，不算成官方資料集 500/500。Stage 與 Core 按 execution 前綴隔離；Stage 該 execution 前綴 28 個物件、8,409,134 bytes，未見 quarantine 物件；summary DQ event 0。`dq=[]` 只代表該次沒有記錄的 DQ event，不能推論每個欄位均通過獨立掃描。Core manifest／inventory 保留 hash 與來源。
- 既有 5 檔 canary 的三個 distinct trading days 已在先前 WBS-3-ACCEPTANCE 以自然 Scheduler 達成 3/3；本次 500 檔 replay 是後續擴大範圍的實際路徑。一次性 replay env 已還原，常態 Scheduler 仍 enabled。

## 關注股、持股與隔離

- 2026-09-27 authenticated dev User App：有效名單內 `2409` 可加入，名單外 `1103` 被後端拒絕，測試項已移除。2026-09-29 再以 Admin 將有效第 4 版暫時換成第 5 版（`5876` 出、`9911` 入），兩版各 500 檔；第 5 版不含 `5876` 時，既有 `5876` 關注仍為 active。第 6 版還原（`9911` 出、`5876` 入）；唯讀 PostgreSQL 比對第 4／6 版成員對稱差為 0，且第 4／5／6 版均各 500 檔。驗收新增的 `5876` 關注已移除，原有 `2330` 保留。
- `janus-private-pipeline-tr7rv` 於 2026-09-29 `Completed=True`，checkpoint 79；dev User App 的真實 `5876` 持股在估值日 2026-09-24 顯示正式 Core 行情價 48.95、行情日 2026-09-24、`可用`，aggregate 恢復發布。`CorePriceReader` 以持股 symbol 讀持久化 OHLCV，查價不以 500 membership 過濾。第 5 版期間沒有另跑 Private Pipeline，因此不宣稱取得該版本下的新估值；名單外後續正式行情收集仍因沒有 enabled symbol-scoped OHLCV config 而回報 `portfolio_coverage_requested=1`、`accepted=0`、`status=partial`、`missing_reason=no_eligible_enabled_symbol_scoped_ohlcv_config`。這是明示的 blocked／missing 診斷，不是可用行情或 1/1 coverage。
- Private Pipeline 使用既有 1 task／1 parallelism／1 vCPU／512 MiB／1800 秒 timeout／最多 1 次 retry；此次 wall time 234.94 秒。修復 Iceberg `large_string` 寫入的 commits `59354c1`、`d9baee4` 已通過本機 35 個 targeted tests，dev workflow `36544027845` 的 API tests／API 與 Private Pipeline deploy 全部成功。測試與 dev runtime 的 owner isolation、Private Mart 與 Core 分離仍依原契約；本次未將私人持股資料寫入 control plane，僅記錄去識別化 symbol 需求與 bounded 診斷。

## 成本與完成語意

使用既有 dev Job、服務與 bucket；沒有新增 GCP 資源、調高本次資源上限或部署 production。以上列出 task 數、CPU／記憶體、執行秒數與 Stage bytes，構成這次執行的 bounded 使用量；未取得實際帳單金額，不宣稱零費用。整批必要官方資料的缺值依使用者指定門檻通過，WBS 的有限 coverage 驗收結案；immutable inventory 的 `partial`、逐檔 `missing`、FinMind `blocked` 與離榜持股 future-feed `partial` 繼續維持原樣，不改寫成全數成功。

更完整的 execution 與歷史證據見 [`operations-and-testing.md`](../spec/operations-and-testing.md)。
