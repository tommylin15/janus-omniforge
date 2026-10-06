# 2026-10-06 Latest-price／Ledger UI 收斂驗收紀錄

狀態：**CLOSED / PASS — implementation、CI、dev deployment、runtime build、交易人工 gate、手機 UI readback 全部驗收完成**

## 範圍

- Ledger 載入 fan-out 降低。
- Stock Detail 個人持股使用 latest-price valuation。
- Stock Header 顯示最近正式前收的漲跌金額／百分比。
- 台股慣例正值紅、負值綠。
- Ledger 持股每檔直接顯示未實現損益／百分比。
- 紀錄頁按月份／按個股可收合，群組摘要只保留已實現損益。
- 年度 selector 同區顯示年度已實現損益。

## GitHub implementation

- `b360b51c167f4bc0756688645a7694ced8e5dcf1` — `perf: lazy load ledger sections`：首屏核心 request + inactive section lazy load + 頁內 request cache。
- `1987590ece969e702c00c2f426e3f3a334c79929` — `feat: refine portfolio price and ledger records`：stock-header change fields、Stock Detail latest owner quote、紅綠 formatter、Ledger 持股 PnL、可收合紀錄與年度 PnL。
- `557a8c19e3a50baca8215b32ed8bed2c6212ef75`、`c311d4b7242afa9acd79bd9b95d44b1a7b6ebefc`：修正新收合／本地化 UI 的 regression assertions，未回退產品功能。

## CI evidence

- Flutter User App workflow `37473733955`：success。
- `flutter analyze --no-fatal-infos lib test`：PASS。
- `flutter test`：**64 tests passed**。
- web build／PWA assets validation：PASS。
- Portfolio Completeness Contract run `37473094103`：PASS。
- Deploy workflow API targeted tests：PASS。

重要 regression 覆蓋：Ledger months／symbols 預設收合與展開、append-only correction、annual realized PnL、Holdings latest-price／manual refresh、Stock Detail latest quote／change／unrealized PnL、inactive Ledger sections 不阻塞首屏。

## Dev deployment／runtime evidence

- 功能／測試 main：`c311d4b7242afa9acd79bd9b95d44b1a7b6ebefc`。
- Deploy dev workflow `37473734282`：**success**。
- Cloud Run revision：`janus-api-gc311d4b7242a-config`。
- traffic：**100%**。
- image digest：`sha256:1298af28d8ad98792925c53de10933e2f31af4dc7b1160c71fc318ee905552c1`。
- latest created／ready revision：皆為 `janus-api-gc311d4b7242a-config`。
- runtime verify：Flutter User／Admin workspace 與 web build-id 匹配 `c311d4b7242afa9acd79bd9b95d44b1a7b6ebefc`。

## 使用者人工驗收

2026-10-06 使用者明確確認以下兩項均「驗收無誤，結案」：

1. 交易佇列／真實 owner mutation／duplicate guard／transaction → Private Mart refresh。
2. `c311d4b` User App 最終手機畫面 readback，包括 Stock Detail latest-price 持股現價、最近收盤漲跌紅綠、Stock Detail／Ledger 未實現損益紅綠、紀錄月份／個股收合與年度已實現損益。

此項屬 human acceptance evidence；不改寫既有 CI／runtime evidence，也不把未重新量測的 p95 等數值補造。

**本輪 latest-price／Ledger UI 工作正式 CLOSED。**
## Drive 邊界

Drive 的「Janus 交易記錄 UX 參考評估（已吸收／研究來源）— 2026-09-24」保留為歷史研究來源，不改寫成 current implementation source of truth。Drive `JANUS_PROJECT_CONTROL.md` 明定 routine implementation status 應留在 repository，因此本輪 current state 統一回寫 GitHub active docs／archive。

