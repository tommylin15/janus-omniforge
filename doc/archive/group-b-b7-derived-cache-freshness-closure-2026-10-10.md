# B7 derived-cache freshness — current Core 結案（2026-10-10）

**狀態：CLOSED／PASS（本次 source-pinned dev derived cache freshness）。** B7 月度 retrain／OOS 本已 PASS，本次沒有再次派送、重新訓練或修改原始 2026-10-10 月度 execution。B8 已獨立結案，B9 五 specialist 模型品質仍 NOT VERIFIED。

## 變更與安全邊界

- 新增 [fresh Core cache materializer](../../scripts/gcp/b7-refresh-derived-cache.py) 與 [獨立驗收 workflow](../../.github/workflows/b7-derived-cache-freshness.yml)，沿用 B5/B6 的 immutable ML/OOS schema、PyIceberg exact-snapshot reader、source authorization／label maturity 驗證及 B7 `monthly_reconciliation.reconcile_monthly_cache`。
- 選最近七天的最新 Core snapshot（實際同 B7 月度 source），固定 raw-byte SHA-256、OHLCV Iceberg metadata/snapshot ID、日期範圍與 feature/model/version；每次 materialize/receipt 前後重新檢查 latest Core 不漂移。
- 只讀取**原本**月度 `specialist-manifest.json` 的 target 及 25 個 active specialist refs；不派送 `specialist-retrain`、不覆寫原始 `monthly-reconciliation.json`（其 `status=partial` 是當時快取尚 historical 的真實歷史）。
- B6 Parquet shard／manifest 與 B7 acceptance receipt 均採 GCS create-only；acceptance writer 僅允許 `acceptance/b7-cache-freshness/<64 hex>.json`，不放寬 B5 原有 `ml-oos-data/v1/` write allowlist。
- 不操作 canonical Iceberg／PostgreSQL、不使用 BigQuery Storage Read API、不切 BigQuery default、不執行任何 BigQuery query、不呼叫 CEO／LLM、不自動 promotion。

## Live evidence

- 首輪 [#38056418752](https://github.com/tommylin15/janus-omniforge/actions/runs/38056418752)：相依環境及 targeted tests PASS，對新 Core 的 Parquet／manifest 已完成；獨立 B7 receipt 創建被原 B5 前綴限制拒絕，workflow **FAIL**，不可冒充完整 PASS。修正採 B7 專用 create-only writer，不更動 B5 既有 writer 範圍。
- 最終 [#38056677635](https://github.com/tommylin15/janus-omniforge/actions/runs/38056677635)，source SHA `c32c1bc05a54b98f340ccf7f9b36e70c66eec38b`：**GitHub Actions SUCCESS，34 targeted tests PASS**，GCP WIF 真實讀回既有 Core／Mart GCS、Parquet、manifest、reconciliation 與 acceptance receipt，全部步驟 PASS；artifact `b7-derived-cache-freshness-38056677635`。
- 固定 Core snapshot ID：`sha256:687fae3ea802ef255bd33ecf5e21a6d25801c467f8836181dae9fc3ef97a344e`（與 B7 原月度當次 Core source 相符）。
- 新的 ML/OOS dataset：**11,432 rows**；`gs://gen-lang-client-0593591102-dev-mart/ml-oos-data/v1/61fe563682341113659c3e56f4572c371a74fa08475eee9cee77ac83227f2c3d/manifest.json`。
- 獨立 immutable acceptance receipt：`gs://gen-lang-client-0593591102-dev-mart/acceptance/b7-cache-freshness/28ea717be70a175b77e002c97162e880c30172d28fddb5317ae9f462fdd16043.json`，在真實 GCS 以 create-only 寫入並 byte-for-byte readback。
- 最終 assertions：新 `reconciliation.status=pass`、`ml_oos_derived_cache.status=current`、`core_identity_relation=exact-core`、`source_fence_matched=true`、`missed_invalidation_detected=false`、target refs 一致；`retrained=false`、`derived_cache_reused=true`（第二輪重用第一輪已寫入之 immutable Parquet）、`champion_promotion=false`、`llm_api_tokens=0`、`ceo_triggered=false`、`canonical_write=false`、`bigquery_jobs=[]`。
- B8 frozen Core `sha256:1eb49a2d…` 的 **10,978 rows** 僅屬舊歷史 benchmark，不是這次 B7 fresh source acceptance；不覆寫或刪除。

## 界線與下一步

這份 PASS 僅證明 **2026-10-10 最新 Core 的 B7 衍生快取新鮮度及同源重新 reconciliation**，不把原始月度 `partial` 改寫成歷史 PASS，不證明未來每月自然觸發，亦不替代 B9 的台灣 PIT walk-forward OOS、模型有效性、calibration/champion promotion 與五個 specialist 品質門檻。

**下一個 active 工作：B9 五 Specialist／OOS 模型品質驗收。** B7 月度重訓與 B8 均不重跑。
