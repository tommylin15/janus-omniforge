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
- [TODO 完成紀錄（2026-09-12：WBS-5）](archive/todo-completed-2026-09-12-wbs5.md)
- [TODO 完成紀錄（2026-09-13：WBS-6／WBS-7）](archive/todo-completed-2026-09-13-wbs6-wbs7.md)
- [TODO 完成紀錄（2026-09-16：WBS-6 usefulness feedback）](archive/todo-completed-2026-09-16-wbs6-usefulness-feedback.md)
- [TODO 完成紀錄（2026-09-16：WBS-8 outcome collection）](archive/todo-completed-2026-09-16-wbs8-outcome-collection.md)
- [TODO 完成紀錄（2026-09-17：WBS-8 pilot release baseline）](archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)

## 目前進度（2026-09-16）

- WBS 4J 獨立 MVP：journal／note／Private Iceberg 完整交易、重跑、刪除與 A／B 隔離已結案；僅依賴 WBS 5 的個人化 analysis overlay 尚未啟用。
- WBS 4C：Agent Runtime／AgentEvent、security contract、context sources、MCP host、Gemini REST、OpenRouter provider、Private Storage、Skills contract、Codex auth lifecycle 與 Chat API contract 的已完成部分已歸檔；Codex Chat API durable continuation、真人 device-code 流程與整合驗收仍未完成。
- WBS-4C-CODEX-BRIDGE checkpoint：雙向 stdio JSON-RPC、Threads／Turns／Items、device-code managed login、request-bound Approvals、共用 MCP dynamic-tool path 與 `turn/started` 事件驅動 cancellation 已完成；GCP Cloud Build contract tests 5／5 通過，Cloud Run health 3／3 通過，live Codex cancellation 200 通過，checkpoint reconnect 通過。現有全域 Secret／固定 owner 仍僅是 dev POC，不代表 owner-scoped auth lifecycle 完成。驗收 build `2d95aa6e-cc4e-47d5-97ae-ce9dcfafc479`、revision `janus-agent-gateway-00017-tpf`、digest `sha256:b03a041f2ddf19d3028777d7531f94599fee728024dac471156932ad64df9541`。
- WBS-4C-PRIVATE-STORAGE：migration 016、Private Iceberg assistant events／Skill revisions、PostgreSQL bounded index、credential-shaped field fail-closed、冪等重跑、A／B 隔離與 Codex auth cleanup pending 契約已完成；GCP dev evidence 詳見 `spec/operations-and-testing.md`。
- WBS-4C-CODEX-AUTH-LIFECYCLE：完成部分已移至 [`archive/todo-completed-2026-09-09.md`](archive/todo-completed-2026-09-09.md)；互動式 device-code login 真人流程仍未驗收。
- WBS 3 收尾：`WBS-3-ACCEPTANCE` 的 Scheduler 5-stock canary 已於 2026-09-15 完成 3/3；full enabled market 亦已完成 bounded GCP dev 驗收，證據已移至 [`archive/todo-completed-2026-09-15-wbs3-acceptance.md`](archive/todo-completed-2026-09-15-wbs3-acceptance.md) 與 [`archive/todo-completed-2026-09-15-wbs3-full-market.md`](archive/todo-completed-2026-09-15-wbs3-full-market.md)。當時 enabled universe 為 5 檔；queue claim、connection exhaustion、VM restart/reconnect、bundle runtime probes、Direct VPC／identity negative evidence 與 billing／Free Tier dev guard 已通過。
- WBS-5-SUPPLY-INTELLIGENCE-PLANNING：foundation／ontology、六 domain Source Matrix、seed graph、signal／Mart contract 與 Pilot measurement／epoch planning 已完成；Gate A ready for review，Gate B 仍須逐一完成來源授權。證據見 [`spec/supply-chain-planning.md`](spec/supply-chain-planning.md) 與 [`archive/todo-completed-2026-09-16-wbs5-supply-planning.md`](archive/todo-completed-2026-09-16-wbs5-supply-planning.md)。
- WBS-7-PILOT-LEDGER-DURABILITY【High-Completion Target—已滿足】：bounded daily／monthly logical backup 與 isolated restore 已完成；GCP dev evidence 見 [`archive/todo-completed-2026-09-16-wbs7-ledger-durability.md`](archive/todo-completed-2026-09-16-wbs7-ledger-durability.md)。
- WBS-8-PILOT-OUTCOME-COLLECTION【High-Completion Target—已滿足】：Pilot outcome pipeline 與 lineage 已完成；本機 4/4 targeted tests、GCP dev migration／acceptance 通過，證據見 [`archive/todo-completed-2026-09-16-wbs8-outcome-collection.md`](archive/todo-completed-2026-09-16-wbs8-outcome-collection.md)。
- WBS-8-PILOT-RELEASE-BASELINE【High-Completion Target—已滿足】：material-change baseline／epoch lineage 已完成；本機 4/4 targeted tests、既有 GCP dev migration／acceptance 與 Mart Job immutable image/env evidence 通過，證據見 [`archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md`](archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md)。
- 最新驗證：Codex POC bridge Cloud Build `9dec1039-0052-420d-9ef1-6719ed46991a` 與 OpenRouter／Gemini runtime probe `20050302-861a-4c84-84ad-c96f21903776` 均 SUCCESS；完整證據與既有驗證見 `spec/operations-and-testing.md` 與 [`secret_list.md`](secret_list.md)。
- Secret bundle consolidation：已完成程式、測試、GCP dev prepare／部署與三個 Job smoke；尚待 Codex A/B live auth entry isolation，以及明確授權後的 legacy cleanup，詳見 [`doc/secret_list.md`](secret_list.md)。
- WBS 4R 與全市場／關注股切片：source／contract 與 GCP dev acceptance 已完成，證據移至 [`archive/todo-completed-2026-09-14-wbs4r-market-scope.md`](archive/todo-completed-2026-09-14-wbs4r-market-scope.md)。實際全市場抓取仍受 WBS-3 canary 2/3 gate；分 K／Tick、新聞、研究仍受來源授權與成本 gate。
- Dev image cleanup repair：`janus-api` 已切換至現存 immutable digest，並刪除無 active 引用的 `mcp-acceptance`、舊 `web` 與舊 `janusai-poc/janus-postgres` image；兩個 Artifact Registry repo 仍維持每個 package 最新 1 版，active digest 保護風險詳見 `spec/operations-and-testing.md`。

