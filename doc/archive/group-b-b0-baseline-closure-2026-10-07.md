# B0 Specialist Baseline 結案證據 — 2026-10-07

## 結論

B0 **CLOSED / PASS**。本輪只建立 B 組後續 reader／BigQuery canary 可重複比較的 PyIceberg baseline，不代表 B1～B9 已完成。

沒有建立或啟用 BigQuery／BigLake resource/API，沒有擴大 IAM，沒有重做 A 組 migration／backfill／serving／UI。

## 實作與部署

- baseline implementation：`4dcb0309d9a8db525d8599e0c51d6b65bd856f45`
- Deploy dev workflow：`37488522467`
- 現有 `janus-intelligence-mart` runtime 由 deployment readback 證明使用上述 implementation SHA。
- B0 增加 bounded telemetry：input row count、rows by dataset、scan planning evidence、screening/evaluation artifact hash、elapsed、peak RSS；未知 GCS bytes 保持 `null`。
- `MART_OPERATION=specialist-baseline` 只允許既有 dev project／bucket，要求 OOS evaluation，且 `MART_AI_ENABLED=false`。

## Failure → Recovery evidence

第一次 workflow run `37490232648` 在執行 baseline workload 前失敗。原因是 workflow 從錯誤的 Cloud Run Job JSON path 讀取 `JANUS_GIT_SHA`，得到 missing；因此 runtime SHA gate **fail closed**，沒有 baseline workload 被誤執行。

commit `8b7fa5465f1516c00b63b2dad913f19d72a0dc18` 將 env readback path 修正為目前 Cloud Run Job 的實際結構，第二次才執行 workload。

這段失敗不計入 baseline performance；它只作 workflow guard／recovery evidence。

## 成功 live baseline

- GitHub Actions run：`37490477263`
- job：`112361575980`
- Cloud Run execution：`janus-intelligence-mart-9bwkq`
- specialist execution_id：`3ece7127-9c04-4e00-aff3-21de583bcf36`
- analysis_as_of：`2026-10-06`
- Core snapshot id：`sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`
- Core snapshot URI：`gs://gen-lang-client-0593591102-dev-core/executions/17b091be-c454-4fea-b5de-b16c0a9c8c6c/core-snapshot.json`
- Core snapshot raw-byte hash：`sha256:8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8`

## 輸入與 scan evidence

| Dataset | Rows | Planned files | Symbol filter |
|---|---:|---:|---|
| benchmark | 752 | 43 | no |
| events | 329 | 4 | yes |
| financials | 15,756 | 77 | yes |
| ohlcv | 70,863 | 94 | yes |
| valuation | 4,953 | 99 | yes |
| **Total** | **92,653** | **317** | — |

每個 dataset 都由 manifest 指定的 immutable Iceberg snapshot fence 讀取。workflow JSON serialization 將大型 table snapshot ID 顯示成 scientific notation，因此本結案以 Core snapshot id/hash 作主要固定 identity，不從 log 反推整數。

`planned_scan_bytes=null`、`actual_gcs_read_bytes=null`。這表示該次 runtime 沒有取得可信 byte telemetry，不代表 0 bytes。

## Screening / evaluation

- screening_count：**500**
- latest market date：`2026-10-06`
- EOD missing：**1 / 500 = 0.2%**，accepted
- 5D history missing：**39 / 500 = 7.8%**，accepted
- 20D history missing：**39 / 500 = 7.8%**，accepted
- 60D history missing：**39 / 500 = 7.8%**，accepted
- 120D history missing：**39 / 500 = 7.8%**，accepted
- `auto_fail=false`
- screening output hash：`sha256:39b25796ac9d8e13b9bd2925e06a4fe916ba25664cb51cf7b49f5806b904ecc9`
- evaluation output hash：`sha256:7f35ef1206256c00ad8735d92b9c3202031db0737a8235ca8d5f163810a7829c`

## Performance baseline

- elapsed：**725.726 seconds**（約 12 分 6 秒）
- peak RSS：**694.7 MiB**
- LLM API tokens：**0**

這是「固定 Core snapshot + 500 檔 screening + OOS evaluation」整輪 baseline；不是單純讀取 92,653 rows 的 I/O 時間。

## B0 completion boundary

B0 完成的是 baseline／telemetry／runtime evidence。它**不勾選** TODO 的「抽出 exact-snapshot analytics reader」，因為那是 B1；也不代表 BigQuery compatibility、每日 500 排程、五 specialist、cache、月度批次或 B9 OOS acceptance 已完成。

baseline request 在結案 commit 中改為 `enabled=false`，避免日後編輯 request 檔時意外再跑。下一個工程步驟：**B1 Exact-snapshot reader**。
