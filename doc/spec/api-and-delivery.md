# Janus SPEC — API、User、Admin 與交付

## 12. User、Admin 與 API

- Flutter User App 與 Admin Web 為兩個獨立入口；User 導覽不顯示 Admin，Admin 必須通過獨立認證與授權。
- FastAPI 作為共用 HTTP boundary，但 `/api/v1/public/*`、`/api/v1/me/*` 與 `/api/v1/admin/*` 分離 router、response model、auth、rate limit、CORS 與 audit policy。
- 公開端只讀 publishable Mart／service index，不直讀 Iceberg catalog owner 或 control schema。
- Core query 的 canonical boundary 為 Admin-authenticated `GET /api/v1/admin/core/{symbol}/summary` 與
  `GET /api/v1/admin/core/{symbol}/datasets/{dataset_id}`；遷移期保留相同契約的 deprecated
  `/api/v1/core/*` alias，完成 Admin／Core 回歸後才移除舊 WSGI boundary。
- `GET /api/v1/public/reports/{scope_type}/{scope_id}` 可用 `analysis_as_of` 精確選日；服務由
  `janus_public_api` 只讀 publishable view，驗證 immutable GCS metadata hash，再讀 index
  指定的 Iceberg snapshot。回應不公開 object URI，且輸出前再次拒絕 blocked／insufficient data。
- 404 不觸發即時爬蟲、Agent 或 LLM。
- Admin 只寫 control DB／queue，不在 request 中執行長任務。
- Admin「資料營運中心」保留為資料操作入口；`/admin/stocks` 右側一次只呈現一個分頁面板，不把所有管理功能同時展開。
- 股票資料狀態以可排序、篩選、分頁的欄列表格呈現，不以原始 JSON 作主要 UI；巢狀 DQ／quarantine／execution 明細亦轉為子表或定義清單。
- 第一階段只開放 Collection／backfill；Analysis action 與「Mart 分析」必須 hidden／disabled，且不得建立無 consumer 的 queued execution。完成 Mart persisted queue consumer 後才啟用。
- Admin 可按 market／industry／symbol scope 檢視已持久化的 `mart_scoped_analysis`；讀取不得觸發即時 Agent。Prompt 由 repository 版控，不提供 Admin 編輯。
- blocked report、raw payload、secret、traceback、broker data 不得公開。
- User App 主頁以 `mart_daily_brief` 為唯一首屏資料入口；個股健檢讀取 `mart_candidate_health` 與可定位 evidence，前端不重算健康度。
- `/api/v1/me/journal/*`、`/api/v1/me/notes/*`、`/api/v1/me/watchlist/*`、`/api/v1/me/chats/*`、`/api/v1/me/portfolio/*` 與 `/api/v1/me/investment-profile` 只允許 authenticated user 存取自己的資料。所有 query 與 index 以 `user_id` 作為所有權邊界；不接受 client 指定他人 `user_id`。
- 私人助理 runtime 為 `openrouter | gemini | codex`，model／assistant profile 分離；每個 thread 固定 runtime／model，切換新建／fork，保留 parent lineage 與選取的 context。對話不綁定單一股票。
- OpenRouter 使用 runtime `OPENROUTER_API_KEY` 動態選擇具所需 tools／streaming capability 的模型；Gemini 以 `GEMINI_API_KEY` 直接呼叫 Gemini Developer REST API 免費層，保留 Google Search Grounding／citations／查詢時間，不引入 Google GenAI SDK；Codex 由 Cloud Run Agent Gateway 在容器內以 stdio JSON-RPC 啟動 App Server，使用 managed OAuth／device-code，不使用直接 OpenAI API fallback。
- 所有 runtime 共用 MCP Host 工具授權、Skills 與 AgentEvent UI；Codex 原生 sandbox／approval 另經 bridge 映射，不能用一般文字 token 串流取代。
- User token 只接受 User OAuth audience 並只授權 `/api/v1/me/*`；不得用於 `/api/v1/admin/*`。Admin token／session 亦不因具管理權限而取得一般交易內容讀取能力。
- User 可匯出自己的交易、筆記、關注股、Skills 與對話資料並要求刪除私人資料；刪除採可稽核、可重試的非同步流程，涵蓋 PostgreSQL、Private Core／Mart、GCS artifact、Codex thread／auth state 與 service cache，且不影響依法或安全要求保留的最小 audit metadata。排隊後該 owner 進入 `DELETING` 並拒絕新 login、turn 與 artifact write；任一步失敗保留 `CLEANUP_PENDING`，只有必要 cleanup 全部完成才可標示 `COMPLETED`。
- 交易日誌／PnL 納入私人 MVP；市場投票排行榜、遊戲化、付費、公開績效排名與券商同步不在當前範圍。
- 個人記帳、筆記、關注股與私人聊天室可在公開 Mart 前獨立上線至 dev；未完成的「今日／公開探索」只顯示 coming soon，不得因此觸發即時分析或阻擋私人功能。
- UI 詳細契約見 `../ui.md`。

