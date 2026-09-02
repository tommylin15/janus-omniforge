# Janus — Work Breakdown Structure

版本：1.8
基準：資料產品優先、GCP-first monorepo、GCS／Iceberg／DuckDB、Flutter／FastAPI 雙入口、開發期 30% gate

## 已完成 WBS 索引

WBS 0、1、2、4 已完成並移至
[archive/wbs-completed-through-2026-08-31.md](archive/wbs-completed-through-2026-08-31.md)。
本檔只保留仍含未完成範圍的 WBS。

## WBS 3 — Ingestion + Core + Admin Data Operations

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
- 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。只有 `official`／`approved_fallback` 可啟用。

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

### 3.3 Core 寫入安全檢查

- required key、type、date、duplicate、range、cross-source check。
- null 保留；0 依欄位語意處理。
- corporate action／極端漲跌不直接刪除。
- 失敗資料進 quarantine，合格資料寫 Iceberg Core。
- 本節只保留避免錯寫、資料毀損與 future leakage 的最小 trust-boundary 檢查；跨源校準、品質評分、完整 DQ dashboard 與門檻調優排到 WBS 8.4，且必須在 Admin／User UI 驗收後執行。

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
- 使用 Secret Manager credential 與 private IP，完成 ingestion、DuckDB query、FastAPI、Admin Web 與 Mart Cloud Run／Jobs control DB smoke tests。

### 3.8 Dev Stage → Core → Admin Data Operations MVP（第一階段）

- 本階段只完成資料營運閉環；Mart、LLM、Flutter 公開研究頁與私人交易不在範圍。
- Admin 開放股票管理、Collection／backfill、股票資料狀態、最近執行、資料源健康、核心 50 名單、排程／Stage retention 與已核准資料源設定。
- Collection 必須由 persisted queue consumer claim，依序留下 execution item、Stage manifest／quarantine、Core commit fence 與 terminal status；Admin 查詢不得呼叫上游來源。
- 排程設定成功保存後自動 reconcile 至既有 Cloud Scheduler；retention／cleanup 只清除已有 Core commit fence 的 execution。
- Analysis action 與「Mart 分析」在 persisted Mart consumer 完成前 hidden／disabled，不得建立無 consumer 的 queued execution。
- 股票狀態、execution item、寫入安全與 quarantine 使用 bounded、可排序／篩選／分頁的結構化表格；不得顯示 raw payload、object URI、secret、完整 upstream error 或 traceback。
- 股票刪除 guard 涵蓋 collection config、execution、market、report、fundamental 引用並顯示安全摘要；所有設定異動保存 audit。

### 3.9 第一階段驗收條件

- 先以既有 5 檔 canary 完成手動 Collection、指定日期 backfill、同日 replay、failure／retry 與 Stage cleanup。
- 連續 3 個交易日由既有 Scheduler 正常完成；expected／received／missing、8 個核准來源狀態、Core row/hash/date/null profile 與成本摘要均有證據。
- canary 通過後才擴至當日 enabled 全市場；market-scope endpoint 維持單次抓取與 symbol fan-out，不逐檔重複請求。
- queue claim concurrency、connection exhaustion、PostgreSQL restart／reconnect、Direct VPC／firewall 與 Free Tier guard 實機通過。
- 營運者只透過 Admin 即可設定、觸發、追蹤、定位失敗並安全重跑，不需登入 GCP 或直接查資料庫。
- 驗收只使用既有 dev 資源；不得部署 production、提高既有限額或建立新付費資源。

## WBS 4J — 個人交易筆記 MVP（第二階段）

### 4J.1 Ledger／API

- Dev User 使用 Google OIDC／Google Sign-In 與獨立 User OAuth client／audience；API 驗證 issuer、audience、expiry，以 Google `sub` 對應內部 UUID `user_id`，email 只供顯示。Dev 可使用 User allowlist，不建立自有密碼系統。
- 建立最小 `services/api` FastAPI app，只含 health、上述 User auth boundary 與 `/api/v1/me/journal/*`；User token 不得存取 `/api/v1/admin/*`，既有 WSGI Admin 在 WBS 6 回歸完成前保留。
- PostgreSQL 以獨立 schema／role 保存 append-only 使用者交易 event、reversal／replacement、idempotency key、optimistic version 與單調遞增 `ledger_version`；金額使用固定精度 decimal，不建立 outbox。
- `/api/v1/me/journal/*` 提供新增、更正、歷史、positions、年度 PnL、匯出與刪除；身分只取自 authenticated user，不接受 client 指定 `user_id`。

