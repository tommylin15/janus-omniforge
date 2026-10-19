# 2026-10-17｜Admin v2 四頁架構與工程順序（核准設計）

狀態：**核准設計；2026-10-19 A1～A5（含 A4-U）已依原 TODO 指定測試／驗收範圍列 PASS**，當前 runtime 仍以實際 SHA/CI/部署 readback 為準。下列工程順序留作**歷史設計**，不是 active 重作指令；證據見 [原 TODO](archive/todo-before-consolidation-2026-10-19.md)、[Operations](spec/operations-and-testing.md)。本文件是 [TODO](todo.md) 中 `ADMIN-V2` 工作的設計依據，不是額外工作包或另一份執行 queue。

## 1. 決策與優先序

- 主選單改為 **`總覽`、`批次`、`資料品質`、`系統設定`** 四頁；沿用 `apps/user_app` Flutter／PWA、FastAPI Admin 授權與既有 Material 3 shell，不重建 Admin 專案。
- 取代 [2026-10-03 六頁導覽決策](archive/decision-2026-10-03-admin-ui-scope-and-governance.md) 在「主導覽、功能位置」的規範；歷史安全決策、private 隔離、versioned config／retry／audit 與已接受能力繼續有效。
- **原 2026-10-17 僅文件範圍已由 2026-10-18 工程啟動授權取代**。ADMIN-V2 主要工程放在 D01～D06、DRL-01 的適用核心資料／Controller／serving 契約穩定後，D07／D08 的 UI 整合之前。**不要求 D06 全部 I/O 優化或歷史 TTM、五年河流完工**才開始；缺 evidence 的項目明示 unknown／not certified。
- D01～D06 **不新增 scope、工項、驗收 gate、排程或擴大原任務**；不得因 ADMIN-V2 新增工作倒灌既有產品／資料／部署工作包。既有 User 實機 PASS 不重開。
- DRL-01、D07、D08 保留本身原定工作包；Admin v2 僅共用其正式資料契約／成果物和對應 UI 容器，避免平行功能與第二套 canonical data。

## 2. 產品資訊架構（四主頁）

| 主頁 | 首屏內容 | 次層詳細頁／原功能歸位 | 不做什麼 |
|---|---|---|---|
| **總覽** | 異常優先：逾期／失敗批次、資料 freshness、Private Mart 最新合格估值日、DQ／retention 異常、待處理數 | 批次 occurrence、DRL 缺口、AI／資料健康的 deep link | 不把正常 execution 洗版，不假造 deployed status 或 KPI |
| **批次** | Effective 排程、last success、last actual terminal、duration、blocked／unknown／partial | 原逐項執行、歷史 execution、安全 retry、Private recalculation、備份與 Iceberg 維護工作 | 不維護第二份 Scheduler／Job table，不任意重派未知工作，不在前台直接操作 Cloud Run |
| **資料品質** | TWSE／TPEx coverage、來源新鮮度、OHLCV／營收／EPS、重要標的資料可用性、D06 storage anomalies | 原「個股」Stock Workbench 的資料健康／approved gap repair；原「市場資訊」全市場母體／進出／來源；原「資料治理」Stage／Core／Mart／retention／Iceberg storage | 不複製 User 股價圖、交易、KD、估值；不以人工 Master 寫入取代官方 universe |
| **系統設定** | 低頻操作的分組入口：AI／Gateway、權限與稽核、Worker、Retention／storage 配置 | 原「AI 分析」的 Specialist profile/evaluation 與 D08 CEO profile/capability/usage/history，versioned route，原 governance 設定 | 不把設定狀態當有效 runtime，不展示 Owner 私人交易正文 |

**原六頁不等於砍功能：**「個股」「市場資訊」整併到「資料品質」的 detail／search；「AI 分析」整併到「系統設定 → AI 模型與 Gateway」，以子頁／tab 保留可深連結的操作面與歷史；原「資料治理」的監控進「資料品質」、低頻配置進「系統設定」、Private 執行控制進「批次」。原能力先復用，退役 API／路由前必須查 caller、權限、稽核及回退。

### 響應式與互動