## High-Completion Dev Pilot Target（planning marker；不變更正式 Entry Gate）

- 使用者選擇 High-Completion strategy：在不越過 Production、Post-Pilot evidence-dependent work、未核准 data source、frozen scope 與 human approval gates 的前提下，盡可能提高 Dev Pilot Day 1 完成度。
- `High-Completion Target` 是使用者選擇的較高完成度 execution strategy，不改變正式 `Dev Pilot Entry Gate`；未完成 target 中的非正式 blocker，不等同於正式 Entry Gate failure。
- 正式 `WBS-8-DEV-PILOT-ENTRY` Gate 不變；某項即使標記 `【High-Completion Target】`，也不代表其 governance classification 已變成 `Entry Blocker`。正式 `WBS-8-DEV-PILOT-ENTRY` checklist 保持獨立標記與判定。
- 35 個 logical target = 32 條目前未勾選 checklist + 3 條已滿足的既有 WBS：`WBS-6-PILOT-USEFULNESS-FEEDBACK`、`WBS-7-PILOT-LEDGER-DURABILITY`、`WBS-8-PILOT-OUTCOME-COLLECTION`。Useful feedback 的 Cloud Run rollout／真人 OAuth journey 已完成；其餘未完成項目仍由 Dev UI/runtime acceptance 追蹤，不視為已驗收。
- `todo.md` 目前共有 58 條未勾選 checklist；未標記的 26 條保留原 governance classification。Research Context planning 可按 High-Completion 提前完成，但仍屬 Pilot Evolution，不是正式 Entry blocker。

## 下一步執行佇列（兩條可平行 track）

### Track A：資料／市場安全

WBS-3-ACCEPTANCE 與 full enabled market bounded 驗收均已完成並歸檔；本次不自動開始下一個 WBS。

### Track B：Pilot readiness + ChatGPT MCP

以下項目可立即開始，不以前置完成 WBS-3-ACCEPTANCE 為條件：

1. 【Sol】WBS-6-CHATGPT-MCP-CONTRACT：確認 Custom MCP／OAuth compatibility 與三個 read-only tool contract。
2. 【Sol】WBS-6-CHATGPT-MCP-ADAPTER：依 contract 在既有 `janus-api` 建立 bounded read-only adapter；不安全時停止並提交架構決策；不等待 WBS-3。
3. 【Sol】WBS-8-CHATGPT-MCP-ACCEPTANCE：完成 connector acceptance；若外部 plan／UI 阻擋，等待使用者決定是否以 blocked connector 啟動 Pilot。

只有 `WBS-8-DEV-PILOT-ENTRY` 必須等待：

