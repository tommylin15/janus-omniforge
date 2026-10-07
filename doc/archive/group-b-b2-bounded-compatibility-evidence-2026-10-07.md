# B2 bounded compatibility evidence — 2026-10-07

此 checkpoint 的 bounded probe 已通過；B2 整體仍 partial，不代表 shared catalog 或 workload cutover 已完成。

## CI／deployment／runtime readback

- Implementation SHA：`c97aa885d308183816af70e0f83cbb5a5fa3c1ec`，已 push 到 `main`。
- [BigQuery compatibility contracts run 37575746360](https://github.com/tommylin15/janus-omniforge/actions/runs/37575746360)：**20 PASS**，acceptance script py_compile 通過。
- [Deploy dev run 37575746520](https://github.com/tommylin15/janus-omniforge/actions/runs/37575746520)：Mart targeted tests **106 PASS**（7 個既有 LightGBM feature-name warnings）；deploy／verify 全部 success。
- 既有 specialist smoke execution `janus-intelligence-mart-95j7x` 成功；未因此把 BigQuery 切成 default。
- Cloud Run Job readback Git SHA 與 implementation SHA 一致；image digest=`sha256:742fa102ae6b625ed5685893e39b015f78f6349289b9c97488a6ae4e6c118236`；資源仍 **1 CPU／1 GiB**。
- BigQuery SDK 使用獨立 probe hash lock，沒有加入 Mart serving image 的預設依賴，也沒有 Storage Read API client／readsessions 需求。
- 後續文件整理 commit 不改 runtime code。模型架構問題本輪只提供建議；沒有啟動 BigQuery ML training、新增 training backend 或變更 specialist 模型契約。

## 既有 dev 資源

2026-10-07 唯讀確認 `bigquery.googleapis.com`／`biglake.googleapis.com` 已啟用；Core bucket `gen-lang-client-0593591102-dev-core` 位於 `US-CENTRAL1`。使用者明確要求建立 dataset 後，已建立 `gen-lang-client-0593591102.janus_analytics_dev`，readback location=`us-central1`、defaultTableExpirationMs=`86400000`。

使用者另明確授權 bounded dev probe 後，已建立 `projects/131494961796/locations/us-central1/connections/janus_core_probe`，其 service account `bqcx-131494961796-mt30@gcp-sa-bigquery-condel.iam.gserviceaccount.com` 僅新增 dev-core bucket 的 `roles/storage.objectViewer`。以下 existing external table 定義皆已 readback `us-central1`、`expires=null`、固定 B0 manifest 的 metadata URI，沒有 native data copy：

- `benchmark_v1_b2_5084459386493044934`
- `ohlcv_v1_b2_8549832172546885809`
- `financials_v1_b2_801346769573568770`

固定原始 B0 manifest raw-byte SHA256=`8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8`，Core identity=`sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`。三張 external schema 名稱與各自 pinned Iceberg metadata schema 一致；第一個 bounded dry-run 回報 0 bytes，當時 guard 拒絕 live query。此 0 為未知估算下限，不是 0 掃描成本。

使用者後續明確允許未知估算的 bounded live probe，並確認自動路徑採 **整次 execution ≤1 GiB（1,024 MiB）**，不是每 query 1 GiB。最新 adapter 允許 unknown estimate（保留 null），每 query 套用剩餘 execution budget、timeout ≤60 秒；已知估算超限、未知 billed bytes 或累計超限仍停止。這是最新明確指示，取代本輪初始「未知估算即停」策略；不取消 snapshot／fidelity／cutover gates。

本次 live 使用較小的 **100 MB 整批 budget**、日期 `2026-10-01`～`2026-10-06`、symbol `2330`（benchmark 無 symbol filter），一般 query/result API；逐列 multiset 比對包含原始數值字串、source/provenance、null、DATE／TIMESTAMP：

| Dataset | PyIceberg / BigQuery rows | Null cells | Processed bytes | Billed bytes | BigQuery elapsed / PyIceberg read |
|---|---:|---:|---:|---:|---:|
| benchmark | 4 / 4 | 4 | 868 | 10,485,760 | 3.375 s / 8.766 s |
| ohlcv | 4 / 4 | 4 | 505,468 | 10,485,760 | 3.282 s / 7.391 s |
| financials | 312 / 312 | 2,064 | 567,220 | 10,485,760 | 3.640 s / 23.953 s |

全部 row multisets 相等，總 processed=1,073,556 bytes、billed=31,457,280 bytes。這是小 cohort 的 controlled GCP dev evidence，不是 Cloud Run 整輪／liquid-500 效能證明。Core 數值欄目前多為 STRING，不能以本次結果冒充 native DECIMAL precision/scale 的 live coverage；unit contract 有 native Decimal／date／timestamp／null 保留驗證。Peak RSS、GCS read bytes、partition pruning 仍 unknown。

Live artifact 已以 generation=0 保存到 `gs://gen-lang-client-0593591102-dev-mart/acceptance/specialists/b2-fixed-snapshot-20261007.json`，GCS readback SHA256 與本機輸出一致：`7192dee25c5062deb023b8d5d7587525c5ba2df6834b8f18c3cdb3e14beb834c`。Artifact 記錄的是實際執行時的 100 MB 人工 probe；後續預設 budget 調整為 1 GiB，不改寫這份歷史 evidence。
