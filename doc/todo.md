# Janus × OmniForge — TODO

版本：1.3
用途：只保留未完成工作與目前驗收條件；完成證據移至 archive。

已完成項目與歷史 checkpoint：

- [TODO 完成紀錄（截至 2026-08-31）](archive/todo-completed-through-2026-08-31.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)

## P0 — 資料源雙軌契約與控制面重整

- [ ] 定義文本 entity-to-symbol Core schema；保留規則／模型版本、confidence、evidence 與人工覆核狀態，但 sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。（契約／WBS／todo 邊界已固定；schema 實作待 P1）

- [ ] source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。（契約欄位與 P1 telemetry work item 已建立；runtime 聚合待實作）

## P0 — 排程 Stage → Core、回跑與暫存生命週期

- [ ] Admin UI 可調整啟用資料源、排程時間、交易日／holiday override、單日或區間回跑參數、Stage retention／cleanup 開關；所有設定須驗證、稽核並以 control database 持久化。

- [ ] Admin UI 提供 execution 狀態、Stage／Core commit、清理結果、資料源失敗與 backfill 進度；敏感錯誤只顯示 safe message。

- [ ] 增加整合測試：排程閉環、前次 Stage 安全清理、失敗保留、日期區間回跑、指定來源回跑、Core 重跑去重、benchmark 獨立更新與 Admin 設定驗證。

## P0 — Admin Data Operations MVP

- [ ] 股票資料狀態頁：Core 最新日期、資料集覆蓋、row count、DQ／quarantine 摘要。

- [ ] 將股票資料狀態、execution item、DQ／quarantine 的 raw JSON 主視圖改為類 Excel 欄列表格；支援 sticky header、排序、篩選、分頁、欄位顯示與按需子表，且不得暴露 raw payload／object URI／完整 upstream error。

- [ ] 其餘 Admin 大型列表查詢須在 repository 層完成 bounded indexed cursor pagination；股票與 execution 已完成，明細維持按需載入。

- [ ] Admin UI 管理全市場／核心 50 membership 與 effective date；超過 50 檔時必須拒絕，所有異動須留下 audit。

- [ ] 將目前唯讀的資料源設定實體化為管理介面，支援 cadence、coverage tier 與 authorization status；`candidate`／`blocked` 來源不得啟用，異動須驗證並留下 audit。

- [ ] 完整實作股票刪除 guard，涵蓋 collection config、execution、market、report、fundamental 等跨資料域引用，並在 UI 顯示各類引用數量與不可刪除原因。

- [ ] 將 Admin 建立的 Collection／Analysis queued execution 接上可運作的 queue consumer、Ingestion／Mart Job，並以 persisted 狀態與 safe message 呈現端到端結果；排隊成功不得視為工作完成。（2026-08-31：Collection trigger-filtered claim、lease recovery、retry／terminal state 與 item persistence 已完成；Analysis consumer 依賴 P1 Mart pipeline）

- [ ] 將 Admin 排程與 Stage retention／cleanup 設定接上實際 Cloud Scheduler 與 cleanup runtime；保留 optimistic version、audit 與 Core commit cleanup fence，設定寫入成功不得誤報 runtime 已套用。

## P0 — Stage／Core 與 Admin MVP 驗證

- [ ] PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM restart/reconnect、retention/pruning tests。（migration／Web role contract／retention-pruning 自動測試已通過；queue claim、connection exhaustion、VM restart/reconnect 實機驗證仍待完成）

- [ ] Direct VPC egress／firewall tests：指定 workload 可連 `5432`，public internet、未授權 identity 與其他 network tag 不可連線。

- [ ] Free Tier gcloud guard tests：只允許一台 `e2-micro`、eligible `us-central1` zone、全部 Standard Persistent Disk ≤30 GB、無 external IP／NAT／snapshot／replica／Serverless VPC connector。

- [ ] UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。

## P1 — 全市場量化網

- [ ] 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。

- [ ] 對 market-scope endpoint 採單次抓取、批次快取與 symbol fan-out；不得逐檔重複請求。

- [ ] 產製每日 market coverage report：expected／received／missing symbols、來源成功數、freshness、合法 empty／unavailable 與 DQ 摘要。

- [ ] 建立 `mart_screening_signals`：技術面突破、量能、流動性與異動候選；結果不得在 collection request 內即時計算。

- [ ] 驗證全市場同日 replay 冪等、bounded memory／runtime、GCS 成本與缺檔不被誤標成功。

## P1 — 核心 50 放大鏡

- [ ] 以 control DB 核心 membership 收集深度財報、公司事件／重大訊息、公司行動與 PIT publication time。

- [ ] 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。