1. Track A 的 WBS-3 safety／full-market gate 完成。
2. Track B 四個既有 Pilot readiness gap ready。
3. `WBS-5-SUPPLY-INTELLIGENCE-PLANNING` 完成；這只要求正式 planning evidence，不要求六個 domain ingestion-ready。
4. ChatGPT MCP acceptance 完成，或因外部 plan／UI capability blocked 且經人工允許。

Entry Gate 通過後才記錄 `pilot_started_at`，進入 `WBS-8-DEV-PILOT-RUN` 的 6 calendar
months operational phase；完成後才可開始 `WBS-8-PROD-GO-NOGO`。

## 模型確認規則

- 每次只取佇列中的一個原子任務。正式執行前，AI 必須先提醒建議模型與任務名稱，等使用者明確回覆已切換模型後才開始；完成後停止，下一項重新確認。
- 每個日曆日第一次 Gemini 串接前，先查官方模型清單，選出當日前三個 Stable model，依序試用；優先 free tier，不自動開啟 paid gate，並受使用者明確授權的 scope／次數上限約束。全部失敗時維持 fail-closed、不得寫 placeholder。
- 下方每個未完成待辦均已標示【Sol】或【Luna】；若一項同時含安全／底層與 UI／CRUD，執行前先依上方佇列拆分，不用單一模型包辦混合範圍。

## P1（私人 P0 後續）— Admin Data Operations MVP


## P1（私人 P0 後續）— Stage／Core 與 Admin MVP 驗證

- [ ] 【Sol】 【High-Completion Target】 UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。
  （2026-09-02：實際 dev URL 的 live Playwright、API/runtime 與安全輸出已通過；
  revision／digest 詳見 operations-and-testing。真人 Google login 仍未執行。）

- [x] 【Sol】 canary 通過後才擴至當日 enabled 全市場；market-scope endpoint 單次抓取並 symbol fan-out，不逐檔重複請求。2026-09-15 以當時 enabled 5 檔 `1102`／`2327`／`2330`／`2381`／`4958` 完成：Cloud Run `janus-ingestion-core-tf66g`、control execution `2191139b-2dab-4bf4-886b-12735e6cdc02`，11 staged、1 legal empty、missing=0、failed=0；bounded config 已停用防止意外重跑。證據見 [`archive/todo-completed-2026-09-15-wbs3-full-market.md`](archive/todo-completed-2026-09-15-wbs3-full-market.md)。

- [ ] 【Sol】 【High-Completion Target】 第一階段完成定義：營運者只透過 Admin 即可設定已核准來源與去識別化深度追蹤名單、觸發／排程 Collection、查看 Stage／Core／quarantine、定位失敗並安全重跑，不需登入 GCP 或直接查資料庫。

## P0（WBS 4J）— 個人記帳、筆記與關注股 MVP

- [ ] 【Sol】 【High-Completion Target】 個人化分析只在 authenticated-user 邊界內引用公開 `mart_scoped_analysis` 的 symbol scope；不阻擋記帳／筆記／關注股／聊天室 MVP，也不把私人資料寫回公開 Mart。


## P0（WBS 4C）— 多供應商私人助理／MCP／Skills（Pilot frozen／deferred）

WBS-4C remaining expansion 在六個月 Dev Pilot 期間 frozen／deferred，除非 security、
correctness 或明確核准的 Pilot use case 必要；既有可用功能保留。`WBS-4C-ACCEPTANCE`
未完成部分不得宣稱完成，且不再是 active execution queue、Pilot Entry prerequisite
或 ChatGPT MCP prerequisite。

- [ ] 【Sol】 資料源只讀已發布 Janus Core／Mart 與 authenticated owner 的 Private Core／Mart；實作 `GET /api/v1/me/ai-sources`、thread-bound `context-preview`／短效 opaque `context_ref` 與 service-identity-only internal resolve。只接受 typed selector，不接受 SQL、GCS URI、object path 或 client `user_id`。外部來源須有 allowlist、授權、日期、provenance、quota 與外送政策，不在 chat request 即時爬取未核准來源；既有 public／journal／portfolio／ingestion API 不改語意。

- [ ] 【Sol】 Codex 以 Cloud Run 容器內 App Server stdio JSON-RPC 與 managed OAuth／device-code 驅動；整合 Threads／Turns／Items／Approval Requests、取消及 sandbox。不得使用 OpenAI API key、Responses／Codex API 或其他直接付費 fallback。

