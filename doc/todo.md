# Janus — TODO

版本：2.0
用途：只保留未完成工作與目前驗收條件；完成證據移至 archive。

已完成項目與歷史 checkpoint：

- [TODO 完成紀錄（截至 2026-08-31）](archive/todo-completed-through-2026-08-31.md)
- [TODO 完成紀錄（2026-09-02）](archive/todo-completed-2026-09-02.md)
- [TODO 完成紀錄（2026-09-03）](archive/todo-completed-2026-09-03.md)
- [TODO 完成紀錄（2026-09-05）](archive/todo-completed-2026-09-05.md)
- [TODO 完成紀錄（2026-09-06）](archive/todo-completed-2026-09-06.md)
- [TODO 完成紀錄（2026-09-09）](archive/todo-completed-2026-09-09.md)
- [TODO 完成紀錄（2026-09-11）](archive/todo-completed-2026-09-11.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)

## 目前進度（2026-09-11）

- WBS 4J 獨立 MVP：journal／note／Private Iceberg 完整交易、重跑、刪除與 A／B 隔離已結案；僅依賴 WBS 5 的個人化 analysis overlay 尚未啟用。
- WBS 4C：Agent Runtime／AgentEvent、security contract、context sources、MCP host、Gemini REST、OpenRouter provider、Private Storage、Skills contract、Codex auth lifecycle 與 Chat API contract 的已完成部分已歸檔；Codex Chat API durable continuation、真人 device-code 流程與整合驗收仍未完成。
- WBS-4C-CODEX-BRIDGE checkpoint：雙向 stdio JSON-RPC、Threads／Turns／Items、device-code managed login、request-bound Approvals、共用 MCP dynamic-tool path 與 `turn/started` 事件驅動 cancellation 已完成；GCP Cloud Build contract tests 5／5 通過，Cloud Run health 3／3 通過，live Codex cancellation 200 通過，checkpoint reconnect 通過。現有全域 Secret／固定 owner 仍僅是 dev POC，不代表 owner-scoped auth lifecycle 完成。驗收 build `2d95aa6e-cc4e-47d5-97ae-ce9dcfafc479`、revision `janus-agent-gateway-00017-tpf`、digest `sha256:b03a041f2ddf19d3028777d7531f94599fee728024dac471156932ad64df9541`。
- WBS-4C-PRIVATE-STORAGE：migration 016、Private Iceberg assistant events／Skill revisions、PostgreSQL bounded index、credential-shaped field fail-closed、冪等重跑、A／B 隔離與 Codex auth cleanup pending 契約已完成；GCP dev evidence 詳見 `spec/operations-and-testing.md`。
- WBS-4C-CODEX-AUTH-LIFECYCLE：完成部分已移至 [`archive/todo-completed-2026-09-09.md`](archive/todo-completed-2026-09-09.md)；互動式 device-code login 真人流程仍未驗收。
- WBS 3 收尾：`WBS-3-ACCEPTANCE` 暫停於 1/3；既有 Scheduler 繼續自動累積 canary，切換至 WBS 5 期間不得宣告 WBS 3 結案。queue claim、connection exhaustion、VM restart/reconnect、bundle runtime probes、Direct VPC／identity negative evidence 與 billing／Free Tier dev guard 已通過。
- 最新驗證：Codex POC bridge Cloud Build `9dec1039-0052-420d-9ef1-6719ed46991a` 與 OpenRouter／Gemini runtime probe `20050302-861a-4c84-84ad-c96f21903776` 均 SUCCESS；完整證據與既有驗證見 `spec/operations-and-testing.md` 與 [`secret_list.md`](secret_list.md)。
- Secret bundle consolidation：已完成程式、測試、GCP dev prepare／部署與三個 Job smoke；尚待 Codex A/B live auth entry isolation，以及明確授權後的 legacy cleanup，詳見 [`doc/secret_list.md`](secret_list.md)。

## 下一步執行佇列

