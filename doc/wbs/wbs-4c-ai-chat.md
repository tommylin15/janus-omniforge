# Janus WBS 4C — 多供應商私人助理

狀態：新版目標契約；尚未完成 runtime 驗收。個股為可選 context，對話不綁定單一股票或 AI 廠商。

## 執行切片與必讀文件

所有切片先讀 [API／Assistant contract](../spec/api-and-delivery.md) 與
[架構決策](../spec/overview-and-decisions.md)，只執行 TODO 指定的一項。UI 切片另讀
[User App](../ui/user-app.md)、[States/API](../ui/states-and-api.md) 與 UI foundations；
私人資料切片再讀 WBS 4J。

| 任務 ID | 範圍／完成條件 | 前置 |
|---|---|---|
| `WBS-4C-ENGINE-SECURITY` | Agent Runtime／AgentEvent、capability、credential／approval／資料外送契約與可執行 contract tests；評估並取代舊 engine security 草稿 | ready，僅契約實作，不建立雲端資源 |
| `WBS-4C-CLOUD-RUNTIME` | Cloud Run Agent Gateway、按需容器、Codex App Server 子行程、暫存 sandbox、checkpoint／重連與 managed auth 可行性 POC | ENGINE-SECURITY；任何部署與付費先過人工 gate |
| `WBS-4C-OPENROUTER` | 動態模型目錄、tool capability 篩選、串流 function-call loop、用量與失敗狀態 | ENGINE-SECURITY；付費呼叫另需人工同意 |
| `WBS-4C-GEMINI-API` | Gemini REST API、API key、Google Search Grounding、citation／查詢時間、免費額度與 429 handling | ENGINE-SECURITY；免費層及模型能力確認 |
| `WBS-4C-CONTEXT-SOURCES` | Janus Core／Private Mart read-only context、外部來源 allowlist、source list／preview／opaque ref API、日期／provenance／owner 邊界 | ENGINE-SECURITY |
| `WBS-4C-MCP-HOST` | 容器內 stdio、遠端 Streamable HTTP／legacy SSE、協定交涉、工具發現與受控執行 | ENGINE-SECURITY、CLOUD-RUNTIME |
| `WBS-4C-CODEX-BRIDGE` | Cloud Run 容器內 stdio JSON-RPC、managed login、Threads／Turns／Items／Approvals 與共用 MCP 路徑 | CLOUD-RUNTIME、MCP-HOST |
| `WBS-4C-SKILLS` | GCP 儲存、載入／啟用／自訂 skill、版本化 prompt／workflow 與 tool scope | ENGINE-SECURITY、MCP-HOST、PRIVATE-STORAGE |
| `WBS-4C-PRIVATE-STORAGE` | Private Iceberg 正文／events／Skills 與 PostgreSQL index、owner isolation、冪等／匯出／刪除／雲端暫存清理 | runtime／event contract |
| `WBS-4C-CHAT-API` | Threads CRUD／fork、bounded SSE、取消、approval response 與續接去重 | runtime／storage／approval contract |
| `WBS-4C-ASSISTANT-UI` | 既有 Flutter Web／mobile 私人助理、Markdown／程式碼高亮／streaming、MCP／Skills／Approval 操作 | CHAT-API、provider／MCP／Skills contracts |
| `WBS-4C-ACCEPTANCE` | Cloud Run、三 runtime、資料源、MCP transports、Skills、approval、Grounding、privacy、重跑／刪除與 UI 驗收 | 上述切片 |

## 4C.1 多供應商 Agent Runtime

