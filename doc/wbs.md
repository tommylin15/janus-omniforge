# Janus × OmniForge — Work Breakdown Structure

版本：1.2
基準：GCP-first monorepo、GCS／Iceberg／DuckDB、雙軌資料供應、開發期 30% gate

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
- 來源契約加入 coverage tier、cadence、market、scope、authorization status、retention 與 safe provenance。
- 股票 master 動態維護上市／上櫃狀態；不得以固定 1,700 或 2,000 檔作完整性判斷。

### 3.2A 全市場量化網

- 以當日 enabled 股票 master 收集日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與 benchmark。
- 每日產製 market coverage、missing symbols、source health、freshness 與合法 empty／unavailable 摘要。
- 全市場回應採一次抓取、批次快取與 symbol fan-out，禁止逐檔重複呼叫同一 market endpoint。
- 產製 `mart_screening_signals` 所需 deterministic Core inputs；screening 不在 ingestion request 內執行。

### 3.2B 核心 50 放大鏡

- control DB 維護最多 50 檔核心 membership、effective time、理由、owner 與 collection cadence。
- 深度財報、公司事件／重大訊息與公司行動優先；分 K／Tick、新聞、券商研究、Podcast、社群文本須在來源審查通過後個別啟用。
- 高頻／文本／另類 collection 與全市場排程隔離，具獨立 quota、retention、成本與 failure policy。
- 文本實體對應可進 Core，但情緒、聲量、AI 示警與投資判讀只能進 versioned Mart。

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

### 3.6 PostgreSQL Free Tier VM 與 Control DB 基礎（WBS 4 前置）

- Terraform 建立單一 Compute Engine `e2-micro`，固定於 `us-central1` eligible zone。
- VM 不配置 external IP，只使用 private IP；IAP／OS Login 管理，firewall 不公開 `5432`。
- 使用總量 ≤30 GB 的 Standard Persistent Disk；Free Tier 模式不建立 snapshot、backup、HA 或 replica。
- 安裝固定 PostgreSQL 版本，建立 control、Iceberg catalog、publication、audit database/schema 與最小 database roles。
- credential 由 Secret Manager 提供；Cloud Run、Cloud Run Jobs 與內嵌 DuckDB runtime 透過 VPC private path 連線。
- 驗證 VM health、PostgreSQL readiness、schema migration、JDBC catalog smoke query 與 Free Tier 資源邊界。

### 3.7 PostgreSQL Control DB Integration（WBS 4 前置）

- 將 control schema、FK、CHECK、index 與 execution transition migration 到 PostgreSQL。
- 實作 PostgreSQL control repository；SQLite 只作 unit-test reference。
- 以 transaction／row lock／安全 claim 讓 queued execution 可被 worker 恢復與冪等處理。
- Response cache 的 payload／raw response 留在 GCS Stage；PostgreSQL 僅保存 key、URI、hash、TTL、observed time 與狀態 metadata。
- 設定低連線數 pool、statement／idle timeout、migration lock 與 reconnect，避免壓垮 `e2-micro`。
- 使用 Secret Manager credential 與 private IP，完成 ingestion、DuckDB query、Web 與 Mart Cloud Run／Jobs control DB smoke tests。

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

## WBS 5 — Intelligence Mart

### 5.0 Runtime 與輸入邊界

- `intelligence-mart` 以 Cloud Run Job 執行，只讀 analysis-as-of 可見的
  versioned Core snapshot；Analysis 不得即時補抓、呼叫 scraper 或改寫 Core。
- Mart Job 使用 Direct VPC egress、專用 service account 與 workload-specific
  PostgreSQL catalog／publication credentials；連線池、statement timeout 與 retry
  必須有界。
- 每次執行固定 `execution_id`、`analysis_as_of`、Core snapshot ID、schema／feature／
  model version 與 immutable governance snapshot version，作為重跑及稽核邊界。
- Mart 必須由 ingestion 成功完成 DQ、Core commit 並發出 `core.dataset.ready.v1` 後，
  透過 workflow／event 觸發；事件需攜帶 execution 與 immutable Core snapshot 邊界。
  Cloud Scheduler 不得讓 ingestion 與 Mart 在相同時間各自獨立觸發，以免 Mart
  讀取尚未完成或不一致的 Core snapshot。

### 5.1 Feature pipeline

- 全市場 `mart_screening_signals`：突破、量能、流動性與異動候選。
- 12 月／12 季 Fundamental features。
- PE／PB／ROE／D/E Valuation features。
- 5／20／60 日 Positioning features。
- 20／60／120 日 Quant、Beta、ATR、turnover。
- PIT Event Risk features。
- 核心 50 `mart_core_alpha`、`mart_risk_portfolio` 與經核准文本的 `mart_alternative_sentiment`。
- 五個 Mart schema 均使用 versioned Iceberg table／partition；至少保存 symbol／coverage、
  analysis date、上述 lineage、completeness、confidence、data quality、publication／
  analysis outcome，以及 evidence／artifact reference。不得只保存無法追溯來源的最終分數。
- `mart_master_investment_memo` 保存五角色結論、screening／risk／sentiment 摘要、
  aggregate score、bull／bear、contradictions、contributions、Devil's Advocate 反證、
  blocked／insufficient-data reason 與 CIO 結構化摘要。