### 12.1 私人助理 runtime contract

- 不建立 React／Tauri 或使用者地端 runtime。既有 Flutter Web／Android／iOS 經 FastAPI／Agent Gateway authenticated HTTPS 共用 threads／events；Node.js／TypeScript Agent Gateway、Codex App Server 與 stdio-only MCP 都只在 Cloud Run 容器內執行。
- Agent Gateway 使用 Cloud Run Service `min-instances=0` 按需啟動，MVP concurrency=1，限制 max instances、CPU、memory、request timeout 與暫存 volume。每個 turn 在容器內啟動或租用 owner-bound Codex／MCP 子行程；完成、取消、timeout 或 disconnect 後清理。持久狀態與 replay cursor 外存，不依賴 instance affinity。
- Codex App Server 的 stdio JSONL 只存在 container process boundary，gateway 對前端提供 HTTPS SSE／POST；不得直接暴露其實驗性 WebSocket transport。App Server 目前屬實驗性且官方不支援 production workload，因此 managed auth refresh、Linux sandbox、child-process lifecycle、timeout／重連必須先通過 dev POC 與人工 production gate。
- Codex device login 由 authenticated service request 呼叫 `/internal/v1/codex/session:login-start`，再以同一 owner 呼叫 `/internal/v1/codex/session:login-status`；Gateway 只回傳 bounded device-code 欄位，session 與 App Server process 綁定 owner，TTL 到期自動 eviction，成功後將 auth rotation 寫入 owner-keyed bundle entry。
- MCP Host 每 server 一個 client／session，支援 Cloud Run 容器內 stdio、遠端 Streamable HTTP 與 legacy SSE；完成協定交涉、tools/list 分頁／變更、tools/call、取消、失敗清理與遠端認證。工具 namespace、參數 schema、timeout、輸出大小與 owner 必須驗證。可 HTTP 化且需獨立擴縮的 MCP 優先部署私有 Cloud Run Service。
- Janus context adapter／內部 MCP 只讀已發布 Core／Mart 與 authenticated owner 的 Private Core／Mart，回傳 bounded records、as-of date、source ID、provenance 與 artifact reference；模型與外部 MCP 不取得 GCS URI、PostgreSQL credential 或任意 query。第三方 source 必須先登錄授權、quota、timeout、外送政策與 retention。
- Assistant-facing source API 為 `GET /api/v1/me/ai-sources` 與 `POST /api/v1/me/chats/{conversation_id}/context-preview`。來源清單只回 source ID／kind、capabilities、as-of／freshness、owner scope、status、quota 與 disclosure；preview 只接受 typed resource selector／date range，回傳短預覽、provenance 摘要與短效 opaque `context_ref`，不接受 SQL、GCS URI、object path 或 client `user_id`。`POST .../messages` 只接受已核發且同 owner／thread／未過期的 `context_ref[]`，server 固定 turn snapshot 後再交 Agent。
- Agent Gateway 只以 service identity 呼叫 `POST /internal/v1/assistant/context:resolve`；請求包含 signed owner／thread／turn claims 與 opaque refs，response bounded 且去除 storage locator。既有 public market／journal／portfolio API 與 ingestion pipeline 不因 assistant source API 改變；新路由只是安全選取與轉譯層。
- MCP 管理 API 為 `GET／PUT /api/v1/me/mcp/servers` 與 `GET /api/v1/me/mcp/servers/{server_id}/tools`；前端只管理 allowlisted config reference、啟用狀態與 tool grants，不能提交 stdio command、container image、raw secret 或任意 remote URL。server-side discovery 成功後才回 namespaced tool schema／health。
- OpenRouter／Gemini adapter 將工具 schema 轉成各自 Function Calling 格式，保留模型 continuation metadata，執行有限輪次 loop。Codex 透過 dynamic-tool bridge 或受控 MCP facade 共用 Host 執行邊界；不重跑其內建 agent loop，不以共用 registry 取代實際授權。
- Skills 可載入／啟用／停用／自訂，版本化 system prompt fragments、required tools 與 workflow；內建 skill 隨 immutable image 發版，自訂 revision 存 Private Iceberg／GCS 並由 PostgreSQL bounded index 定位，turn 開始時物化核准 snapshot 到暫存 sandbox。Skill 不得包含任意上傳 executable、改寫 host policy 或取得未核准工具。
- 最小事件 envelope 包含 eventId、seq、threadId、turnId 及可選 itemId／provider IDs；事件種類為 text delta、item upsert、tool request／result、approval request／resolved、citation、usage、turn completed／cancelled／error。
- SSE 使用既有 chats events route，支援 bounded replay／cursor／backpressure；authenticated HTTPS POST 傳送 approval／cancel。批准必須綁定 owner／turn／request／參數，重播與過期拒絕；provider 專屬 approval decision 由 adapter 映射。
- Chat API 已提供 owner-scoped `POST/GET /api/v1/me/chats/threads`、thread read/fork、`POST .../messages`、bounded `GET .../events?cursor=&limit=`、cancel、approval response、assistant export 與 deletion status；message turn 的 provider continuation metadata 以受控 JSON 持久化於 PostgreSQL，event 仍寫入 Private Iceberg／索引。Agent Gateway 的 signed OpenRouter／Gemini dispatch 已於 GCP dev live probe 通過；Codex Chat API dispatch 會以 owner auth 啟動或 resume 原生 thread，並由 `tests/test_chat_api.py` 驗證 message → gateway → 下一 turn continuation。
- Shell／寫檔預設不授權，經明確批准後只限該 turn 的 Cloud Run 暫存 sandbox；MCP process 另做程序／環境隔離。Janus Admin、交易／筆記／watchlist mutation 與下單仍禁止；外部內容及 Skill 無法覆蓋。
- API／MCP keys 與 Codex auth cache 只在 Secret Manager 或另經核准的 GCP credential store，API payload 僅傳 connection reference。Dev 以三個 workload bundle 管理 credential；同 bundle consumer 共享 resource-level IAM 的安全取捨已由 owner 核准。Codex 由 authenticated identity 映射內部 owner UUID，Gateway 不接受 client 指定 Secret resource name；A／B auth 在共用 bundle 內以 UUID 分區，`CODEX_HOME` 與 App Server process 仍隔離。refresh 驗證該 owner 的新 entry 後銷毀舊 bundle version，刪除只移除該 owner entry；Gateway 不得取得 project-wide admin。工具輸出／event 先去 secret 再儲存，不保存 raw provider error；owner-scoped auth lifecycle 未通過 GCP dev 驗收時 fail closed。
- Dev credential resource 由 operator 僅為 allowlisted owner 建立並逐資源授權；大量正式使用者的自助 provisioning 與成本另案核准，不藉此擴大 Gateway 或 User API 權限。
- GCP dev Secret／bundle 對照、欄位名稱、消費者與 IAM metadata 以 [Secret Bundle 清單](../secret_list.md) 為單一查閱入口；provider bundle 包含 MCP signing key，不建立獨立 signing Secret。
- Codex 刪除依序停止 owner session、執行 App Server logout、刪除 owner auth，再清私人 artifacts 與 PostgreSQL index；各步驟冪等，無 thread 或 auth 已不存在仍可成功。App Server logout 只代表 managed credentials 已清除，不宣稱供應商端 refresh token 已撤銷。Iceberg snapshot／orphan file 與 GCS object version 的實際保留期限必須被驗證並向 UI 揭露。
- 長正文／context／citations／items／skill revisions 儘可能進 Private Iceberg；PostgreSQL 保存 bounded thread／turn／pending approval／usage reservation 索引與 artifact references。Cloud Run filesystem 只作 bounded ephemeral storage；核准保留的 artifact 寫入 Private GCS／Iceberg，刪除涵蓋雲端狀態與暫存 reference。
- Gemini 免費 Grounding 須確認模型能力與專案 quota；額度不足／不可用明確回報，禁止自動付費。OpenRouter 啟用付費另需同意；quota／budget 用原子 reservation 防併發超支。私人 context 外送須明確選取並顯示供應商。
- 只有 Cloud Run 無法滿足超過 request timeout 的不可中斷 turn、必要持久 daemon／特殊 sandbox 權限，或實測資源／連線需求時，才提出 Compute Engine／GKE 方案；必須先提供成本、安全、維運、資料遷移與退出評估，取得使用者明確決定後才能實作或建立資源。

