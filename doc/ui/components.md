# Janus UI — 元件契約

更新：2026-10-03

## 6. 元件契約

本文件只保存目前有效的共用 presentation contract。舊 `AnalystCard`／CIO／Gemini narrator 專屬語意不再是 active UI contract；研究元件改為 persisted specialist outputs + optional persisted On-demand CEO report。

## StockHealthCard

輸入只接受 backend／Mart 已發布且具狀態語意的欄位，例如：

- `stock_id`
- `stock_name`
- `mart_health_score`（如該分數已通過 active Mart／publication contract）
- `chips_status`
- `plain_language_analysis`
- `analysis_as_of`
- `data_status`
- `confidence`

規則：

- Widget 不計算健康度、方向、confidence 或 fallback。
- 健康度不是獲利機率；顯示時必須同時提供資料日期／status／risk context。
- `partial`／`stale` 顯示狀態；`blocked`／`insufficient_data` 不以 0 分或假方向替代。
- `plain_language_analysis` 只能來自已持久化的 deterministic template／validated report，不在 Flutter 補字或呼叫 LLM。

## StockHeader

- canonical symbol、name、market。
- persisted／approved quote 的 close、change、change percent；null 顯示資料暫缺。
- 顯示 market data `as_of`／trade date。
- research report `analysis_as_of` 與 market quote time 分開，不暗示 report 是即時分析。

## KLineChart

- 位於 Stock Detail Advanced section，預設收合。
- D／W／M period；MA 5／10／20／60／120／240 依資料可用性。
- OHLCV／指標 tooltip、loading／error／empty／request-race protection。
- 必須有可讀 table／summary 替代；hover／focus／touch／Escape 可操作。
- 不作為 canonical score／research direction 的計算器。

## MetricsGrid／DeterministicSignalSummary

- 只呈現 Mart 已計算的 typed values、formula／revision reference 與資料狀態。
- `null`／insufficient 不顯示 0 或方向暗示。
- UI 不重新計算 financial、technical、valuation、portfolio values。

## SpecialistCard

五種 specialist：

- Fundamental
- Valuation
- Quant
- Risk／Regime
- Event／Catalyst

共同欄位優先為：

- specialist type；
- analysis/data as-of；
- status／freshness；
- structured metrics／score／probability（只有 active specialist contract 定義時）；
- positive／negative drivers；
- SHAP／feature contribution 或 rule contribution；
- missing／stale／partial；
- evidence／provenance references；
- what changed since previous artifact（如可用）。

規則：

- specialist 日常 output 來自 Python／SQL／ML，不以 provider/model badge 暗示每日 LLM worker。
- advanced detail 才顯示 engine／model／feature version、input hash、snapshot、artifact identity。
- markdown 只允許安全 subset，不執行 HTML。
- historical artifact immutable；切換歷史時不得借用最新 evidence 補舊結果。

## CEOReportCard

只呈現 persisted On-demand CEO report，不在 page load 呼叫 provider。

至少可顯示：

- report status；
- analysis as-of／generated-at；
- thesis；
- cross-specialist conflicts；
- bull／base／bear（如 active schema 提供）；
- key risks／invalidation conditions／unknowns；
- specialist freshness／material delta；
- evidence／provenance summary。

若使用者具 backend capability，可在卡片或相關 action 區顯示 `分析`／`重新分析`；按下後只建立 command／execution，不把 enqueue 當成功報告。in-flight、quota／cooldown、provider/profile gate 由 backend 決定。

CEO report 不計算、補值或覆寫 canonical number，也沒有 publication authority。

## AnalysisHistory

- 依日期／execution／artifact version 切換 facts、specialist outputs、CEO reports 與 sources。
- 舊 artifact immutable。
- legacy field 若 null／unknown 就照實顯示，不借用最新資料。
- Mobile 可用 bottom sheet／full-screen route；desktop 可用 dialog／side panel。

## EvidenceAndSources

- 只使用目前所選 artifact 的 provenance／evidence。
- source name 可去重；fallback／source status 明示。
- 不顯示 raw object URI、credential locator、secret、unsafe query string 或完整 upstream traceback。
- inferred／hypothesis 不得用 confirmed 樣式。

## CompanyEventTimeline

- 依 `published_at DESC`。
- 相同類型且語意近似可只顯示最新版；有實質變更的更正公告保留。
- collapsed 顯示 title／published time；expanded 顯示 type、severity、effective／observed／fetched、safe body／summary、source。
- critical／high／medium／low／unknown 使用一致狀態語意；unknown 顯示待分類。
- cursor 載入更多；附件不存在不顯示 action。

## MarketActivityPanel

- Mobile 兩欄、desktop 可四欄。
- financing／securities lending／day trading／attention-disposition 等只呈現 backend 值。
- 單位轉換需明確；如 DB 是股、UI 顯示張，detail／tooltip 保留原單位。
- healthy-empty 與 source unavailable 分開。

## ComplianceDisclaimer

至少涵蓋：

- analysis／data as-of；
- status／confidence（明示非獲利機率）；
- data quality／missing／blocking／warning；
- governance／model or artifact version（需要時）；
- source scope；
- 標準研究／風險免責。

## TradingJournalForm

- Material 3 controls；事件類型：買進、賣出、現金股利、股票股利。
- date、canonical stock autocomplete、shares／price／dividend／currency／note 等依 event type 顯示。
- decimal validation；不得預填虛構價格。
- fee／tax preview 可有，但 canonical 值與 rule/profile version 由 backend 持久化。
- mutation 成功顯示 ledger event／safe success state；若 Private Mart 尚未更新，明示 pending，不在 Flutter 假裝已重算 PnL。
- correction 使用 reversal／replacement semantics；UI 不做無痕覆寫。

## PnLSummary／PortfolioSummary

- realized／unrealized 分開。
- 顯示 valuation date、cost method、missing/stale affected scope。
- canonical aggregate withheld 時不由 Flutter忽略缺值自行加總。
- operational shares／average cost 與 Private Mart valuation／PnL 的時間與權威層級需分開。

## NoteEditor

- 原生 multiline field、optional symbol／trade link、pending follow-up toggle。
- save 建立 revision；不需要 rich-text／attachment system 才能完成基本功能。

## Research Context 元件（Planned）

優先重用既有元件；必要時可包含：

- `MarketRegimeCard`
- `ResearchThesisCard`
- `ResearchStateBadge`
- `DataFreshnessBadge`
- `MissingDataList`
- `SupplyChainExposureCard`
- `DeterministicSignalSummary`

所有元件只顯示 backend／Mart 已持久化內容，不計算 canonical values、不把 hypothesis 標成 confirmed，也不新增聊天／Agent／tool approval UI。

## Cross-project boundary

`ChatRoom`、generic `DataSourcePicker`、MCP Skill approval、Agent timeline 等對話產品元件屬 omniAgent，不是 Janus User App component contract。Janus 只呈現投資資料、研究 artifact 與 Admin operational controls。