- [ ] 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。

- [ ] 建立 Anue／鉅亨新聞候選評估卡；10 分鐘 cadence 在授權、robots／API terms、rate limit、保存／引用／再發布及成本核准前保持 disabled。核准後使用獨立 execution、bounded overlap window、URL／content hash dedup、PIT publication time 與 entity-to-symbol evidence。

- [ ] 盤點 FinData-compatible 候選 repository／變體，與現有 TWSE／TPEx 法人、融資融券、持股 adapter 比對 license、維護狀態、欄位正確性與重複度；既有官方 adapter 可涵蓋時不新增依賴。

- [ ] 評估 `mlouielu/twstock` 作行情 fallback／解析參考；驗證 request limit、即時資料條款、schema 與穩定性。不得直接採用其買賣點作 Core 事實，所需 MA／訊號須在 Mart 以版本化 deterministic feature 重算。

- [ ] Podcast／PTT／Dcard／股市爆料同學會等另類文本先完成平台條款、PII、刪除、引用與再發布政策；未核准不得收集。

- [ ] 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables。

- [ ] 驗證核心名單變更不改寫歷史 membership，移出名單後停止深度收集但保留依法可保存的歷史 provenance。

## P1 — Mart／Agents

- [ ] 建立可執行的 `intelligence_mart` package／Cloud Run Job entrypoint、bounded runtime 設定與 persisted queue claim；2026-08-31 已完成 connectivity entrypoint、1 CPU／1 GiB／300s／1 retry Job 與實機 smoke，persisted queue claim 仍待完成，Analysis 排隊成功不得視為完成。

- [ ] 建立 `core.dataset.ready.v1` → Mart 的 workflow／event trigger；只接受 ingestion DQ／Core commit 成功且帶有 execution ID、immutable Core snapshot ID 的事件，並驗證 ingestion failed／partial 不觸發、重送保持冪等。不得以同時各自排程 ingestion 與 Mart 取代依賴串接。

- [ ] Mart Job 只透過 Direct VPC egress 與專用 read/write role 存取 PostgreSQL metadata；2026-08-31 已驗證 catalog／publication role 與 private path，feature／evidence payload 的 GCS／Iceberg 寫入邊界仍待實作與驗收。

- [ ] 固定 Mart execution input contract：`execution_id`、`analysis_as_of`、Core snapshot ID、schema／feature／model version 與 immutable governance snapshot version；禁止 Analysis 即時補抓或改寫 Core。

- [ ] 建立 `mart_screening_signals`、`mart_core_alpha`、`mart_risk_portfolio`、`mart_alternative_sentiment`、`mart_master_investment_memo`、`mart_industry_analysis` 與 `mart_symbol_analysis` versioned Iceberg schemas；共用欄位須涵蓋 symbol／industry／coverage、analysis date、lineage、completeness、confidence、data quality、analysis outcome、publication status、prompt revision 與 evidence／artifact reference。

- [ ] 定義五角色 versioned prompt template contract：全域／產業／個股 scope、個股 → 產業 → 全域解析順序、draft／active／retired、effective time、reviewer、reason、optimistic version 與 audit；Mart execution 固定 resolved prompt revision IDs 至 immutable governance snapshot。

- [ ] Fundamental features／Agent。

- [ ] Valuation features／Agent。

- [ ] Positioning features／Agent。

- [ ] Quant features／Agent。

- [ ] Event Risk features／Agent。

- [ ] Evidence Validator：驗證 URL、時間、單位、duplicate、stale、conflict、source authorization 與 future leakage；evidence 必須可追至 provenance／Core snapshot。

- [ ] Devil's Advocate 反證階段只引用合格 evidence，不得自行補資料或產生無來源數字。

- [ ] Aggregator bull／bear／contradictions／contributions。

- [ ] 統一 `insufficient_data` 契約語意：作為 completeness gate 的 analysis outcome／reason，與 `PublicationStatusV1` 分欄；同步修正 `spec.md`、contracts、API／UI mapping 與 contract tests，低於 30% 或無有效分數不得進公開 index。

- [ ] blocked／publishable view；只有 `publishable`／`published` 可進公開 service index。

- [ ] immutable governance snapshot version。

- [ ] deterministic rerun tests。

- [ ] RAG 只檢索 analysis-as-of 可見的 Core／Mart snapshot，並以測試阻擋 future leakage。

- [ ] 產業 Agent 只分析該次 immutable industry membership snapshot；指定個股 Agent 產出獨立 role payload。兩者只用 PIT 合格 evidence，並驗證 prompt revision 變更不覆寫歷史 Mart。

## P1 — LLM

- [ ] 建立 evidence-only structured prompt。

