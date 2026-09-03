# Janus — TODO

版本：1.9
用途：只保留未完成工作與目前驗收條件；完成證據移至 archive。

已完成項目與歷史 checkpoint：

- [TODO 完成紀錄（截至 2026-08-31）](archive/todo-completed-through-2026-08-31.md)
- [TODO 完成紀錄（2026-09-02）](archive/todo-completed-2026-09-02.md)
- [TODO 完成紀錄（2026-09-03）](archive/todo-completed-2026-09-03.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)

目前執行順序：

1. 完成 WBS 3 的 Dev Stage → Core → Admin Data Operations MVP。
2. 完成 WBS 4J 個人交易筆記 MVP；可先於公開 Mart／Agents／LLM。
3. 再執行全市場深化、WBS 5 Intelligence Mart、公開 FastAPI／Flutter 與後續 PIT／發布。

## P0 — Admin Data Operations MVP

- [ ] 將股票資料狀態、execution item、寫入安全／quarantine 的 raw JSON 主視圖改為類 Excel 欄列表格；支援 sticky header、排序、篩選、分頁、欄位顯示與按需子表，且不得暴露 raw payload／object URI／完整 upstream error。

- [ ] 其餘 Admin 大型列表查詢須在 repository 層完成 bounded indexed cursor pagination；股票與 execution 已完成，明細維持按需載入。

- [ ] 完整實作股票刪除 guard，涵蓋 collection config、execution、market、report、fundamental 等跨資料域引用，並在 UI 顯示各類引用數量與不可刪除原因。

- [x] 在 WBS 5 persisted Mart consumer 完成前，將 Admin Analysis action 與「Mart 分析」hidden／disabled，且不得建立無 consumer 的 queued execution；Collection queue consumer、lease recovery、terminal state、item persistence 與指定來源／日期 backfill runtime 維持可用。（2026-09-02：dev revision `janus-web-00037-g25` 的 live Playwright 與 API smoke 通過；第一階段只顯示七個資料營運分頁，Analysis POST 回 400 且 execution IDs 不變，五檔 backfill／replay／failure execution 均由 persisted worker claim 至 terminal state。）

## P0 — Stage／Core 與 Admin MVP 驗證

- [ ] PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM restart/reconnect、retention/pruning tests。（migration／Web role contract／retention-pruning 自動測試已通過；queue claim、connection exhaustion、VM restart/reconnect 實機驗證仍待完成）

- [ ] Direct VPC egress／firewall tests：指定 workload 可連 `5432`，public internet、未授權 identity 與其他 network tag 不可連線。

- [ ] Free Tier gcloud guard tests：只允許一台 `e2-micro`、eligible `us-central1` zone、全部 Standard Persistent Disk ≤30 GB、無 external IP／NAT／snapshot／replica／Serverless VPC connector。

- [ ] UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。
  （2026-09-02：實際 dev URL 的 live Playwright、API/runtime 與安全輸出已通過；
  revision／digest 詳見 operations-and-testing。真人 Google login 仍未執行。）

- [ ] 5 檔 canary 由既有 Scheduler 連續 3 個交易日正常完成；expected／received／missing、8 個核准來源狀態、Core row/hash/date/null profile 與成本摘要均留下證據。（2026-09-03：首日 execution `janus-ingestion-core-8mvg4` 經既有一次 retry 後失敗，連續成功為 0/3；詳見 operations-and-testing。）

- [ ] canary 通過後才擴至當日 enabled 全市場；market-scope endpoint 單次抓取並 symbol fan-out，不逐檔重複請求。

- [ ] 第一階段完成定義：營運者只透過 Admin 即可設定已核准來源與核心名單、觸發／排程 Collection、查看 Stage／Core／quarantine、定位失敗並安全重跑，不需登入 GCP 或直接查資料庫。

## P1（第二階段／WBS 4J）— 個人交易筆記 MVP

- [ ] 建立最小 `services/api` FastAPI app，只包含 health、Google OIDC User auth boundary 與 `/api/v1/me/journal/*`；使用獨立 User OAuth client／audience，驗證 issuer／audience／expiry，以 Google `sub` 對應內部 UUID `user_id`，email 只供顯示。既有 WSGI Admin 保留至後續回歸完成。

- [ ] PostgreSQL 建立隔離的 append-only trade ledger、reversal／replacement、optimistic version、idempotency key、單調遞增 `ledger_version`、user-leading indexes 與 RLS／等價 ownership guard；金額一律固定精度 decimal，不建立 outbox。