## 13. GCP 開發與 CI/CD

| 項目 | 選擇 |
|---|---|
| 開發環境 | Cloud Workstations；低頻可用 Cloud Shell Editor |
| 原始碼 | GitHub monorepo、branch protection、PR review |
| GCP 認證 | Workload Identity Federation，不使用長效 JSON key |
| 建置 | Cloud Build path-based pipelines |
| Image | Artifact Registry，由 source deploy／Cloud Build 管理 |
| 部署 | 同一 immutable image digest 依序 promote dev → staging → prod |
| Secret | Secret Manager，依三個 workload bundle 對 runtime identity 授權 |
| IaC | GitHub Actions／gcloud idempotent scripts；production apply 需人工批准 |

API request telemetry contains only router family、method、status、duration、
server-generated request ID；query、body、token 與 object URI 不進 log。Ingestion／
Mart Job completion records contain execution／trace ID、duration、retry and publication
counts plus bounded error taxonomy. Admin execution details expose the shared trace、
related persisted executions、Core snapshot ID and Mart publication state, allowing an
operator to trace UI → Job → Core → Mart without exposing raw payload or storage credentials。
Source health shows latest expected／received coverage、freshness、cache age and schema drift;
core-focus gap remains aggregate-only and never exposes user-to-symbol membership。

