# Janus × OmniForge — Work Breakdown Structure

版本：1.0  
基準：GCP-first monorepo、GCS／Iceberg／Trino、開發期 30% gate

## WBS 0 — 專案啟動與決策封版

### 0.1 GCP 與 GitHub

- 建立 GitHub monorepo、branch protection、CODEOWNERS。
- 建立 `janus-dev` GCP project、billing budget 與 `us-central1` 基準。
- 建立 Workload Identity Federation 與 Cloud Build service account。
- 啟用 Cloud Run、Cloud Build、Artifact Registry、GCS、Pub/Sub、Scheduler、Secret Manager、Logging／Monitoring。

### 0.2 契約與治理

- 建立共用 contracts package、schema version 與 compatibility policy。
- 固定開發期 completeness gate=30%。
- 建立 provenance、quality flags、publication status、execution status enum。
- 盤點 deterministic constants，標示 approved／development-default／pending。

### 0.3 驗收條件

- PR 可觸發 Cloud Build。
- GitHub 不保存 service-account JSON key。
- Terraform plan 可重現 dev 基礎資源。

## WBS 1 — 雲端開發與 CI/CD 基礎

### 1.1 開發環境

- 建立 Cloud Workstations configuration／devcontainer。
- 固定 Python、Node、Java／Trino 與 CLI 版本。
- 加入 pre-commit、lint、type check、unit test。

### 1.2 建置流水線

- `ingestion-core` path-based build。
- `intelligence-mart` path-based build。
- `trino` path-based build。
- `web` path-based build。
- 產生 immutable image digest、SBOM、vulnerability result。

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

## WBS 3 — Ingestion + Core Job

### 3.1 Scraper framework

- async HTTP、bounded timeout、retry、rate limit。
- schema drift、empty、partial、fallback、unavailable 狀態。
- 日期、時區、股／張、比例與市場別正規化。

### 3.2 第一階段資料源

- TWSE／TPEx OHLCV、PE/PB、法人。
- MOPS／FinMind fallback 三類財報。
- 官方 benchmark。
- 公司事件。
- 市場活動與 issued shares／turnover。

### 3.3 Core DQ

- required key、type、date、duplicate、range、cross-source check。
- null 保留；0 依欄位語意處理。
- corporate action／極端漲跌不直接刪除。
- 失敗資料進 quarantine，合格資料寫 Iceberg Core。

### 3.4 Execution 與事件

- queued／running／completed／partial／failed。
- processed／success／failure／retry count。
- 發出 `core.dataset.ready.v1`。

### 3.5 驗收條件

- 2330 可重跑且 Core row/hash/date/null profile 一致。
- 個股行情已存在時 benchmark 仍更新。
- 新 null 不覆蓋有效值。
- Job 與 API 資源隔離。

## WBS 4 — Trino on Cloud Run

### 4.1 Image 與設定

- 建置固定版 Trino image。
- 設定 GCS Iceberg connector 與 JDBC catalog。
- 設定 query memory、concurrency、timeout、spill／temp policy。

### 4.2 Cloud Run

- 2 vCPU、4–8 GiB；min=0、max=1。
- IAM-only ingress；不公開。
- health／readiness endpoint。
- 同區 GCS、PostgreSQL、Jobs。

### 4.3 Query client

- Job 提交 SQL、輪詢狀態、取得結果。
- 處理冷啟動、取消、timeout、失敗分類。
- backfill 拆分 partition batch。

### 4.4 驗收條件

- scale-to-zero 後可冷啟動並完成 smoke query。
- 查詢期間呼叫端持續等待，不遺失 coordinator 狀態。
- 非授權身分無法呼叫。
- 產生 CPU／RAM／query duration 指標與預算告警。

## WBS 5 — Intelligence Mart

### 5.1 Feature pipeline

- 12 月／12 季 Fundamental features。
- PE／PB／ROE／D/E Valuation features。
- 5／20／60 日 Positioning features。
- 20／60／120 日 Quant、Beta、ATR、turnover。
- PIT Event Risk features。

