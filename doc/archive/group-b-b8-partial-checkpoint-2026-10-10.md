# B8 第一階段同源驗證 checkpoint — 2026-10-10

狀態：**B8 PARTIAL**。ML/OOS 既有 BigQuery Parquet 與固定 Core 的 PyIceberg independent reduction **PASS**；500 檔 screening BigQuery real path 因 GitHub Actions CI 身分讀取既有 BigLake catalog 遇到 **HTTP 403 / BLOCKED**。尚無 B8 完整 performance／FinOps／fallback gate，不切換 default。

## 固定界線
- B0～B6 不重做；B7 月度執行機制 PASS；derived cache freshness PARTIAL；B8 使用 B2/B5 frozen Core，不冒充 B7 最新 Core 或 B9 模型品質。
- Iceberg canonical / PIT / provenance 不修改；PostgreSQL hot path 不影響；無新 IAM、無 Storage Read API、無 CEO、無模型重訓；BigQuery 每次 1 GiB billed 與單查詢 60 秒 ceiling。

## 真實驗收與阻塞
1. [B8 ML/OOS workflow #38029439580](https://github.com/tommylin15/janus-omniforge/actions/runs/38029439580) SUCCESS：26 targeted tests PASS。固定 Core snapshot sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab、analysis_as_of=2026-10-06。既有 B5 immutable BigQuery Parquet 10,978 筆與 PyIceberg 獨立 reduction 比對 different_keys=0／changed_rows=0，GCS bytes/hash readback；此為 **資料 fidelity PASS**，沒有重做 BigQuery export 或模型訓練，equal-run BigQuery performance／當次 billed bytes **NOT VERIFIED**。
2. [B8 matched-screening #38029212373](https://github.com/tommylin15/janus-omniforge/actions/runs/38029212373) FAIL：36 targeted tests PASS；PyIceberg reference 完成，BigQuery candidate failure，安全 fallback audit，status=partial，不能宣稱 screening fidelity PASS。
3. [B8 candidate diagnostic #38029590161](https://github.com/tommylin15/janus-omniforge/actions/runs/38029590161) FAIL：bq-probe stage RuntimeError；catalog 分類過於籠統，不以此一筆推論權限根因。
4. [B8 frozen catalog preflight #38029803051](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051) FAIL：36 targeted tests PASS，固定 Core catalog readback 前置檢查顯示 B8_CATALOG_PREFLIGHT=FAIL reason_code=IAM_403 exception_type=RuntimeError；後續 billable screening canary **未執行**。確切 IAM permission 尚 unknown，不自行擴權；實際 BigQuery billed bytes 未讀回，不填 0。

## 後續 gate
- B8 screening **BLOCKED**：先確認是否有現有已核准、可重現、免 IAM 擴權的執行路徑；若需要權限擴張先取得使用者明確授權。catalog pointer/fence 能 readback 後才做固定 Core 的 full screening cold/warm PyIceberg vs BigQuery 數據、成本、效能、fallback 比對。不能以失敗資料切 default。
- B8 ML/OOS performance **PARTIAL**：fidelity PASS 不等於同次 PyIceberg vs BigQuery reduction/export end-to-end benchmark。B5 歷史 SQL export elapsed、30 MiB bill 不作此 workload 的 equal-run 結論。記錄 RSS／GCS I/O（未知 null）、BQ processed/billed bytes、end-to-end elapsed。
- B8/B9 銜接 derived cache freshness **PARTIAL**：當次 Core dependent table snapshot/pointer、analysis date、feature/query/schema/model version 匹配後才 refresh immutable derived cache；不能為此重跑已驗證 B7 retrain。
- B9 model quality **NOT VERIFIED**：須使用與當次 Core source fence、PIT/data-priority、source authorization 相容的 OOS 資料，不用 B8 舊 fixed Core fidelity 代替。

相關程式：scripts/gcp/b8-matched-screening.py、scripts/gcp/b8-matched-ml-oos.py；tests/test_b8_matched_screening.py、tests/test_b8_matched_ml_oos.py；.github/workflows/b8-matched-screening.yml、.github/workflows/b8-ml-oos-readback.yml。


## 既有 dev BigLake 執行身分 readback（2026-10-10）
- [Read-only identity workflow #38030454991](https://github.com/tommylin15/janus-omniforge/actions/runs/38030454991)：**預期 FAIL / B8 screening BLOCKED**；offline safety unittest **4/4 PASS**、同 SHA [selective CI #38030455095](https://github.com/tommylin15/janus-omniforge/actions/runs/38030455095) SUCCESS。run SHA `85ca8b109bb4e8af3b464e120703f498c18b7b52`；詳細唯讀 JSON 在該 workflow artifact `b8-existing-identity-38030454991`。
- 固定 B2 Core manifest raw hash `8eda0eae...` 與 `core_snapshot_id=sha256:1eb49a2d...` 驗證 PASS。讀回既有四個 runtime 資源、三個不同 service account：Mart=`intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com`；Ingestion 與 controller=`ingestion-core@gen-lang-client-0593591102.iam.gserviceaccount.com`；API=`janus-user-api@gen-lang-client-0593591102.iam.gserviceaccount.com`。
- 直接透過既有 GitHub WIF/CI 身分 GET BigLake Iceberg REST catalog frozen `ohlcv_v1` pointer：`HTTP_403`，因此未繼續 `benchmark_v1`／BigQuery query。
- CI 試圖**只沿用既有代理授權**取得上述三個 runtime SA 的唯讀 probe token：全部 `DENIED_OR_UNAVAILABLE`、`catalog=NOT_TESTED`。這**不能證明** runtime SA 自身無 BigLake 讀權；只能證明**目前 CI 沒有已驗證且可重現的既有執行路徑**。歷史 B2 `janus-ci` project IAM policy GET 亦 denied；無法由目前 CI 推定各 runtime SA 實際有效權限。
- 沒有更新 IAM、沒有新建/執行 Cloud Run Job 或 Cloud Build、沒有新 BigQuery query/billed job、沒有重訓、沒有讀寫 canonical。**B8 screening 維持 BLOCKED；PyIceberg default／cutover=false**。要解除 blocker，需透過既有**已授權且可受控實際執行**的身分讀取同一 frozen Core 的 catalog pointers，或另外取得使用者明確授權的 IAM 決策；不得將此診斷 FAIL 改標 B8 PASS。
