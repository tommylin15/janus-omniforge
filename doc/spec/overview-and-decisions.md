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
3. P0 同步交付可切換的私人聊天室：`codex` 與 `chatgpt` 兩種 profile 共用 Codex App Server 的 ChatGPT managed OAuth／device-code 與訂閱通道；`gemini` profile 使用 Gemini 加 Google Search grounding。禁止 OpenAI API key、Responses API、Codex API 或其他按量 OpenAI API 通道。
4. 三種 profile 可並存，但每個 conversation 固定一個 engine/profile；切換時建立新 conversation 或 fork，保留原 provider、model、context 與 citation lineage。啟用 Gemini 計費資源前須另取得明確費用同意。
5. 完成私人 MVP 後，再執行全市場深化、公開 Intelligence Mart、公開研究 UI 與發布流程。

## 2. 已確認的架構決策

- 從第一天起在 GCP 開發、測試與部署，不以地端 runtime 為必要條件。
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
- 私人聊天室提供 `codex`、`chatgpt`、`gemini` 三個可選 profile。官方沒有另一個獨立的 ChatGPT App Server daemon；`chatgpt` 是 Janus 在同一 Codex App Server 上提供的對話型 profile，使用 `appBrand=chatgpt` 的 managed OAuth 登入體驗，`codex` 則是受限工具的 agentic profile。兩者均使用使用者既有訂閱，不得要求或接受 OpenAI API key，也不得呼叫 Responses API、Codex API 或其他按量 OpenAI API。
- `gemini` 是可主動選擇的並存 profile，不是靜默 fallback。它使用 Google AI Studio API key 與 Gemini Developer API 免費層，支援 Google Search grounding、回傳可點擊來源與查詢時間，並受每人每日與專案每日免費額度 hard limit 約束；付費層維持停用。
- Codex／ChatGPT 認證資料不得寫入 PostgreSQL、Iceberg、log 或 client storage，由每位使用者隔離的 Codex-managed auth store 管理。任何 profile 都不得取得 shell、寫檔、Admin、交易 mutation 或自動下單能力。
- Cloud Run Service 全部 `min-instances=0`；寫入 Core 的 ingestion Job 單 task 執行，API／query runtime 對 Core 採 read-only。
- Artifact Registry 可由 source deploy／Cloud Build 自動管理，但底層仍需保存容器映像。
- Artifact Registry 僅使用 image、digest、metadata 與 cleanup；禁止 Artifact Analysis API、Container Scanning API、vulnerability scanning 與 occurrence API。SBOM 僅可離線產生，不以掃描結果作為 build gate。