### 5.2 五角色與 Validator

- 五個 discriminated role payload。
- nullable score、confidence、missing_data、evidence。
- URL、時間、單位、duplicate、stale、conflict、future validation。
- Evidence 必須引用可定位的 provenance／Core snapshot；未核准來源、缺 publication
  time 或超過 `analysis_as_of` 的資料不得成為角色或 LLM 輸入。

### 5.3 Aggregator／Publication

- 初始權重與 effective weight。
- bull／bear／contradictions／contributions。
- Devil's Advocate 反證階段與 CIO `mart_master_investment_memo`；兩者只使用合格 evidence。
- 30% development gate。
- manual review、critical、high≥75 blocking。
- immutable governance snapshot version。
- `insufficient_data` 是 completeness gate 的分析結果，必須與 publication lifecycle
  狀態分欄保存；實作前須讓 spec、contracts、API 與 UI 使用同一語意。只有
  `publishable`／`published` 可進公開 service index。

### 5.4 LLM

- 第一版 LLM provider 使用順序：Gemini → OpenRouter → GroqCloud；取消 Vertex AI。
- Structured output 與 evidence-only prompt。
- Gemini 發生 429／`RESOURCE_EXHAUSTED` 或 provider unavailable 時依序 fallback 至 OpenRouter，再至 GroqCloud。
- 非 429 錯誤結構化失敗，不寫 placeholder。

### 5.5 Mart writer

- GCS Mart bucket 保存 Iceberg／Parquet data 與 metadata、versioned feature／role／
  evidence／aggregation payload、model／evaluation artifact、完整結構化 report 與
  Markdown export；大型 governance diff 亦留在 GCS。
- PostgreSQL 只保存 catalog、control、publication、audit、report metadata 與 bounded
  service index，包括 object URI、snapshot ID、hash、version 與狀態；不得保存完整
  report、feature 或 evidence payload。
- publication schema 使用 migration、唯一鍵、retention、bounded pool 與
  workload-specific role；blocked／insufficient-data 成品不得進 publishable view。
- 發出 `mart.report.ready.v1`。

### 5.6 驗收條件

- Analysis 不呼叫 scraper。
- LLM 關閉時 deterministic output 不改變。
- blocked 不進 publishable view。
- 同一 Core snapshot + governance version 可重現相同 deterministic 結果。
- RAG 只能檢索 analysis-as-of 可見的 Core／Mart snapshot，未核准來源不得進 evidence。
- Contract、Iceberg schema evolution 與儲存邊界測試證明 PostgreSQL 沒有完整 Mart
  payload，且 publication index 可解析至正確 immutable GCS／Iceberg artifact。

## WBS 6 — Web、Public API 與 Admin

### 6.1 Public API

- health、topics、summary、latest report、history、Kline、events。
- cursor／pagination、safe error、404 waiting state。
- 不公開 raw payload、blocked、secret、traceback。

### 6.2 Public UI

- 首頁、搜尋、題材卡、個股頁。
- K 線 D／W／M、MA、OHLCV 替代表格。
- Metrics、Aggregation、Market Activity、五角色、Events、History、Sources、Disclaimer。
- 全市場 screening 與核心標的視圖明確分流；顯示 coverage、freshness、來源健康與資料不足。
- 情緒溫度、多空雷達與風險紅綠燈只呈現後端 versioned Mart，不由前端重算。

### 6.3 Admin UI

- 股票管理、跨頁批次選取。
- Collection／Analysis 分開觸發。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。
- 全市場／核心 50 membership、effective date、cadence、來源授權狀態與 quota 管理；超過 50 檔必須拒絕。

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
- PostgreSQL dev VM 使用 private IP、≤30 GB Standard Persistent Disk、IAP／OS Login；不得公開 `5432`，Free Tier 模式不自動建立 snapshot／backup／replica。

### 7.2 Observability

- execution／trace ID。
- source/dataset health、freshness、schema drift。
- Job duration、retry、publication、API SLI。
- log redaction 與安全錯誤 taxonomy。
- 按 coverage tier 顯示 expected／received symbols、來源成功數、cache age 與核心 50 深度資料缺口。

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

## WBS 8 — PIT、QA 與發布

### 8.1 PIT

- 5／20／60 交易日 outcome。
- relative benchmark、MFE／MAE、coverage、calibration。
- 不合格樣本排除原因與 provenance ID。
- membership 與來源授權均以 effective time 納入 PIT；不得用今日核心名單回填歷史樣本。

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
| M1 | WBS 2–4 | PostgreSQL Free Tier VM → 2330 Source → Stage → DuckDB／Iceberg Core，bounded query 可冷啟動 |
| M1.5 | WBS 3–4 | 全市場日頻 baseline 與核心 50 membership／collection boundary 通過 |
| M2 | WBS 5 | Screening／Core Alpha／五角色 → Mart，30% gate、Devil's Advocate 與 blocked 正確 |
| M3 | WBS 6 | Public／Admin 完整讀取 persisted Mart |
| M4 | WBS 7–8 | 監控、安全、PIT、實機 QA、canary／rollback 通過 |