- 行動端（390px）四入口可用 drawer／單選底部導覽；桌面 NavigationRail／側欄；詳細頁採 drill-down，避免所有欄位一次曝光。
- 總覽以 2×2 少量狀態卡 + 待處理異常清單為主；清單有「最後更新、原因、影響範圍、前往詳細」；僅 backend 認定安全時呈現操作。
- 批次以「排程／最近三天歷史／異常」三檢視；詳細頁才顯示 execution ID、request/attempt、source、終態、lineage；允許 bounded 過往查詢。
- 資料品質以「市場涵蓋／重要標的／官方來源／儲存維護」四區；股票級查看合法期間、missing reason、provenance 和獲准修復。
- 系統設定按「AI 模型／Gateway／執行參數／權限稽核」組織；現存 storage/retention 設定依權限提供，不能在 UI 暗示已生效。

## 3. D01～D06／DRL-01 的影響只列入 ADMIN-V2 主要工程

| 既有成果／工作 | ADMIN-V2 的承接位置 | 僅做的 Admin 工作 |
|---|---|---|
| D01 持股／估值 | 總覽、批次 | Private Mart 合格估值日、延遲／重算狀態；只讀去識別化 metadata，Owner 交易留 User |
| D02 快照／首頁 | 總覽、資料品質 | persisted snapshot 新鮮度、API 讀回／資料可用狀態；不重做快照管線 |
| D03 四頁／圖表 | 資料品質 | 股票與市場資料缺口、特徵 readiness；不新建 Admin 分析圖表 |
| D04 Controller／備份 | 批次、系統設定 | effective schedule／occurrence／workload terminal／safe retry、備份執行／還原證據、Worker 設定；不新設 scheduler |
| D05 Release／Jobs | 總覽詳細資訊 | 最新已驗證 SHA／digest／revision、API／Jobs readback（拿不到即 unknown）；不在 Admin 建新發布控制 |
| D06 Iceberg／I/O | 資料品質、批次 | objects／active bytes／maintenance receipt、compaction／cleanup／protected refs、可比負載 I/O 證據；僅呈現已可靠量測值 |
| DRL-01 資料可用性 | 資料品質、總覽 | 同一份 readiness／source evidence；市場 TWSE 90%／TPEx 70%、持股／關注 120 日、營收 13 月、EPS **2026Q1/Q2 合格 vs. 歷史 TTM 未認證**分開標記；不新增資料來源與總帳 |

表中只定義 **ADMIN-V2 自己要接線／呈現／驗證的工作**；**不得反向加入 D01～D06 的 acceptance 或指派額外後端交付。** 若某指標沒有合格 published API／telemetry，只在 Admin 顯示 `unknown`／`not_verified`，並於 ADMIN-V2 記錄受阻，不替代來源工程。

## 4. ADMIN-V2 主要重構內部順序（不另開平行工作包）

1. **A0 規格整併（本輪）**：更新 TODO／WBS-6／Admin UI／D07／D08 的同一套導航契約；只文檔，沒有 runtime PASS。
2. **A1 Shell／權限與低風險 UI 收斂**：六頁改四頁，保留深連結、User/Admin token boundary、既有 accepted functions；檢查 390px／desktop／accessibility；排除前台持股／分析複製品。
3. **A2 總覽與批次整合（D01、D02、D04、D05）**：整合 Controller/occurrence 實際 terminal、Private queue、snapshot freshness、必要的 deployed metadata；補許可／重入／unknown fence／audit，不造第二排程。
4. **A3 資料品質整併（DRL-01、D03、D02）**：市場與重要股票 readiness、官方來源、合法期別、資料缺漏／修復流程；檢查 TPEx 與 TWSE 既有 Admin master 管理契約，不盲目擴人工寫權。
5. **A4 Iceberg／備份／設定整合（D06、D04）**：儲存、retention、compaction／cleanup receipts、protected refs、備份狀態及 Worker 參數；對照真正的 controller/runtime，無 evidence 就 unknown。
6. **A4-U 全站與單一使用者追蹤**：在現有「總覽 → 使用分析」整合 Flutter 事件埋點、後端批次／每日每使用者聚合、個人視角、有限事件時間線及安全與非阻塞驗收；不直接寫 Iceberg、不動 D01～D06。
7. **A5 測試、受控 dev 發布與驗收**：Flutter/Admin API targeted + CI、有效權限／Owner 隔離、retry 安全、同 SHA GHCR/Cloud Run 受控發布與 rollback、實機 Admin 正向讀回；保留 accepted User 路徑。A1～A5 未有 evidence 不能標 PASS。

