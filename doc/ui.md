# Janus — UI Specification

版本：1.9
狀態：索引；頁面與元件契約依下列切片為準

## 目前 UI 環境定位

目前 GCP `dev` UI 是個人使用階段的真實操作介面，不是 demo／mock UI。Janus User／Admin 畫面呈現已持久化的投資與營運資料、真實登入狀態及 Job／Scheduler 結果；資料缺失、服務不可用、partial／stale 時要明確顯示狀態，不以 sample／placeholder 假裝成功。Janus source 與 canonical dev deployment 均不含 generic Chat／Agent UI。

測試 fixture、假 secret、故障注入或 localhost 頁面只供自動化／異常驗收，不應出現在正常使用者操作流或被列成正式資料來源。未來若建立獨立 Production UI，是多人化／HA／正式對外營運議題，不是目前 dev UI 能否真實使用的前置條件。

## 產品完整度原則

- UI shell／layout／read-path acceptance 與「資料已足以形成可用產品」是不同完成條件。只證明頁面可載入、能顯示 missing／stale，不得延伸宣稱 market coverage、portfolio valuation 或整體功能完成。
- User「今日」必須先能呈現 deterministic published market baseline；Mart／AI Daily Brief 是 enhancement。Mart unavailable 時只降級相關研究區塊，不應讓已存在的 Core 市場資料整頁不可見。
- 個人持股主要畫面應使用 canonical 股票名稱＋代號，正式 aggregate market value／cost basis／unrealized PnL／return 只讀 Private Mart。缺價／stale 時必須指出受影響範圍並 withholding 不可靠 aggregate，不由 Flutter 補算。
- Admin target workspace 仍須完成 Flutter shell、overview／batch 與 stock data workbench 才能宣稱不依賴 GCP／DB 的主要營運閉環；legacy static Admin 在 parity 與 rollback gate 前保留。

## AI 最小讀取規則

所有 UI 工作先讀 foundations，再只讀目標頁面、元件或 API 狀態切片。Admin 工作不需讀 User App 頁面；純後端工作不需讀 UI；release 驗收才讀 A11y 與 checklist。

## UI 路由

| 任務 | 必讀切片 | 條件增讀 |
|---|---|---|
| 所有 UI、視覺、responsive、Navigation／Shell | [UI Foundations](ui/foundations.md) | 再讀一個目標功能切片 |
| 今日、關注、個股、記帳／筆記、資產、我的、Research Context | [User App 頁面](ui/user-app.md) | 實作元件時讀 Components；串 API 時讀 States/API |
| Flutter／Web 共用呈現元件 | [元件契約](ui/components.md) | 只增讀元件所在頁面 |
| loading／error 等狀態與 FastAPI endpoints | [狀態語意與 API 契約](ui/states-and-api.md) | 不需預讀 Admin |
| Admin tabs、tables、governance、reports | [Admin UI](ui/admin.md) | 只在全域 layout 時讀 Foundations |
| Dialog、鍵盤、讀屏、實機與 release checklist | [A11y 與 Release](ui/accessibility-and-release.md) | release 前依入口增讀 User 或 Admin |

執行優先序見 [TODO](todo.md)，領域規格見 [SPEC](spec.md)，WBS 驗收見 [WBS](wbs.md)。
