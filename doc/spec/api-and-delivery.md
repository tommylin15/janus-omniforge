# Janus SPEC — API、User、Admin 與交付

## 12. User、Admin 與 API

- User 與 Admin 是同一 Flutter codebase 內的不同 workspace／navigation surface；User
  導覽不顯示 Admin。`/api/v1/admin/*` 仍由 backend 每次 request enforce Admin
  authorization，並使用與 User 不同的 token audience／CORS／audit boundary。現有
  static Admin 在 migration 期間保留，直到 Flutter parity 與 auth／browser acceptance
  完成，不得先刪除。
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
- Legacy static Admin current surface 已有 Collection／backfill、Analysis queue 與 persisted
  Mart index；新 Flutter workspace 必須保留已驗收的 bounded read／review semantics，且在
  新 AI consumer 未完成前不得把 AI role／CIO／Profile controls 當作可用。
- Admin 可按 market／industry／symbol scope 檢視已持久化的 `mart_scoped_analysis`；讀取不得觸發即時 Agent。System Guardrail 與 Output Schema 由系統鎖定；Role Methodology／CIO Prompt 由唯一 Admin 以 immutable version、content hash、author、timestamp 與 Profile reference 管理。
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

### 12.0 Planned Mart AI and rerun API semantics

下一版 API contract（尚未實作）必須保留 immutable execution／artifact lineage，並
遵守以下 dependency semantics：

- 單角色重跑預設使用目前 Production Profile，只重建受影響 role、validator、CIO、
  CIO validator 與 governance；其他 role artifact reuse。進階操作才可 override profile。
- Core／相關 Fact Pack 改變時，先更新 Fact Pack 再跑 role；prompt/model 改變不重算
  deterministic facts；CIO prompt/model 改變只跑 CIO；governance-only change 不呼叫
  LLM；全部重跑保留於進階。
- retry 只允許 retryable failed item，不把 partial success 變成 full success；舊
  execution 永久保留，新的 execution／retry lineage 可稽核。
- Planned Analysis Profile endpoints 應支援 current／history、建立新的 Production
  version、compare（role／CIO diff、validator failure、provider/model、latency、token
  usage、cost、fact hash）與 rollback；rollback 不覆蓋舊版。

### 12.1 私人助理 runtime contract

