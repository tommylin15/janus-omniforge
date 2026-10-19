# Janus WBS 7 — 安全、監控與 FinOps

## WBS 7 — 安全、監控與 FinOps

### 執行環境

目前 `dev` 是 Janus 個人真實使用的平行上線環境，因此安全與 FinOps 的目標是讓這套真實環境可長期使用，而不是為尚不存在的 production/staging 複製一套同等基礎設施。未來若進入多人、HA／SLA 或正式營運，再依 Pilot evidence 設計獨立 production boundary。

### 7.1 IAM／Secret

- ingestion、Mart、FastAPI 與 Admin Web 分離 service account；Flutter client 不持有 GCP service-account credential。
- Secret Manager 依核准的 workload bundle 授權，並記錄擴大的 blast radius。
- 目前 dev live workload 之間仍維持 least-privilege service identity／owner boundary；未來 production 若建立，權限與 secret 再獨立切分，不要求現在先建立 production IAM mirror。
- PostgreSQL dev VM 使用 private IP、≤30 GB Standard Persistent Disk、IAP／OS Login；不得公開 `5432`，Free Tier 模式不自動建立 PD snapshot／HA／replica。Pilot／parallel-live durability 使用已人工核准的 bounded `pg_dump → restricted Private GCS` strategy。

### 7.2 Observability

- execution／trace ID。
- source/dataset health、freshness、schema drift。
- Job duration、retry、publication、API SLI。
- log redaction 與安全錯誤 taxonomy。
- 按 coverage tier 顯示 expected／received symbols、來源成功數、cache age 與關注股深度資料缺口；不得顯示個別使用者關注關係。
- 監控與錯誤 evidence 以真實 dev Cloud Run／Job／Scheduler／API 流量為主；synthetic probe 只補健康檢查，不可掩蓋真實失敗率。

### 7.3 FinOps

- Cloud Run min=0、max limits。
- GCS lifecycle、Artifact Registry cleanup。
- Artifact Registry 僅允許 image／digest／metadata／cleanup；禁止 Artifact Analysis、Container Scanning、vulnerability scanning 與 occurrence API。
- bounded logical PostgreSQL backup、restricted Private GCS retention、restore drill 與 VM／GCS／retention 成本檢查；PD snapshot 不是目前 parallel-live backup strategy。
- single TWD 320 notification budget，10%／50%／100% thresholds；budget 是 notification，不是 spending cap，actual spend 以 Cloud Billing 為準，不新增 paid BigQuery billing export。
- 每月成本報告與異常檢查以目前真實 dev usage 為準；不得用假流量推估冒充實際成本 evidence。

### 7.3A `WBS-7-INGESTION-ICEBERG-FINOPS-AB`｜2026-10-18 P0

**唯一優先序**在 [TODO FINOPS-AB／FINOPS-C](../todo.md)；**AI 工程指令**在 [FINOPS-AB/C 卡](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md)，不是第二份工單。A＋B 已授權優先實作；2026-10-18 週維護啟用已有既有文件／CI 收據；程式 `effective_batches()` 在 `FINOPS_WEEKLY_MAINTENANCE=true` 時週六23:30，當期自然 occurrence 仍須另讀真實 runtime。

- A：`janus-ingestion-core` 的 Iceberg Compaction、`janus-intelligence-mart` 的 Mart Cleanup、Core Cleanup 同組改每週六 23:30 邏輯時段；週六 non-trading 不得依賴當天 ingestion SUCCESS，必驗最新有效 EOD snapshot、跨日依賴、互斥、延遲、no-op、failed/ambiguous 和 rollback。不得改掉每天市場收集或當日 Private/Owner 所需處理。
- B：Ingestion Data Supplement bounded date/selected field、同日同 Dataset 安全合併提交與 no-op、Snapshot/metadata reuse、dirty-partition compaction。不能降低 PIT、版本修正、provenance、全市場 coverage 或 research/private protected references；保存固定 Core snapshot。
- 由 Cloud Run **可計費** vCPU-seconds／GiB-seconds、execution duration、GCS ReadObject/GetObjectMetadata/Write/List、Iceberg metadata／小檔量、Mart BQ billed bytes（若適用）、data parity 做同負載前後比較；bucket-level GCS I/O 不能未經歸因算在單一 Job。原 D06 歷史記錄不改寫，30% CPU/50% Metadata 只作改善目標。
- A/B tests、CI、GHCR immutable digest、受控 Job deployment／Scheduler occurrence 和真實資料端到端讀回皆須通過，才可結案；依 10/18 current-only 決策已取消 external research fence 作為舊 snapshot 的清理 gate；current 檔、7日 orphan、generation、writer/catalog 安全與實刪讀回仍需驗證。

### 7.3B D07-PRE｜Colab 唯一流程與有條件的 FINOPS-C

歷史 `WBS-7-BIGQUERY-C-PREFLIGHT` 僅供引用映射，現行只有 [TODO D07-PRE](../todo.md) 一個工作包。**Colab 是 D07 研究資料整理、特徵/標籤、模型訓練與 OOS 的唯一目標執行器**；Core/PyIceberg 僅提供 canonical 唯讀來源，Janus Controller／Mart 保留月度登記/版本治理/正式 inference。BQ **預設 DEFER**，只有資料量實測導致 Colab RAM、Join／耗時或 I/O 明確瓶頸且具收益時，才在必要已核准授權下執行 SQL 前置縮減，回送 versioned Parquet 由 Colab 繼續訓練，禁 BQML/Storage Read API。需評估免費 Colab CPU 的實跑與安全/來源許可、FINOPS-AB 後 GCS I/O、因 BQ 前處理可能新增的 billed bytes、共享配額／region／IAM／回退；不能把 BQ 省略時預設為零費用。免費 Colab 尚不具可驗證無人值守月度能力，先用人工啟動與來源/輸出 hash receipt，直到官方合規自動化另行驗收；此缺口不因選定架構而消失。

### 7.4 `WBS-7-PILOT-LEDGER-DURABILITY`

- Implementation 前確認 PostgreSQL schema／dependency，選擇 bounded whole-database logical dump 或 minimum restore-complete scope；不得把 Private Mart 當 ledger backup。
- Retention：每日 logical backup，保留最近 14 個 daily backup；每月 1 個 monthly checkpoint，最多保留至本次 6-month Pilot 結束；禁止 unbounded retention。Pilot 結束後若 dev 繼續作為個人 live 環境，保留政策須重新以實際成本與恢復需求決定，不因名稱是 dev 就自動取消 backup。
- 至少每月一次 isolated restore drill，驗證 restore success、owner boundary、ledger event count／consistency、latest expected ledger version、reversal／replacement semantics 與 no secret leakage；不得影響或破壞現有 dev live ledger。
- 實作前量測 compressed dump size、projected monthly GCS bytes 與 retention footprint，納入 monthly FinOps evidence；若 restore 需要新的付費 persistent resource 或成本明顯超出小型個人環境預期，STOP 並要求人工決定。

### 7.5 驗收條件

- 無長效 service-account key。
- 無 secret／raw payload／敏感 URL 外洩。
- 可用 execution ID 從 UI 追至 Job、Core、Mart 與 report。
- 安全完成不以「尚未建立 production IAM／HA」判失敗；應以目前 dev live workload 的 auth、owner isolation、secret handling、backup/restore、監控與成本 evidence 判定。