1. 【Sol】`WBS-5`：目前執行；先完成 persisted analysis queue claim 與 `core.dataset.ready.v1` immutable input fence，再依 WBS 5 切片逐項驗收。
2. 【Sol】`WBS-3-ACCEPTANCE`：暫停於 canary 1/3；只由既有 Scheduler 自動累積，不與 WBS 5 同回合結案。
3. 【Sol】`WBS-4C-ACCEPTANCE`：完成 Cloud Run、provider、資料源、MCP、Skills、streaming、approval、Grounding、privacy 與刪除整合驗收。
4. 【Luna】`WBS-6` → 【Sol】`WBS-7` → 依逐項標籤執行 `WBS-8`；WBS 4J 個人化 overlay 等 `mart_scoped_analysis` 可用後再做。

## 模型確認規則

- 每次只取佇列中的一個原子任務。正式執行前，AI 必須先提醒建議模型與任務名稱，等使用者明確回覆已切換模型後才開始；完成後停止，下一項重新確認。
- 下方每個未完成待辦均已標示【Sol】或【Luna】；若一項同時含安全／底層與 UI／CRUD，執行前先依上方佇列拆分，不用單一模型包辦混合範圍。

## P1（私人 P0 後續）— Admin Data Operations MVP


## P1（私人 P0 後續）— Stage／Core 與 Admin MVP 驗證

- [ ] 【Sol】 PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM restart/reconnect、retention/pruning tests。（queue claim、connection exhaustion、VM restart/reconnect 已於 GCP dev 通過；migration／Web role contract／retention-pruning 自動測試已通過）


- [ ] 【Sol】 UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。
  （2026-09-02：實際 dev URL 的 live Playwright、API/runtime 與安全輸出已通過；
  revision／digest 詳見 operations-and-testing。真人 Google login 仍未執行。）

- [ ] 【Sol】 5 檔 canary 由既有 Scheduler 連續 3 個交易日正常完成；expected／received／missing、8 個核准來源狀態、Core row/hash/date/null profile 與成本摘要均留下證據。（bundle 修正後已完成 Scheduler smoke `janus-ingestion-core-j5qbv`；2026-09-11 的自動排程 execution `janus-ingestion-core-4zft5` 已完成資料日 2026-09-10，post-fix scheduled canary 目前 1/3，詳見 operations-and-testing。）

- [ ] 【Sol】 canary 通過後才擴至當日 enabled 全市場；market-scope endpoint 單次抓取並 symbol fan-out，不逐檔重複請求。

- [ ] 【Sol】 第一階段完成定義：營運者只透過 Admin 即可設定已核准來源與去識別化深度追蹤名單、觸發／排程 Collection、查看 Stage／Core／quarantine、定位失敗並安全重跑，不需登入 GCP 或直接查資料庫。

## P0（WBS 4J）— 個人記帳、筆記與關注股 MVP

- [ ] 【Sol】 個人化分析只在 authenticated-user 邊界內引用公開 `mart_scoped_analysis` 的 symbol scope；不阻擋記帳／筆記／關注股／聊天室 MVP，也不把私人資料寫回公開 Mart。


## P0（WBS 4C）— 多供應商私人助理／MCP／Skills

- [ ] 【Sol】 資料源只讀已發布 Janus Core／Mart 與 authenticated owner 的 Private Core／Mart；實作 `GET /api/v1/me/ai-sources`、thread-bound `context-preview`／短效 opaque `context_ref` 與 service-identity-only internal resolve。只接受 typed selector，不接受 SQL、GCS URI、object path 或 client `user_id`。外部來源須有 allowlist、授權、日期、provenance、quota 與外送政策，不在 chat request 即時爬取未核准來源；既有 public／journal／portfolio／ingestion API 不改語意。

- [ ] 【Sol】 Codex 以 Cloud Run 容器內 App Server stdio JSON-RPC 與 managed OAuth／device-code 驅動；整合 Threads／Turns／Items／Approval Requests、取消及 sandbox。不得使用 OpenAI API key、Responses／Codex API 或其他直接付費 fallback。

