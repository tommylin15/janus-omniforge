# TODO 完成紀錄（2026-09-15：WBS-3-ACCEPTANCE）

## Scheduler 5-stock canary 3/3

- 第三交易日資料日：`2026-09-14`（Asia/Taipei）；Scheduler execution：`janus-ingestion-core-c995d`；control execution：`3ee7a128-3a69-4704-8563-2def733032ad`。
- Scheduler：`janus-ingestion-daily`，`ENABLED`、`30 7 * * *`、`Asia/Taipei`；第三次執行於 `2026-09-14T23:30:03Z` 建立，`2026-09-14T23:32:45Z` 成功完成，Cloud Run status `Completed=True`、`succeededCount=1`。
- 5 檔固定 symbols：`1102`、`2327`、`2330`、`2381`、`4958`。8 個核准 source／dataset work items：`requested=8`、`staged=7`、`skipped=5`、`failed=0`、`empty=0`；5 個 FinMind symbol 因 `official_source_fresh` 合法跳過，因此 `expected=12`、`received=12`、`missing=0`。
- 8 個核准 source／dataset 狀態均為可接受成功：`taiex`、`tpex-benchmark`、`twse-valuation`、`twse-institutional`、`mops`、`twse-events`、`twse-market-activity` 實際成功寫入；`finmind` 以 official-source-fresh cache hit 成功略過，沒有 failed／unavailable 狀態。
- Core ready evidence：`as_of=2026-09-14`、`row_count=1982`、`coreSnapshotHash=sha256:64cb0ef47c9102cf0b8c689e9b709acbe018919105beaef6eaedfec929638f98`、snapshot id `sha256:9834993558b99526296cdd6dece75ff654723a8136aac0b15967971f60c7a642`；Core snapshot artifact 顯示 6 個 incremental table 的 rows，並無 OHLCV `null_profile` 欄位；本次沒有 DQ failure 或 quarantine。
- Cost／resource evidence：既有 immutable image `us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/ingestion-core@sha256:c5fc66a0ed0d395d07b66b96e6baedcf9739ff94328cb5eb4504ddd2889849f1`；1 task、1 vCPU、1 GiB、timeout 1800 秒、maxRetries 1；本次 execution 約 2 分 22.75 秒，未建立或擴大 GCP 資源，未觸發全市場抓取。

## 尚未完成

- Full enabled market 尚未執行；需另行依既有 market-scope 單次抓取／symbol fan-out 規則驗收。