- 不建立 React／Tauri 或使用者地端 runtime。generic Flutter Chat client source 已歸 omniAgent，經其 authenticated Chat API 使用 threads／events；Janus Flutter source 只保留投資 User/Admin UI。API image 建置固定拆分前 User App Web artifact 以保留舊 Chat UI，部署保護尚未經新 GCP dev image 驗收；Janus Chat UI／FastAPI／Gateway 仍是 live 相容性路徑，尚未 cutover。Codex App Server 與 stdio-only MCP 仍只在雲端容器執行。
- Agent Gateway 使用 Cloud Run Service `min-instances=0` 按需啟動，MVP concurrency=1，限制 max instances、CPU、memory、request timeout 與暫存 volume。每個 turn 在容器內啟動或租用 owner-bound Codex／MCP 子行程；完成、取消、timeout 或 disconnect 後清理。持久狀態與 replay cursor 外存，不依賴 instance affinity。
- Codex App Server 的 stdio JSONL 只存在 container process boundary，gateway 對前端提供 HTTPS SSE／POST；不得直接暴露其實驗性 WebSocket transport。App Server 目前屬實驗性且官方不支援 production workload，因此 managed auth refresh、Linux sandbox、child-process lifecycle、timeout／重連必須先通過 dev POC 與人工 production gate。
- Codex device login 由 authenticated service request 呼叫 `/internal/v1/codex/session:login-start`，再以同一 owner 呼叫 `/internal/v1/codex/session:login-status`；Gateway 只回傳 bounded device-code 欄位，session 與 App Server process 綁定 owner，TTL 到期自動 eviction，成功後將 auth rotation 寫入 owner-keyed bundle entry。
- MCP Host 每 server 一個 client／session，支援 Cloud Run 容器內 stdio、遠端 Streamable HTTP 與 legacy SSE；完成協定交涉、tools/list 分頁／變更、tools/call、取消、失敗清理與遠端認證。工具 namespace、參數 schema、timeout、輸出大小與 owner 必須驗證。可 HTTP 化且需獨立擴縮的 MCP 優先部署私有 Cloud Run Service。
- Janus context adapter／內部 MCP 只讀已發布 Core／Mart 與 authenticated owner 的 Private Core／Mart，回傳 bounded records、as-of date、source ID、provenance 與 artifact reference；模型與外部 MCP 不取得 GCS URI、PostgreSQL credential 或任意 query。第三方 source 必須先登錄授權、quota、timeout、外送政策與 retention。
- Assistant-facing source API 為 `GET /api/v1/me/ai-sources` 與 `POST /api/v1/me/chats/{conversation_id}/context-preview`。來源清單只回 source ID／kind、capabilities、as-of／freshness、owner scope、status、quota 與 disclosure；preview 只接受 typed resource selector／date range，回傳短預覽、provenance 摘要與短效 opaque `context_ref`，不接受 SQL、GCS URI、object path 或 client `user_id`。`POST .../messages` 只接受已核發且同 owner／thread／未過期的 `context_ref[]`，server 固定 turn snapshot 後再交 Agent。
- 目前 Janus 的 `POST /internal/v1/assistant/context:resolve` 以 Google service identity／caller allowlist 保護；request 攜帶 owner／thread／turn 與 opaque refs，Janus 再以 owner／thread／expiry 查核 snapshot，回應去除 storage locator。現況尚未把 owner claim 與 service token 加密綁定，不得將其文件化為已完成的 signed-owner boundary。`packages/contracts/janus-context.v1.json` 描述 Janus 擁有的 snake_case wire；omniAgent 擁有 generic Agent contract，只有後續經驗證的 external consumer 才能走此 bounded API/MCP，不直接讀 Janus storage。既有 public market／journal／portfolio API 與 ingestion pipeline 不因拆分改變。
- MCP 管理 API 為 `GET／PUT /api/v1/me/mcp/servers` 與 `GET /api/v1/me/mcp/servers/{server_id}/tools`；前端只管理 allowlisted config reference、啟用狀態與 tool grants，不能提交 stdio command、container image、raw secret 或任意 remote URL。server-side discovery 成功後才回 namespaced tool schema／health。
- OpenRouter／Gemini adapter 將工具 schema 轉成各自 Function Calling 格式，保留模型 continuation metadata，執行有限輪次 loop。Codex 透過 dynamic-tool bridge 或受控 MCP facade 共用 Host 執行邊界；不重跑其內建 agent loop，不以共用 registry 取代實際授權。
- Skills 可載入／啟用／停用／自訂，版本化 system prompt fragments、required tools 與 workflow；內建 skill 隨 immutable image 發版，自訂 revision 存 Private Iceberg／GCS 並由 PostgreSQL bounded index 定位，turn 開始時物化核准 snapshot 到暫存 sandbox。Skill 不得包含任意上傳 executable、改寫 host policy 或取得未核准工具。
- 最小事件 envelope 包含 eventId、seq、threadId、turnId 及可選 itemId／provider IDs；事件種類為 text delta、item upsert、tool request／result、approval request／resolved、citation、usage、turn completed／cancelled／error。
- SSE 使用既有 chats events route，支援 bounded replay／cursor／backpressure；authenticated HTTPS POST 傳送 approval／cancel。批准必須綁定 owner／turn／request／參數，重播與過期拒絕；provider 專屬 approval decision 由 adapter 映射。
- Chat API 已提供 owner-scoped `POST/GET /api/v1/me/chats/threads`、thread read/fork、`POST .../messages`、bounded `GET .../events?cursor=&limit=`、cancel、approval response、assistant export 與 deletion status；message turn 的 provider continuation metadata 以受控 JSON 持久化於 PostgreSQL，event 仍寫入 Private Iceberg／索引。Agent Gateway 的 signed OpenRouter／Gemini dispatch 已於 GCP dev live probe 通過；Codex Chat API dispatch 會以 owner auth 啟動或 resume 原生 thread，並由 `tests/test_chat_api.py` 驗證 message → gateway → 下一 turn continuation。
- omniAgent split 的 Chat API／`omni_chat` schema 目前僅為獨立程式碼與本地契約；Janus 仍是 live writer，migration 016 與歷史私人資料保持原狀。歷史 owner mapping、資料 export/copy/verify、runtime dispatch 與 routing cutover 均未驗收，詳見 omniAgent `docs/chat-storage-migration.md`。
- Shell／寫檔預設不授權，經明確批准後只限該 turn 的 Cloud Run 暫存 sandbox；MCP process 另做程序／環境隔離。Janus Admin、交易／筆記／watchlist mutation 與下單仍禁止；外部內容及 Skill 無法覆蓋。
- API／MCP keys 與 Codex auth cache 只在 Secret Manager 或另經核准的 GCP credential store，API payload 僅傳 connection reference。Dev 以三個 workload bundle 管理 credential；同 bundle consumer 共享 resource-level IAM 的安全取捨已由 owner 核准。Codex 由 authenticated identity 映射內部 owner UUID，Gateway 不接受 client 指定 Secret resource name；A／B auth 在共用 bundle 內以 UUID 分區，`CODEX_HOME` 與 App Server process 仍隔離。refresh 驗證該 owner 的新 entry 後銷毀舊 bundle version，刪除只移除該 owner entry；Gateway 不得取得 project-wide admin。工具輸出／event 先去 secret 再儲存，不保存 raw provider error；owner-scoped auth lifecycle 未通過 GCP dev 驗收時 fail closed。
- Dev credential resource 由 operator 僅為 allowlisted owner 建立並逐資源授權；大量正式使用者的自助 provisioning 與成本另案核准，不藉此擴大 Gateway 或 User API 權限。
- GCP dev Secret／bundle 對照、欄位名稱、消費者與 IAM metadata 以 [Secret Bundle 清單](../secret_list.md) 為單一查閱入口；provider bundle 包含 MCP signing key，不建立獨立 signing Secret。
- Codex 刪除依序停止 owner session、執行 App Server logout、刪除 owner auth，再清私人 artifacts 與 PostgreSQL index；各步驟冪等，無 thread 或 auth 已不存在仍可成功。App Server logout 只代表 managed credentials 已清除，不宣稱供應商端 refresh token 已撤銷。Iceberg snapshot／orphan file 與 GCS object version 的實際保留期限必須被驗證並向 UI 揭露。
- 長正文／context／citations／items／skill revisions 儘可能進 Private Iceberg；PostgreSQL 保存 bounded thread／turn／pending approval／usage reservation 索引與 artifact references。Cloud Run filesystem 只作 bounded ephemeral storage；核准保留的 artifact 寫入 Private GCS／Iceberg，刪除涵蓋雲端狀態與暫存 reference。
- Gemini 免費 Grounding 須確認模型能力與專案 quota；額度不足／不可用明確回報，禁止自動付費。OpenRouter 啟用付費另需同意；quota／budget 用原子 reservation 防併發超支。私人 context 外送須明確選取並顯示供應商。
- 只有 Cloud Run 無法滿足超過 request timeout 的不可中斷 turn、必要持久 daemon／特殊 sandbox 權限，或實測資源／連線需求時，才提出 Compute Engine／GKE 方案；必須先提供成本、安全、維運、資料遷移與退出評估，取得使用者明確決定後才能實作或建立資源。

