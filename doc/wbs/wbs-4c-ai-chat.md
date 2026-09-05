# Janus WBS 4C — 可切換私人 AI 聊天室

## WBS 4C — 可切換私人 AI 聊天室（P0）

### 4C.1 Engine 與認證

- 提供 `codex | chatgpt | gemini` 三個受控 profile；`codex` 與 `chatgpt` 共用 Codex App Server，但分別採 agentic／conversation policy。`chatgpt` 是 Janus profile 名稱，不宣稱存在另一個官方 App Server daemon。
- `codex`／`chatgpt` 只使用 ChatGPT managed OAuth 或 device-code 與使用者訂閱；禁止 OpenAI API key、Responses API、Codex API 或其他按量 OpenAI API。
- `gemini` 使用 Google AI Studio 建立的 `GEMINI_API_KEY` 呼叫 Gemini Developer API 免費層，固定採支援免費 Google Search grounding 的模型；key 只存在伺服器端 Secret Manager／環境變數。付費層維持停用。
- 每個 conversation 固定 engine/profile；切換建立新 conversation／fork，不在同一 lineage 無痕換引擎，也不做靜默 fallback。

### 4C.2 Context、儲存與安全

- `/api/v1/me/chats/*` 只組合 authenticated user 選定的持股、交易、筆記、關注股，以及已持久化公開 Core／Mart；每次回答保存 context snapshot、engine、model、資料日期、search flag 與 citations。
- messages、context 與 citations 儘可能寫入 Private Iceberg；PostgreSQL 只保存 session index、status、idempotency、checkpoint 與 artifact reference。provider credential／refresh token 不得進 PostgreSQL、Iceberg、log 或 Flutter storage。
- 所有 profile 禁止 shell、寫檔、Admin、交易／筆記／watchlist mutation 與自動下單工具。外部內容視為不可信輸入，不得解除 tool／publication／ownership policy。
- Gemini grounding 回答顯示可點擊來源與查詢時間；不保存完整新聞正文。缺 citation、資料不足、rate limit 或 provider unavailable 時顯示明確狀態，不生成 placeholder 或改用其他引擎。

### 4C.3 Flutter 與驗收

- 聊天室顯示 engine selector、目前登入／額度狀態、使用中的私人 context、來源、資料日期與投資免責聲明；切換引擎前提示將建立新 conversation／fork。
- 只允許聊天室 endpoint 使用 bounded SSE；一般頁面仍不得在 load 時啟動模型。取消、斷線重連與重複 event 必須冪等。
- 驗證三 profile 可選、conversation lineage、Codex managed login/logout／rate limit、Gemini grounding citation、A／B 隔離、prompt injection、無 OpenAI API-key 路徑、Iceberg 重跑／匯出／刪除與 Gemini 免費額度 hard limit。
