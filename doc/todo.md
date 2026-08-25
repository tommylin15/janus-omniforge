# Janus × OmniForge — TODO

版本：1.0  
用途：由 AI／開發者依順序執行；完成時勾選並附 PR、Cloud Build、execution 或測試證據。

## P0 — 開工前阻擋項目

- [ ] 取得 GitHub repo 或建立 `janus-omniforge` monorepo。
- [ ] 確認 GCP Project ID、Billing account、region=`us-central1`。
- [ ] 確認 PostgreSQL：Cloud SQL、Supabase 或 GCE PostgreSQL。
- [ ] 確認 AI 可建立 PR，但 production deploy 需人工批准。
- [ ] 確認第一批股票：至少 `2330`。
- [ ] 確認第一版 LLM：Vertex AI／Gemini。
- [ ] 確認 dev bucket／resource 命名。
- [ ] 建立 US$1／US$5／US$10 billing alerts。

## P0 — Repository 與雲端開發

- [ ] 建立 `apps/web`。
- [ ] 建立 `jobs/ingestion-core`。
- [ ] 建立 `jobs/intelligence-mart`。
- [ ] 建立 `services/trino`。
- [ ] 建立 `packages/contracts`、`governance`、`provenance`、`observability`。
- [ ] 建立 `infra`、`tests/contract`、`tests/e2e`。
- [ ] 建立 Cloud Workstations／Cloud Shell Editor 開發設定。
- [ ] 固定 Python、Node、Java／Trino 版本與 lockfiles。
- [ ] 加入 branch protection、CODEOWNERS、PR template。

## P0 — IAM、CI/CD 與 Secret

- [ ] 建立 GitHub → GCP Workload Identity Federation。
- [ ] 建立 Cloud Build service account。
- [ ] 建立四個 runtime service accounts。
- [ ] 套用最小 IAM，不建立長效 JSON key。
- [ ] 啟用必要 GCP APIs。
- [ ] 建立 path-based Cloud Build triggers。
- [ ] 建立 Artifact Registry cleanup policy。
- [ ] 建立 Secret Manager secrets（只放名稱，不把值寫入 repo）。
- [ ] 確認 build 產出 immutable digest 與 SBOM。

## P0 — Contracts 與治理

- [ ] 定義 source IDs、dataset IDs。
- [ ] 定義 `DataProvenanceV1`。
- [ ] 定義 `ExecutionStatusV1`。
- [ ] 定義 `QualityFlagV1`。
- [ ] 定義 `PublicationStatusV1`。
- [ ] 定義 `CoreDatasetReadyV1` 與 `MartReportReadyV1`。
- [ ] 固定 development completeness gate=30%。
- [ ] 將 manual review、critical、high≥75 blocking 寫入測試。
- [ ] 盤點所有 deterministic constants 與核准狀態。

## P0 — Stage／Core

- [ ] 建立 dev Stage／Core／Mart buckets 或隔離 prefixes。
- [ ] 設 uniform bucket-level access 與 lifecycle。
- [ ] 實作原始物件 + sidecar metadata 寫入。
- [ ] 實作 content hash 與 idempotency key。
- [ ] 實作 quarantine 路徑。
- [ ] 建立 Iceberg Core schemas 與 partition strategy。
- [ ] 實作 null、duplicate、date、unit、schema drift DQ。
- [ ] 禁止 0 一律轉 null。
- [ ] 禁止 >11% 漲跌一律刪除。

## P0 — 第一批 Scrapers

- [ ] TWSE／TPEx OHLCV。
- [ ] PE／PB 與法人。
- [ ] MOPS／FinMind 三類財報。
- [ ] TAIEX／TPEx benchmark。
- [ ] 公司事件。
- [ ] 融資融券、借券、當沖、注意／處置。
- [ ] issued shares 與 turnover ratio。
- [ ] 休市／盤前最近有效交易日回看。
- [ ] 全市場回應同批快取。
- [ ] bounded timeout、retry、rate-limit tests。

## P0 — Trino

- [ ] 固定 Trino 版本並建立 image。
- [ ] 設定 GCS Iceberg connector。
- [ ] 設定 JDBC catalog PostgreSQL。
- [ ] 部署 Cloud Run Service：2 vCPU、4–8 GiB、min=0、max=1。
- [ ] 設 IAM-only ingress。
- [ ] 設 query memory、concurrency、timeout。
- [ ] 實作 Job query submit／poll／cancel client。
- [ ] 驗證 scale-to-zero 冷啟動。
- [ ] 驗證長查詢不因呼叫端提前離開而中斷。

