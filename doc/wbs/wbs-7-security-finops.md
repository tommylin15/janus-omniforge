# Janus WBS 7 — 安全、監控與 FinOps

## WBS 7 — 安全、監控與 FinOps

### 7.1 IAM／Secret

- ingestion、Mart、FastAPI 與 Admin Web 分離 service account；Flutter client 不持有 GCP service-account credential。
- Secret Manager 依核准的 workload bundle 授權，並記錄擴大的 blast radius。
- production 權限與 dev 分離。
- PostgreSQL dev VM 使用 private IP、≤30 GB Standard Persistent Disk、IAP／OS Login；不得公開 `5432`，Free Tier 模式不自動建立 PD snapshot／HA／replica。Pilot 例外為已人工核准的 bounded `pg_dump → restricted Private GCS` ledger durability strategy。

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
- bounded logical PostgreSQL backup、restricted Private GCS retention、restore drill 與 VM／GCS／retention 成本檢查；PD snapshot 不是目前 Pilot backup strategy。
- single TWD 320 notification budget，10%／50%／100% thresholds；budget 是 notification，不是 spending cap，actual spend 以 Cloud Billing 為準，不新增 paid BigQuery billing export。
- 每月成本報告與異常檢查。

### 7.4 `WBS-7-PILOT-LEDGER-DURABILITY`

- Implementation 前確認 PostgreSQL schema／dependency，選擇 bounded whole-database logical dump 或 minimum restore-complete scope；不得把 Private Mart 當 ledger backup。
- Retention：每日 logical backup，保留最近 14 個 daily backup；每月 1 個 monthly checkpoint，最多保留至本次 6-month Pilot 結束；禁止 unbounded retention。
- 至少每月一次 isolated non-production restore drill，驗證 restore success、owner boundary、ledger event count／consistency、latest expected ledger version、reversal／replacement semantics 與 no secret leakage；不得影響或破壞既有 dev ledger。
- 實作前量測 compressed dump size、projected monthly GCS bytes 與 retention footprint，納入 monthly FinOps evidence；若 restore 需要新的付費 persistent resource 或成本明顯超出小型 Pilot backup 預期，STOP 並要求人工決定。

### 7.5 驗收條件

- 無長效 service-account key。
- 無 secret／raw payload／敏感 URL 外洩。
- 可用 execution ID 從 UI 追至 Job、Core、Mart 與 report。