- 受控 runtime 為 `openrouter | gemini | codex`；provider、model 與 assistant／skill profile 分開保存。`chatgpt` 如保留只作 Codex 對話 preset，不是第四個 provider 或另一個 daemon。
- OpenRouter 使用 `OPENROUTER_API_KEY`，從模型目錄動態選擇 Claude、Llama、Gemini 等已核准模型；依實際 tool／streaming capability 提供選項，不保證所有模型支援 Function Calling。路由與 fallback 必須明示，不靜默切換。
- Gemini 直接呼叫 Gemini Developer REST API，使用 Google AI Studio 的 `GEMINI_API_KEY` 與免費層；不使用 Google GenAI SDK 或 Vertex AI workload identity。Google Search Grounding 是必要能力，須確認選定模型／專案的免費支援及實際 quota，保留 citations、查詢時間與 attribution；不可用時明確回報，不切到付費。
- Codex App Server 與 Node.js／TypeScript Agent Gateway 包裝在 Cloud Run Service 容器；gateway 在容器內以 stdio JSONL 啟動並管理 App Server 子行程，再將事件轉為 authenticated HTTPS SSE。使用 ChatGPT managed OAuth／device-code，不改成 OpenAI API key 或直接 Responses／Codex API fallback。
- 不建立 React／Tauri 桌面程式或任何使用者地端 runtime。既有 Flutter Web／Android／iOS 只連 FastAPI／Agent Gateway 的雲端 API；provider、MCP 與 Codex secrets 不下發前端。
- Cloud Run 採 `min-instances=0` 按需啟動；MVP 每 instance concurrency 為 1，設定 bounded max instances／timeout。所有 thread／event／approval checkpoint 外部持久化，client 必須可用 cursor 重連，不依賴 best-effort session affinity 或容器記憶體。
- Codex App Server 目前屬實驗性且官方不支援 production workload；Cloud Run 方案先完成 dev POC，驗證 Linux 容器、managed auth refresh、sandbox、stdio lifecycle、取消及重連後，才可另行核准 production。驗證失敗時不得靜默改用直接 OpenAI API。
- 每個 thread 固定 runtime／model；切換新建或 fork，選擇要轉移的 context，保留 parent lineage；供應商原生 thread ID 不可直接跨 provider 重用。

## 4C.2 MCP Host 與 Skills

- 應用作為 MCP Host，對每個已核准 server 建立獨立 client／session；支援 Agent Cloud Run 容器內的 stdio 子行程、遠端 Streamable HTTP 與明確設定的 legacy SSE。瀏覽器與使用者裝置不啟動 MCP process。
- 使用 MCP SDK 處理 initialize／capability negotiation／initialized、`tools/list` 分頁與 list-changed、`tools/call`、timeout／cancel／disconnect。resources／prompts 等依已交涉能力提供；不支援的 server-initiated requests 明確拒絕。
- 工具名稱以穩定 namespace 映射至 server／tool，驗證 JSON Schema、ownership 與授權；雲端 adapters 執行 bounded tool loop，保留 provider 所需原始 continuation metadata。
- Codex 可透過 dynamic tools bridge 或 Host 的受控 MCP facade 進入相同工具執行與 approval 邊界。共用 registry 本身不算共用 enforcement；不得直連後繞過 Host policy，也不得重複執行 Codex 自有 agent loop。
- Skills 支援使用者載入、啟用、停用、自訂與版本化；內容包含 system prompt fragment、所需工具與領域 workflow。每個 turn 記錄 skill 版本／prompt snapshot；執行中的 turn 不受後續 skill 編輯影響。
- Skill／MCP tool description／外部新聞／筆記不可擴大 host 權限；自動化 workflow 每一步使用相同工具 dispatch／approval，不允許以 prompt 或任意載入程式繞過。
- 內建 Skills 隨 immutable image 發版；使用者自訂 skill 定義與 revision 存 Private Iceberg／GCS、以 PostgreSQL bounded index 定位，執行 turn 時只把核准 snapshot 物化到容器暫存目錄。Skill 預設只含 prompt／workflow manifest，不允許上傳任意可執行程式。

## 4C.3 資料源與雲端執行邊界

