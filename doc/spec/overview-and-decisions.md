# Janus SPEC — 產品目標與架構決策

## 1. 產品目標

建立以台股為主的個人投資工作台與湖倉型智慧投資研究平台。第一優先是讓使用者安全管理交易記帳、個人筆記、關注股與私人 AI 對話；後續才以官方與核准 fallback 資料產製市場、板塊、話題與候選股研究 Mart。

User App 與 Admin UI 是兩個獨立入口。Flutter 的公開研究頁只讀取符合發布政策的公開 Mart 成品，私人記帳、筆記、關注股與 AI 對話只讀取 authenticated user 的 ledger／Private Core／Mart；Admin Web 用於資料營運、治理、執行與發布審查。除明確的私人聊天室外，兩者均只經 FastAPI 契約取用已持久化資料，不直讀 Stage，也不在一般 page load 內觸發即時爬取、Agent 或 LLM。

個人投資工作台是 User App 的第一優先私人功能。PostgreSQL append-only ledger 保存需要 OLTP 一致性的交易事實、冪等鍵與單調遞增 `ledger_version`；筆記正文、對話訊息、對話 context／citation snapshot、關注名單歷史與交易正規化資料儘可能保存於 Private Iceberg Core，PostgreSQL 只保留必要的目前狀態、索引、版本、工作狀態、checkpoint 與 artifact reference。Private Mart 計算庫存、成本與損益；同步失敗可從最後成功 checkpoint 重跑，不另建 outbox。私人資料不得進公開 Mart／service index、話題、排行榜或他人的分析。

資料供應採雙軌策略：以全市場約 1,700–2,000 檔的低成本日頻資料作為搜尋與篩選大網，再對使用者主動加入關注名單的標的收集經核准的深度資料。深度追蹤不再代表「50 大」或平台推薦；MVP 仍以最多 50 個 active distinct symbols 作成本／quota 技術護欄，實際檔數以有效關注需求、股票 master 與市場狀態為準。

系統是研究、風險提示與手動交易筆記工具，不是自動下單、券商帳戶同步、持牌投顧或保證獲利服務。

### 1.1 交付順序

1. 先完成個人工作台所需的最小 Dev Stage → Core、股票 master、User auth 與 Private Iceberg 基礎；WBS 3 其餘 Admin polish／全市場擴張不得阻擋私人 MVP。
2. P0 交付交易記帳、個人筆記、關注股與最小 Flutter；正式損益只讀 Private Mart，私人長內容儘可能進 Iceberg。
3. P0 交付 GCP 雲端多供應商私人助理：OpenRouter 動態模型、Gemini Developer REST API（API key／免費層／Google Search Grounding），以及 Cloud Run 容器內 Codex App Server（stdio JSON-RPC／managed OAuth），以統一 Agent Runtime／events 整合資料源、MCP Host、Skills 與 Threads UI。
4. 每個 thread 固定 runtime／model；切換時建立新 thread 或 fork，保留 provider、model、context、citation 與 parent lineage。Gemini 不引入 Google GenAI SDK，且付費層停用；OpenRouter 與新 GCP 付費資源啟用另需人工同意。
5. 完成私人 MVP 後，再執行全市場深化、公開 Intelligence Mart、公開研究 UI 與發布流程。

## 2. 已確認的架構決策