- [ ] 禁止模型產生未在 evidence 出現的數字。

- [ ] 禁止模型修改 score、confidence、quality、publication。

- [ ] 接 Gemini，並固定 provider 優先順序為 Gemini → OpenRouter → GroqCloud。

- [ ] 實作 Gemini → OpenRouter → GroqCloud 的 429／`RESOURCE_EXHAUSTED`／provider unavailable fallback。

- [ ] 非 429 結構化失敗。

- [ ] LLM 失敗不得寫 placeholder report。

- [ ] LLM 關閉時 deterministic outputs 完全一致。

## P1 — Mart 閉環

- [ ] 建立 GCS Mart warehouse／Iceberg namespace 與 versioned partition strategy，產製七張 versioned Mart tables（既有五張加 `mart_industry_analysis`、`mart_symbol_analysis`）。

- [ ] 將 feature／role／evidence／aggregation payload、model／evaluation artifact、完整結構化 report、Markdown export 與大型 governance diff 寫入 GCS；保存 object URI、snapshot ID、hash 與版本。

- [ ] 以 migration 建立 PostgreSQL report metadata 與 publication service index；使用唯一鍵、bounded pool、statement timeout、retention 與 workload-specific role。

- [ ] PostgreSQL 只保存 catalog／control／publication／audit／service-index metadata 與 artifact reference；以 schema／integration test 阻擋完整 report、feature 或 evidence payload 寫入 Free Tier VM。

- [ ] 發出 `mart.report.ready.v1`。

- [ ] 驗證 blocked 不進 publishable view。

- [ ] 驗證 publication index 可解析至正確 immutable GCS／Iceberg artifact，且 blocked／insufficient-data 成品不會被 Web／OmniForge 匯出。

- [ ] 驗證 2330 在相同 Core snapshot、governance、schema／feature／model version 下可重現 deterministic Mart；LLM 關閉時 deterministic output 不變。

## P1 — Admin Governance／Reports

- [ ] Governance／audit metadata 使用 PostgreSQL migration、optimistic lock、retention 與專用 role；大 payload／diff artifact 放 GCS。

- [ ] Governance typed editing、validation、diff、history、optimistic lock。

- [ ] Report block／unblock 保存理由與 audit。

- [ ] 「AI Prompt」管理五角色全域／產業／個股 revisions，提供 typed validation、resolved preview、diff、activate／retire 與歷史；保存／預覽不得直接觸發 Mart Job。

- [ ] 「Mart 分析」以表格檢視產業／個股已持久化分析，支援 analysis date、industry、symbol、角色、prompt revision、analysis outcome、publication status 篩選，並可解析至 immutable Core／Mart artifact。

## P1 — Public API／UI

- [ ] Health、topics、summary。

- [ ] Latest report、history、Kline、events。

- [ ] 未知／停用股票 404。

- [ ] 已啟用無資料顯示等待批次。

- [ ] 查無資料不觸發 scraper／Agent／LLM。

- [ ] blocked、raw payload、secret、traceback 不公開。

- [ ] Public API 只讀 PostgreSQL service index／publishable metadata，使用 bounded read-only pool 與 statement timeout；不得直連 catalog owner 或觸發即時抓取。

- [ ] 完成 `ui.md` 所有 P0 元件。

- [ ] 全市場 screening 與核心標的深度頁分流；顯示 coverage、freshness、來源健康與資料不足。

- [ ] 情緒溫度計、多空雷達圖與風險紅綠燈只顯示後端 versioned Mart，前端不得自行計分。

## P1 — 全系統自動化測試

- [ ] Backend pytest、contract tests、Frontend Vitest。

- [ ] Playwright responsive／interaction。

- [ ] TypeScript／ESLint／production build。

- [ ] Iceberg schema evolution tests。

- [ ] Failure／retry／idempotency tests。

- [ ] PostgreSQL role isolation、pool exhaustion、restart/reconnect、migration rollback 與 publication index tests。

- [ ] 安全輸出與 log redaction tests。

## P2 — PIT 與治理校準

- [ ] PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。

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

- [ ] production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。

- [ ] 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。

- [ ] incident runbook。

- [ ] production 人工批准。

## P3 — OmniForge／PodBrief

- [ ] 只從 publishable Mart／service index 匯出 report 的 Markdown exporter；不得掃描 PostgreSQL control/catalog 或將大 payload 複製回 Free Tier VM。

- [ ] YAML schema validator。

- [ ] 小白／一般／分析師／Auditor 四階視圖。

- [ ] 雙鏈與標籤。

- [ ] Podcast 授權與保存政策。

- [ ] 逐字稿、時間碼與摘要 provenance。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
