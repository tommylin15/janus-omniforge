# B2 BigQuery compatibility probe

狀態：B2 compatibility CLOSED / PASS；shared catalog mapping、native decimal/schema evolution、真實 Core partition pruning 已通過。Workload canary/default cutover 仍待後續驗收；PyIceberg 維持預設。

## 既有 dev 資源

使用既有 dev project `gen-lang-client-0593591102`、region `us-central1`、dataset `janus_analytics_dev`、connection `janus_core_probe`，只讀 dev-core bucket。資源／IAM 與 bounded live compare 的實際建立、授權及 readback 證據見 [B2 bounded checkpoint](archive/group-b-b2-bounded-compatibility-evidence-2026-10-07.md)。執行前應重新 readback table metadata mapping／region／expiration；不得自行啟用新 API、擴 IAM 或遷移 canonical catalog。

目前使用者核准的策略：unknown estimate 保留 null；整次 execution 上限 1 GiB（1,073,741,824 bytes），每 query 只使用剩餘 budget，timeout 上限 60 秒。Snapshot／fidelity／cutover gates 保留。

24 小時是可重建中間 table 的預設 TTL，不是 dataset／canonical GCS 到期。固定 Core external table 定義必須個別取消 expiration；training／evaluation artifacts 依既有 retention，不受此 dataset default 管理。

## 2026-10-07 B2 結案

本機既有 principal 完成 register，復用 `janus_core_dev`（primary location US、storage region us-central1、end-user credentials），本輪沒有修改 IAM。Live readback 修正舊暫停文件的 catalog 未建立說法。

三張固定 B0 metadata URI 在 `b2_core_fixed_20261007` 的 catalog mapping 精確相等；dev-mart acceptance table 的 native DECIMAL(20,4)/add-column/null 通過；真實 ohlcv 窄／寬日期 processed bytes 為 42,678/1,602,600，query 前後 pointer 相同。9 jobs 共 60 MiB billed bytes，immutable GCS evidence readback PASS。完整 evidence 見 [B2 結案](archive/group-b-b2-closure-2026-10-07.md)。

可重跑完整驗收（既有 dev 授權與 credentials；本機 Windows 使用 gcloud.cmd）：

```text
python scripts/gcp/b2-lakehouse-acceptance.py --output b2-evidence.json
```

僅接續 Core pruning 時，使用相同 output 與其已保存的 `.jobs.json`：

```text
python scripts/gcp/b2-lakehouse-acceptance.py --output b2-evidence.json --core-pruning-only
```

帳本保留已消耗 bytes，整輪上限 1 GiB；pending/unknown billed bytes 必須先 readback job 才能繼續。Mapping 已存在時精確驗證，禁止 overwrite；測試 table 使用 `field-id`、`day` transform、`trade_date_day` 名稱，automatic table management=false，DML 僅在 acceptance table 啟用。

BigQuery contract CI 在 push 時維持執行，包含本次 3 項 acceptance script checks。一次性 non-register live workflow 改為 workflow_dispatch，避免腳本 push 再建立測試 table 或暫時修改 bucket IAM；需要重跑時依當次 dev／IAM 授權執行。

## Probe 邊界

- `BigQueryAnalyticsReader` 實作 B1 protocol，但未接入預設 specialist runtime；PyIceberg 保持預設。
- 只使用一般 `google-cloud-bigquery` query／job result API；不安裝 Storage Read client、不使用 dataframe／Arrow download。
- 當前 probe 僅支援既有 legacy external table：manifest metadata URI 必須是 versioned UUID metadata JSON，直接讀該檔證明 Iceberg V2 current snapshot 與 fence 一致；external source URI／region／欄位名稱須吻合，查詢後再驗 etag。不能證明則拒絕結果。
- 此路徑只作 bounded transition evidence，不是最終 shared catalog 架構；shared Lakehouse／REST catalog exact mapping 已由獨立 live acceptance script 證明；此 adapter 尚未接入 shared catalog，沒有 canonical catalog migration。
- 每張 table 必須指定 date／partition 欄位與日期範圍；symbol cohort ≤500、selected columns、累計 row bound、dry-run 與整批 bytes budget。所有 dry-run 通過後才執行實際查詢。
- 外部來源 dry-run bytes 可能只是下限；未知／0 estimate 正式記為 null，依最新授權採 execution budget 控制，不宣稱 LIMIT 可控制掃描費用。maximum_bytes_billed 套用剩餘 budget；此參數不涵蓋全部 GCS 成本，timeout／cancel 也不代表零費用。
- schema evolution 的欄位差異會拒絕；decimal／timestamp/date／null 保留 SDK native values。小 cohort 的資料／null／日期時間／source/provenance 相等已證明；native decimal precision/scale、add-column evolution/null、Core partition pruning 與 shared catalog mapping 已由獨立 live script 驗收；不得因此切 default 或宣稱所有 workload 已完成。
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

## 後續驗收

B2 compatibility spike 已結案。Shared catalog adapter/workload 接線、全 workload canary／failure/audit fallback／FinOps acceptance 留待 B3 及後續項目；不得以 bounded compatibility success 取代。Adapter 未成為 specialist default。

官方依據：[Iceberg external tables 與型別映射](https://docs.cloud.google.com/bigquery/docs/iceberg-external-tables)、[query 權限；Storage Read permission 僅適用該 API](https://docs.cloud.google.com/bigquery/docs/query-iceberg-data)。


## B5 ML/OOS direct export 500 與 staged workaround（2026-10-08）

- 2026-10-08 B5 live diagnostics 確認 Core manifest、shared catalog pointer、GCS listing、BigQuery dry-run 與 reduced count 全部成功；直接 `EXPORT DATA ... AS SELECT ... FROM shared Iceberg catalog` 的 query job 回傳 `internalError / HTTP 500`。單純延長等待或 SDK 隱式 job retry 都不構成修復。
- Google BigQuery 官方 external-table 限制指出不可直接對 external table 執行 export job，應先儲存 reduced query results 再 export。B5 改採 **同一 bounded BigQuery SQL script**：`CREATE TEMP TABLE b5_export_reduced AS <bounded select>` → 從 `_SESSION.b5_export_reduced` 執行 `EXPORT DATA` → `DROP TABLE`。僅使用 BigQuery 自管臨時衍生資料，不建立永久 dataset/table、不變更 Iceberg canonical、default PyIceberg 或 PostgreSQL serving，不使用 Storage Read API。
- GCS 仍輸出 `ml-oos-data/v1/<identity-hash>/part-*.parquet` 與 immutable manifest；Core pointer 必須先後一致。BigQuery 所有 BigQuery query job 維持單 job 60 秒、整次 execution 1 GiB billed bytes 上限（unknown fails closed），腳本子工作 readback 與 stage heartbeat 必須保留；如 script 失敗，清查臨時表／部分 Parquet、billed bytes 與不可變 prefix，禁止將 partial 當成 full success。
- **BigQuery TEMP TABLE 可能產生暫時儲存費用**；本路徑不建常駐計費資源，script 正常時明確 DROP，失敗由 BigQuery 自動在 24h 內移除。任何增大資源、提高預算或 IAM 權限均另需授權。實際 live export/readback 必須由 CI/runtime evidence 確認，文件與程式修補不能自動標 B5 CLOSED。
- 官方資料：[external tables limitations](https://docs.cloud.google.com/bigquery/docs/external-tables)、[multi-statement TEMP TABLE 與儲存計費](https://docs.cloud.google.com/bigquery/docs/multi-statement-queries)。