- [ ] 【Sol】 Codex auth lifecycle 必須先於 Chat API／Assistant UI：authenticated owner 經 service-authenticated internal request 傳入 Gateway；A／B 共用一個 Secret bundle，但 payload 以 owner UUID 分區，並各自使用隔離 `CODEX_HOME` 與 App Server process。refresh 以 read-modify-write 建立新 bundle version、驗證該 owner 後銷毀舊版本；刪除只移除該 owner entry。刪除時拒絕該 owner 新 login／turn／artifact write，停止 session、logout、刪 owner auth，失敗保留 `CLEANUP_PENDING` 並可重試。Gateway 不接受 client owner／Secret name，不授 project-wide Secret Manager admin；MVP 維持 `max-instances=1` 以序列化 bundle 寫入，擴展多 instance 前須改用 distributed lock／CAS。




- [ ] 【Sol】 驗證 Cloud Run scale-to-zero／cold start／timeout／中斷重連、三 runtime、內外資料源 provenance、MCP stdio／HTTP／SSE、動態工具、Skill 權限、Codex auth／approval／取消、Grounding、quota／provider unavailable、context 外送提示、A／B 隔離、stream 續接／去重、Iceberg 重跑／匯出／刪除與無 placeholder。Codex auth 必須覆蓋 A／B load／rotate／destroy 隔離、orphan auth、cleanup 403 重試、刪除期間寫入拒絕、session eviction／logout、刪後重新登入與 secrets 不落 log／DB／Iceberg；另驗證 Iceberg snapshot／orphan file 與 GCS object version 的實際物理清除期限。若 Cloud Run 無法滿足不可中斷長 turn、持久 daemon、特殊 sandbox 權限或實測資源需求，先提交 Compute Engine／GKE 成本、安全、維運與退出評估，取得使用者決定後才能採用。（2026-09-09 checkpoint：provider live probe `fd435461-71fc-4b8f-86bf-e583431900c5`、Grounding/stream live probe `31b2f8ac-25fa-4bbb-aca2-46c2ea3210aa`、approval/quota contracts `7960f7b5-e1fe-4b63-86cb-50d4b878a8fd`、Private Storage/privacy/delete regression `275ec264-0dde-46d7-b755-c49ad90b870e`、context sources、Skills、Web bundle 與 MCP transports GCP dev 通過；Codex 0.153.4 POC `ca212276-2dde-4ce1-bbdf-6982c3d943a2`、device-code probe `e7b91774-8682-4077-8f5d-d50054d9640d`、直接 App Server probe `eff86a80-a94a-44da-af76-0f1efccef287` 與 alpha probe `e04655d7-28bd-47fa-9a28-8fa98bf61358` 均因 Codex device-auth request error 失敗，網路診斷 `9a251707-c075-40d2-9f32-a6c75eb11023` 已證實 endpoint 可正常回傳 device code；managed-auth／approval live flow 保持未完成，詳見 operations-and-testing。）
- 2026-09-09 後續：CA remediation image／revision 已部署，真人 device-code、cancellation、checkpoint reconnect、logout／destroy 已通過；approval-handle dev revision `janus-agent-gateway-00038-j78` 已完成真人 side-effect turn（approval request／accept／resolved、command exitCode=0、turn completed；詳見 `spec/operations-and-testing.md`）。其餘整合驗收仍未完成。
- 2026-09-10：Gateway handle／Chat API／approval／cancel／SSE cursor contract 本地回歸 150 tests、Flutter widget 2 tests 通過；Gateway `00041-fn`、API `00048-x6x` 已部署 dev，Gateway 維持 `min=0 / max=1 / concurrency=2`，僅新增 dev-only `CODEX_SANDBOX_MODE=read-only`。OpenRouter/Gemini live build `7d661ef6-3ac5-4dd3-9f69-080966746ad0` SUCCESS；OAuth client ID 已在既有 API bundle、client secret 欄位缺失；MCP allowlist 修正後 job execution 未留下 application log。owner B auth 已重新登入並上傳為 enabled version 7，本機 `account/read(refreshToken=true)` 成功；新 revision approval live probe `cc5fecfa-b0e4-46f8-be22-391b96e2e15d` 通過真實 `approval_request`、錯誤 binding rejection、accept command completion 與 decline no-command-completion。Chat API 真人 Google OAuth E2E、SSE reconnect、MCP execution 與完整整合仍未完成，不勾選 `WBS-4C-ACCEPTANCE`；臨時 IAM 與 probe 檔案已清空。

