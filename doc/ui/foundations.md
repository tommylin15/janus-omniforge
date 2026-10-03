# Janus UI — 原則、視覺、Responsive 與 Shell

更新：2026-10-03

## 1. UI 原則

- UI 只呈現 backend／Core／Mart／Private Mart 已持久化且授權可見的資料；不在前端重算 canonical score、PnL、retention 或 fallback。
- blocked／invalid／insufficient 資料依 publication／auth contract 隱藏或明示狀態；null 不顯示 0。
- 明確區分 loading、error、empty、unavailable、partial、stale、fallback、blocked、unknown。
- confidence 明示為資料／分析信心度，不是獲利機率。
- 不輸出保證獲利、確定買賣指示或無 evidence 目標價。
- provenance 只對應目前所選 artifact／日期，不借用最新來源補舊結果。
- User 與 Admin 共用 Flutter codebase但 workspace、navigation、route guard、token audience、backend auth、CORS、audit 分離。
- 2026-10-02 起 legacy static Admin 已退役；Flutter／PWA 是唯一 active Admin frontend。
- User App 採「結論 → 原因 → 風險 → 來源」的減法層次；advanced data 放後面。
- generic Chat／Agent UI 由 omniAgent 持有；Janus User App 不新增 Chat／Ask Janus 主入口。

## 2. 視覺系統

- User App 使用 Flutter Material 3、`ColorScheme.fromSeed`、圓角 Card、清楚字階與充足留白；沒有明確需要時不引入第三方 UI kit。
- 支援 light／dark／system theme。
- Admin 以可讀、低複雜度營運介面為主；不為視覺效果增加不必要 dashboard／graph。
- 台股價格漲跌：上漲 red、下跌 green；治理／健康語意另以文字＋icon 輔助，不能只靠顏色。
- amber = warning／partial／fallback／attention；red = blocking／critical／failed。
- 系統字型優先，不依賴 Google Fonts。
- 一般文字 WCAG AA 4.5:1；大字 3:1；focus indicator 3:1。

外部設計參考只可吸收 presentation pattern，不取得 Janus data model／runtime authority；Active UI contract 仍以本目錄文件為準。

## 3. Responsive Layout

| 裝置 | Layout | Navigation | Detail／History |
|---|---|---|---|
| Mobile | 單欄，User App 優先 | Material 3 AppBar + NavigationBar | Bottom sheet／full-screen route |
| iPad | 兩欄可用 | NavigationRail 或 NavigationBar | Centered dialog／side pane |
| Desktop／Web | bounded grid，避免無必要 horizontal overflow | NavigationRail／Header | dialog／side pane |

- 支援 safe area、`viewport-fit=cover`、`100dvh`。
- 主要控制 target 至少 44×44 CSS px。
- Material 3 NavigationBar 主要項目高度至少 56px。
- 高密度表格只用於 Admin 明確需要的資料閱讀，不把 User App 變成 spreadsheet UI。

## 4. User App shell

- `AppBar` 只放目前頁標題、必要資料日期／操作；不放 Admin 入口。
- `NavigationBar`：今日、關注、記帳／筆記、我的。
- 未完成 capability 顯示 bounded unavailable／disabled，不以 sample／debug output 代替。
- 關注／個股頁只讀 persisted data；page load 不觸發 scraper、specialist recompute 或 CEO LLM。
- Stock Detail specialist／CEO 依 `user-app.md`：persisted-first、manual CEO only、permission-aware、immutable history。

## 5. Admin shell

唯一 active Admin frontend 是 Flutter／PWA `資料營運中心`。

主導覽目標：

- 總覽
- 批次
- 個股
- 市場資訊
- AI 分析
- 資料治理

原 `進階管理` placeholder 的目標名稱為 `資料治理`；程式尚未完成 rename 時視為 implementation gap，不改變 contract。

- Desktop 可用 `NavigationRail`；窄螢幕用 `NavigationDrawer`／等價單選 navigation。
- 右側一次只顯示目前功能面板，不把所有管理功能堆成單頁。
- 工程欄位、snapshot/hash/lineage/provider/model 等放 detail，不佔第一屏。
- 批次第一版使用簡單表格／清單，不要求 DAG。
- 資料治理第一版單頁呈現 retention／DQ／storage／maintenance anomaly，不要求 metadata catalog／lineage graph。
- Admin backend authorization 是 security boundary；Flutter hidden button 不算授權。
- 不導入第二套 scheduler／control plane／metadata platform 只為改善 UI。

## 6. Global status

- API unavailable 顯示安全、可理解文案，不呈現 upstream traceback。
- 需要時顯示資料日期、最後更新、source health、execution state。
- `unknown`／`未定義`／`尚未檢查` 不得顯示為 0 或正常。
- partial success 不呈現 full success。