- 市場資料、API 與私人助理全部在 GCP 開發、測試與部署；不建立 React／Tauri 桌面程式或使用者地端 Codex／MCP runtime。Web／mobile client 只經 authenticated HTTPS 連線。
- 一個 GitHub monorepo，市場資料、智慧 Mart、私人帳本、API、User 與 Admin 保持清楚邊界；Core query 能力由 Job／API 各自內嵌的 DuckDB runtime 提供。
- User 與 Admin 前端分離：`apps/user_app` 為 Flutter + Material 3；現有 `apps/web` 專注 Admin Web，不在 User App 暴露 Admin 導覽或管理功能。
- Dev User authentication 固定使用 Google OIDC／Google Sign-In，使用獨立於 Admin 的 OAuth client／audience。API 驗證 issuer、audience、expiry，並以 `(provider="google", subject=sub)` 對應內部 UUID `user_id`；email 只供顯示，不作所有權鍵。Dev 可另加 User allowlist，不建立自有密碼系統。
- `services/api` 以 FastAPI 提供 public、private-journal 與 Admin API router；共用 service／repository 時仍使用不同路由、response model、認證、CORS、IAM 與 audit 邊界。現有 WSGI boundary 保留至 FastAPI 回歸測試完成後移除。
- GCS + Iceberg + DuckDB／PyIceberg 是資料主架構；DuckDB 不作為獨立持久資料庫。
- PostgreSQL 保存 Iceberg catalog、控制、治理、execution、publication、audit、服務索引與私人交易事件帳本；市場 raw payload 與完整 Mart payload 仍不進 PostgreSQL。
- Dev／MVP PostgreSQL 採 Compute Engine `e2-micro` 單一 VM 自架，位於 `us-central1`；Free Tier 模式限制 Standard Persistent Disk 總量 ≤30 GB、不配置 external IP，並以 IAP／OS Login 管理。此配置不作為 production HA 架構。
- `e2-micro` 僅承載 PostgreSQL，不承載 DuckDB 分析工作；DuckDB 內嵌於 Cloud Run Job／Service process，暫存與記憶體限制由各 runtime 獨立管理。
- 開發／重構期最低有效完整度為 30%；正式發布門檻日後依 PIT 回測與人工治理調整。
- LLM 只做提取、摘要、解釋與白話轉譯；不計算或修改 deterministic 分數、不補值、不決定發布。
- 私人助理不綁定個股或單一廠商，runtime 為 `openrouter | gemini | codex`；model 與 assistant／skill profile 分離。延續既有 Flutter Web／Android／iOS 與 FastAPI，新增的 Node.js／TypeScript Agent Gateway 只部署 Cloud Run。`chatgpt` 如保留僅是 Codex preset，不是獨立 provider。
- Gemini 直接用 `GEMINI_API_KEY` 呼叫 Developer REST API 免費層，保留 Google Search Grounding、citations／查詢時間與免費額度限制；不用 Google GenAI SDK／Vertex AI workload identity。OpenRouter 以獨立 API key 動態選擇已核准模型，Codex 只用 managed OAuth／device-code，不建立直接 OpenAI API fallback。
- Agent Gateway 與 Codex App Server 同置 Cloud Run Service；gateway 在容器內管理 stdio JSONL 子行程並透過 HTTPS SSE 提供統一 events。`min-instances=0`、MVP concurrency=1、bounded max instances／timeout；checkpoint 必須外部持久化，不能依賴容器記憶體、暫存檔或 session affinity。
- Codex App Server 目前屬實驗性且官方不支援 production workload；先完成 dev Cloud Run POC 與 managed auth refresh／sandbox／重連驗證，通過人工 gate 後才可決定 production。不得靜默改用直接 OpenAI API。
- Janus Core／Mart 與 owner-scoped Private Core／Mart 由 Cloud Run context service／內部 read-only MCP 提供 bounded context；外部資料源須先登錄授權、資料日期、provenance、quota 與外送政策。模型不得直接取得 GCS URI、資料庫 credential 或跨 owner query。
- MCP Host 支援 Cloud Run 容器內 stdio 子行程、遠端 Streamable HTTP、legacy SSE、協定交涉與動態工具；可獨立擴縮的 MCP 優先部署私有 Cloud Run Service。Skills 可載入／啟用／自訂 prompt 與 workflow：內建版本隨 image 發布，自訂版本存 Private Iceberg／GCS 並在 turn 開始時物化到雲端暫存 sandbox。兩者共用 host tool policy／approval，不能靠 prompt 擴權或上傳任意可執行程式。
- Provider／MCP／PostgreSQL secrets 與 Codex auth cache 使用 Secret Manager，不進正文、image、log 或前端 storage。Dev 經人工安全 gate 核准收斂為 API＋Web＋Pipeline、Agent＋Mart＋Ingestion、owner-keyed Codex auth 三個 bundle；這是降低 IAM 隔離以換取管理簡化的 dev/MVP 取捨。私人 context 外送須明確選取並揭露供應商資料處理條件。完整 runtime／data／MCP／Skills／事件契約見 [API 與交付](api-and-delivery.md)。
- Cloud Run writable filesystem 只作有大小上限的 turn sandbox；核准保存的輸出去 secret 後寫入 Private GCS／Iceberg。只有 Cloud Run 無法滿足不可中斷長 turn、持久 daemon、特殊 sandbox 權限或實測資源需求時，才提出 Compute Engine／GKE 成本、安全、維運與退出評估，取得使用者明確決定後才能採用。
- Cloud Run Service 全部 `min-instances=0`；寫入 Core 的 ingestion Job 單 task 執行，API／query runtime 對 Core 採 read-only。
- Artifact Registry 可由 source deploy／Cloud Build 自動管理，但底層仍需保存容器映像。
- Artifact Registry 僅使用 image、digest、metadata 與 cleanup；禁止 Artifact Analysis API、Container Scanning API、vulnerability scanning 與 occurrence API。SBOM 僅可離線產生，不以掃描結果作為 build gate。
