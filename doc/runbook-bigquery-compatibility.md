# B2 BigQuery compatibility probe

狀態：partial；adapter／20 項 contract tests 與三張 fixed-snapshot bounded live row fidelity 已通過；正式 shared catalog／partition scan／全 workload cutover 尚未驗收。

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

24 小時是可重建中間 table 的預設 TTL，不是 dataset／canonical GCS 到期。固定 Core external table 定義必須個別取消 expiration；training／evaluation artifacts 依既有 retention，不受此 dataset default 管理。

## Probe 邊界

- `BigQueryAnalyticsReader` 實作 B1 protocol，但未接入預設 specialist runtime；PyIceberg 保持預設。
- 只使用一般 `google-cloud-bigquery` query／job result API；不安裝 Storage Read client、不使用 dataframe／Arrow download。
- 當前 probe 僅支援既有 legacy external table：manifest metadata URI 必須是 versioned UUID metadata JSON，直接讀該檔證明 Iceberg V2 current snapshot 與 fence 一致；external source URI／region／欄位名稱須吻合，查詢後再驗 etag。不能證明則拒絕結果。
- 此路徑只作 bounded transition evidence，不是最終 shared catalog 架構；尚未實作 shared Lakehouse／REST catalog snapshot mapping，也沒有 catalog migration。
- 每張 table 必須指定 date／partition 欄位與日期範圍；symbol cohort ≤500、selected columns、累計 row bound、dry-run 與整批 bytes budget。所有 dry-run 通過後才執行實際查詢。
- 外部來源 dry-run bytes 可能只是下限；未知／0 estimate 正式記為 null，依最新授權採 execution budget 控制，不宣稱 LIMIT 可控制掃描費用。maximum_bytes_billed 套用剩餘 budget；此參數不涵蓋全部 GCS 成本，timeout／cancel 也不代表零費用。
- schema evolution 的欄位差異會拒絕；decimal／timestamp/date／null 保留 SDK native values。小 cohort 的資料／null／日期時間／source/provenance 相等已證明；native decimal precision/scale、完整 schema evolution、partition pruning 與正式 shared catalog 仍未驗收，不可宣稱 B2 CLOSED 或切 default。
- timeout cancel job；overflow／mapping drift／unknown billed bytes 不回傳 partial snapshot。adapter exception 交回呼叫者；B8 audit fallback 尚未實作。

## 可重跑命令

測試環境先安裝現有 Mart dependency，再安裝獨立 probe hash lock；不修改 Mart／serving image 的 runtime dependency。

```powershell
uv pip install --python .tmp/specialist-venv/Scripts/python.exe --require-hashes -r jobs/intelligence-mart/requirements-bigquery-probe.lock
.tmp/specialist-venv/Scripts/python.exe -m pytest tests/test_bigquery_reader.py -q
```

在具有既有 catalog environment／授權 dev credentials 的受控環境，設定 `PYTHONPATH=jobs/intelligence-mart`：

```text
python scripts/gcp/bigquery-compatibility.py --manifest fixed-core-manifest.json --config probe-config.json --output probe-evidence.json
```

預設只做 dry-run。`--execute` 僅供已授權 existing dev resources，會以相同 predicates／snapshot 做 PyIceberg row compare，不能繞過 snapshot／成本 gate。config 不保存 credentials：

```json
{
  "project": "gen-lang-client-0593591102",
  "location": "us-central1",
  "manifest_sha256": "8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8",
  "core_snapshot_id": "sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab",
  "maximum_bytes_billed": 1073741824,
  "row_limit": 1000,
  "symbols": ["2330"],
  "tables": {"core.ohlcv_v1": "gen-lang-client-0593591102.janus_analytics_dev.ohlcv_v1_b2_8549832172546885809"},
  "date_bounds": {"core.ohlcv_v1": ["trade_date", "2026-10-01", "2026-10-06"]}
}
```

Probe 保留原始完整 immutable manifest／snapshot identity，另外用 `table_scope` 明確指定此次子集；mapping 必須完全覆蓋 scope。Reader `read()` 不接受省略 manifest table 的 mapping，防止 partial probe 被當成完整 runtime input。

## 未完成驗收

connection／bucket-scoped IAM／三張 external table 與 bounded Core row compare 已依本次使用者明確授權完成。尚需正式 shared catalog exact-snapshot mapping、完整 schema evolution／native decimal coverage、partition pruning 與全 workload canary／failure/audit fallback／FinOps acceptance；這些 gate 不由小 cohort success 取代。Adapter 未成為 specialist default；TODO 保持未勾選。

官方依據：[Iceberg external tables 與型別映射](https://docs.cloud.google.com/bigquery/docs/iceberg-external-tables)、[query 權限；Storage Read permission 僅適用該 API](https://docs.cloud.google.com/bigquery/docs/query-iceberg-data)。