- [ ] 【Sol】 Codex auth lifecycle 必須先於 Chat API／Assistant UI：authenticated owner 經 service-authenticated internal request 傳入 Gateway；A／B 共用一個 Secret bundle，但 payload 以 owner UUID 分區，並各自使用隔離 `CODEX_HOME` 與 App Server process。refresh 以 read-modify-write 建立新 bundle version、驗證該 owner 後銷毀舊版本；刪除只移除該 owner entry。刪除時拒絕該 owner 新 login／turn／artifact write，停止 session、logout、刪 owner auth，失敗保留 `CLEANUP_PENDING` 並可重試。Gateway 不接受 client owner／Secret name，不授 project-wide Secret Manager admin；MVP 維持 `max-instances=1` 以序列化 bundle 寫入，擴展多 instance 前須改用 distributed lock／CAS。




- [ ] 【Sol】 驗證 Cloud Run scale-to-zero／cold start／timeout／中斷重連、三 runtime、內外資料源 provenance、MCP stdio／HTTP／SSE、動態工具、Skill 權限、Codex auth／approval／取消、Grounding、quota／provider unavailable、context 外送提示、A／B 隔離、stream 續接／去重、Iceberg 重跑／匯出／刪除與無 placeholder。Codex auth 必須覆蓋 A／B load／rotate／destroy 隔離、orphan auth、cleanup 403 重試、刪除期間寫入拒絕、session eviction／logout、刪後重新登入與 secrets 不落 log／DB／Iceberg；另驗證 Iceberg snapshot／orphan file 與 GCS object version 的實際物理清除期限。若 Cloud Run 無法滿足不可中斷長 turn、持久 daemon、特殊 sandbox 權限或實測資源需求，先提交 Compute Engine／GKE 成本、安全、維運與退出評估，取得使用者決定後才能採用。（2026-09-09 checkpoint：provider live probe `fd435461-71fc-4b8f-86bf-e583431900c5`、Grounding/stream live probe `31b2f8ac-25fa-4bbb-aca2-46c2ea3210aa`、approval/quota contracts `7960f7b5-e1fe-4b63-86cb-50d4b878a8fd`、Private Storage/privacy/delete regression `275ec264-0dde-46d7-b755-c49ad90b870e`、context sources、Skills、Web bundle 與 MCP transports GCP dev 通過；Codex 0.153.4 POC `ca212276-2dde-4ce1-bbdf-6982c3d943a2`、device-code probe `e7b91774-8682-4077-8f5d-d50054d9640d`、直接 App Server probe `eff86a80-a94a-44da-af76-0f1efccef287` 與 alpha probe `e04655d7-28bd-47fa-9a28-8fa98bf61358` 均因 Codex device-auth request error 失敗，網路診斷 `9a251707-c075-40d2-9f32-a6c75eb11023` 已證實 endpoint 可正常回傳 device code；managed-auth／approval live flow 保持未完成，詳見 operations-and-testing。）
- 2026-09-09 後續：CA remediation image／revision 已部署，真人 device-code、cancellation、checkpoint reconnect、logout／destroy 已通過；approval-handle dev revision `janus-agent-gateway-00038-j78` 已完成真人 side-effect turn（approval request／accept／resolved、command exitCode=0、turn completed；詳見 `spec/operations-and-testing.md`）。其餘整合驗收仍未完成。
- 2026-09-10：Gateway handle／Chat API／approval／cancel／SSE cursor contract 本地回歸 150 tests、Flutter widget 2 tests 通過；Gateway `00041-fn`、API `00048-x6x` 已部署 dev，Gateway 維持 `min=0 / max=1 / concurrency=2`，僅新增 dev-only `CODEX_SANDBOX_MODE=read-only`。OpenRouter/Gemini live build `7d661ef6-3ac5-4dd3-9f69-080966746ad0` SUCCESS；OAuth client ID 已在既有 API bundle、client secret 欄位缺失；MCP allowlist 修正後 job execution 未留下 application log。owner B auth 已重新登入並上傳為 enabled version 7，本機 `account/read(refreshToken=true)` 成功；新 revision approval live probe `cc5fecfa-b0e4-46f8-be22-391b96e2e15d` 通過真實 `approval_request`、錯誤 binding rejection、accept command completion 與 decline no-command-completion。Chat API 真人 Google OAuth E2E、SSE reconnect、MCP execution 與完整整合仍未完成，不勾選 `WBS-4C-ACCEPTANCE`；臨時 IAM 與 probe 檔案已清空。

## P1（WBS 4R）— 個人曝險、績效與 AI 壓力測試

- [x] 【Sol】 建立 investment profile：risk tolerance、investment horizon、primary goal、minimum cash ratio；目前值保留 bounded private index，revision history 寫入 Private Iceberg，只有使用者 opt-in 才能加入 chat context。（source／PostgreSQL／Iceberg／API／GCP dev acceptance complete；證據見 archive。）