**D07 隨後接入**「系統設定 → AI 模型 → Specialist 品質／版本／OOS」及適當資料缺口 detail，沿用 VF-09 真實 artifacts／typed API，不另建第五主頁或第二套管理端；**D08 隨後接入**同一 AI／Gateway 子頁的 CEO profiles、capability、usage、immutable history，正式 Owner 報告仍由 User 查看。兩者沒有因 UI 重排而取得新模型、付款或發布授權。

## 4.1 ADMIN-V2 行為分析｜全站統計與單一使用者追蹤（A4-U）

**需求：**管理者必須能從「總覽 → 使用分析」先看全站趨勢、再選擇經授權可見的單一使用者，了解其每日開啟哪些功能、操作次數、活躍停留時間、最後活動日及有限時間線。**這是本 ADMIN-V2 內的新增子切片，非 D01～D08 或 DRL-01 的新增工作。** UI 不增第五個主選單。

### 操作介面

- 全站頁：DAU、總操作次數、總有效活躍秒數、功能排名，按日／週／月與最近 7／30／90 天篩選；顯示成功／失敗或上報不完整比例，避免將事件遺失視為零。
- 使用者清單：僅授權 Admin 可用，支援按後端使用者目錄查詢或選取單一 `user_id`，顯示識別所必需的名稱／Email、最近活動、近 7 日操作次數／活躍時間；未必要公開全部 Email，不提供 User App 或 MCP 的他人活動清單。
- 個人詳情：單日／日曆區間依 `feature_id` 分組呈現 `page_view`、`action`、成功／失敗、`active_duration_ms`，最近 7 天可下鑽到粗粒度時間線（時間、功能、事件類別、結果）。不顯示筆記、交易明細、股票代號、輸入值、搜尋文字、URL query 或自由輸入 payload；操作次數不把自動 polling、rebuild、scroll/repaint 當作手動使用。
- 若樣本／權限／收集證據不足，顯示 `unknown`／`partial`／`no_data`，不能顯示虛構 0 或完整度 100%。

### 輕量事件契約

建議 `usage-event.v1` 僅包含 allowlist 的 `feature_id`、`event_type`（`page_view`／`feature_action`／`action_result`／`active_interval`）、`action_key`、`outcome`、`client_time`、`active_duration_ms`、opaque `session_id`、`event_id`、`schema_version`。**`user_id` 只從後端已驗證 Google User token 綁定**，前端 user ID、Email、owner/subject 一律不作身分依據；禁止持久化 bearer token、Cookie、自由文字、金融金額與 user-to-symbol 關係。

- Flutter 共用 `UsageTracker` 覆蓋 User 的「今日／關注／記帳／筆記／我的／個股詳情／重要操作」，及 Admin 對應主頁；Page enter/leave 不依賴 `dispose`（現有 IndexedStack 保留未顯示頁）。用 route/page 選擇、Flutter lifecycle、Web visibility／focus 判斷前景；閒置 60 秒後不再計時，恢復互動才重新累計。連續 interval 要限制上限並分段，顯示「估計活躍時間」而非確切閱讀時間。
- 在記憶體短期累積，每 60 秒或 20 筆（先到者）以 **fire-and-forget** 傳送 `POST /api/v1/me/usage/batches`，不得阻擋導航／記帳／交易／重算；背景切換／離頁僅盡力傳送。可設定隊列上限、短 timeout、有限重試／丟棄，不能無上限持久化私人事件或無限補送。
- Server 每批驗證 schema、feature allowlist、最大筆數／bytes／秒數、過舊時間、期間跨日及 client/received time 偏差；transaction 一起記錄 `batch_id` 冪等去重收據與每日 user-feature 聚合，避免 retry 加倍。拒絕未知 action、任意 payload 欄位及偽造其他 owner ID；事件 endpoint 不在業務同步 API 鏈內執行。
- 建議資料層：**PostgreSQL** `usage_ingest_receipts`（極短期防重）、`usage_user_feature_daily`（`user_id` + 台北日 + `feature_id`）、最近有限 `usage_recent_events`（可選）和 `usage_monthly_summary`。Daily 保存 count/success/fail/active_seconds/page entry/session count/last_event_at／完整度；不是 canonical investment data，也不可拿一般 User/App 業務行為推測交易內容。索引要界定 user/date/feature，避免逐事件大量寫入。
- 先採保守資料保留：原始安全事件 **7 天**、收據 **7 天**、單一使用者每日彙總 **180 天**、必要每月去敏彙總 **12 個月**（上線以實測容量再調整）；提供 retention purge、刪除請求與告知/權限政策，不能把使用者追蹤視為可永久保留的行政 audit log。
- **MVP 不新增 GCS/Iceberg 寫入**：現有 e2-micro PostgreSQL 僅做小量批次統計，測資源後才判定是否另採月結 GCS/Parquet 歸檔。Iceberg 是未來可選的長期分析封存，不能逐 event commit；若採月分區，不強制每月一個實體檔，也不新增 Scheduler/Job 作 ADMIN-V2 的前置。