### 4J.2 Private Core／Mart

- private pipeline 依 persisted checkpoint 批次讀取 `ledger_version`，將新 ledger event 冪等地直接正規化至 Private Iceberg Core；失敗從最後成功 checkpoint 重跑，不建立 Private Stage／DataSrc。
- 產製 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；使用第一階段股票 master／行情 Core，MVP 成本法固定移動平均，估值缺價不得當成 0。
- Private Mart 只由 `/api/v1/me/*` 依 authenticated user 讀取，不進 public publication index、話題或排行榜；公開 `mart_scoped_analysis` 完成後再加入 symbol-scope 個人化 overlay。

### 4J.3 最小 Flutter

- 第二階段只啟用「筆記／我的」：交易表單、歷史、更正、持股、已實現／未實現與年度損益、匯出及刪除。
- 「今日／探索／個股分析」顯示 coming soon／disabled，不得觸發 scraper、Agent 或 LLM。
- 不串券商、不自動匯入、不自動下單；FIFO 等第二成本法等會計／稅務語意與回歸測試完成後再評估。

### 4J.4 驗收條件

- PostgreSQL ledger 只保存交易事實、冪等鍵與 pipeline checkpoint，不保存 Mart payload。
- 使用者 A 無法讀寫或推測使用者 B 的 ledger／Private Core／Mart；交易更正、跨年損益、超賣拒絕、缺價、重跑與刪除路徑可重現。
- User／Admin OAuth audience 混用、偽造或 client 指定 `user_id` 均被拒絕；email 變更不改變資料所有權。
- Flutter 不重算正式損益；所有結果可追至 ledger version、Private Iceberg snapshot 與 valuation date。

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
- 新增單一 `mart_scoped_analysis`，以 market／industry／symbol scope 保存五角色輸出、membership snapshot、evidence、missing data、analysis outcome、prompt version 與 CIO 聚合 payload。
- 新增 `mart_market_regime_daily`、`mart_sector_rotation_daily`、`mart_topic_trends_daily`、`mart_candidate_health` 與 `mart_daily_brief`；每日摘要只組合同一 analysis-as-of 的已發布成品，不重算上游分數。
- 公開 Mart schema 均使用 versioned Iceberg table／partition；至少保存 symbol／industry／coverage、
  analysis date、上述 lineage、completeness、confidence、data quality、publication／
  analysis outcome，以及 evidence／artifact reference。不得只保存無法追溯來源的最終分數。
- `mart_scoped_analysis` 的 aggregate payload 保存 screening／risk／sentiment 摘要、aggregate score、bull／bear、contradictions、contributions、Devil's Advocate 反證、blocked／insufficient-data reason 與 CIO 結構化摘要。

### 5.2 五角色與 Validator

- 五個 discriminated role payload。
- nullable score、confidence、missing_data、evidence。
- URL、時間、單位、duplicate、stale、conflict、future validation。
- Evidence 必須引用可定位的 provenance／Core snapshot；未核准來源、缺 publication
  time 或超過 `analysis_as_of` 的資料不得成為角色或 LLM 輸入。
- 五角色使用 repository 版控的固定 structured prompt，不提供 Admin 編輯或 scope override。每次 execution 固定 prompt version／content hash 至 immutable governance snapshot；修改不得回寫歷史分析。

### 5.3 Aggregator／Publication

- 初始權重與 effective weight。
- bull／bear／contradictions／contributions。
- Devil's Advocate 反證階段與 `mart_scoped_analysis` CIO aggregate payload；兩者只使用合格 evidence。
- 30% development gate。
- manual review、critical、high≥75 blocking。
- immutable governance snapshot version。
- `insufficient_data` 是 completeness gate 的分析結果，必須與 publication lifecycle
  狀態分欄保存；實作前須讓 spec、contracts、API 與 UI 使用同一語意。只有
  `publishable`／`published` 可進公開 service index。

### 5.4 LLM