- [ ] 建立 PostgreSQL ledger → Private Iceberg Core batch pipeline：依 persisted checkpoint 讀取新 `ledger_version`，冪等寫入後才推進 checkpoint，失敗可重跑；不建立 Private Stage／DataSrc。使用獨立 bucket prefix／namespace／role／retention，public、一般 Admin 與其他使用者不可讀取。

- [ ] 建立 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl`、`mart_user_annual_pnl`；使用第一階段股票 master／行情 Core，MVP 成本法固定移動平均，缺價不顯示 0。

- [ ] 建立 `/api/v1/me/journal/*` typed contract：新增交易、更正、歷史、持股、年度損益、匯出與刪除；身分只取自驗證內容，不接受 client 指定 `user_id`。

- [ ] 實作本人 ledger 匯出與可稽核、可重試的私人資料刪除工作流；涵蓋 PostgreSQL、Private Core／Mart、cache、完成證據與依法或安全要求保留的最小 audit metadata。

- [ ] 建立最小 Flutter「筆記／我的」流程；「今日／探索／個股分析」保持 coming soon／disabled，不得觸發 scraper、Agent 或 LLM。

- [ ] 驗證超賣拒絕、更正事件、費稅、跨年、估值日期、重跑冪等、刪除與使用者 A／B 隔離；Private artifact 不得進 public service index。

- [ ] 驗證 User／Admin audience 混用、偽造或 client 指定 `user_id` 均被拒絕，email 變更不改變資料所有權；Dev User allowlist 不得授予 Admin 權限。

- [ ] 未來個人化分析只在 authenticated-user 邊界內引用公開 `mart_scoped_analysis` 的 symbol scope；不阻擋交易筆記 MVP，也不把私人交易資料寫回公開 Mart。

- [ ] 不實作券商同步、自動下單、公開績效排行榜或 FIFO 切換；這些需另行法遵／會計／安全決策。

## P1 — 全市場量化網

- [ ] 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。

- [ ] 對 market-scope endpoint 採單次抓取、批次快取與 symbol fan-out；不得逐檔重複請求。

- [ ] 產製每日 market coverage report：expected／received／missing symbols、來源成功數、freshness、合法 empty／unavailable 與最小寫入安全摘要；完整 DQ 延至 P4。

- [ ] 建立 `mart_screening_signals`：技術面突破、量能、流動性與異動候選；結果不得在 collection request 內即時計算。

- [ ] 驗證全市場同日 replay 冪等、bounded memory／runtime、GCS 成本與缺檔不被誤標成功。

## P1 — 核心 50 放大鏡

- [ ] 以 control DB 核心 membership 收集深度財報、公司事件／重大訊息、公司行動與 PIT publication time。

- [ ] 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。

- [ ] 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。

- [ ] 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。

- [ ] 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables；entity-to-symbol 保留規則／模型版本、confidence、evidence 與人工覆核狀態，sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。

- [ ] 驗證核心名單變更不改寫歷史 membership，移出名單後停止深度收集但保留依法可保存的歷史 provenance。

## P1 — Mart／Agents

- [ ] 建立可執行的 `intelligence_mart` package／Cloud Run Job entrypoint、bounded runtime 設定與 persisted queue claim；2026-08-31 已完成 connectivity entrypoint、1 CPU／1 GiB／300s／1 retry Job 與實機 smoke，persisted queue claim 仍待完成，Analysis 排隊成功不得視為完成。

- [ ] persisted Mart consumer 完成並通過 terminal-state／retry 驗收後，才重新啟用 Admin Analysis action 與「Mart 分析」。

- [ ] 建立 `core.dataset.ready.v1` → Mart 的 workflow／event trigger；只接受 ingestion 最小寫入安全檢查／Core commit 成功且帶有 execution ID、immutable Core snapshot ID 的事件，並驗證 ingestion failed／partial 不觸發、重送保持冪等。不得以同時各自排程 ingestion 與 Mart 取代依賴串接。

- [ ] Mart Job 只透過 Direct VPC egress 與專用 read/write role 存取 PostgreSQL metadata；2026-08-31 已驗證 catalog／publication role 與 private path，feature／evidence payload 的 GCS／Iceberg 寫入邊界仍待實作與驗收。

- [ ] 固定 Mart execution input contract：`execution_id`、`analysis_as_of`、Core snapshot ID、schema／feature／model version 與 immutable governance snapshot version；禁止 Analysis 即時補抓或改寫 Core。

- [ ] 建立公開 versioned Iceberg Mart schemas：screening／core alpha／risk／sentiment、單一 `mart_scoped_analysis`，以及 `mart_market_regime_daily`、`mart_sector_rotation_daily`、`mart_topic_trends_daily`、`mart_candidate_health` 與 `mart_daily_brief`；共用欄位涵蓋 analysis date、lineage、completeness、confidence、data quality、analysis outcome、publication status 與 evidence／artifact reference。

- [ ] 建立市場狀態與每日摘要 pipeline；`mart_daily_brief` 只能組合同一 analysis-as-of 的已發布 market／sector／topic／candidate artifact，不重算上游分數。

- [ ] 建立板塊輪動 deterministic features：產業 membership snapshot、5 日法人買超力道、力道變化、20 日成交金額與漲潮／輪動／觀望／退潮狀態。

- [ ] 建立候選股健康度 contract：`stock_id`、`stock_name`、1–100 `mart_health_score`、受控 `chips_status`、evidence-only `ai_whitepaper_analysis`、analysis-as-of、資料狀態與 evidence references；LLM 不得計算分數。

- [ ] 定義 repository 版控的五角色固定 structured prompt contract；不提供 Admin 編輯或 scope override，Mart execution 固定 prompt version／content hash 至 immutable governance snapshot。

- [ ] Fundamental features／Agent。

- [ ] Valuation features／Agent。

- [ ] Positioning features／Agent。

- [ ] Quant features／Agent。

- [ ] Event Risk features／Agent。

- [ ] Evidence Validator：驗證 URL、時間、單位、duplicate、stale、conflict、source authorization 與 future leakage；evidence 必須可追至 provenance／Core snapshot。

- [ ] Devil's Advocate 反證階段只引用合格 evidence，不得自行補資料或產生無來源數字。

- [ ] Aggregator bull／bear／contradictions／contributions。

- [ ] 將 contracts、API／UI mapping 與 contract tests 同步為正式文件已固定的 `insufficient_data` 語意：它是 completeness gate 的 analysis outcome／reason，與 `PublicationStatusV1` 分欄；低於 30% 或無有效分數不得進公開 index。

- [ ] blocked／publishable view；只有 `publishable`／`published` 可進公開 service index。

- [ ] immutable governance snapshot version。

- [ ] deterministic rerun tests。

- [ ] `mart_scoped_analysis` 的 industry scope 只分析該次 immutable membership snapshot；symbol scope 產出獨立 role payload。兩者只用 PIT 合格 evidence，並驗證 prompt version 變更不覆寫歷史 Mart。

## P1 — LLM

- [ ] 建立 evidence-only structured prompt。

- [ ] 禁止模型產生未在 evidence 出現的數字。

- [ ] 禁止模型修改 score、confidence、quality、publication。

- [ ] 接 Gemini；429／`RESOURCE_EXHAUSTED`／provider unavailable 採 bounded retry，不接第二套 provider。

- [ ] 非 429 結構化失敗。

- [ ] LLM 失敗不得寫 placeholder report。

- [ ] LLM 關閉時 deterministic outputs 完全一致。

## P1 — Mart 閉環

- [ ] 建立 GCS Mart warehouse／Iceberg namespace 與 versioned partition strategy，產製 `spec.md` 定義的公開 Mart tables；不得以固定表數掩蓋市場／板塊／話題／候選／每日摘要資料產品。

- [ ] 將 feature／role／evidence／aggregation payload、model／evaluation artifact、完整結構化 report 與大型 governance diff 寫入 GCS；保存 object URI、snapshot ID、hash 與版本。

- [ ] 以 migration 建立 PostgreSQL report metadata 與 publication service index；使用唯一鍵、bounded pool、statement timeout、retention 與 workload-specific role。

- [ ] PostgreSQL 的市場分析邊界只保存 catalog／control／publication／audit／service-index metadata 與 artifact reference；私人 ledger 使用獨立 schema／role。以 schema／integration test 阻擋完整 report、feature、evidence 或 Private Mart payload 寫入 Free Tier VM。

- [ ] 發出 `mart.report.ready.v1`。

- [ ] 驗證 blocked 不進 publishable view。

- [ ] 驗證 publication index 可解析至正確 immutable GCS／Iceberg artifact，且 blocked／insufficient-data 成品不會被公開 API／Web 讀取。

- [ ] 驗證 2330 在相同 Core snapshot、governance、schema／feature／model version 下可重現 deterministic Mart；LLM 關閉時 deterministic output 不變。

## P1 — Admin Governance／Reports

- [ ] Governance／audit metadata 使用 PostgreSQL migration、optimistic lock、retention 與專用 role；大 payload／diff artifact 放 GCS。

- [ ] Governance typed editing、validation、diff、history、optimistic lock。

- [ ] Report block／unblock 保存理由與 audit。

- [ ] 「Mart 分析」以表格檢視 market／industry／symbol scope 的 `mart_scoped_analysis`，支援 analysis date、scope、industry、symbol、角色、prompt version、analysis outcome、publication status 篩選，並可解析至 immutable Core／Mart artifact。

## P1 — FastAPI／Flutter User

- [ ] 擴充 WBS 4J 的最小 `services/api` FastAPI app，將現有 WSGI routes 逐一以 contract tests 遷移；完成 Admin／Core query 回歸後才移除 WSGI boundary。

- [ ] 分離 `/api/v1/public/*`、`/api/v1/me/*`、`/api/v1/admin/*` 的 router、response model、auth、CORS、rate limit、IAM 與 audit。

- [ ] Public API 提供 health、daily brief、sector rotation、topics、candidates、stock health、history、Kline、events。

- [ ] 未知／停用股票 404。

- [ ] 已啟用無資料顯示等待批次。

- [ ] 查無資料不觸發 scraper／Agent／LLM。

- [ ] blocked、raw payload、secret、traceback 不公開。

- [ ] Public API 只讀 PostgreSQL service index／publishable metadata，使用 bounded read-only pool 與 statement timeout；不得直連 catalog owner 或觸發即時抓取。Private journal API 使用獨立 role 並強制 authenticated-user ownership。

- [ ] 建立 `apps/user_app` Flutter + Material 3 app；完成「今日、探索、筆記、我的」獨立導覽，不顯示 Admin 入口。

- [ ] 今日頁顯示同一 analysis-as-of 的市場狀態、三則重點、板塊輪動、熱門話題與五張候選股健康卡；資料日期不一致時顯示 partial。

- [ ] 實作 `StockHealthCard`：健康度圓環、籌碼 Chip、`Icons.psychology` 白話 AI Card、資料日期、風險與「非獲利機率」；blocked／insufficient 不顯示分數。

- [ ] 個股 K 線、Metrics、五角色與 provenance 放在預設收合的進階資料，不得先於健康度與白話摘要。

- [ ] 交易筆記 UI 支援新增、更正、歷史篩選、持股與年度損益；正式成本／損益只讀 Private Mart，不在 Flutter 重算。

- [ ] 全市場 screening 與核心標的深度頁分流；顯示 coverage、freshness、來源健康與資料不足。

## P1 — 全系統自動化測試

- [ ] Backend pytest、FastAPI contract tests、Flutter analyze／widget tests、Admin Vitest。

- [ ] Flutter Android／iOS／Web responsive／interaction 與 Admin Playwright。

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

- [ ] 對 weights／40-60 thresholds 做 walk-forward。

- [ ] 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] Flutter Android／iOS／Web 的 phone、tablet、desktop breakpoint。

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

## P4 — UI 驗收後的資料品質強化（最後執行）

順序 gate：Admin 資料營運中心與 Flutter「今日／探索／個股健康／交易筆記」完成自動化、實機與 A11y 驗收前，本節全部保持 blocked，不得提前開工。

- [ ] source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。

- [ ] 建立跨源一致性、null profile、freshness、coverage、schema drift、outlier 與 corporate-action 的完整 DQ ruleset；版本化門檻與例外理由。

- [ ] 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的 quality discount；只影響新 Mart revision，不改寫歷史結果。

- [ ] 完成 Admin DQ dashboard、quarantine drill-down、quality revision diff 與 evidence link；不提供 raw payload／object URI 旁路。

- [ ] 以 UI 驗收發現的閱讀誤差、partial／stale 混淆與缺價案例建立回歸集，再決定是否提高 30% development gate。

- [ ] 對 30% gate 做 coverage／錯誤率分析，產出可審查的門檻 revision 提案。

- [ ] 完成 DQ replay、false-positive／false-negative、跨源衝突、資料延遲與 private/public 隔離驗收後，才能提出 production-grade data quality revision。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