- Janus 市場資料只讀已發布 Core／Mart；使用者持股、交易、筆記、關注股只讀 authenticated owner 的 Private Core／Mart。由 Cloud Run context service 或內部 read-only MCP 暴露 bounded query，不讓模型直接取得 GCS URI、PostgreSQL credential 或跨 owner 查詢能力。
- User API 新增來源清單與 thread context preview：只接受 typed resource selector／date range，回短預覽、provenance 與短效 owner／thread-bound opaque reference；message 以 reference 固定 turn snapshot。Agent Gateway 只用 service identity 解析 reference。既有 public market、journal、portfolio 與 ingestion API 不改語意。
- Google Search Grounding 是 Gemini provider capability；其他新聞、研究與第三方資料源必須登錄 source ID、授權、資料日期、provenance、timeout、quota 及可外送範圍，再透過核准的 remote MCP 或既有 ingestion／Mart 使用，不在聊天 request 臨時爬取未核准來源。
- stdio-only MCP binary 必須建入經核准的 Agent image 並在同一 Cloud Run instance 內按 turn／session 啟動；可 HTTP 化且需獨立擴縮者部署成私有 Cloud Run MCP service。兩者都用專用 service account、Secret Manager reference、egress allowlist 與 bounded CPU／memory／output。
- Cloud Run writable filesystem 只作有大小上限的暫存 sandbox，instance 終止即視為遺失；核准保留的輸出先去 secret，再寫入 Private GCS／Iceberg artifact。不得把容器磁碟、背景 daemon 或單一長連線當永久狀態。
- 只有 Cloud Run 無法滿足超過 request timeout 的不可中斷 turn、必要的持久 daemon／特殊 sandbox 權限，或經量測的資源／連線需求時，才提出 Compute Engine／GKE 評估。提案必須先列成本、安全、維運與退出方案，取得使用者明確決定後才能採用或建立資源。

## 4C.4 安全、私人 context 與儲存

- 預設最小權限。使用者核准的 shell／寫檔只在該 turn 的 Cloud Run 暫存 sandbox 內執行，approval 顯示操作與範圍，拒絕／到期／取消即不執行。MCP subprocess 本身亦需隔離，不假設 Codex sandbox 保護外部 MCP。
- Approval 不可授予 Janus Admin、交易／筆記／watchlist mutation 或下單；這些既有產品限制仍保留，擴充需另外明確決策。
- Provider API keys、MCP credentials 與 Codex auth cache 只存在 Secret Manager 或經核准的隔離 GCP credential store，不進 browser／Flutter storage、PostgreSQL、Iceberg、image 或 log。Cloud Run managed auth refresh 的安全持久化是 POC gate，未通過不得上 production。
- Context 僅由 authenticated owner 明確選取；外送雲端前顯示供應商與資料範圍。Gemini 免費層的資料處理條件需揭露，未取得相應同意前不外送敏感私人內容。
- Messages、context、citations、已過濾的 items／events／tool results 儘可能存 Private Iceberg；PostgreSQL 只存 bounded thread／turn／approval 狀態索引、idempotency、checkpoint／artifact reference。可恢復的 approval／event 狀態不能只存在程序記憶體。
- 匯出／刪除涵蓋雲端私人 artifact、skill revision、thread／cache／auth state 與暫存 artifact reference；未完成清理時記錄待處理，不虛報完成。引用公開資料不改寫 public Mart／publication policy。
- Gemini 付費層停用；OpenRouter 付費啟用仍需人工 billing gate 與核准的 request／user／project limits。quota／預算計數須支援原子 reservation、併發與重啟；僅傳入數字做比較不算 hard limit。

## 4C.5 Threads、Streaming 與驗收

- 共用事件包含 text delta、item upsert、tool request／result、approval request／resolved、citation、usage、turn completed／cancelled／error；保留 threadId／turnId／itemId／eventId／seq 與 provider 原生 ID 映射。
- UI 只用統一事件模型渲染，Codex 額外顯示 Items、Turns 與 Approval Requests。SSE 使用 cursor 續接、bounded replay、backpressure；approval／cancel 只經 authenticated HTTPS POST。
- Approval 綁定 owner、thread、turn、request 及具體參數；拒絕跨 owner、過期或重播，不能將 UI boolean 當全域權限。
- 驗收需覆蓋 Cloud Run scale-to-zero／cold start／timeout／中斷重連、三 runtime 真實或受控協定測試、內部與外部資料源 provenance、MCP stdio／HTTP／SSE、動態工具、Skill 權限、Codex managed auth／approval／取消、Grounding 來源、provider unavailable／quota、A／B 隔離、匯出／刪除、stream 續接去重及無 placeholder。
- MCP Host、Skills、遠端 transport 與 approval UI 都是本 WBS 必交付能力；可分切片，不能在完成宣告時省略。
