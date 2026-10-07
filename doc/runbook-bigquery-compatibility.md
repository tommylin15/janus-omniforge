# B2 BigQuery compatibility probe

狀態：partial；adapter／20 項 contract tests 與三張 fixed-snapshot bounded live row fidelity 已通過；正式 shared catalog／partition scan／全 workload cutover 尚未驗收。

## 既有 dev 資源

使用既有 dev project `gen-lang-client-0593591102`、region `us-central1`、dataset `janus_analytics_dev`、connection `janus_core_probe`，只讀 dev-core bucket。資源／IAM 與 bounded live compare 的實際建立、授權及 readback 證據見 [B2 bounded checkpoint](archive/group-b-b2-bounded-compatibility-evidence-2026-10-07.md)。執行前應重新 readback table metadata mapping／region／expiration；不得自行啟用新 API、擴 IAM 或遷移 canonical catalog。

目前使用者核准的策略：unknown estimate 保留 null；整次 execution 上限 1 GiB（1,073,741,824 bytes），每 query 只使用剩餘 budget，timeout 上限 60 秒。Snapshot／fidelity／cutover gates 保留。

24 小時是可重建中間 table 的預設 TTL，不是 dataset／canonical GCS 到期。固定 Core external table 定義必須個別取消 expiration；training／evaluation artifacts 依既有 retention，不受此 dataset default 管理。

## 2026-10-07 暫停 checkpoint

使用者已明確授權建立可計費 Lakehouse runtime catalog，但於 2026-10-07 15:51（Asia/Taipei）要求暫停 B2、先回寫進度。**目前尚未建立 catalog，也尚未修改 IAM。**

Latest live preflight：

- Cloud Build default identity：`biglake.catalogs.create=true`、`biglake.catalogs.list=true`、`biglake.tables.register=false`。
- project IAM：可 `getIamPolicy`，不可 `setIamPolicy`；因此不能由同一 automation identity 自動補 project-level register permission。
- dev-core bucket IAM：可 `getIamPolicy`／`setIamPolicy`；object get/list 可用，本輪尚未做 bucket IAM mutation。
- 固定 B0 Core fences 已重新 readback；manifest SHA256 仍為 `8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8`。
- GCS acceptance evidence path PASS：`janus-ci` 可讀 fixed Core manifest，也可對既有 dev-mart acceptance prefix 做 generation=0 immutable write/readback。
- B2 仍 **PARTIAL / PAUSED**；shared-catalog exact-snapshot mapping、native decimal/schema evolution、partition pruning 三項尚未完成。

暫停與下次接續入口見 [B2 paused checkpoint](archive/group-b-b2-paused-checkpoint-2026-10-07.md)。再次繼續時，不重跑已通過的 20 contract tests、106 Mart regression、320-row fidelity、Core fence readback 或 GCS evidence path。

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
