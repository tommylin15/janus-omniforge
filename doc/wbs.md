# Janus × OmniForge — Work Breakdown Structure

版本：1.3
基準：GCP-first monorepo、GCS／Iceberg／DuckDB、雙軌資料供應、開發期 30% gate

## 已完成 WBS 索引

WBS 0、1、2、4 已完成並移至
[archive/wbs-completed-through-2026-08-31.md](archive/wbs-completed-through-2026-08-31.md)。
本檔只保留仍含未完成範圍的 WBS。

## WBS 3 — Ingestion + Core Job

### 3.1 Scraper framework

- async HTTP、bounded timeout、retry、rate limit。
- schema drift、empty、partial、fallback、unavailable 狀態。
- 日期、時區、股／張、比例與市場別正規化。
- 日頻執行依交易日曆決定 target trading date，先查 persisted cache／Core freshness；完整則冪等略過，缺漏才依核准來源優先序抓取。FinMind 僅在已核准 dataset 的官方來源缺漏／不可用時作 fallback，禁止由 Admin page load 或 Mart／Agent 呼叫。
- 新聞等高頻來源使用獨立 execution、bounded overlap window、content hash／URL dedup、quota、retention 與 safe failure，不與日頻全市場工作綁成單一長任務。

### 3.2 第一階段資料源

- TWSE／TPEx OHLCV、PE/PB、法人。
- MOPS／FinMind fallback 三類財報。
- 官方 benchmark。
- 公司事件。
- 市場活動與 issued shares／turnover。
- 來源契約加入 coverage tier、cadence、market、scope、authorization status、retention 與 safe provenance。
- 股票 master 動態維護上市／上櫃狀態；不得以固定 1,700 或 2,000 檔作完整性判斷。
- Anue／鉅亨新聞、FinData-compatible、`mlouielu/twstock` 先建立候選 adapter 評估卡，不直接納入 runtime dependency。審查在 Admin「資料營運中心 → 資料源設定」完成，涵蓋 license／terms／robots、rate limit、retention／再發布、穩定性、欄位與內容重複度、成本及安全；只有 `official`／`approved_fallback` 可啟用。
- Anue 的 10 分鐘 cadence 在審查通過前保持 disabled；FinData 優先與既有 TWSE／TPEx adapter 比較並避免重複；twstock 只作行情 fallback／解析參考，其技術指標若採用須由 Mart 以版本化 deterministic feature 重算。

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
- 新增 `mart_industry_analysis`，以產業 membership snapshot 為範圍保存五角色產業結論、共通／分歧 evidence、風險、完整度與 prompt revision。
- 新增 `mart_symbol_analysis`，為指定個股獨立保存五角色輸出、evidence、missing data、analysis outcome 與實際 prompt revision；CIO 聚合仍寫入 `mart_master_investment_memo`。
- 七個 Mart schema 均使用 versioned Iceberg table／partition；至少保存 symbol／industry／coverage、
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
- 五角色 prompt 使用有 schema 的 versioned template，支援全域角色預設及產業／個股 override；解析優先序為個股 → 產業 → 全域。每次 execution 固定實際 prompt revision ID 至 immutable governance snapshot，修改不得回寫歷史分析。
- prompt revision 具 draft／active／retired、effective time、變更理由、reviewer、optimistic lock 與 audit；啟用前須通過 structured-output、evidence-only、prompt-injection 與 forbidden-field 驗證。

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
- 產業與個股分析可由 Admin 解析至正確 immutable Mart artifact；切換 prompt revision 後只影響新 execution，舊結果仍可依 revision 重現。

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

- 保留「資料營運中心」名稱與入口；`/admin/stocks` 使用 tablist／單面板模式，右側一次只顯示目前功能，不同功能不得整頁同時堆疊。
- 分頁至少包含：股票管理、股票資料狀態、最近執行、資料源健康、核心 50 名單、排程與保存設定、資料源設定、AI Prompt、Mart 分析。
- 股票管理支援跨頁批次選取；股票資料狀態與 execution／DQ／quarantine 明細以類 Excel 的欄列表格呈現，支援 sticky header、排序、篩選、分頁與欄位顯示，不以 raw JSON 作主要介面。
- Collection／Analysis 分開觸發。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。
- 全市場／核心 50 membership、effective date、cadence、來源授權狀態與 quota 管理；超過 50 檔必須拒絕。
- 「資料源設定」提供候選 adapter review checklist 與狀態轉換，保存證據、reviewer、理由與 audit；`candidate`／`blocked` 不得出現可成功啟用的控制。
- 「AI Prompt」按五角色管理全域／產業／個股 prompt revision、預覽 resolved template 與歷史 diff；保存不直接啟動 Mart Job。
- 「Mart 分析」按 analysis date、產業、symbol、角色、prompt revision、analysis outcome 與 publication status 篩選 `mart_industry_analysis`／`mart_symbol_analysis`，只讀已持久化 artifact。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `ui.md`。
- tab 具鍵盤操作、ARIA 與可分享 query-string deep link；重載後保留所選分頁，未選面板不重複抓取大型 details。

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