- [x] 【Sol】 建立具 effective time／provenance 的多產業 membership 與 `mart_user_exposure`；分攤方法、現金、持股市值、valuation date 與 membership snapshot 可追溯，Flutter／LLM 不重算。（source／API／GCP dev acceptance complete；現行 ledger 無入出金事件，cash-safety 明示 `insufficient_data`，不得推算。）

- [x] 【Sol】 建立年度現金流與 XIRR；先通過買賣、現金／股票股利、更正、跨年、無根、多根與缺資料測試，非唯一有效結果不得填 0。（source／回歸案例／API／GCP dev acceptance complete。）

- [x] 【Sol】 建立 deterministic portfolio stress scenarios 與 cash-safety result，再交由使用者選定的 Codex／ChatGPT／Gemini profile 解釋；模型不得修改數值或產生下單動作。（source／API／GCP dev acceptance complete；模型不可改寫數值。）

- [x] 【Sol】 建立 private investment-profile、portfolio summary／exposure／performance／stress-test typed endpoints 與 Flutter 儀表板；通過 A／B 隔離、重跑、資料日期、缺價、profile opt-in、citation 與免責聲明驗收。（Flutter／API／GCP dev acceptance complete；證據見 archive。）

## P1 — 全市場量化網

- [ ] 【Sol】 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。（2026-09-16 checkpoint：OHLCV runtime registry、symbol-scoped fan-out、DQ／quarantine summary 與 `core.ohlcv_v1` writer 已接入；targeted tests 27 passed，Cloud Build `16962da0-7706-4a08-83aa-1348404d6d45`／digest `sha256:a8953df49f42a9324adeb3eb7cb622de43e75f7fad56763ce11d2bb2beb75dbc` 已部署既有 dev job。原 5 檔中 stale `2381` 已停用並標記 `delisted`；初次重跑 Cloud Run `janus-ingestion-core-rwt4w`／control execution `cffec813-2054-4a2d-a4b4-05846f5d8c46` 使有效 enabled universe 為 4 檔 `1102`／`2327`／`2330`／`4958`，40 rows、quarantined=0、failed=0、Core snapshot 成功。同日 replay `janus-ingestion-core-scdrp`／control execution `ecd1aef9-c6ec-4e03-ab31-b83506a31cc2` 為 `core_created=0`、`core_reused=40`，runtime 14,795 ms；Stage 32,394 bytes、Core 437 bytes，bounded job 1 vCPU／1 GiB／1800 秒。bounded config 已停用；WBS-3 replay／成本／runtime 切片完成，整體量化網仍待其他 dataset。）

- [x] 【Luna】 對 market-scope endpoint 採單次抓取、批次快取與 symbol fan-out；不得逐檔重複請求。（source／回歸案例 complete；實際全市場執行仍等 WBS-3 canary 3/3。）

- [x] 【Luna】 產製每日 market coverage report：expected／received／missing symbols、來源成功數、freshness、合法 empty／unavailable 與最小寫入安全摘要；完整 DQ 延至 P4。（source／回歸案例 complete；實際全市場執行仍等 WBS-3 canary 3/3。）

- [x] 【Sol】 建立 `mart_screening_signals`：技術面突破、量能、流動性與異動候選；結果不得在 collection request 內即時計算。（source／回歸案例 complete；實際全市場執行仍等 WBS-3 canary 3/3。）

- [x] 【Sol】 驗證全市場同日 replay 冪等、bounded memory／runtime、GCS 成本與缺檔不被誤標成功。（2026-09-16：OHLCV replay `ecd1aef9-c6ec-4e03-ab31-b83506a31cc2` 成功，`created=0`／`reused=40`；Cloud Run application duration 14,795 ms，job cap 1 vCPU／1 GiB／1800 秒；Stage 21 objects／32,394 bytes、Core 437 bytes；先前 stale `2381` 空回的 failed execution 保留為缺檔 fail-closed 證據。）

## P1 — 個人關注股深度追蹤

- [x] 【Sol】 以 authenticated watchlist 形成去識別化 active symbol membership，收集深度財報、公司事件／重大訊息、公司行動與 PIT publication time；Admin 不得取得 user-to-symbol 對應。（去識別化 append-only membership source／contract complete；實際深度來源仍受下列授權 gate。）

- [ ] 【Sol】 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。

- [ ] 【Sol】 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。

- [ ] 【Sol】 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。

