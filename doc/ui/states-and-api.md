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
| deleting | 正在刪除 Janus 私人資料，暫時無法寫入 | amber + progress，不提供相關寫入操作 |
| cleanup_pending | 部分雲端資料仍在清理，系統會安全重試 | amber + request ID／重試狀態，不顯示完成 |

## 8. Janus User UI／FastAPI 契約

- Janus Flutter repository 只負責 Janus 投資／Admin HTTPS、typed decoding 與 UI 狀態；不得計算正式分數、損益或 fallback 內容。generic Chat／Agent／MCP／approval client 已移至 omniAgent source，Janus User UI 不主動呼叫 omniAgent。
- 200 保存 response；404 依 error code 顯示不存在或等待批次；401／403 導向登入或安全拒絕；network／5xx 顯示服務錯誤。
- Janus 投資頁一般載入不得啟動 scraper、Agent、LLM 或 Private Mart 重算。舊 Janus Chat API／SSE route 在部署切換前仍保留給既有 live client，但不屬於 Janus 新 UI source 的導航或元件契約。

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
- `GET／PUT /api/v1/me/investment-profile`
- `GET /api/v1/me/portfolio/summary`
- `GET /api/v1/me/portfolio/exposure`
- `GET /api/v1/me/portfolio/performance?year=YYYY`
- `POST /api/v1/me/portfolio/stress-tests`
- `DELETE /api/v1/me/private-data`
- `GET /api/v1/me/private-data/deletions/{request_id}`

Planned Admin workspace endpoints（不代表已實作）至少需要：

- actionable overview、batch／execution details、retry classified failed item、retry lineage。
- symbol／中文名稱 search、dataset health、gap repair、affected-role mapping、single-role
  rerun、historical facts／roles／CIO。
- Analysis Profile current／history、new Production version、compare、rollback、prompt
  versions、provider/model capability 與 fixed test symbols。

上述所有 `/api/v1/admin/*` endpoint 每次都必須由 backend Admin authorization enforce；
Flutter 隱藏控制不構成 auth。單角色 rerun 預設使用 current Production Profile，依賴
未變更的 Fact Pack reuse；Core／Fact Pack 改變先重建 facts，prompt/model 改變不重算
facts，CIO-only 改變不重跑 role，governance-only 改變不呼叫 LLM。

Janus Private endpoint 只接受獨立 User OAuth audience 的 Google OIDC token；API 驗證 issuer、audience、expiry，以 Google `sub` 對應內部 UUID `user_id`，email 只供顯示。使用者身分不接受 request body 或 query string 指定 `user_id`，User token 不得存取 Admin endpoint。`DELETE /private-data` 回 `202`、request ID 與初始狀態；status endpoint 僅允許 request owner 查詢。舊 Chat／approval／MCP／Skills API 在 live cutover 前仍由 Janus 安全維護，不構成 Janus UI 的長期 product surface。

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