## P1（WBS 4R）— 個人曝險、績效與 AI 壓力測試

- [ ] 【Sol】 建立 investment profile：risk tolerance、investment horizon、primary goal、minimum cash ratio；目前值保留 bounded private index，revision history 寫入 Private Iceberg，只有使用者 opt-in 才能加入 chat context。

- [ ] 【Sol】 建立具 effective time／provenance 的多產業 membership 與 `mart_user_exposure`；分攤方法、現金、持股市值、valuation date 與 membership snapshot 可追溯，Flutter／LLM 不重算。

- [ ] 【Sol】 建立年度現金流與 XIRR；先通過買賣、現金／股票股利、更正、跨年、無根、多根與缺資料測試，非唯一有效結果不得填 0。

- [ ] 【Sol】 建立 deterministic portfolio stress scenarios 與 cash-safety result，再交由使用者選定的 Codex／ChatGPT／Gemini profile 解釋；模型不得修改數值或產生下單動作。

- [ ] 【Sol】 建立 private investment-profile、portfolio summary／exposure／performance／stress-test typed endpoints 與 Flutter 儀表板；通過 A／B 隔離、重跑、資料日期、缺價、profile opt-in、citation 與免責聲明驗收。

## P1 — 全市場量化網

- [ ] 【Sol】 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。

- [ ] 【Luna】 對 market-scope endpoint 採單次抓取、批次快取與 symbol fan-out；不得逐檔重複請求。

- [ ] 【Luna】 產製每日 market coverage report：expected／received／missing symbols、來源成功數、freshness、合法 empty／unavailable 與最小寫入安全摘要；完整 DQ 延至 P4。

- [ ] 【Sol】 建立 `mart_screening_signals`：技術面突破、量能、流動性與異動候選；結果不得在 collection request 內即時計算。

- [ ] 【Sol】 驗證全市場同日 replay 冪等、bounded memory／runtime、GCS 成本與缺檔不被誤標成功。

## P1 — 個人關注股深度追蹤

- [ ] 【Sol】 以 authenticated watchlist 形成去識別化 active symbol membership，收集深度財報、公司事件／重大訊息、公司行動與 PIT publication time；Admin 不得取得 user-to-symbol 對應。

- [ ] 【Sol】 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。

- [ ] 【Sol】 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。

- [ ] 【Sol】 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。

- [ ] 【Sol】 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables；entity-to-symbol 保留規則／模型版本、confidence、evidence 與人工覆核狀態，sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。

- [ ] 【Sol】 驗證關注需求變更不改寫歷史 membership；最後一位使用者取消關注後停止新的深度收集，但保留依法可保存的歷史 provenance。MVP 超過 50 個 distinct active symbols 時安全拒絕並顯示 quota。

## P1 — Mart／Agents

- [ ] 【Sol】 建立可執行的 `intelligence_mart` package／Cloud Run Job entrypoint、bounded runtime 設定與 persisted queue claim；2026-08-31 已完成 connectivity entrypoint、1 CPU／1 GiB／300s／1 retry Job 與實機 smoke。2026-09-11 已實作 analysis-only `FOR UPDATE SKIP LOCKED` lease、bounded retry／terminal transition 與 immutable input／artifact completion fence；本機 targeted tests 9/9 通過、`git diff --check` 通過。GCP dev migration 017、函式 EXECUTE-only privilege、queue rejection／retry execution `janus-intelligence-mart-zj8zw` 與 smoke execution `janus-intelligence-mart-fq96m` 已驗證；matching Core manifest 的 SHA-256／execution／snapshot fence、deterministic create-if-absent Mart input artifact、首次 succeeded `janus-intelligence-mart-z5tn8` 與 replay `janus-intelligence-mart-xr64n` 已驗證；Cloud Build `fe30fa4f-7cd4-4bb7-8500-41d1a8cfe077` SUCCESS。完整 feature／role／publication pipeline 仍待後續切片；Analysis 排隊或 claim 成功不得視為完成。

- [ ] 【Sol】 persisted Mart consumer 完成並通過 terminal-state／retry 驗收後，才重新啟用 Admin Analysis action 與「Mart 分析」。

