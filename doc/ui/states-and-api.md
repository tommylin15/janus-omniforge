# Janus UI — 狀態語意與 API 契約

更新：2026-10-06

## 7. UI 狀態語意

| 狀態 | 使用者文案 | 視覺／行為 |
|---|---|---|
| loading | 資料載入中 | bounded skeleton／spinner |
| empty | 目前沒有資料 | zinc |
| unavailable | 資料來源暫時無法使用 | amber |
| partial | 部分資料可用 | amber + 缺失清單 |
| stale | 資料日期較舊 | amber + 實際日期 |
| fallback | 使用備援來源 | 低調 badge + source |
| insufficient_data | 資料完整度不足，無法評估 | zinc，不顯示方向／0 分 |
| blocked | 未通過治理／權限／執行 gate | public 不假裝成功；Admin red |
| queued | 已建立工作，等待執行 | 不顯示為成功 |
| running | 執行中 | 顯示 started／last update |
| succeeded | 執行成功 | 只在 workload／artifact 真正完成時使用 |
| failed | 執行失敗 | safe reason + retryability |
| error | 服務暫時發生問題 | 安全文案，不顯示 traceback |
| deleting | 正在刪除 Janus 私人資料，暫時無法寫入 | amber，不提供相關 mutation |
| cleanup_pending | 部分資料仍在清理 | amber + request／retry state，不顯示完成 |

`unknown`／`尚未檢查`／`未定義` 不是 `0`。沒有 evidence 就顯示未知，不自行推導正常。

## 8. Janus User UI／FastAPI 契約

- Flutter 只負責 typed decoding、presentation、navigation 與 mutation command；不得計算正式 score、PnL、retention completion、fallback 或 provider route。
- 200 保存 response；404 依 error code 顯示不存在／尚未產生；401／403 導向登入或安全拒絕；network／5xx 顯示 bounded service error。
- 一般 page load 不啟動 scraper、Agent、CEO LLM 或 Private Mart 重算。
- generic Chat／Agent client 不屬 Janus User App；Janus MCP／OAuth adapter 留在 API boundary。

### 8.0 Public endpoints

主要 public endpoints 依實作／runtime 為準，現行 UI contract 包含：

- `/api/v1/public/health`
- `/api/v1/public/market-home`
- `/api/v1/public/daily-brief?date=YYYY-MM-DD`
- `/api/v1/public/sectors/rotation?date=YYYY-MM-DD`
- `/api/v1/public/topics?date=YYYY-MM-DD`
- `/api/v1/public/candidates?date=YYYY-MM-DD`
- `/api/v1/public/stock-header/{symbol}`
- `/api/v1/public/stocks/{symbol}/health`
- `/api/v1/public/stocks/{symbol}/reports`
- `/api/v1/public/stocks/{symbol}/kline?period=D|W|M`
- `/api/v1/public/stocks/{symbol}/events?cursor=...`

`market-home` 的 deterministic benchmark／market activity／institutional sections 各自保留 as-of、freshness、coverage、provenance、status；Mart research 不可成為 baseline availability prerequisite。

公開 endpoint 不回 blocked private artifact、raw object URI、secret、credential locator 或 owner identifier。

### 8.1 Private endpoints

主要 owner-scoped endpoints：

- `GET／POST /api/v1/me/journal/trades`
- `POST /api/v1/me/journal/trades/{event_id}/corrections`
- `GET /api/v1/me/journal/positions`
- `GET /api/v1/me/journal/pnl?year=YYYY`
- `GET /api/v1/me/journal/monthly-summary?year=YYYY`
- `GET /api/v1/me/journal/symbol-summary?year=YYYY`
- `GET /api/v1/me/portfolio/quotes`
- `POST /api/v1/me/portfolio/quotes/refresh`
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

身分只由 User OAuth audience 的驗證 token 決定；`user_id`／owner 不接受 query／body 指定。email 只供顯示，不作 ownership key。

交易／更正成功不代表 Private Mart 已完成 valuation；UI 應分開呈現 operational projection 與 canonical valuation／PnL。

