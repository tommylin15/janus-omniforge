# 2026-10-17｜Admin v2 四頁架構與工程順序（核准設計）

狀態：**設計／文件已核准；主要重構程式、CI、dev runtime 未執行／未驗收**。本文件是 [TODO](todo.md) 中 `ADMIN-V2` 工作的設計依據，不是額外工作包或另一份執行 queue。

## 1. 決策與優先序

- 主選單改為 **`總覽`、`批次`、`資料品質`、`系統設定`** 四頁；沿用 `apps/user_app` Flutter／PWA、FastAPI Admin 授權與既有 Material 3 shell，不重建 Admin 專案。
- 取代 [2026-10-03 六頁導覽決策](decision-2026-10-03-admin-ui-scope-and-governance.md) 在「主導覽、功能位置」的規範；歷史安全決策、private 隔離、versioned config／retry／audit 與已接受能力繼續有效。
- **本輪只寫設計／任務順序**。ADMIN-V2 主要工程放在 D01～D06、DRL-01 的適用核心資料／Controller／serving 契約穩定後，D07／D08 的 UI 整合之前。**不要求 D06 全部 I/O 優化或歷史 TTM、五年河流完工**才開始；缺 evidence 的項目明示 unknown／not certified。
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
6. **A5 測試、受控 dev 發布與驗收**：Flutter/Admin API targeted + CI、有效權限／Owner 隔離、retry 安全、同 SHA GHCR/Cloud Run 受控發布與 rollback、實機 Admin 正向讀回；保留 accepted User 路徑。A1～A5 未有 evidence 不能標 PASS。

**D07 隨後接入**「系統設定 → AI 模型 → Specialist 品質／版本／OOS」及適當資料缺口 detail，沿用 VF-09 真實 artifacts／typed API，不另建第五主頁或第二套管理端；**D08 隨後接入**同一 AI／Gateway 子頁的 CEO profiles、capability、usage、immutable history，正式 Owner 報告仍由 User 查看。兩者沒有因 UI 重排而取得新模型、付款或發布授權。

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
