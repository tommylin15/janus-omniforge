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

## 2026-10-07 結案後補強與人工驗收

10/06 結案後，使用者追加並完成以下 User App 補強：

- 交易新增／更正後 immediate owner-scoped Private Mart 損益重算；scheduled pipeline 保留 fallback。
- annual PnL 加上 latest-ledger-version stale fence，避免交易已更新時短暫回傳舊年度損益。
- 只有損益確實 pending／stale 時顯示「重新計算損益」；正常、確認為 0 或單純 unavailable 不顯示。
- 關注股票第一層主要動作為「搜尋」，選定股票後才使用「儲存」。
- 持股 latest-price：盤中可見頁面每分鐘 revalidate；13:30 後停止分鐘輪詢，14:30 handoff 後同一頁面生命週期只自動讀一次 persistent latest state；明確手動 refresh 例外。
- User 頁面損益與報酬統一台股語意：正值紅、負值綠、0／未知中性；負值使用減號，不使用會計括號。

工程證據：

- 功能主體：`bbc4151fed2799dabc348f8145cd3f9b28a97d81`。
- Flutter test 契約修正：`14cd38ccc73edf5b7ebfbf5774b3ce6992d89025`、`56ac94dbd0c8d1fc70885e5f0ab0fbfe5cfaca8d`。
- stale fence：`afa3e8214bb19fc7dc67ebae482edbf464cb9305`。
- Flutter User App run `37542658237`：**SUCCESS，66 tests passed**，analyze／PWA metadata／production web build PASS。
- Portfolio Completeness Contract run `37542950801`：**SUCCESS**。
- Deploy dev run `37542951194`：**SUCCESS**；API targeted suite **185 passed**。
- API revision `janus-api-gafa3e8214bb1-config`：Ready、default traffic **100%**；image digest `sha256:1d19df5ab7480bcedb6e897584f7ab59e792241e7c1d2e7ba9337fbb6b641aa1`。
- Private Pipeline Cloud Build `ef6abbfc-c06d-444e-91bf-136401d2b4b1`：SUCCESS；既有 Job readback `Ready=True`。該 run 中條件式 live acceptance／mobile queue writer seed 為 skipped，保留原始事實，不冒充執行成功。

2026-10-07 使用者明確回報人工驗收完成並要求回寫文件後結案。此確認補足先前唯一剩餘的手機 UI human gate；因此本次結案後補強狀態為 **CLOSED / PASS**。

## Drive 邊界

Drive 的「Janus 交易記錄 UX 參考評估（已吸收／研究來源）— 2026-09-24」保留為歷史研究來源，不改寫成 current implementation source of truth。Drive `JANUS_PROJECT_CONTROL.md` 明定 routine implementation status 應留在 repository，因此本輪 current state 統一回寫 GitHub active docs／archive。