### 12.2 Janus ChatGPT MCP Connector

ChatGPT Custom MCP App 是 external MCP client／consumer，不是第四個 Janus
runtime、Janus MCP Host、Skill runtime 或 Janus Chat API thread；不加入
`openrouter | gemini | codex` provider loop，不共享 Janus thread lifecycle，不
自動載入 Janus Skills，也不把 ChatGPT conversation persistence 寫入 Private
Iceberg。若未來要把 Janus Skill 暴露成 external MCP capability，另案 review。

首選路徑為 `ChatGPT → remote read-only MCP → existing janus-api → shared bounded
query boundary`。不得預設新增 `janus-mcp` Cloud Run service；implementation 前
必須確認既有 `janus-api` ingress、authentication 與 protocol hosting 是否安全
可用，否則先停下並提交新 service／tunnel／既有 service adjustment 的架構、成本、
安全、IAM、維運與退出比較。

第一版 logical tool surface 固定為三個 read-only tool；全部宣告
`readOnlyHint=true`、`destructiveHint=false`、`openWorldHint=false`，JSON Schema
全部 `additionalProperties=false`：

- `janus_sources`：input 為空 object。使用 OAuth scope `janus.sources.read`；回傳目前
  principal 可用的 `source_id`、`owner_scope`、resource enum、freshness、status、
  quota／bounds 與 disclosure，不回傳資料內容或 storage locator。
