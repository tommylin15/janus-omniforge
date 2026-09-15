# Janus UI — 狀態語意與 API 契約

## 7. UI 狀態語意

| 狀態 | 使用者文案 | 視覺 |
|---|---|---|
| loading | 資料載入中 | skeleton／spinner |
| empty | 目前沒有資料 | zinc |
| unavailable | 資料來源暫時無法使用 | amber |
| partial | 部分資料可用 | amber + 缺失清單 |
| stale | 資料日期較舊 | amber + 實際日期 |
| fallback | 使用備援來源 | 低調 badge + source |
| insufficient_data | 資料完整度不足，無法評估 | zinc，不顯示方向 |
| blocked | 報告未通過發布審查 | 公開端不回傳；Admin red |
| error | 服務暫時發生問題 | 安全文案，不顯示 traceback |
| deleting | 正在刪除私人資料，暫時無法建立新對話或登入 Codex | amber + progress，不提供相關寫入操作 |
| cleanup_pending | 部分雲端資料仍在清理，系統會安全重試 | amber + request ID／重試狀態，不顯示完成 |

## 8. User UI／FastAPI／Cloud Run Agent 契約

- Flutter repository 只負責 HTTPS、取消過期 request、typed decoding 與 UI 狀態；不得計算正式分數、損益或 fallback 內容。Codex App Server 與 stdio MCP 只由 Cloud Run Agent Gateway 在容器內啟動，client 不持有或啟動本地 runtime。
- 200 保存 response；404 依 error code 顯示不存在或等待批次；401／403 導向登入或安全拒絕；network／5xx 顯示服務錯誤。
- 只有 `/api/v1/me/chats/{conversation_id}/events` 可使用 bounded SSE；其他 endpoint 不使用 SSE，也不得在一般 page load 時啟動 scraper、Agent、LLM 或 Private Mart 重算。Cloud Run cold start、timeout／recycle 與 reconnect 是明確 typed state，續接一律帶 last event cursor。

主要 public endpoints：

- `/api/v1/public/health`
- `/api/v1/public/daily-brief?date=YYYY-MM-DD`
- `/api/v1/public/sectors/rotation?date=YYYY-MM-DD`
- `/api/v1/public/topics?date=YYYY-MM-DD`
- `/api/v1/public/candidates?date=YYYY-MM-DD`
- `/api/v1/public/stocks/{symbol}/health`
- `/api/v1/public/stocks/{symbol}/reports`
- `/api/v1/public/stocks/{symbol}/kline?period=D|W|M`
- `/api/v1/public/stocks/{symbol}/events?cursor=...`

主要 private journal endpoints：

- `GET／POST /api/v1/me/journal/trades`
- `POST /api/v1/me/journal/trades/{event_id}/corrections`
- `GET /api/v1/me/journal/positions`
- `GET /api/v1/me/journal/pnl?year=YYYY`
- `POST /api/v1/me/journal/export`
- `GET／POST /api/v1/me/notes`
- `POST /api/v1/me/notes/{note_id}/revisions`
- `GET／POST／DELETE /api/v1/me/watchlist`
- `GET／POST /api/v1/me/chats`
- `POST /api/v1/me/chats/{conversation_id}/fork`
- `POST /api/v1/me/chats/{conversation_id}/messages`
- `GET /api/v1/me/chats/{conversation_id}/events`
- `POST /api/v1/me/chats/{conversation_id}/approvals/{request_id}`
- `POST /api/v1/me/chats/{conversation_id}/cancel`
- `GET /api/v1/me/ai-sources`
- `POST /api/v1/me/chats/{conversation_id}/context-preview`
- `GET／PUT /api/v1/me/mcp/servers`
- `GET /api/v1/me/mcp/servers/{server_id}/tools`
- `GET／PUT /api/v1/me/ai-connections`
- `GET／PUT /api/v1/me/skills`
- `GET／PUT /api/v1/me/investment-profile`
- `GET /api/v1/me/portfolio/summary`
- `GET /api/v1/me/portfolio/exposure`
- `GET /api/v1/me/portfolio/performance?year=YYYY`
- `POST /api/v1/me/portfolio/stress-tests`
- `DELETE /api/v1/me/private-data`
- `GET /api/v1/me/private-data/deletions/{request_id}`

Private endpoint 只接受獨立 User OAuth audience 的 Google OIDC token；API 驗證 issuer、audience、expiry，以 Google `sub` 對應內部 UUID `user_id`，email 只供顯示。使用者身分不接受 request body 或 query string 指定 `user_id`，User token 不得存取 Admin endpoint。Provider／MCP connection 只傳 opaque reference，API key／Codex auth cache 不經 payload。`context-preview` 只接受 typed selector，回短效 owner／thread-bound `context_ref`；message 不接受 SQL、GCS URI、object path 或 raw private payload。Approval response 另驗證 owner、thread、turn、request、參數摘要、expiry 與一次性消費；所有 mutation 具 idempotency key、optimistic version 與 audit event。`DELETE /private-data` 回 `202`、request ID 與初始狀態；status endpoint 僅允許 request owner 查詢。owner 為 `DELETING` 時，新的 Codex login／turn 與私人 artifact mutation 回 typed conflict，不得在 client 端假裝完成。

## 9. ResearchContext state／API planning

ResearchContext 沿用 `loading | empty | unavailable | partial | stale | fallback |
insufficient_data | error`，不建立第二套狀態。例如 margin 缺失為 `partial`、
financial data 超過 freshness contract 為 `stale`、缺少足以判斷的核心資料為
`insufficient_data`；UI 不得將缺值顯示為 0，LLM 不得補值。

`ResearchContext` endpoint／response 目前為 **planned／proposed**，不在上方 implemented
endpoint 清單中。未來 response 必須 typed、bounded、owner-scoped，保留同一
`analysis_as_of`、freshness、provenance、PIT 與 explicit missing／stale／partial。
ChatGPT MCP 使用同一 server boundary，不接受 arbitrary SQL、GCS locator 或 owner ID，
且不提供 mutation。