- 第一版 LLM provider 只使用 Gemini。
- Structured output 與 evidence-only prompt。
- Gemini 發生 429／`RESOURCE_EXHAUSTED` 或 provider unavailable 時 bounded retry；仍失敗或其他錯誤皆結構化失敗，不寫 placeholder。

### 5.5 Mart writer

- GCS Mart bucket 保存 Iceberg／Parquet data 與 metadata、versioned feature／role／
  evidence／aggregation payload、model／evaluation artifact 與完整結構化 report；大型 governance diff 亦留在 GCS。
- PostgreSQL 的市場分析邊界只保存 catalog、control、publication、audit、report metadata
  與 bounded service index，包括 object URI、snapshot ID、hash、version 與狀態；私人
  ledger 使用獨立 schema／role。不得保存完整 report、feature 或 evidence payload。
- publication schema 使用 migration、唯一鍵、retention、bounded pool 與
  workload-specific role；blocked／insufficient-data 成品不得進 publishable view。
- 發出 `mart.report.ready.v1`。

### 5.6 驗收條件

- Analysis 不呼叫 scraper。
- LLM 關閉時 deterministic output 不改變。
- blocked 不進 publishable view。
- 同一 Core snapshot + governance version 可重現相同 deterministic 結果。
- Contract、Iceberg schema evolution 與儲存邊界測試證明 PostgreSQL 沒有完整 Mart payload，且 publication index 可解析至正確 immutable GCS／Iceberg artifact。
- market／industry／symbol 分析可由 Admin 解析至正確 immutable `mart_scoped_analysis` artifact；切換 repository prompt version 後只影響新 execution，舊結果仍可依 version／hash 重現。
- 市場狀態、每日摘要、板塊輪動、熱門話題與候選健康度可由相同 analysis-as-of 重建，且 Flutter 不參與分數計算。

## WBS 6 — FastAPI、Flutter User 與 Admin

### 6.1 FastAPI

- 擴充 WBS 4J 建立的最小 `services/api` FastAPI app；將現有 WSGI handler 逐路由遷移並以 contract tests 保持既有 Admin 行為，完成後才移除 WSGI boundary。
- `/api/v1/public/*` 提供 health、daily brief、sector rotation、topics、candidates、stock health、history、Kline、events。
- `/api/v1/me/*` 提供交易新增／更正、positions 與年度 PnL；身分只取自驗證內容，不接受 client 指定 `user_id`。
- `/api/v1/admin/*` 保留控制面能力；public、private 與 admin router 分離 response model、auth、CORS、rate limit、IAM 與 audit。
- cursor／pagination、safe error、404 waiting state；不公開 raw payload、blocked、secret、traceback 或 private artifact reference。

### 6.2 Flutter User App

- 建立 `apps/user_app`，使用 Flutter Material 3 與平台原生元件；不先引入第三方 state／UI 套件。
- 兩層主動線：今日顯示市場狀態、每日摘要、板塊輪動、熱門話題與候選股；探索提供搜尋與完整列表。
- 個股首屏依序顯示健康度圓環、籌碼狀態與 `Icons.psychology` 白話 AI Card；K 線、Metrics、五角色與 provenance 預設收在進階資料。
- 個人交易筆記提供手動交易表單、歷史明細、持股、已實現／未實現與年度損益；正式結果只讀 Private Mart，不在 Flutter 重算。
- 「我的」提供私人 ledger 匯出與可稽核刪除流程；刪除涵蓋 PostgreSQL、Private Core／Mart 與 cache。
- 支援 light／dark／system theme、phone／iPad／web responsive、VoiceOver／TalkBack 與至少 44×44 target。
- User App 不顯示 Admin 導覽、公開績效排行榜、下單或券商同步控制。

### 6.3 Admin UI