### 8.2 Stock Detail specialist／CEO API semantics

五 specialist 的 User read path 只讀 persisted／validated outputs，不提供「每日五 LLM roles」的同步執行 endpoint。

Planned／additive CEO command contract 在實作前必須至少具備：

- authenticated user；
- DB-backed capability，例如 `ceo_analysis.request`；
- symbol／profile validation；
- in-flight duplicate guard；
- quota／cooldown；
- provider/profile approval；
- command／execution ID；
- status／safe failure reason；
- immutable report history。

`分析`／`重新分析` 只建立新 execution/report；不得原地覆寫舊 report，也不得因 request accepted 顯示成 analysis succeeded。

Specialist upstream change 只標記 CEO report freshness／material delta，不自動觸發 CEO。

### 8.3 Admin workspace API semantics

Admin workspace 依 `admin.md`，不再定義舊五角色/CIO control surface。

至少需要 bounded read／action contract 支援：

- actionable overview；
- effective batch／occurrence list；
- execution detail、retryability、retry lineage；
- dataset/source health；
- market universe；
- Stage／Core／Mart／Private operational governance summary；
- retention／maintenance／storage telemetry；
- specialist model／evaluation status；
- CEO provider/profile/capability/quota/cooldown/usage audit（對應 WBS 完成後）。

manual rerun／retry 必須走 backend allowlist、authorization、idempotency／duplicate guard、dependency／exclusive guard 與 audit。Flutter 不接受任意 Cloud Run job name、checkpoint 或 storage path。

### 8.4 Analysis Profile

Analysis Profile 的現行產品語意：

- specialist champion／model／version／evaluation；
- CEO provider／model／profile／route；
- immutable profile version／history；
- compare／rollback／audit；
- bounded test symbols／evaluation evidence。

`Codex CLI → OpenRouter → Gemini` 只適用 On-demand CEO／approved escalation。五 specialist production 主路徑不使用 per-role LLM provider route。

Profile 修改建立新 version，不覆寫舊 execution／artifact 的 effective config。rollback 也建立新的 audit lineage。

### 8.5 Transaction-record presentation contract

Flutter 可依既有 history 做 year／month／symbol grouping；canonical accounting semantics 仍在 backend／Private Mart。

- 年度已實現損益使用 `/journal/pnl?year=YYYY`；月份與個股已實現損益分別使用 typed `monthly-summary`／`symbol-summary`。
- 月份／個股群組預設收合，群組 summary **只呈現已實現損益**；買進支出、賣出回收、股利、交易筆數不再是群組標題必備資訊。
- 展開後才顯示單筆交易；append-only correction action 必須仍可到達。
- Flutter 不得自行把 history cash flow 加總成 authoritative realized PnL；typed aggregate unavailable 時顯示 pending／unavailable。

## 9. Auth／owner boundary

- User OAuth 與 Admin auth audience 分離。
- User token 不得存取 `/api/v1/admin/*`。
- Admin session 不因管理權限自動取得一般 user trade／position 內容。
- Flutter hidden control 不是 security boundary。
- private delete request 只允許 owner 查 status；`CLEANUP_PENDING` 不顯示 completed。

## 10. MCP boundary

Janus MCP 是 authenticated read-only boundary；不接受 arbitrary SQL、table、URI、owner selector 或 mutation。owner 由 server 驗證 principal 綁定。

三個 logical tools：

- `janus_sources`
- `janus_market_context`
- `janus_private_context`

output bounded、sanitized，保留 as-of／provenance／status；不回 secret、raw payload、GCS locator、internal owner identifier。

## 11. ResearchContext state／API planning

ResearchContext 沿用本文件既有狀態，不建立第二套 state machine。未來 response 必須 typed、bounded、owner-scoped、同一 `analysis_as_of`，保留 freshness／provenance／PIT 與 explicit missing／stale／partial。

ResearchContext 目前是 planned／proposed；在 active TODO 啟動前不得把概念 endpoint 當成已實作。ChatGPT MCP 可共用同一 server boundary，但不提供 mutation 或 arbitrary database access。