### 13.1 Dev PostgreSQL VM

- 使用 Compute Engine `e2-micro`，只承載 control plane、Iceberg catalog、publication index、audit metadata 與低流量私人交易 ledger；GCS／Iceberg 不搬到 VM。
- PostgreSQL 使用 private IP；Cloud Run、Cloud Run Jobs 與 DuckDB 所在 runtime 僅透過 VPC 連線，禁止公開 `5432`。
- VM 使用 Standard Persistent Disk，Free Tier 模式總配置量 ≤30 GB；不自動建立 snapshot／backup，資料庫 credential 存 Secret Manager。任何備份與 restore drill 必須另行評估費用。
- `e2-micro` 只有 1 GiB RAM，僅限 dev／MVP 低併發；私人 ledger 必須有 bounded query、retention／export 與容量告警。production 必須重新評估 dedicated VM、HA 或其他 managed PostgreSQL 方案。
- Free Tier 目標另受 billing account 資格、每月 1 GB outbound 額度與其他 GCP 資源費用影響；gcloud bootstrap guard 不等於保證帳單為 US$0。
- Compute Engine 與 Standard Persistent Disk 依 instance 運轉時間、provisioned disk、snapshot 與網路流量計費；實際價格以 [Compute Engine pricing](https://cloud.google.com/products/compute/pricing) 為準。

PostgreSQL VM 是 Iceberg SQL catalog 與 control DB 的前置基礎；必須先完成 VM、private connectivity、schema／role bootstrap、PostgreSQL repository migration 與 smoke query，才可部署內嵌 DuckDB 的 Cloud Run runtime。SQLite control repository 僅供 unit tests，不是 production backend。

### 13.2 Artifact Registry cost guard

- Cloud Build 可 build、push image、解析 immutable digest 與執行 cleanup；不得呼叫 Artifact Analysis API、Container Scanning API、vulnerability scanning 或 occurrence API。
- SBOM 如有需要，使用本地工具產生 SPDX／CycloneDX，作為一般 build artifact 保存；不建立掃描 occurrence，也不等待 vulnerability result。

Schema evolution、migration、backfill、production Job trigger 不得隨 API、Admin Web 或 User App deployment 自動執行。
