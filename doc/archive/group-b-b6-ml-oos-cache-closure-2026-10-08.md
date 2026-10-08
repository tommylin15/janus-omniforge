# B6 Dirty dependency / BigQuery-derived ML/OOS cache — 結案

狀態：**CLOSED / PASS（2026-10-08）**。範圍限 B5 Parquet derived ML/OOS input cache，不重做 B4 五 specialist cache，不包含 B7 排程、B8 fallback/FinOps、B9 模型 OOS 品質。

## 原始實作及修復
- [Implementation `8ba064c`](https://github.com/tommylin15/janus-omniforge/commit/8ba064c30184b7bff4225cd155f915373f4b5d8d)：`b6-ml-oos-dirty-v1` fingerprint 精準追蹤 `core.ohlcv_v1` fixed snapshot/pointer、date bounds、schema/query/feature/model/label/cohort 版本。非依賴表造成的 global Core ID 變更允許 reuse，但不得篡改舊 artifact 的 `core_snapshot_id`；結果另列 requested/artifact IDs。
- 查 BigQuery 前驗證原 manifest、Parquet object SHA256/bytes、row/count bounds、retention、catalog pointer；128 manifests/240 秒限制；新增 SQL source 未納入 allowlist 則 fail closed。不得使用 Storage Read API、不得改 canonical；miss 保持 B5 1 GiB 整輪 billed bytes 上限、每 query 60 秒限制。
- 初版 CI [#37708629894](https://github.com/tommylin15/janus-omniforge/actions/runs/37708629894) 與 acceptance [#37708629743](https://github.com/tommylin15/janus-omniforge/actions/runs/37708629743) 因測試修改 analysis_as_of 而未同步 date_bounds 上界造成 1 failed。[`59035e6`](https://github.com/tommylin15/janus-omniforge/commit/59035e6d8de1b46ebc3f62cdac1b0331153ce318) 修正測試日期 fence，原失敗紀錄保留。

## CI、dev runtime evidence
- [Deploy dev CI #37708769385](https://github.com/tommylin15/janus-omniforge/actions/runs/37708769385) **SUCCESS**；Mart regression **137 passed／7 warnings**。本次只改 exporter/test，`deploy-mart` step **SKIPPED**；沒有把 skipped 偽報成部署完成。
- [B5/B6 live acceptance #37708769182](https://github.com/tommylin15/janus-omniforge/actions/runs/37708769182) **SUCCESS**；install/tests/Mart deployed image confirm/Cloud Build export/Cloud Run Mart readback 五 markers 全 True。新版本 `59035e6` 的 evidence 由該 workflow 回寫 [source JSON](group-b-b5-live-acceptance-recovery-v4-2026-10-07.json)。
- `reused=true`、`cache_hit_verified=true`、`reuse_reason=exact-identity`、`bigquery_jobs=[]`、`total_billed_bytes=0`、`storage_read_api_used=false`。來源指紋 `sha256:5881ab7ccff96e13f92f5d7133389c5ae78eb859481f2b9bccc0717a18004773`。
- Parquet dataset：**10,978 rows／533,945 bytes**；`dataset_content_hash=sha256:16100c1ee0403e4846ef866c59299e4b58f85aa88d7fe4e5647c418112452799`，Core `sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`，`analysis_as_of=2026-10-06`。GCS manifest `gs://gen-lang-client-0593591102-dev-mart/ml-oos-data/v1/70e0dc3b7d4a6ab3a0437bd0c633de56986bc72b6d8b14e5d85861f0771164a6/manifest.json`。
- Cloud Run execution `janus-intelligence-mart-p8wjs` 的 row count、size、content hash、Core ID 與 exporter 全相等；`llm_api_tokens=0`、`ceo_triggered=false`。

## 未被本次證明的項目
- Live 真實驗證為 **相同 fixed global Core snapshot** 下的 zero-query cache hit。global Core ID 變更但 OHLCV 相同的 reuse、來源/version/date dirty selective invalidation **僅由 targeted tests** 驗證，沒有修改真實 Core 製造 dirty injection。
- BigQuery error→PyIceberg audit fallback/FinOps 比較留 **B8**；月度第一個週六 10:30 Asia/Taipei effective scheduling/reconciliation 留 **B7**；五 specialist 真正 OOS 模型品質與 champion 留 **B9**。PyIceberg 仍維持 default reader。

**下一步 B7。**