- [ ] 【Sol】 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables；entity-to-symbol 保留規則／模型版本、confidence、evidence 與人工覆核狀態，sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。

- [ ] 【Sol】 【High-Completion Target】 驗證關注需求變更不改寫歷史 membership；最後一位使用者取消關注後停止新的深度收集，但保留依法可保存的歷史 provenance。MVP 超過 50 個 distinct active symbols 時安全拒絕並顯示 quota。

## P1 — Mart 閉環

## P1 — Admin Governance／Reports

## P1 — FastAPI／Flutter User

## P1 — 全系統自動化測試

## P1 — WBS-7 安全、監控與 FinOps

## P1 — Pilot Readiness Gaps

- [x] 【Sol】 【High-Completion Target—runtime acceptance + OAuth verified】 `WBS-6-PILOT-USEFULNESS-FEEDBACK`：提供 authenticated owner-scoped `useful`／`neutral`／`misleading` bounded feedback，綁定 immutable analysis result，不改 deterministic score 或 publication input，優先重用既有 analysis card。既有 local API／Flutter／GCP dev database evidence 見 [`archive/todo-completed-2026-09-16-wbs6-usefulness-feedback.md`](archive/todo-completed-2026-09-16-wbs6-usefulness-feedback.md)；2026-09-16 zero-traffic candidate smoke、canonical dev rollout 與 rollback tag 已完成。2026-09-17 使用者確認後，既有 OAuth client 加入 canonical origin；真人登入載入 2330 已發布分析，選擇 `neutral`，save/readback 顯示 `passed: true`。完整 revision／digest／時間／rollback 與 OAuth evidence 見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。
- [x] 【Sol】 【High-Completion Target】 `WBS-8-PILOT-RELEASE-BASELINE`：建立 material-change baseline／epoch lineage，追蹤 git SHA、immutable image digest、governance、prompt、schema、feature／signal、model／provider、source/config revision 與 Core／Mart snapshot；不調整 Artifact Registry retention。完成證據見 [`archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md`](archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md)。

## P1 — ChatGPT MCP Connector（Dev Pilot Enabler）

- [x] 【Sol】 【High-Completion Target—contract and OAuth facade dev rollout complete】 `WBS-6-CHATGPT-MCP-CONTRACT`：2026-09-17 已依官方 OpenAI remote MCP／OAuth requirements 定義 `janus_sources`、`janus_market_context`、`janus_private_context` 的 read-only schema、owner binding、public／private allowlist、shared bounded query、provenance、quota／disclosure；另在既有 `janus-api` 實作 Google-upstream、Janus-signed resource-bound OAuth facade 與一次性 hashed authorization code store。GCP dev bundle v16、issuer／resource、明確 user allowlist 與 protected-resource／authorization-server metadata、PKCE／token negative checks 已驗證；完整 rollout 紀錄見 [`archive/todo-completed-2026-09-17-wbs6-chatgpt-mcp-auth-rollout.md`](archive/todo-completed-2026-09-17-wbs6-chatgpt-mcp-auth-rollout.md)。

- [x] 【Sol】 【High-Completion Target—GCP dev rollout and runtime acceptance complete】 `WBS-6-CHATGPT-MCP-ADAPTER`：已在既有 `janus-api` 加入 stateless `POST /mcp`、三個 read-only tool、per-tool OAuth scope／challenge、token-subject owner binding，並抽出 Chat preview／MCP 共用的 bounded direct read；拒絕 arbitrary SQL／URI／table／owner input、mutation 與不必要 chat snapshot。`tests/test_mcp_adapter.py`、`tests/test_mcp_oauth.py`、`tests/test_user_api.py` 共 32 tests 通過，Python compile、Git Bash `bash -n`、`git diff --check` 通過；Cloud Build `7d070e60-d8c1-4e7f-821f-5d8a54bd9196` source upload／image push、Cloud Run no-traffic revisions `janus-api-mcp-adapter3`／`janus-api-mcp-oauth4` 與 GCP VM/IAP protocol／OAuth／bounded-read acceptance 完成。證據見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 [`archive/todo-completed-2026-09-17-wbs6-chatgpt-mcp-adapter.md`](archive/todo-completed-2026-09-17-wbs6-chatgpt-mcp-adapter.md)。

- [ ] 【Sol】 【High-Completion Target】 `WBS-8-CHATGPT-MCP-ACCEPTANCE`：Blocked until adapter complete、使用者確認支援所需 ChatGPT custom read-only MCP plan／UI，且明確授權任何 GCP dev deployment／test；驗收 discovery、OAuth lifecycle、owner isolation、market／private bounded reads、opt-in、sanitization、provenance、limits、no mutation 與 cost evidence。此 connector 不得成為 Janus Production Release prerequisite。