- `janus_market_context`：使用 OAuth scope `janus.market.read`。input 必填 `symbol`
  （`^[0-9A-Z._-]{1,20}$`）與 `resource` enum；resource 固定為 `ohlcv`、
  `valuation`、`institutional`、`financials`、`events`、`market-activity`、
  `benchmark`。`start_date`／`end_date` 必須同時提供、ISO date、順序正確且 range
  不超過 366 天；`limit` default 10、min 1、max 20。不接受 dataset／table／URI／
  offset／raw query。
- `janus_private_context`：使用 OAuth scope `janus.private.read`。input 必填
  `resource` enum，固定為 `positions`、`annual-pnl`、`exposure`、`performance`、
  `stress-tests`、`investment-profile`、`watchlist`、`trades`；optional `symbol`
  只適用於 `positions`／`watchlist`／`trades`，optional `year`（1900–9999）為
  `annual-pnl`／`performance` 必填且可用於 `trades`，`limit` default 10、min 1、
  max 20。其他 resource／selector 組合安全拒絕。`trades` 重用既有 owner-scoped
  `ledger_history`；`investment-profile` 僅在既有 `ai_context_opt_in=true` 時回傳；
  第一版不暴露 free-form `notes`。

`janus_market_context` 與 `janus_private_context` 共用以下 output envelope：

```json
{
  "schema_version": "janus.mcp.v1",
  "status": "available|partial|missing|stale",
  "resource": "allowlisted-resource",
  "as_of": "ISO-8601-or-null",
  "records": [],
  "provenance": [],
  "bounds": {"limit": 10, "returned": 0, "truncated": false, "max_output_bytes": 32768},
  "disclosure": "source and external-AI disclosure"
}
```

`records` 合計最多 20 筆／32 KiB；超限只在完整 record 邊界截斷並明示
`truncated=true`。`provenance` 只允許 `source_id`、`provenance_id`、`snapshot_id`、
`ledger_version`、`valuation_date` 等非 locator metadata。空資料回 `missing` 與空陣列，
不得補算、即時爬取或用 LLM 產生 placeholder。

所有 tools 都要求 authentication，包括 public market tool，以避免匿名 abuse／quota
cost。MCP request 不接受 `user_id`、`owner_id`、Google `sub`、email、Secret name 或
credential locator；owner 只能由 server 驗證後的 `(issuer, subject)` binding 映射至
既有 internal UUID，不得只用 email 自動合併帳號。