### Admin API／安全邊界

- `GET /api/v1/admin/usage/overview`：已彙總全站統計；`GET /api/v1/admin/usage/users`：授權名單與查詢；`GET /api/v1/admin/usage/users/{user_id}`：單一使用者日／功能彙總；`GET /api/v1/admin/usage/users/{user_id}/recent`：可選最近七日的 allowlisted 粗粒度操作時間線。皆沿用 Admin audience、backend server-side 授權、bounded date/rate/page limit；存取個人追蹤資料另留 admin read audit，不暴露資料表／owner 綁定於公開端點。
- 對使用者明示正在收集的事件類別、用途、保存期限、可見角色與刪除／退出或停用規則；部署前確認適用資料保護規範與使用者通知。允許對個別使用者停用後續非必要分析收集；停用不影響產品功能。Admin 不得因角色能看 Private Pipeline aggregate，就自動取得各人交易／個股內容。
- 覆蓋正反權限測試（User 不可查他人，admin token/user token audience 隔離），以及重新登入、換帳號、重送、離線、背景／閒置、跨午夜與被拒 event。A5 必驗開／關 UsageTracker 的頁面切換 p95、API p95、CPU／DB I/O／儲存增量；業務操作延遲不得因 telemetry 上報而提高至不可接受，失敗不得影響業務提交。


## 5. 權威來源、安全及驗收

- 後端以 `/api/v1/admin/*` 每次執行 Admin authorization；UI 隱藏不構成授權。所有 Private 工作只顯示必要去識別化狀態，不能推回 owner-to-symbol 或交易正文。
- Effective scheduling 由 Batch Controller／PostgreSQL control／Scheduler live evidence 判定；`enqueued`≠`dispatched`≠`succeeded`；unknown／partial／blocked／skipped 與成功不同。
- 資料只讀既有 Core／Mart／DRL／publication 與持久化 evidence；不在 Flutter 重新計算 canonical number、不人工臆造財報期別或 PIT、不重新建立資料庫／排程器。
- 特別核對 `AdminService.batches()` 曾對所有 job 回傳 `deployment_status: unknown`、Admin stock upsert 曾只接受 TWSE、已退役 market-universe swap 及 legacy static routes；以 **新施工時的 main/現場** 核對，決定接線／退役，不在本次文件階段聲稱已修正。
- 有安全 rollback／受控發布才實際變更；完成須 GitHub implementation、targeted tests／CI、API/Jobs live evidence、Admin auth、手機/桌面與實際 runtime readback，不能只憑文件、Build 或 UI screenshot。

## 6. 執行入口與文件職責

- **唯一 queue／順序／狀態：**[TODO](todo.md) 的 `ADMIN-V2`。
- **UI 結構／操作／狀態語意：**[Admin UI](ui/admin.md)。
- **工程與驗收邊界：**[WBS-6](wbs/wbs-6-api-and-apps.md)。
- **五角色／CEO 既有工作包：**[D07](execution-cards/d07-specialist-b9-oos.md)、[D08](execution-cards/d08-ceo-admin-owner-report.md)。
- D01～D06 原卡片維持原樣，不因本設計修改其 status／gate／承諾；待實作時只在 ADMIN-V2 的 acceptance 記錄 Admin 整合證據。