- [ ] 【Sol】 建立 `core.dataset.ready.v1` → Mart 的 workflow／event trigger；只接受 ingestion 最小寫入安全檢查／Core commit 成功且帶有 execution ID、immutable Core snapshot ID 的事件，並驗證 ingestion failed／partial 不觸發、重送保持冪等。不得以同時各自排程 ingestion 與 Mart 取代依賴串接。

- [ ] 【Sol】 Mart Job 只透過 Direct VPC egress 與專用 read/write role 存取 PostgreSQL metadata；2026-08-31 已驗證 catalog／publication role 與 private path，feature／evidence payload 的 GCS／Iceberg 寫入邊界仍待實作與驗收。

- [ ] 【Sol】 固定 Mart execution input contract：`execution_id`、`analysis_as_of`、Core snapshot ID、schema／feature／model version 與 immutable governance snapshot version；禁止 Analysis 即時補抓或改寫 Core。

- [ ] 【Sol】 建立公開 versioned Iceberg Mart schemas：screening／core alpha／risk／sentiment、單一 `mart_scoped_analysis`，以及 `mart_market_regime_daily`、`mart_sector_rotation_daily`、`mart_topic_trends_daily`、`mart_candidate_health` 與 `mart_daily_brief`；共用欄位涵蓋 analysis date、lineage、completeness、confidence、data quality、analysis outcome、publication status 與 evidence／artifact reference。

- [ ] 【Sol】 建立市場狀態與每日摘要 pipeline；`mart_daily_brief` 只能組合同一 analysis-as-of 的已發布 market／sector／topic／candidate artifact，不重算上游分數。

- [ ] 【Sol】 建立板塊輪動 deterministic features：產業 membership snapshot、5 日法人買超力道、力道變化、20 日成交金額與漲潮／輪動／觀望／退潮狀態。

- [ ] 【Sol】 建立候選股健康度 contract：`stock_id`、`stock_name`、1–100 `mart_health_score`、受控 `chips_status`、evidence-only `ai_whitepaper_analysis`、analysis-as-of、資料狀態與 evidence references；LLM 不得計算分數。

- [ ] 【Sol】 定義 repository 版控的五角色固定 structured prompt contract；不提供 Admin 編輯或 scope override，Mart execution 固定 prompt version／content hash 至 immutable governance snapshot。

- [ ] 【Sol】 Fundamental features／Agent。

- [ ] 【Sol】 Valuation features／Agent。

- [ ] 【Sol】 Positioning features／Agent。

- [ ] 【Sol】 Quant features／Agent。

- [ ] 【Sol】 Event Risk features／Agent。

- [ ] 【Sol】 Evidence Validator：驗證 URL、時間、單位、duplicate、stale、conflict、source authorization 與 future leakage；evidence 必須可追至 provenance／Core snapshot。

- [ ] 【Sol】 Devil's Advocate 反證階段只引用合格 evidence，不得自行補資料或產生無來源數字。

- [ ] 【Sol】 Aggregator bull／bear／contradictions／contributions。

- [ ] 【Sol】 將 contracts、API／UI mapping 與 contract tests 同步為正式文件已固定的 `insufficient_data` 語意：它是 completeness gate 的 analysis outcome／reason，與 `PublicationStatusV1` 分欄；低於 30% 或無有效分數不得進公開 index。

- [ ] 【Sol】 blocked／publishable view；只有 `publishable`／`published` 可進公開 service index。

- [ ] 【Sol】 immutable governance snapshot version。

- [ ] 【Luna】 deterministic rerun tests。

- [ ] 【Sol】 `mart_scoped_analysis` 的 industry scope 只分析該次 immutable membership snapshot；symbol scope 產出獨立 role payload。兩者只用 PIT 合格 evidence，並驗證 prompt version 變更不覆寫歷史 Mart。

## P1 — 公開 Mart LLM

- [ ] 【Sol】 建立 evidence-only structured prompt。

- [ ] 【Sol】 禁止模型產生未在 evidence 出現的數字。

- [ ] 【Sol】 禁止模型修改 score、confidence、quality、publication。

