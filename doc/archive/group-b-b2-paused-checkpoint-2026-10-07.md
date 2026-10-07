# B2 暫停 checkpoint — 2026-10-07 15:51（Asia/Taipei）

## 狀態

使用者要求暫停 B2，先回寫進度文件。此 checkpoint 之後不得再建立 Lakehouse catalog、修改 IAM、執行 native decimal／schema evolution／partition pruning live acceptance，直到使用者明確要求繼續。

B2 目前仍為 **PARTIAL / PAUSED**，不是 CLOSED。PyIceberg 維持預設 reader；BigQuery compatibility path 仍為 opt-in transition evidence。整次 BigQuery execution budget 維持 **1 GiB（1,073,741,824 bytes）**，單 query timeout 維持 **60 秒**。

## 已完成且保留的 B2 證據

- BigQuery adapter contract tests：**20 PASS**。
- Mart targeted regression：**106 PASS**；deployment／specialist smoke 已成功。
- 三張 fixed-snapshot legacy external table bounded live compare：PyIceberg／BigQuery 共 **320 rows** 逐列 multiset 相等；既有歷史 probe billed bytes 共 31,457,280。
- 固定 B0 Core identity：
  - Core snapshot：`sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`
  - manifest SHA256：`8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8`
- 2026-10-07 Core fence readback workflow `37583598067`：**success**，三張 table fence：
  - `core.benchmark_v1` snapshot `5084459386493044934`
  - `core.ohlcv_v1` snapshot `8549832172546885809`
  - `core.financials_v1` snapshot `801346769573568770`
- GCS evidence path workflow `37583433091`：**success**；`janus-ci` 可讀固定 Core manifest、可對既有 `dev-mart/acceptance` 做 generation=0 immutable write 並 readback。此 preflight 只留下 1 個安全 acceptance probe object。
- 使用者已明確授權 **建立可計費 Lakehouse runtime catalog**；此授權已解除 paid-resource decision gate，但在本 checkpoint 之前尚未建立 catalog。

## 最新 IAM／permission evidence

完整 permission preflight workflow `37583053053`：**success**；probe 本身 `mutations_performed=false`。Cloud Build default identity 的 latest binary permission evidence：

- `biglake.catalogs.create = true`
- `biglake.catalogs.list = true`
- `biglake.tables.register = false`
- `resourcemanager.projects.getIamPolicy = true`
- `resourcemanager.projects.setIamPolicy = false`
- `storage.buckets.getIamPolicy = true`
- `storage.buckets.setIamPolicy = true`
- `storage.objects.get = true`
- `storage.objects.list = true`

IAM fast gate workflow `37583755729`：**success**；結論為 `can_temporary_iam_bootstrap=false`，因 Cloud Build 可讀 project IAM policy 但**不能** `setIamPolicy`。

這組 latest permission evidence 取代稍早「Cloud Build 無 catalog list 能力」的粗粒度 preflight 判讀。實際上 Cloud Build identity 已有 catalog create/list，但沒有 table register，也不能自行做 project IAM bootstrap。

## 尚未完成的三個 B2 live gate

1. **shared catalog exact-snapshot mapping**
   - catalog 尚未建立。
   - Cloud Build 可 create/list catalog，但缺 `biglake.tables.register`。
   - Cloud Build 不能自行 project `setIamPolicy`，因此不能用同一 identity 自動補 project-level register permission。
   - bucket IAM 可讀／可改，但本輪尚未進行任何 bucket IAM mutation。

2. **schema evolution / native decimal**
   - unit contract 已證明 SDK native `Decimal`／date／timestamp／null 保留。
   - 真實 Core 目前主要數值欄仍為 STRING；尚未建立專用小型 Iceberg acceptance table 驗 `DECIMAL(20,4)` precision/scale 與 add-column evolution。

3. **partition pruning**
   - 尚未用真實 `ohlcv_v1` 做寬／窄 partition predicate 的 processed-byte 比較；telemetry 仍為 unknown。

## 下次接續入口

使用者再次要求「繼續 B2」時，從此處開始，不重跑已通過的 20／106 tests、320-row fidelity、Core fence readback 或 GCS evidence path。

優先順序：

1. 找到／使用可執行的 least-privilege principal，補足 **Lakehouse table register** 所需權限；避免把一般 `janus-ci` 永久提升為廣泛 admin。
2. 建立單一 `us-central1` Lakehouse runtime catalog；不啟用 automatic table management。
3. register 三張既有 canonical Iceberg metadata fence，逐張驗 metadata location + current snapshot exact mapping。
4. 在既有 dev acceptance prefix 建小型 Iceberg acceptance table，驗 native decimal + schema evolution。
5. 對 `ohlcv_v1` 做 bounded partition-pruning live probe；所有 BigQuery query 共用整輪 1 GiB budget、每 query ≤60 秒。
6. 三個 gate 全 PASS 才更新 B2 CLOSED；否則維持 PARTIAL/BLOCKED。

## Evidence files

- `archive/group-b-b2-bounded-compatibility-evidence-2026-10-07.md`
- `archive/group-b-b2-lakehouse-preflight-2026-10-07.json`
- `archive/group-b-b2-iam-capability-preflight-2026-10-07.json`
- `archive/group-b-b2-cloudbuild-metadata-preflight-2026-10-07.json`
- `archive/group-b-b2-permission-preflight-2026-10-07.json`
- `archive/group-b-b2-iam-setpolicy-fast-gate-2026-10-07.json`
- `archive/group-b-b2-gcs-evidence-preflight-2026-10-07.json`
- `archive/group-b-b2-core-fence-readback-2026-10-07.json`
