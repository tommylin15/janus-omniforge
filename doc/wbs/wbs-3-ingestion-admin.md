# Janus WBS 3 — Ingestion、Core 與 Admin

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

### 3.2B 個人關注股深度追蹤

- 由 authenticated watchlist 形成去識別化的 active symbol membership；control DB 只保存收集用 symbol、effective time、理由與 cadence，不保存 user-to-symbol 對應。
- MVP 保留最多 50 個 active distinct symbols 的 quota／成本護欄，但不再提供「50 大」產品名單或推薦語意。
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
- Admin 開放股票管理、Collection／backfill、股票資料狀態、最近執行、資料源健康、去識別化深度追蹤名單、排程／Stage retention 與已核准資料源設定。
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