### 5.2 五角色與 Validator

- 五個 discriminated role payload。
- nullable score、confidence、missing_data、evidence。
- URL、時間、單位、duplicate、stale、conflict、future validation。

### 5.3 Aggregator／Publication

- 初始權重與 effective weight。
- bull／bear／contradictions／contributions。
- 30% development gate。
- manual review、critical、high≥75 blocking。
- immutable governance snapshot version。

### 5.4 LLM

- Vertex AI／Gemini 第一版。
- Structured output 與 evidence-only prompt。
- 429／RESOURCE_EXHAUSTED provider fallback。
- 非 429 錯誤結構化失敗，不寫 placeholder。

### 5.5 Mart writer

- versioned report、feature、model、governance metadata。
- publishable view／service index。
- 發出 `mart.report.ready.v1`。

### 5.6 驗收條件

- Analysis 不呼叫 scraper。
- LLM 關閉時 deterministic output 不改變。
- blocked 不進 publishable view。
- 同一 Core snapshot + governance version 可重現相同 deterministic 結果。

## WBS 6 — Web、Public API 與 Admin

### 6.1 Public API

- health、topics、summary、latest report、history、Kline、events。
- cursor／pagination、safe error、404 waiting state。
- 不公開 raw payload、blocked、secret、traceback。

### 6.2 Public UI

- 首頁、搜尋、題材卡、個股頁。
- K 線 D／W／M、MA、OHLCV 替代表格。
- Metrics、Aggregation、Market Activity、五角色、Events、History、Sources、Disclaimer。

### 6.3 Admin UI

- 股票管理、跨頁批次選取。
- Collection／Analysis 分開觸發。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `ui.md`。

## WBS 7 — 安全、監控與 FinOps

### 7.1 IAM／Secret

- 四部署單元分離 service account。
- Secret Manager 單項授權。
- production 權限與 dev 分離。

### 7.2 Observability

- execution／trace ID。
- source/dataset health、freshness、schema drift。
- Job duration、retry、publication、API SLI。
- log redaction 與安全錯誤 taxonomy。

### 7.3 FinOps

- Cloud Run min=0、max limits。
- GCS lifecycle、Artifact Registry cleanup。
- US$1／US$5／US$10 budget alert。
- 每月成本報告與異常檢查。

### 7.4 驗收條件

- 無長效 service-account key。
- 無 secret／raw payload／敏感 URL 外洩。
- 可用 execution ID 從 UI 追至 Job、Core、Mart 與 report。

## WBS 8 — PIT、QA 與發布

### 8.1 PIT

- 5／20／60 交易日 outcome。
- relative benchmark、MFE／MAE、coverage、calibration。
- 不合格樣本排除原因與 provenance ID。

### 8.2 自動化 QA

- pytest、contract tests、Vitest、Playwright、TypeScript、build。
- schema／migration／Iceberg evolution 測試。
- failure、retry、idempotency、rollback 測試。

### 8.3 實機與 A11y

- iOS Safari、Android Chrome、iPad Safari。
- VoiceOver、TalkBack、keyboard、touch、safe area。
- WCAG AA 實際對比。

### 8.4 Release

- dev → staging → production 同一 digest。
- canary、rollback、backup／restore、runbook。
- 人工 production approval。

### 8.5 驗收條件

- 所有 release gate 通過才可宣稱正式上線。
- 任何 blocked item 都有 owner、deadline、evidence link。

## 建議里程碑

| 里程碑 | 範圍 | 完成定義 |
|---|---|---|
| M0 | WBS 0–1 | 雲端 workspace、monorepo、CI/CD、IaC 可運作 |
| M1 | WBS 2–4 | 2330 Source → Stage → Core，Trino 可冷啟動查詢 |
| M2 | WBS 5 | Core → 五角色 → Mart，30% gate 與 blocked 正確 |
| M3 | WBS 6 | Public／Admin 完整讀取 persisted Mart |
| M4 | WBS 7–8 | 監控、安全、PIT、實機 QA、canary／rollback 通過 |

