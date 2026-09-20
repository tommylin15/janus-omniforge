# Janus WBS 4J — 個人記帳、筆記與關注股

## WBS 4J — 個人記帳、筆記與關注股 MVP（P0）

### 執行環境

本 WBS 的 `dev` 就是目前個人真實使用的 Janus 工作台。交易、筆記、關注股、Private Core／Mart、Google OAuth、Cloud Scheduler 與 Flutter 驗收都優先使用真實 dev 路徑；sample user、mock portfolio 或 local-only 流程只能補 edge case，不能取代主要 acceptance。未建立 staging／production 不得被當成私人工作台不可真實使用的理由。

### 4J.1 Ledger／API

- Dev User 使用 Google OIDC／Google Sign-In 與獨立 User OAuth client／audience；API 驗證 issuer、audience、expiry，以 Google `sub` 對應內部 UUID `user_id`，email 只供顯示。Dev 可使用 User allowlist，不建立自有密碼系統。
- 建立最小 `services/api` FastAPI app，只含 health、上述 User auth boundary 與 `/api/v1/me/journal/*`、`/api/v1/me/notes/*`、`/api/v1/me/watchlist/*`；User token 不得存取 `/api/v1/admin/*`，既有 WSGI Admin 在 WBS 6 回歸完成前保留。
- PostgreSQL 以獨立 schema／role 保存 append-only `BUY`／`SELL`／`CASH_DIV`／`STOCK_DIV` event、reversal／replacement、idempotency key、optimistic version 與單調遞增 `ledger_version`；date、symbol、shares、price、fee、tax、currency 依交易類型驗證並使用固定精度 decimal，不建立 outbox。
- `/api/v1/me/journal/*` 提供新增、更正、歷史、positions 與年度 PnL；`/api/v1/me/notes/*` 提供單一 revision model，可獨立存在或連結 symbol／trade event；`/api/v1/me/watchlist/*` 提供關注、取消、排序、目標價與目前名單。身分只取自 authenticated user，不接受 client 指定 `user_id`。

### 4J.2 Private Core／Mart

- private pipeline 依 persisted checkpoint 批次讀取 ledger／note／watchlist version，將新事件冪等地直接正規化至 Private Iceberg Core；失敗從最後成功 checkpoint 重跑，不建立 Private Stage／DataSrc。
- normal execution 未指定 `VALUATION_DATE` 時，只使用執行當下可見且不晚於 Asia/Taipei 當日的最新 persisted Core OHLCV trading date；週末、休市或當日 ingestion 尚未完成時沿用最近可用日期。explicit `VALUATION_DATE=YYYY-MM-DD` 保留 deterministic historical replay。
- dev 以四個 weekday Cloud Scheduler（07:40／11:00／14:00／21:30，`Asia/Taipei`）觸發同一 `janus-private-pipeline` Cloud Run Job；這些是目前真實個人資料更新排程，不是 staging 模擬排程。空 change queue 不解析 valuation、不重寫 Mart、不推進 checkpoint。
- 產製 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；使用第一階段股票 master／行情 Core，MVP 成本法固定移動平均，估值缺價不得當成 0。
- 筆記正文與 revision、關注歷史儘可能保存在 Private Iceberg；PostgreSQL 只保留交易 OLTP facts、目前關注狀態、必要索引、版本、checkpoint 與 artifact reference。
- Private Core／Mart 只由 `/api/v1/me/*` 依 authenticated user 讀取，不進 public publication index、話題或排行榜；公開 `mart_scoped_analysis` 完成後再加入 symbol-scope 個人化 overlay。

### 4J.3 最小 Flutter

- P0 啟用「關注／筆記／我的」；「筆記」內含「記帳／筆記」分頁，提供交易、歷史、更正、持股、損益與可連結股票／交易的一般筆記。
- 「今日／公開探索」顯示 coming soon／disabled；關注股詳情可先顯示已持久化行情與私人內容，不得因 page load 觸發 scraper、Agent 或 LLM。
- 不串券商、不自動匯入、不自動下單；FIFO 等第二成本法等會計／稅務語意與回歸測試完成後再評估。

### 4J.4 驗收條件

- PostgreSQL 只保存交易事實、目前關注狀態、必要索引、冪等鍵與 pipeline checkpoint，不保存筆記正文或 Private Mart payload。
- 使用者 A 無法讀寫或推測使用者 B 的 ledger／notes／watchlist／Private Core／Mart；交易更正、筆記 revision、關注異動、跨年損益、超賣拒絕、缺價、重跑與刪除路徑可重現。
- User／Admin OAuth audience 混用、偽造或 client 指定 `user_id` 均被拒絕；email 變更不改變資料所有權。
- Flutter 不重算正式損益；所有結果可追至 ledger version、Private Iceberg snapshot 與 valuation date。
- 「可使用」的完成證據優先來自真實 dev Google OAuth → API → PostgreSQL／Private Iceberg → pipeline → Flutter 的閉環；local fixture 通過只能證明局部契約，不能單獨宣稱整體已完成。

### 4J.5 `WBS-4J-PRIVATE-RESEARCH-STATE-CONTRACT`（Pilot Evolution／Planned）

- 先定義 owner-scoped `research_thesis`、`candidate_state`、`strategy_state`、`decision_record` 與 `investment_policy` semantic contract；欄位與 effective-time／revision semantics 以 [Intelligence and governance](../spec/intelligence-and-governance.md) 為準。
- 優先重用既有 note revisions、artifact／index、Private Core／Mart 與 owner isolation。Trade ledger 與 research thesis 保持不同資料模型；歷史 thesis／strategy 不就地覆寫。
- 現有 investment profile 已有 risk tolerance、horizon、goal、minimum cash；concentration boundaries 與 mandate 為 **Schema Extension Candidate**。本切片不決定 PostgreSQL table／migration。
- 後續 Private Context exposure 必須 typed、bounded、owner-scoped、PIT／provenance-aware，並顯式回傳 stale／missing／partial。
