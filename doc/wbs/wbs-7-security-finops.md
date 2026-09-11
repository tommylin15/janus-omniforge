# Janus WBS 7 — 安全、監控與 FinOps

## WBS 7 — 安全、監控與 FinOps

### 7.1 IAM／Secret

- ingestion、Mart、FastAPI 與 Admin Web 分離 service account；Flutter client 不持有 GCP service-account credential。
- Secret Manager 依核准的 workload bundle 授權，並記錄擴大的 blast radius。
- production 權限與 dev 分離。
- PostgreSQL dev VM 使用 private IP、≤30 GB Standard Persistent Disk、IAP／OS Login；不得公開 `5432`，Free Tier 模式不自動建立 snapshot／backup／replica。

### 7.2 Observability

- execution／trace ID。
- source/dataset health、freshness、schema drift。
- Job duration、retry、publication、API SLI。
- log redaction 與安全錯誤 taxonomy。
- 按 coverage tier 顯示 expected／received symbols、來源成功數、cache age 與關注股深度資料缺口；不得顯示個別使用者關注關係。

### 7.3 FinOps

- Cloud Run min=0、max limits。
- GCS lifecycle、Artifact Registry cleanup。
- Artifact Registry 僅允許 image／digest／metadata／cleanup；禁止 Artifact Analysis、Container Scanning、vulnerability scanning 與 occurrence API。
- PostgreSQL VM persistent disk snapshot、restore drill 與 VM／disk／snapshot 成本檢查。
- US$1／US$5／US$10 budget alert。
- 每月成本報告與異常檢查。

### 7.4 驗收條件

- 無長效 service-account key。
- 無 secret／raw payload／敏感 URL 外洩。
- 可用 execution ID 從 UI 追至 Job、Core、Mart 與 report。
