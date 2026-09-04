# Janus WBS 6 — API、Flutter 與 Admin

## WBS 6 — FastAPI、Flutter User 與 Admin

### 6.1 FastAPI

- 擴充 WBS 4J 建立的最小 `services/api` FastAPI app；將現有 WSGI handler 逐路由遷移並以 contract tests 保持既有 Admin 行為，完成後才移除 WSGI boundary。
- `/api/v1/public/*` 提供 health、daily brief、sector rotation、topics、candidates、stock health、history、Kline、events。
- `/api/v1/me/*` 提供交易、筆記、關注股、私人聊天室、positions 與年度 PnL；身分只取自驗證內容，不接受 client 指定 `user_id`。
- `/api/v1/admin/*` 保留控制面能力；public、private 與 admin router 分離 response model、auth、CORS、rate limit、IAM 與 audit。
- cursor／pagination、safe error、404 waiting state；不公開 raw payload、blocked、secret、traceback 或 private artifact reference。

### 6.2 Flutter User App

- 建立 `apps/user_app`，使用 Flutter Material 3 與平台原生元件；不先引入第三方 state／UI 套件。
- P0 主動線依 `../ui.md` 提供關注、記帳／筆記、AI 與我的；後續「今日」顯示市場狀態、每日摘要、板塊輪動、熱門話題與候選股，公開探索收在今日的次頁。
- 個股首屏依序顯示健康度圓環、籌碼狀態與 `Icons.psychology` 白話 AI Card；K 線、Metrics、五角色與 provenance 預設收在進階資料。
- 個人工作台提供關注股、手動交易、一般筆記、歷史明細、持股、已實現／未實現與年度損益，以及 WBS 4C 三 profile 私人聊天室；正式結果只讀 Private Mart，不在 Flutter 或模型內重算。
- 「我的」提供全部私人資料匯出與可稽核刪除流程；刪除涵蓋 PostgreSQL、Private Core／Mart、Codex local thread／auth state 與 cache。
- 支援 light／dark／system theme、phone／iPad／web responsive、VoiceOver／TalkBack 與至少 44×44 target。
- User App 不顯示 Admin 導覽、公開績效排行榜、下單或券商同步控制。

### 6.3 Admin UI

- WBS 3 已負責 Stage／Core Data Operations 的可操作閉環；本節延伸公開 Mart、governance 與 reports，不重建第二套資料營運入口。
- 保留「資料營運中心」名稱與入口；`/admin/stocks` 使用 tablist／單面板模式，右側一次只顯示目前功能，不同功能不得整頁同時堆疊。
- 分頁至少包含：股票管理、股票資料狀態、最近執行、資料源健康、深度追蹤名單、排程與保存設定、資料源設定、Mart 分析。
- 股票管理支援跨頁批次選取；股票資料狀態與 execution／DQ／quarantine 明細以類 Excel 的欄列表格呈現，支援 sticky header、排序、篩選、分頁與欄位顯示，不以 raw JSON 作主要介面。
- Collection／Analysis 分開觸發。
- WBS 3 第一階段只啟用 Collection；Analysis 與「Mart 分析」在 WBS 5 persisted consumer 完成前 hidden／disabled。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。
- 全市場／去識別化關注股深度 membership、effective date、cadence、來源授權狀態與 quota 管理；MVP 超過 50 個 active distinct symbols 必須拒絕，Admin 不得取得 user-to-symbol 對應。
- 「資料源設定」只管理已核准來源；候選來源維持 disabled／blocked 設定，不提供審查或啟用控制。
- 「Mart 分析」按 analysis date、scope、industry、symbol、角色、prompt version、analysis outcome 與 publication status 篩選 `mart_scoped_analysis`，只讀已持久化 artifact。
- Admin 使用獨立入口與認證；一般 Admin 營運頁不得瀏覽使用者交易內容。只有另行核准的隱私事件處理流程可接觸必要最小 metadata，且必須 audit。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- Flutter 不自行計算正式損益；User 與 Admin 入口、token audience、CORS 與導覽分離。
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `../ui.md`。
- tab 具鍵盤操作、ARIA 與可分享 query-string deep link；重載後保留所選分頁，未選面板不重複抓取大型 details。
- 詳細 User／Admin 驗收依 `../ui.md`；今日頁所有卡片必須使用同一 analysis-as-of，個人工作台通過交易更正、筆記 revision、關注異動、聊天室 engine lineage 與跨使用者隔離測試。