## Pilot Feature Freeze／Deferred

以下未完成類型移出 active execution queue，標示為 Pilot feature freeze／deferred；不刪除既有 code 或歷史 TODO。只有 correctness、security、data-integrity、cost regression、Pilot blocker fix 或既有功能維護可例外處理：

- remaining Codex productionization、WBS-4C feature expansion、new Skills functionality、new MCP workflows、new provider。
- social／Podcast／未核准 alternative-source adapter、extra AI role、extra analysis dashboard、額外 UI cosmetic polish。
- Pilot 實際不用的完整 device／A11y matrix；實際使用裝置所需的 release coverage 仍保留。
- 新 GCP service、HA／replica／multi-region／GKE，以及為架構漂亮而新增 infrastructure。

Supply-chain Intelligence foundation／research planning 是本 freeze 的明確例外；只允許
ontology、Source Matrix、seed graph、signal contract 與 Pilot measurement／epoch planning。
production ingestion、schema／migration、crawler、未核准 adapter、paid source、tick／
high-frequency source、Mart implementation 與新 GCP resource 仍 frozen／deferred，直到
WBS-5 Gate A–E 及個別 source approval 條件滿足。

## P2 — PIT 與治理校準

Pilot Day-1 outcome collection 已前移至 `WBS-8-PILOT-OUTCOME-COLLECTION`；本節保留
後續 calibration／optimization、artifact hardening 與治理 revision，不把 model tuning
提前成為 Pilot Entry blocker。

- [ ] 【Sol】 【High-Completion Target】 PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。

- [ ] 【Sol】 【High-Completion Target】 5／20／60 交易日 outcome pipeline。

- [ ] 【Sol】 【High-Completion Target】 relative benchmark、MFE／MAE、coverage。

- [ ] 【Sol】 【High-Completion Target】 缺 publication time／provenance 樣本排除。

- [ ] 【Sol】 【High-Completion Target】 每個排除保留原因與 ID。

- [ ] 【Sol】 對 weights／40-60 thresholds 做 walk-forward。

- [ ] 【Sol】 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] 【Luna】 【High-Completion Target】 Flutter Android／iOS／Web 的 phone、tablet、desktop breakpoint。

- [ ] 【Luna】 【High-Completion Target】 iOS Safari。

- [ ] 【Luna】 【High-Completion Target】 Android Chrome。

- [ ] 【Luna】 【High-Completion Target】 iPad Safari。

- [ ] 【Luna】 【High-Completion Target】 VoiceOver／TalkBack。

- [ ] 【Luna】 【High-Completion Target】 WCAG AA contrast。

- [ ] 【Luna】 【High-Completion Target】 所有主要控制 ≥44×44。

- [ ] 【Luna】 【High-Completion Target】 K 線 pan／zoom／tooltip／替代表格。

- [ ] 【Luna】 【High-Completion Target】 Dialog focus trap、Escape、restore、scroll lock。

- [ ] 【Sol】 【High-Completion Target—Dev only】 canary／rollback。

- [ ] 【Sol】 production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。

- [ ] 【Sol】 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。

- [ ] 【Sol】 【High-Completion Target—Dev only】 incident runbook。

- [ ] 【Sol】 production 人工批准。

## P2 — WBS 8 Dev Pilot／Production Readiness

- [ ] 【Sol】 `WBS-8-DEV-PILOT-ENTRY`：Blocked until WBS-3 canary／full-market safety、ledger durability successful restore、outcome collection、usefulness feedback、release baseline、minimum data-safety DQ（required key／type、duplicate、future leakage、freshness、basic coverage、schema drift、適用時的 obvious outlier／corporate-action sanity）與 security／privacy／cost evidence ready；`WBS-5-SUPPLY-INTELLIGENCE-PLANNING` 也必須完成，但不要求六個 domain ingestion-ready。ChatGPT MCP acceptance 完成，或使用者明確決定允許 connector blocked 狀態啟動 Pilot。只有 Entry Gate 通過時記錄 `pilot_started_at`，不新增 staging／production infrastructure；完整 DQ dashboard／tuning／大型 drill-down 留後續。

- [ ] 【Sol】 `WBS-8-DEV-PILOT-RUN`：Entry 完成後開始 6 calendar months operational phase，持續執行 Scheduler／ingestion／analysis，累積 monthly evidence summary、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence；不新增 feature roadmap，production promotion blocked。