- [ ] 【Sol】 公開批次 Mart 只接 Gemini，與 WBS 4C 的多供應商私人助理分離；不得使用 OpenAI／Codex API。啟用付費前須通過人工 billing gate，429／`RESOURCE_EXHAUSTED`／provider unavailable 採 bounded retry。

- [ ] 【Sol】 非 429 結構化失敗。

- [ ] 【Sol】 LLM 失敗不得寫 placeholder report。

- [ ] 【Sol】 LLM 關閉時 deterministic outputs 完全一致。

## P1 — Mart 閉環

- [ ] 【Sol】 建立 GCS Mart warehouse／Iceberg namespace 與 versioned partition strategy，產製 `spec.md` 定義的公開 Mart tables；不得以固定表數掩蓋市場／板塊／話題／候選／每日摘要資料產品。

- [ ] 【Sol】 將 feature／role／evidence／aggregation payload、model／evaluation artifact、完整結構化 report 與大型 governance diff 寫入 GCS；保存 object URI、snapshot ID、hash 與版本。

- [ ] 【Sol】 以 migration 建立 PostgreSQL report metadata 與 publication service index；使用唯一鍵、bounded pool、statement timeout、retention 與 workload-specific role。

- [ ] 【Sol】 PostgreSQL 的市場分析邊界只保存 catalog／control／publication／audit／service-index metadata 與 artifact reference；私人 ledger 使用獨立 schema／role。以 schema／integration test 阻擋完整 report、feature、evidence 或 Private Mart payload 寫入 Free Tier VM。

- [ ] 【Luna】 發出 `mart.report.ready.v1`。

- [ ] 【Luna】 驗證 blocked 不進 publishable view。

- [ ] 【Sol】 驗證 publication index 可解析至正確 immutable GCS／Iceberg artifact，且 blocked／insufficient-data 成品不會被公開 API／Web 讀取。

- [ ] 【Sol】 驗證 2330 在相同 Core snapshot、governance、schema／feature／model version 下可重現 deterministic Mart；LLM 關閉時 deterministic output 不變。

## P1 — Admin Governance／Reports

- [ ] 【Sol】 Governance／audit metadata 使用 PostgreSQL migration、optimistic lock、retention 與專用 role；大 payload／diff artifact 放 GCS。

- [ ] 【Luna】 Governance typed editing、validation、diff、history、optimistic lock。

- [ ] 【Luna】 Report block／unblock 保存理由與 audit。

- [ ] 【Luna】 「Mart 分析」以表格檢視 market／industry／symbol scope 的 `mart_scoped_analysis`，支援 analysis date、scope、industry、symbol、角色、prompt version、analysis outcome、publication status 篩選，並可解析至 immutable Core／Mart artifact。

## P1 — FastAPI／Flutter User

- [ ] 【Sol】 擴充 WBS 4J 的最小 `services/api` FastAPI app，將現有 WSGI routes 逐一以 contract tests 遷移；完成 Admin／Core query 回歸後才移除 WSGI boundary。

- [ ] 【Sol】 分離 `/api/v1/public/*`、`/api/v1/me/*`、`/api/v1/admin/*` 的 router、response model、auth、CORS、rate limit、IAM 與 audit。

- [ ] 【Luna】 Public API 提供 health、daily brief、sector rotation、topics、candidates、stock health、history、Kline、events；Private API 延續 WBS 4J／4C 的 journal、notes、watchlist 與 chats contract。

- [ ] 【Luna】 未知／停用股票 404。

- [ ] 【Luna】 已啟用無資料顯示等待批次。

- [ ] 【Luna】 查無資料不觸發 scraper／Agent／LLM。

- [ ] 【Sol】 blocked、raw payload、secret、traceback 不公開。

- [ ] 【Sol】 Public API 只讀 PostgreSQL service index／publishable metadata，使用 bounded read-only pool 與 statement timeout；不得直連 catalog owner 或觸發即時抓取。Private journal API 使用獨立 role 並強制 authenticated-user ownership。

- [ ] 【Luna】 建立 `apps/user_app` Flutter + Material 3 app；完成「今日、關注、筆記、AI、我的」獨立導覽，不顯示 Admin 入口。

