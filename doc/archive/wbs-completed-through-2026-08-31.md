# 已完成 WBS（截至 2026-08-31）

來源：`doc/wbs.md`。下列 WBS 已完成；原始範圍與驗收條件完整保留。

## WBS 0 — 專案啟動與決策封版

### 0.1 GCP 與 GitHub

- 建立 GitHub monorepo、branch protection、CODEOWNERS。
- 建立 `janus-dev` GCP project、billing budget 與 `us-central1` 基準。
- Dev／MVP PostgreSQL 採 `us-central1` Compute Engine `e2-micro` 單一 VM，自架 private PostgreSQL；Standard Persistent Disk 總量 ≤30 GB、無 external IP、outbound ≤1 GB/月；production HA 不在此決策內。
- 建立 Workload Identity Federation 與 Cloud Build service account。
- 啟用 Cloud Run、Cloud Build、Artifact Registry、GCS、Pub/Sub、Scheduler、Secret Manager、Logging／Monitoring。

### 0.2 契約與治理

- 建立共用 contracts package、schema version 與 compatibility policy。
- 固定開發期 completeness gate=30%。
- 建立 provenance、quality flags、publication status、execution status enum。
- 盤點 deterministic constants，標示 approved／development-default／pending。
- 建立 source registry 的 `official`／`approved_fallback`／`candidate`／`blocked` 狀態，以及 license、rate limit、retention、PII、引用與再發布審查欄位。
- 固定全市場日頻與核心 50 深度資料的 coverage boundary；membership 具 effective time 且不可改寫歷史。

### 0.3 驗收條件

- PR 可觸發 Cloud Build。
- GitHub 不保存 service-account JSON key。
- Terraform plan 可重現 dev 基礎資源。

## WBS 1 — 雲端開發與 CI/CD 基礎

### 1.1 開發環境

- 建立 Cloud Workstations configuration／devcontainer。
- 固定 Python、Node、DuckDB／PyIceberg 與 CLI 版本。
- 加入 pre-commit、lint、type check、unit test。

### 1.2 建置流水線

- `ingestion-core` path-based build。
- `intelligence-mart` path-based build。
- `web` path-based build。
- 產生 immutable image digest；SBOM 可由 build-local tool 產生，但不執行 Artifact Analysis API、Container Scanning API 或 vulnerability scanning。

### 1.3 部署流水線

- 自動部署 dev。
- staging／production 使用同一 image digest promote。
- migration、backfill、production Job trigger 設人工 approval。
- 設 Artifact Registry cleanup policy。

### 1.4 驗收條件

- 任一目錄變更只建置受影響單元與共用依賴者。
- 失敗 build 不部署。
- 可回退前一 image digest。

## WBS 2 — GCS Stage 與 Provenance

### 2.1 Bucket 與目錄

- 建立 dev Stage／Core／Mart bucket 或隔離 prefix。
- 設定 CMEK（如需要）、uniform access、retention、lifecycle。
- 禁止公開 bucket。

### 2.2 Provenance

- 定義 provenance schema、controlled source/dataset ID。
- 保存 observed／published／fetched、hash、fallback、quality。
- 建立 immutable reuse／new-version 規則。
- 建立 raw payload／object URI 受限存取。

### 2.3 Stage writer

- 寫入原始 JSON／CSV 與 sidecar metadata。
- 使用 idempotency key 防止重複。
- 建立 quarantine 路徑。

### 2.4 驗收條件

- 同一內容重跑不重複建立版本。
- secret／query string 不進 object name、metadata 或 log。
- Stage 可由 execution ID 完整重現。

## WBS 4 — DuckDB／Iceberg Core 與 Query Runtime

### 4.1 Ingestion writer

- 前置條件：WBS 3.6 PostgreSQL VM 與 WBS 3.7 control DB integration、control DB、catalog DB 已通過連線驗證。
- ingestion Cloud Run Job 內嵌固定版 DuckDB／PyIceberg。
- 設定 GCS Iceberg warehouse 與 PostgreSQL SQL catalog。
- 單 task／單 writer；設定 memory、threads、timeout、scan limit 與 temp policy。
- natural key、content hash、null-preserving merge、Iceberg snapshot commit 與 failure-safe Stage cleanup。

### 4.2 Read-only query runtime

- Core query API 可在 Web 或獨立 Cloud Run Service 內嵌另一個 DuckDB process。
- query runtime 對 Iceberg read-only，不得寫 Core 或共用 ingestion 本機 DuckDB 檔案。
- 設定 row／scan bytes、memory、concurrency、statement timeout、pagination 與 cold-start boundary。
- 使用 workload-specific service account、GCS read 與 catalog read-only role；不得取得 catalog owner／Core writer 權限。

### 4.3 Runtime isolation

- DuckDB 不部署到 PostgreSQL `e2-micro` VM；本機 temp／spill 不作持久資料。
- ingestion writer 與 query reader 使用獨立 process、memory budget、timeout、IAM 與 metrics。
- backfill 拆分 date／dataset partition batch；超過單機限制才提出分散式引擎 ADR。

### 4.4 驗收條件

- ingestion clean canary、同日 replay、null-preserving merge 與 catalog reconnect 通過。
- query runtime scale-to-zero 後可冷啟動並完成 bounded read-only smoke query。
- query identity 無法 commit Core；非授權身分無法讀 catalog／warehouse。
- 產生 CPU／RAM／temp usage／query duration 指標與預算告警。

