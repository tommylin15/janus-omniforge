# Janus UI — 原則、視覺、Responsive 與 Shell

## 1. UI 原則

- UI 只呈現後端／Mart 已持久化資料，不在前端重算分數或補資料。
- blocked report 不渲染；null 不顯示 0。
- 明確區分 loading、error、empty、unavailable、partial、stale、fallback、blocked。
- confidence 固定標示為「資料／分析信心度，非獲利機率」。
- 不輸出保證獲利、確定買賣指示或無依據目標價。
- 所有來源只取當前資源／當前日期自己的 provenance。
- User 與 Admin 是同一 Flutter codebase 的不同 workspace；User App 不出現 Admin 導覽，
  route guard、token audience、backend authorization、CORS 與 audit 仍分離。現有
  static Admin 僅在 migration 期間保留，Flutter parity 與 acceptance 前不得刪除。
- User App 使用「結論 → 原因 → 風險 → 來源」的減法層次；首屏不顯示 K 線、密集數字表格或內部 Agent 術語。
- 個人記帳、筆記、關注股、AI 對話與公開市場分析的資料狀態分離；不顯示他人持倉、公開績效排名或下單按鈕。

## 2. 視覺系統

- User App 使用 Flutter Material 3、`ColorScheme.fromSeed`、圓角 Card、清楚字階與充足留白；不引入第三方 UI kit。
- 預設支援 light、dark 與 system theme。Admin 可繼續使用現有深色 zinc 系統，不為了視覺一致破壞密集營運表格的可讀性。
- 價格漲跌依台股慣例：上漲 red、下跌 green；健康／風險語意固定為高健康 green、警戒 amber、低健康／blocking red。顏色旁必須有文字或 icon，不只靠紅綠。
- amber：warning、partial、fallback、attention；不得表示安全。
- red：blocking、critical/high、disposition、停資停券。
- 系統字型優先，不依賴 Google Fonts。
- 一般文字 WCAG AA 4.5:1；大字 3:1；focus indicator 3:1。

設計參考只吸收可驗證的版面語彙，不複製其資料模型或功能：

- [Trace](https://github.com/trentpiercy/trace)：輕量市場探索、清楚的總覽 → 詳情層級與 theme 選擇。
- [artha](https://github.com/wahyuatmaja3/artha)：以新復古／Neo-Brutalism 的粗體重點與直接文案作少量品牌點綴；Janus 保留圓角、低噪訊與金融產品所需的可信感，不採整頁高飽和粗框。
- [Financial-Management-Dashboard-UI](https://github.com/Redvey/Financial-Management-Dashboard-UI) 與 [finance-web](https://github.com/feMoraes0/finance-web)：Flutter dashboard 的 card／grid 佈局參考；User App 只保留一個主指標與漸進揭露，不照搬桌面密集圖表。

## 3. Responsive Layout

| 裝置 | Layout | Navigation | History |
|---|---|---|---|
| Mobile | 單欄，User App 優先 | Material 3 AppBar + NavigationBar | Bottom sheet |
| iPad | 兩欄可用 | NavigationRail 或 NavigationBar | Centered dialog |
| Desktop／Web | 最寬 1200px 的有界 grid，無水平 overflow | NavigationRail／Header | Centered dialog |

- 支援 safe area、`viewport-fit=cover`、`100dvh`。
- 所有主要控制、日期、圖表 toggle、展開按鈕至少 44×44 CSS px。
- Material 3 NavigationBar 主要項目高度至少 56px。

## 4. 全域殼層

### User App shell

- Material 3 `AppBar` 只放當前頁標題、資料日期與必要操作；不放 Admin 入口。
- P0 `NavigationBar`：今日、關注、筆記、AI、我的；「筆記」內以 segmented control 切換記帳／一般筆記。熱門話題與板塊輪動後續收在「今日」，不再增加一排主導覽。
- 未完成項目顯示 coming soon／disabled，不可只 `debugPrint`。safe-area bottom 不遮擋內容。
- P0 啟用「關注／筆記／AI／我的」；「今日」保持 coming soon／disabled，直到公開 Mart API 完成。關注股詳情只讀已持久化行情、私人內容與聊天室，不因 page load 啟動模型。

### Admin shell

- Flutter Admin workspace 使用總覽、批次、個股、AI 分析、進階管理主導覽；主操作以
  中文呈現，工程欄位收在「進階／詳細資訊」。
- 不使用 User App 的底部導覽；依桌面營運工作流提供 responsive tabs／tables。
- Admin backend authorization 是唯一 security boundary；Flutter 隱藏按鈕不算授權。
- static HTML／JS Admin 是 transitional compatibility surface，只有 Flutter parity、
  Admin auth acceptance、browser/runtime acceptance 與 rollback plan 完成後才可 deprecate。

### Global status

- API unavailable 顯示可理解訊息，不呈現 upstream traceback。
- 可選擇顯示最新資料日、更新時間與來源健康摘要。