- [ ] 【Luna】 今日頁顯示同一 analysis-as-of 的市場狀態、三則重點、板塊輪動、熱門話題與五張候選股健康卡；資料日期不一致時顯示 partial。

- [ ] 【Luna】 實作 `StockHealthCard`：健康度圓環、籌碼 Chip、`Icons.psychology` 白話 AI Card、資料日期、風險與「非獲利機率」；blocked／insufficient 不顯示分數。

- [ ] 【Luna】 個股 K 線、Metrics、五角色與 provenance 放在預設收合的進階資料，不得先於健康度與白話摘要。

- [ ] 【Luna】 個人工作台 UI 支援關注股、交易新增／更正、一般筆記 revision、歷史篩選、持股、年度損益與多供應商私人助理；正式成本／損益只讀 Private Mart，不在 Flutter 或模型重算。

- [ ] 【Luna】 全市場 screening 與個人關注股深度頁分流；顯示 coverage、freshness、來源健康與資料不足。

## P1 — 全系統自動化測試

- [ ] 【Luna】 Backend pytest、FastAPI contract tests、Flutter analyze／widget tests、Admin Vitest。

- [ ] 【Luna】 Flutter Android／iOS／Web responsive／interaction 與 Admin Playwright。

- [ ] 【Luna】 TypeScript／ESLint／production build。

- [ ] 【Luna】 Iceberg schema evolution tests。

- [ ] 【Luna】 Failure／retry／idempotency tests。

- [ ] 【Sol】 PostgreSQL role isolation、pool exhaustion、restart/reconnect、migration rollback 與 publication index tests。

- [ ] 【Sol】 安全輸出與 log redaction tests。

## P2 — PIT 與治理校準

- [ ] 【Sol】 PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。

- [ ] 【Sol】 5／20／60 交易日 outcome pipeline。

- [ ] 【Sol】 relative benchmark、MFE／MAE、coverage。

- [ ] 【Sol】 缺 publication time／provenance 樣本排除。

- [ ] 【Sol】 每個排除保留原因與 ID。

- [ ] 【Sol】 對 weights／40-60 thresholds 做 walk-forward。

- [ ] 【Sol】 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] 【Luna】 Flutter Android／iOS／Web 的 phone、tablet、desktop breakpoint。

- [ ] 【Luna】 iOS Safari。

- [ ] 【Luna】 Android Chrome。

- [ ] 【Luna】 iPad Safari。

- [ ] 【Luna】 VoiceOver／TalkBack。

- [ ] 【Luna】 WCAG AA contrast。

- [ ] 【Luna】 所有主要控制 ≥44×44。

- [ ] 【Luna】 K 線 pan／zoom／tooltip／替代表格。

- [ ] 【Luna】 Dialog focus trap、Escape、restore、scroll lock。

- [ ] 【Sol】 canary／rollback。

- [ ] 【Sol】 production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。

- [ ] 【Sol】 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。

- [ ] 【Sol】 incident runbook。

- [ ] 【Sol】 production 人工批准。

## P4 — UI 驗收後的資料品質強化（最後執行）

順序 gate：Admin 資料營運中心與 Flutter「關注／記帳／筆記／AI／個股健康」完成自動化、實機與 A11y 驗收前，本節全部保持 blocked，不得提前開工。

- [ ] 【Luna】 source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。

- [ ] 【Sol】 建立跨源一致性、null profile、freshness、coverage、schema drift、outlier 與 corporate-action 的完整 DQ ruleset；版本化門檻與例外理由。

- [ ] 【Sol】 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的 quality discount；只影響新 Mart revision，不改寫歷史結果。

- [ ] 【Luna】 完成 Admin DQ dashboard、quarantine drill-down、quality revision diff 與 evidence link；不提供 raw payload／object URI 旁路。

- [ ] 【Luna】 以 UI 驗收發現的閱讀誤差、partial／stale 混淆與缺價案例建立回歸集，再決定是否提高 30% development gate。

- [ ] 【Sol】 對 30% gate 做 coverage／錯誤率分析，產出可審查的門檻 revision 提案。

- [ ] 【Sol】 完成 DQ replay、false-positive／false-negative、跨源衝突、資料延遲與 private/public 隔離驗收後，才能提出 production-grade data quality revision。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