依 2026-09-17 官方 OpenAI remote MCP contract，public endpoint 必須是 stable HTTPS
Streamable HTTP（通常 `/mcp`）；OAuth 必須提供 MCP protected-resource metadata、
authorization-server／OIDC discovery、authorization-code + PKCE `S256`、精確的
`resource` 傳遞與 token audience／scope 驗證，並以 CIMD、DCR 或 predefined client
識別 OpenAI host。每個 tool 宣告自己的 `securitySchemes`；未認證 tool call 同時回
`401 WWW-Authenticate` 與 MCP `_meta["mcp/www_authenticate"]`。Canonical resource
由 trusted deployment config 固定為完整 `/mcp` HTTPS URL，不從 request `Host` header
推導。官方參考：[Authenticate users](https://developers.openai.com/plugins/build/auth)、
[Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)、
[Connect and test](https://developers.openai.com/plugins/deploy/connect-chatgpt)。

現有 `GoogleUserAuthenticator` 驗證的是 Google OIDC ID token，且 audience 固定為
Janus User OAuth client ID；ChatGPT MCP 會把 OAuth access token 放入 MCP Bearer request，
並要求 token 綁定 MCP `resource`。因此現有 Google browser OIDC token boundary **不能
直接重用**，Google email 也不能取代 issuer／subject／audience binding。已採用同一
`janus-api` 內嵌 OAuth authorization facade：Google standard OAuth 僅作上游登入，Janus
以 `MCP_OAUTH_SIGNING_KEY` 簽發短效 access token，token 含 issuer／subject／resource
audience／scope，authorization code 只存 hash 且一次性消費。不得在本 WBS 建立獨立
OAuth broker／Cloud Run service；GCP dev callback、bundle、issuer 與 metadata 已驗證，
adapter 不再維持 `auth_blocked`。anonymous market tool、shared static bearer、client
supplied owner 與以 email 推測 owner 也全部拒絕。

MCP output 沿用既有 sanitization，至少保留 source、as-of、provenance、bounded
records 與 material availability／partial status；不得外送 GCS URI、object path、
raw payload、credential、password、secret、token、private artifact locator 或
internal owner identifier。私人資料送往 ChatGPT 必須在 connector setup／UI 明確
揭露為 external AI data use，不預先宣稱 OpenAI retention／training policy。

ChatGPT MCP adapter 必須重用或抽離 shared bounded query boundary 的 source
allowlist、owner scope、typed selector、date／range bound、record／output limit、
sanitization、provenance 與 as-of semantics。不得直接重用目前 chat-only
`ContextSourceService.preview()` 而產生不必要的 `context_ref`／snapshot；ChatGPT
路徑應回傳 direct bounded read result，不需要 Janus chat `context_ref`。

Protocol discovery／`tools/list` 只公開上述 schema、annotation、scope 與 disclosure，
不含 owner data；`tools/call` 才執行 server-side auth／owner binding／quota。第一版不提供
resources、prompts、subscriptions、mutation、write confirmation 或 ChatGPT conversation
snapshot storage。Developer mode／workspace plan 或 policy 是否允許連線屬 acceptance-time
外部 capability，contract 不預先宣稱可用。

既有 `janus-api` 現提供 stateless Streamable HTTP JSON-RPC `POST /mcp`，只處理
initialize、ping、tools/list、tools/call 與必要 notification。三個 tool 均宣告 per-tool
OAuth scope 與 read-only annotations；tool call 驗證 Janus access token 後，以 token subject
綁定 internal owner。Chat API preview 與 MCP direct result 共用同一 bounded read／sanitize
boundary，但 MCP 不建立 `context_ref` 或 conversation snapshot。

第一版只需要 remote MCP tool integration，不要求 embedded ChatGPT UI、Apps SDK
component、custom React UI、write action 或 ChatGPT-side workflow builder。

## 13. GCP 開發與 CI/CD

| 項目 | 選擇 |
|---|---|
| 開發環境 | Cloud Workstations；低頻可用 Cloud Shell Editor |
| 原始碼 | GitHub monorepo、branch protection、PR review |
| GCP 認證 | Workload Identity Federation，不使用長效 JSON key |
| 建置 | Cloud Build path-based pipelines |
| Image | Artifact Registry，由 source deploy／Cloud Build 管理 |
| 部署 | Dev acceptance 後先進既有 Dev Pilot；六個月後依人工 Go／Extend／No-Go 再條件式規劃 staging／production，沿用同一 immutable image digest |
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

## 13.3 ResearchContext composition contract（Proposed／not implemented）

`ResearchContext` 是 existing `janus-api` 上的 typed、bounded、owner-scoped、
provenance-aware 與 PIT-aware server composition contract，不是現有 API response 或新
storage layer。概念區段為 `market`、`company`、`supply_chain`、`private`、
`quality`；頂層固定 `analysis_as_of`。`market` 包含 regime／benchmark／systemic
risk／freshness；`company` 包含 market data、valuation、institutional、leverage、
revenue、financials、events 與 deterministic signals；`supply_chain` 包含 nodes、
relationships、exposures、leading indicators 與 signals；`private` 包含 position、
cost basis、cash／portfolio exposure、investment policy、research thesis、candidate／strategy
state 與 prior decisions；`quality` 包含 missing／stale datasets、fallback sources、
provenance 與 `pit_status`。

Composition 只接受 typed selector、allowlisted resource、bounded date／range／record／byte
limit 與 authenticated principal；私人區段由 principal 綁定 owner，不接受
`user_id`／`owner_id`。各區段必須與同一 `analysis_as_of` 一致，並顯式回傳
missing、stale、partial、freshness 與 provenance。不得輸出 credential、SQL、table
name、GCS URI、object path、raw payload 或內部 owner identifier。

Janus UI 使用 bounded response；ChatGPT MCP 是同一 boundary 的 read-only consumer，可使用
direct bounded result 或 opaque／short-lived context reference，但不得成為 arbitrary SQL client、
GCS／database browser、scraper、canonical financial／technical／portfolio calculator 或 mutation
interface。優先重用 existing `janus-api`；未來只有 insufficiency evidence、cost／security／
operations review 與 explicit approval 後才能提案新 runtime。Google Drive 不在 MCP runtime
contract。
