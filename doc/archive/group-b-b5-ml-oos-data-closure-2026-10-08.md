# B5 ML / OOS data path 結案 — 2026-10-08

狀態：**B5 CLOSED / PASS**，僅結案 ML/OOS **data path**；不代表五 specialist 模型 OOS 品質、monthly retrain/reconciliation、B6 cache、B8 canary/fallback/FinOps 或 B9 full acceptance 已完成。B4 仍維持 CLOSED，PyIceberg 仍為 default。

## GitHub 與 dev 真實驗收

- B5 source/heartbeat/bounded timeouts：`8777f8c`。BigQuery job error/code 與 `job_retry=None`：`55319a6`。Shared Iceberg 直接 `EXPORT DATA` 在 BigQuery 回報 `internalError / HTTP 500`，對應 live run [#37705930155](https://github.com/tommylin15/janus-omniforge/actions/runs/37705930155)。改採 `CREATE TEMP TABLE` → native `EXPORT DATA` → `DROP TABLE`：`c411fc0`。Cloud Build evidence copy `gcloud` entrypoint 修正：`051591e`。
- 最終驗收：[B5 live acceptance #37706568819](https://github.com/tommylin15/janus-omniforge/actions/runs/37706568819) **SUCCESS**；install / targeted tests / deployed-Mart-image confirmation / GCS export / live Mart readback 五項 markers **全部 true**。Cloud Build `a178b778-998e-437c-82d6-7674ea0d4b04` SUCCESS；最新 B5 targeted tests **13 PASS**，Mart regression **129 PASS / 7 warnings**，最新 dev deploy workflow [#37706569206](https://github.com/tommylin15/janus-omniforge/actions/runs/37706569206) success（runtime code 無變更，沿用已驗證 Mart image）。
- Live Mart execution `janus-intelligence-mart-bb25f` **Completed / succeededCount=1**；真實 `ml-oos-data-acceptance` readback `status=pass`，`llm_api_tokens=0`、`ceo_triggered=false`、`storage_read_api_used=false`。
- 機器可讀權威 evidence：[B5 live evidence](group-b-b5-live-acceptance-recovery-v4-2026-10-07.json)，由 CI `[skip ci]` commit 至 main；不是人工編造的 benchmark。

## 核對資料集 identity

- Core snapshot：`sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`。
- `analysis_as_of=2026-10-06`；manifest：`gs://gen-lang-client-0593591102-dev-mart/ml-oos-data/v1/70e0dc3b7d4a6ab3a0437bd0c633de56986bc72b6d8b14e5d85861f0771164a6/manifest.json`。
- Dataset content hash：`sha256:16100c1ee0403e4846ef866c59299e4b58f85aa88d7fe4e5647c418112452799`；manifest SHA256：`sha256:e4828cc907ed5e76e40ad114fd55ddf4161509a61ea18daebc48f4499411f7e9`。
- 10,978 rows，499 symbols，Parquet shard 1，export 533,945 bytes；讀回 first_trade_date=2026-03-19、last_trade_date=2026-09-03。export 與 deployed Mart 消費端 row count / bytes / identity hash / Core snapshot 完全一致。
- 首輪 materialization 真實 BigQuery jobs：count-reduced 10,485,760 billed bytes、CREATE TEMP + EXPORT + DROP script 20,971,520 billed bytes；**合計 31,457,280 bytes（30 MiB）**，遠低於整次 1 GiB 預算。每個 query job 60 秒上限，SQL script 5.84 秒；GCS manifest 在寫後讀回並保證無覆寫。最終成功驗收沿用 immutable dataset（`reused=true`、**本輪 BigQuery billed 0**）；不可把兩輪費用相加後說成「本輪 0」或把首輪錯認為 0。
- BigQuery dry-run estimate=0 不代表零掃描、零費用；用已完成 job `totalBytesBilled` 作成本證據。BigQuery staging temporary table 可能有短期 storage 計費；成功 path 明確 DROP，失敗不能默認零費用。

## 保留約束與後續

- Core catalog fixed pointer 前後一致，immutable output SHA256 驗證，禁止 canonical write、跨 owner private field、future label leakage、Storage Read API；缺值及不足樣本維持 unknown/insufficient。
- B5 僅提供 versioned ML/OOS data path，未證明模型 champion、全歷史 membership、多模型 OOS 品質或 monthly 10:30 Scheduler 已按目標觸發。
- **下一步 B6：擴充 BigQuery-derived ML artifact identity 與 no-change pre-query reuse，驗證 selective invalidation 和 old artifact immutability。** B4 已完成的 Deep Coverage 五 specialist dirty/reuse 不應重做。