- [ ] 【Sol】 `WBS-8-PROD-GO-NOGO`：Blocked until Pilot 完整執行 6 calendar months；review data reliability、analysis usefulness、PIT/outcome、operations burden、automation reliability、actual cost/value、security/privacy 與 feature usage，並列出各功能 keep／freeze／remove／productionize。Outcome 為 `GO`／`EXTEND_PILOT`／`NO_GO`；`GO` 只允許開始 production architecture／migration planning。

## P4 — UI 驗收後的資料品質強化（最後執行）

順序 gate：Admin 資料營運中心與 Flutter「關注／記帳／筆記／AI／個股健康」完成自動化、實機與 A11y 驗收前，本節全部保持 blocked，不得提前開工。

- [ ] 【Luna】 【High-Completion Target】 source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。

- [ ] 【Sol】 【High-Completion Target】 建立跨源一致性、null profile、freshness、coverage、schema drift、outlier 與 corporate-action 的完整 DQ ruleset；版本化門檻與例外理由。

- [ ] 【Sol】 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的 quality discount；只影響新 Mart revision，不改寫歷史結果。

- [ ] 【Luna】 【High-Completion Target】 完成 Admin DQ dashboard、quarantine drill-down、quality revision diff 與 evidence link；不提供 raw payload／object URI 旁路。

- [ ] 【Luna】 【High-Completion Target】 以 UI 驗收發現的閱讀誤差、partial／stale 混淆與缺價案例建立回歸集，再決定是否提高 30% development gate。

- [ ] 【Sol】 對 30% gate 做 coverage／錯誤率分析，產出可審查的門檻 revision 提案。

- [ ] 【Sol】 完成 DQ replay、false-positive／false-negative、跨源衝突、資料延遲與 private/public 隔離驗收後，才能提出 production-grade data quality revision。

## Research Context Pilot Evolution roadmap

本 roadmap 全部為 `planned`，不新增 Dev Pilot Entry blocker；完成狀態必須由 repository／acceptance evidence 更新。

1. [ ] `WBS-3-DATASET-COVERAGE-INVENTORY` 【High-Completion Target】 — status: `planned`；dependency: 現有 source registry／adapter／Core publication evidence；gate: Data Source admission；classification: Pilot Evolution。先完成 coverage／gap validation，不批准新 source。
2. [ ] `WBS-6-RESEARCH-CONTEXT-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: coverage inventory 語意與現有 bounded context boundary；gate: contract review；classification: Pilot Evolution。
3. [ ] `WBS-4J-PRIVATE-RESEARCH-STATE-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: notes／artifacts／Private Core／Mart 現況；gate: owner isolation／revision review；classification: Pilot Evolution。先 contract，再決定 schema extension。
4. [ ] `WBS-5-RESEARCH-MART-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: coverage inventory／ResearchContext contract；gate: deterministic／PIT contract review；classification: Pilot Evolution。規劃 deterministic signals 與 Market Regime，不在本項定公式。
5. [ ] `WBS-3-RESEARCH-DATASET-GAPS` — status: `blocked`；dependency: inventory 證明 Missing／Partial 且個別 source approved；gate: Data Source admission／cost／license；classification: Pilot Evolution。只實作必要 Core gap。
6. [ ] `WBS-6-RESEARCH-CONTEXT-COMPOSITION` — status: `blocked`；dependency: semantic、Private Research State 與 Mart contracts；gate: API security／owner scope review；classification: Pilot Evolution。重用 existing `janus-api`。
7. [ ] `WBS-6-RESEARCH-CONTEXT-UI` — status: `blocked`；dependency: server composition；gate: UI states／provenance acceptance；classification: Pilot Evolution。
8. [ ] `WBS-6-CHATGPT-MCP-RESEARCH-CONTEXT` — status: `blocked`；dependency: MCP CONTRACT／ADAPTER 與 server composition；gate: `WBS-8-CHATGPT-MCP-ACCEPTANCE`；classification: Pilot Evolution。只讀 bounded consumer，無 Drive dependency。
9. [ ] `WBS-5-SUPPLY-RESEARCH-CONTEXT` — status: `blocked`；dependency: Supply-chain Gate D；gate: Gate A–E；classification: existing gated work。依已通過 gate 增量納入 indicators。
10. [ ] `WBS-3-NEWS-ALTERNATIVE-SOURCE-REVIEW` — status: `blocked`；dependency: Pilot evidence 證明必要性；gate: source approval／license／cost；classification: Post-Pilot Conditional。優先順序為 official disclosure／financial reporting／company IR／approved news／licensed research／social／podcast／alternative data。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