## P0 — 2330 Core 閉環

- [ ] 觸發 2330 ingestion execution。
- [ ] 驗證 Stage raw objects。
- [ ] 驗證 Core row count、hash、date coverage、null profile。
- [ ] 驗證 provenance 三種時間與 fallback。
- [ ] 重跑並驗證冪等。
- [ ] 驗證 partial／failed／retry 狀態。
- [ ] 發出並驗證 `core.dataset.ready.v1`。

## P1 — Mart／Agents

- [ ] Fundamental features／Agent。
- [ ] Valuation features／Agent。
- [ ] Positioning features／Agent。
- [ ] Quant features／Agent。
- [ ] Event Risk features／Agent。
- [ ] Evidence Validator。
- [ ] Aggregator bull／bear／contradictions／contributions。
- [ ] 30% insufficient-data gate。
- [ ] blocked／publishable view。
- [ ] immutable governance snapshot version。
- [ ] deterministic rerun tests。

## P1 — LLM

- [ ] 建立 evidence-only structured prompt。
- [ ] 禁止模型產生未在 evidence 出現的數字。
- [ ] 禁止模型修改 score、confidence、quality、publication。
- [ ] 接 Vertex AI／Gemini。
- [ ] 429／RESOURCE_EXHAUSTED fallback。
- [ ] 非 429 結構化失敗。
- [ ] LLM 失敗不得寫 placeholder report。
- [ ] LLM 關閉時 deterministic outputs 完全一致。

## P1 — Mart 閉環

- [ ] 產製 versioned Mart tables。
- [ ] 寫 report／model／governance metadata。
- [ ] 寫 PostgreSQL publication service index。
- [ ] 發出 `mart.report.ready.v1`。
- [ ] 驗證 blocked 不進 publishable view。
- [ ] 驗證 2330 Core → Mart 可重現。

## P1 — Public API／UI

- [ ] Health、topics、summary。
- [ ] Latest report、history、Kline、events。
- [ ] 未知／停用股票 404。
- [ ] 已啟用無資料顯示等待批次。
- [ ] 查無資料不觸發 scraper／Agent／LLM。
- [ ] blocked、raw payload、secret、traceback 不公開。
- [ ] 完成 `ui.md` 所有 P0 元件。

## P1 — Admin

- [ ] 股票搜尋、分頁、enabled、關聯刪除保護。
- [ ] 跨頁選取與 collection／analysis 分開觸發。
- [ ] 最近 50 次 execution。
- [ ] execution details 按需讀取。
- [ ] Governance typed editing、validation、diff、history、optimistic lock。
- [ ] Data-source health 只讀 persisted telemetry。
- [ ] Report block／unblock 保存理由與 audit。

## P1 — 自動化測試

- [ ] Backend pytest。
- [ ] Contract tests。
- [ ] Frontend Vitest。
- [ ] Playwright responsive／interaction。
- [ ] TypeScript／ESLint／production build。
- [ ] Iceberg schema evolution tests。
- [ ] Failure／retry／idempotency tests。
- [ ] 安全輸出與 log redaction tests。

## P2 — PIT 與治理校準

- [ ] 5／20／60 交易日 outcome pipeline。
- [ ] relative benchmark、MFE／MAE、coverage。
- [ ] 缺 publication time／provenance 樣本排除。
- [ ] 每個排除保留原因與 ID。
- [ ] 對 30% gate 做 coverage／錯誤率分析。
- [ ] 對 weights／40-60 thresholds 做 walk-forward。
- [ ] 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] iOS Safari。
- [ ] Android Chrome。
- [ ] iPad Safari。
- [ ] VoiceOver／TalkBack。
- [ ] WCAG AA contrast。
- [ ] 所有主要控制 ≥44×44。
- [ ] K 線 pan／zoom／tooltip／替代表格。
- [ ] Dialog focus trap、Escape、restore、scroll lock。
- [ ] canary／rollback。
- [ ] backup／restore 演練。
- [ ] incident runbook。
- [ ] production 人工批准。

## P3 — OmniForge／PodBrief

- [ ] 只匯出 publishable report 的 Markdown exporter。
- [ ] YAML schema validator。
- [ ] 小白／一般／分析師／Auditor 四階視圖。
- [ ] 雙鏈與標籤。
- [ ] Podcast 授權與保存政策。
- [ ] 逐字稿、時間碼與摘要 provenance。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。