- WBS 3 已負責 Stage／Core Data Operations 的可操作閉環；本節延伸公開 Mart、governance 與 reports，不重建第二套資料營運入口。
- 保留「資料營運中心」名稱與入口；`/admin/stocks` 使用 tablist／單面板模式，右側一次只顯示目前功能，不同功能不得整頁同時堆疊。
- 分頁至少包含：股票管理、股票資料狀態、最近執行、資料源健康、核心 50 名單、排程與保存設定、資料源設定、Mart 分析。
- 股票管理支援跨頁批次選取；股票資料狀態與 execution／DQ／quarantine 明細以類 Excel 的欄列表格呈現，支援 sticky header、排序、篩選、分頁與欄位顯示，不以 raw JSON 作主要介面。
- Collection／Analysis 分開觸發。
- WBS 3 第一階段只啟用 Collection；Analysis 與「Mart 分析」在 WBS 5 persisted consumer 完成前 hidden／disabled。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。
- 全市場／核心 50 membership、effective date、cadence、來源授權狀態與 quota 管理；超過 50 檔必須拒絕。
- 「資料源設定」只管理已核准來源；候選來源維持 disabled／blocked 設定，不提供審查或啟用控制。
- 「Mart 分析」按 analysis date、scope、industry、symbol、角色、prompt version、analysis outcome 與 publication status 篩選 `mart_scoped_analysis`，只讀已持久化 artifact。
- Admin 使用獨立入口與認證；一般 Admin 營運頁不得瀏覽使用者交易內容。只有另行核准的隱私事件處理流程可接觸必要最小 metadata，且必須 audit。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- Flutter 不自行計算正式損益；User 與 Admin 入口、token audience、CORS 與導覽分離。
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `ui.md`。
- tab 具鍵盤操作、ARIA 與可分享 query-string deep link；重載後保留所選分頁，未選面板不重複抓取大型 details。
- 詳細 User／Admin 驗收依 `ui.md`；今日頁所有卡片必須使用同一 analysis-as-of，交易筆記通過跨使用者隔離與更正事件測試。

## WBS 7 — 安全、監控與 FinOps

### 7.1 IAM／Secret

- ingestion、Mart、FastAPI 與 Admin Web 分離 service account；Flutter client 不持有 GCP service-account credential。
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

- pytest、FastAPI contract tests、Flutter analyze／widget tests、Vitest、Playwright、TypeScript、build。
- schema／migration／Iceberg evolution 測試。
- failure、retry、idempotency、rollback 測試。

### 8.3 實機與 A11y

- Flutter Android／iOS／Web、iOS Safari、Android Chrome、iPad Safari。
- VoiceOver、TalkBack、keyboard、touch、safe area。
- WCAG AA 實際對比。

### 8.4 UI 驗收後的資料品質強化

- 本節有順序 gate：Admin 資料營運流程、Flutter 今日／探索／健康檢查／交易筆記與實機 A11y 尚未通過前不得開工。
- 完成跨源一致性、null profile、freshness、coverage、schema drift、outlier／corporate-action 校準與 quality-score 版本化。
- 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的品質折減，不得改寫歷史 Mart。
- Admin DQ dashboard 顯示結構化摘要、quarantine drill-down、門檻 revision 與 evidence；不提供 raw payload 旁路。
- 以已驗收 UI 的真實閱讀問題調整 DQ 門檻；完成前保留 30% development gate，不宣稱 production-grade 品質。

### 8.5 Release

- dev → staging → production 同一 digest。
- canary、rollback、backup／restore、runbook。
- 人工 production approval。

### 8.6 驗收條件

- 所有 release gate 通過才可宣稱正式上線。
- 任何 blocked item 都有 owner、deadline、evidence link。

## 建議里程碑

| 里程碑 | 範圍 | 完成定義 |
|---|---|---|
| M0 | WBS 0–1 | 雲端 workspace、monorepo、CI/CD、IaC 可運作 |
| M1 | WBS 2–4 | PostgreSQL Free Tier VM → 2330 Source → Stage → DuckDB／Iceberg Core，bounded query 可冷啟動 |
| M1.5 | WBS 3 | 5 檔 canary 連續 3 個交易日後擴全市場，Stage／Core／Admin Data Operations 閉環通過 |
| M1.75 | WBS 4J | 個人交易 ledger、Private Core／Mart 與最小 Flutter「筆記／我的」通過隔離及重跑驗收 |
| M2 | WBS 5 | 市場／板塊／話題／候選健康度 Mart、30% gate 與 blocked 正確 |
| M3 | WBS 6 | 擴充 FastAPI、公開 Flutter 與 Admin governance／reports 完整讀取 persisted Mart |
| M4 | WBS 7–8 | UI 實機驗收後完成 DQ 強化、監控、安全、PIT、canary／rollback |
