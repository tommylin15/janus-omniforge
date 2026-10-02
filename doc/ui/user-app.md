# Janus UI — User App 頁面

## 5. User App 頁面

### 5.0 Final Visual Contract

Janus User App 的手機版最終 presentation target 由 [`reference/user-app-final/README.md`](reference/user-app-final/README.md) 定義，固定預留四張圖：

- `reference/user-app-final/today.png` — 今日
- `reference/user-app-final/watchlist.png` — 關注
- `reference/user-app-final/ledger.png` — 記帳／筆記
- `reference/user-app-final/stock-detail.png` — 個股詳情

這四張圖不是 disposable mockup；後續 User App implementation 應逐步 convergence 至其資訊架構、section order、card hierarchy、手機資訊密度與跨頁視覺語言。圖片中的 sample price、PnL、法人金額、日期、AI prose、健康度結果、股票 logo、sparkline 與裝飾圖表只作 illustrative presentation，不得 hard-code 或當成 canonical data。

資料正確性、missing／stale／partial／blocked 語意、auth／owner isolation、PIT／provenance、source authorization、canonical number、publication 與 LLM boundary 仍以 active SPEC／WBS／runtime contract 為準；圖片不得覆蓋治理。圖片與 active contract 衝突時必須指出差異並先更新 active contract，不得靜默選邊。

在四張 PNG binary 尚未 commit 至固定路徑前，只能說 Final Visual Contract 已建立，不能宣稱 visual reference binary 或 final visual acceptance 已完成。四頁與 cross-screen acceptance 的完整清單見 `reference/user-app-final/README.md`。

### 5.1 今日

「今日」是 User App 的市場入口。它不得以公開 Mart／LLM 是否完成作為市場 baseline 可見性的 prerequisite；先顯示 deterministic published market data，再在可用時疊加 Mart／AI 研究內容。

首屏順序：

1. `MarketSnapshotCard`：目前可合法取得的 benchmark／市場摘要、資料日期、freshness 與 coverage status。
2. `MarketActivityCard`：已發布的 market activity 摘要；缺資料時只標記本卡 partial／missing。
3. `InstitutionalFlowCard`：已發布的法人摘要；缺資料時只標記本卡 partial／missing。
4. `MarketRegimeCard`：Mart 可用時顯示一句話市場狀態、`analysis_as_of` 與 deterministic confidence；未就緒時顯示 bounded unavailable state。
5. `DailyBriefCard`：Mart 可用時最多三則今日重點，並列支持因素與風險因素。
6. `SectorRotationList`、`HotTopicList`、`CandidateHealthList`：只在各自已持久化資料可用時顯示；不得為填滿首頁而生成 placeholder。
7. 各資料區塊自己的日期、partial／stale／fallback／missing，以及標準免責聲明。

Deterministic market cards 可以各自保留 source-specific `as_of`／trade date，不必為了視覺一致硬湊同一天，但必須如實顯示日期與 freshness。Mart 子產品仍必須使用同一 `analysis_as_of`；任一 Mart 子產品日期不同時顯示 partial，不得把不同日期的最新版拼成「今日分析」。

`mart_daily_brief` 缺失、error 或尚未產生時，只讓 Mart／AI 研究區塊顯示「研究摘要尚未就緒」；不得讓 deterministic market baseline 整頁退化成「今日市場資料尚未就緒」。首頁 request／section loading 必須 bounded；任一單一 dependency timeout／error 不得造成永久 spinner 或無限阻塞整頁。

### 5.2 關注

本頁取代原平台精選名單／探索主功能，以使用者主動關注的個股為中心；不得因搜尋或 page load 觸發 scraper、Agent 或 LLM。

- 搜尋股票代號或名稱後可加入／取消關注、排序、設定目標價並新增筆記；新加入只允許當前有效的週量 500 個股，由後端檢查；停用股票不出現。既有關注離榜時保留並標明不在本週市場資訊名單。
- 股票名稱搜尋必須與交易表單共用 canonical stock-master search contract；中文名稱與代號都可查詢，結果回 canonical name＋symbol＋admission／active state，不另用 scraper／LLM 補名稱。
- 預設只顯示自己的 active watchlist、最近已持久化行情、持股狀態、待完成筆記與資料日期，不顯示平台推薦榜。
- 股票主要識別優先顯示 canonical 股票名稱＋代號；名稱缺失是資料 completeness 問題，不以空白名稱當成完整狀態。
- MVP 最多 50 個 active distinct symbols；達上限時顯示 quota 說明，不以「50 大」命名。
- 手機版 presentation target 採可掃描的 stock cards，至少容納名稱／代號、recent persisted price／date、held／not-held、target price、待追蹤狀態與 bounded missing／stale；不得為了貼近 mockup 而虛構行情或持股狀態。
- 後續公開探索、板塊輪動、候選股與歷史回放收在「今日／看更多」，不得取代個人關注首頁。

### 5.3 個股健康檢查

固定順序：

1. `StockHeader`
2. 個人持股、成本與估值日期
3. 個人筆記與待追蹤事項
4. `StockHealthCard`
5. `AiPlainLanguageCard`
6. 三項「為什麼」與三項「要注意什麼」
7. `ChipsStatusCard`
8. `CompanyEventTimeline`
9. 可收合的 `EvidenceAndSources`
10. `ComplianceDisclaimer`；不設「詢問 AI」入口

K 線、deterministic Fact Pack、五角色 validated analysis、CIO、估值指標與完整 provenance 屬「進階資料」，預設收合且不得先於健康度與白話摘要。未知／停用股票顯示 404；已啟用但沒有 report 顯示「等待下一次批次」，不得啟動即時分析。AI 文案只讀 validated evidence，不可把 confidence 當獲利機率或把缺失資料補成 0。

「建議／研究資訊」整合在本頁既有 health／plain-language／why-risk／evidence hierarchy，不另建重複 recommendation 頁；顯示 analysis/data as-of、status、confidence、source/evidence 與 disclaimer，不能以保證性語氣呈現投資結果。

歷史分析（Planned）可切換 `analysis_as_of`、execution 與 snapshot，並檢視舊 facts、roles 與 CIO；歷史 artifact immutable。單角色重跑由 Admin 操作，完成後 User 只看到新的 immutable result 與資料日期，不把 partial success 顯示成完整分析。

### 5.4 個人記帳與筆記

- 本頁是 P0 User App 主功能，不依賴公開 Mart／LLM；使用 segmented control 切換「記帳／筆記」。進入「記帳」時預設次導航為 **持股**，不是紀錄。
- 交易或更正 API 成功首先代表 append-only ledger 已持久化；同一次 backend 流程須更新 deterministic synchronous operational position projection，使 shares／average cost／cash impact 等可立即反映。Flutter 不自行計算 authoritative holdings。Private Mart 仍持有 canonical valuation／PnL／exposure／performance 與 reconciliation；若 Mart 尚未追上，UI 明示其 valuation date／checkpoint／pending 狀態，而不是把 operational projection 冒充最新 canonical PnL。
- 與市場探索分頁，現行能力可顯示「目前持股」、「本年已實現損益」與「待完成筆記」摘要；正式數值不得由 Flutter 自算。
- 持股與交易主要識別優先顯示 canonical 股票名稱＋代號；若 stock master 無法解析名稱，應顯示 bounded partial／data issue，而不是把只有代號的狀態誤認為產品完整。交易新增表單與 Watchlist 共用中文名稱／代號 search contract。
- 行情採 **DB-first／stale-while-revalidate**：頁面先讀 latest successful operational quote／valuation read model 與 timestamp，再依 market session refresh approved source；成功後保存 `source`、`quote_at`、`received_at`、session／freshness／status 並更新 UI，失敗時保留 last success 並顯示 stale／refresh error。Top-right refresh 與自動 refresh 共用相同 backend route／policy。
- 行情 routing 是 backend versioned contract，不由 Flutter hard-code。使用者指定目標預設：盤中 **Yahoo → Fugle realtime → TWSE MIS**；盤後 **TWSE published/EOD → Fugle → Yahoo**。只有 source authorization／license／quota-cost／health gate 已通過的來源才進 effective route；未核准來源必須跳過並明示 blocked。Yahoo 未取得明確授權前不得成為 executable runtime source。盤中 operational quote 不覆寫 canonical Core OHLCV 或正式 Private Mart EOD valuation。
- 既有 TWSE MIS 的 10 秒 bounded cache、交易時段／holiday guard、成交價語意、120 秒 stale 判定與 last-success preservation 可作 source-adapter 基線；擴充成 multi-source router 後，每個 adapter 仍需有 bounded timeout／retry 與 provenance。非盤中點入可只查一次；前景 polling 需 bounded，不得因單一來源失敗永久 spinner。
- 缺值明示 missing，必要 aggregate withheld；不得用五檔掛單價、舊正式估值或 0 偽裝成交價。股價類（現價、均價、成交單價、目標價／估價）固定顯示小數二位；金額、股數、比例顯示四捨五入整數、comma 千分位，負數以括號顯示；股票代號、日期與十進位交易輸入保持原語意。
- 交易類型：買進、賣出、現金股利、股票股利；依類型顯示日期、股票代號／名稱、股數、成交單價、股利金額、幣別與備註。手續費／證券交易稅由 backend 依 broker／instrument／event／day-trade rule 與 version 計算並持久化；前端可 preview，但不要求每次手填，也不得自行重建 canonical fee/tax。
- 新增私人「操作池／Broker Profile」設定：current cash／cash strategy、broker fee discount multiplier（例如 `0.4` 表示標準手續費的 40%）、minimum broker fee 與必要的 rule/profile version。現金最好由可稽核 cash ledger（opening/deposit/withdrawal/trade/dividend）推導；若新增 CASH_IN／CASH_OUT／adjustment，須維持 append-only／audit，不以可任意覆寫單一 cash number 破壞歷史重現。
- 使用十進位輸入、明確單位與即時格式驗證；不得用浮點數造成金額誤差，也不得預填虛構價格。
- 歷史明細支援股票與年份篩選；修正既有交易時呈現「建立更正」而非無痕覆寫。
- 年度報表顯示已實現損益、費用、交易次數與年度比較。未實現損益必須標示估值日期與缺價狀態。
- 預設成本法為移動平均法並顯示在報表；尚未核准 FIFO 前不提供切換。
- 一般筆記使用單一 revision model，可獨立存在或連結股票／交易；列表提供文字、股票、年份與待追蹤狀態篩選，修改時保留歷史版本。
- 所有 empty／loading／error 狀態不得洩漏其他使用者是否存在資料。

#### 5.4.1 交易記錄 UX 2.0（基礎 presentation／read-path acceptance 已完成）

本節吸收 2026-09-24 交易／持股參考 App 的產品評估。既有 Flutter/API targeted tests 與 canonical dev authenticated read-only acceptance 已證明 layout、交易月份／明細、年度報表、表單、missing／stale／partial presentation 等基礎 read-path 行為；**這個完成判定不代表 market coverage、股票名稱解析、aggregate portfolio valuation／return 或整體 User App 已完整。** 每檔行情 date 早於 portfolio valuation date 時由 backend 標記 stale；aggregate unrealized PnL 在 contract 要求 withheld 的 stale／缺價情境不得由 Flutter 補算。

交易記錄第一屏在資料可用時應優先呈現：

1. 持股市值：最新成功 Private Mart valuation date 的 aggregate market value。
2. 未實現損益與報酬率：與持股市值同一 canonical valuation contract 的 aggregate unrealized PnL／return。
3. 本年已實現損益：當年度 canonical realized PnL。
4. 估值日期與缺價／stale／partial 狀態；aggregate withheld 時顯示 affected count／symbols 或等價 bounded diagnosis。
5. 次導航「持股／紀錄／報表」；手機不得把三者塞成同一高密度表格，且進入記帳頁時預設為「持股」。

「紀錄」的目標資訊架構為 `年份 → 月份 accordion → 單筆交易`。月份摘要不得把所有金流混成「收入／支出」，至少分開：

- 買進支出
- 賣出回收
- 股利收入
- 已實現損益

`cash flow` 與 `PnL` 是不同語意：賣出回收金額不等於獲利，股利收入也不得在沒有正式 contract 時直接冒充交易 realized PnL。正式 canonical 數值由 backend／Private Mart 提供；Flutter 可以做純視覺 grouping，但不得自行建立新的會計口徑。

單筆交易列優先顯示日期、交易類型、股票名稱／代號、適用時的「股數 × 成交單價」與淨現金流。點入 detail 後再顯示成交總額、手續費、證券交易稅、幣別、備註、必要的 ledger／valuation 資訊，以及「建立更正」。append-only ledger 與 correction／replacement 語意不變。

手機版可採明顯的 FAB「＋」作為快速新增入口；先選買進／賣出／現金股利／股票股利，再依 event type 顯示必要欄位。不得顯示不適用欄位，也不得因便利性改變 backend validation 或 ledger contract。

「持股」在手機優先使用兩到三行卡片，而非橫向多欄表格；在資料可用時顯示股票名稱／代號、持有股數、現價／均價、今日漲跌、未實現損益／報酬率，點擊後進 Janus 個股詳情並銜接持股、成本、筆記與研究內容。shares／average cost 等 operational state 可在 ledger commit 後立即更新；正式 valuation／PnL 仍只讀 Private Mart，兩者資料時間與狀態必須分開呈現。

「報表」可逐步納入持股占比、現金比例、年度已實現損益、股利、費用／稅、交易次數與年度比較；產業曝險只在正式 exposure contract 就緒後顯示。圓餅圖等圖表是次要呈現，不取代可讀數值與資料日期。

以下參考 App 功能的最新處理：

- 券商手續費折數現在可作為私人 Broker Profile 的 fee-rule 輸入輔助，但不得覆寫已持久化的實際 fee；每筆 trade 保存適用 rule/profile version，確保歷史重現。
- 不提供任意切換 FIFO／移動平均等成本法；目前 canonical MVP 維持移動平均法。
- 不提供「是否計入賣出費用」等會改變 canonical PnL 的自由 toggle。
- 預計交易／scenario 不得直接寫入正式 ledger 或實際損益。

#### 5.4.2 持股完整度（Active Product Completeness contract）

- 所有 active positions 必須能對應 canonical stock master 的股票名稱與代號；無法解析時標示 partial／data issue 並保留可追蹤原因。
- Private Mart 對每檔持股提供 shares、average cost、market price／value、price date／valuation date、unrealized PnL／return 與 price status；User UI 只讀正式 canonical valuation 欄位。ledger commit 後的 operational position projection 可先反映 shares／average cost 等 deterministic state，但不得冒充 Private Mart PnL／valuation。
- 同幣別 aggregate 至少包含 market value、cost basis、unrealized PnL／return。若任何 required position 因 missing／stale／不相容 valuation date 使 aggregate 不可靠，backend 必須依 canonical policy withheld 並回傳 affected count／symbols 或等價 bounded diagnosis；不得讓 UI 自行忽略缺值後加總。
- 完成判定必須以 authenticated GCP dev 真實 owner data 驗證目前 active holdings，而不是只有 fixture 或 presentation test。

### 5.5 跨專案 UI 邊界

Janus User App 不提供 Chat／Ask Janus／provider／runtime／MCP／Skills／approval 產品入口。generic 對話介面由 omniAgent 持有；Janus 透過 authenticated bounded API／MCP 提供使用者明確授權的投資 context。Janus source 與 canonical GCP dev revision 均已移除舊 Chat API runtime 與舊 Chat UI。

### 5.6 資產與風險（P1）

- 顯示總資產、現金水位、持股、估值日期與缺價狀態；正式數值只讀 Private Mart。
- 曝險先用可讀的現金／產業比例列表與總和，圖表為次要呈現；一檔股票跨產業時顯示版本化分攤說明。
- 年度績效顯示已實現損益、股利、費稅、交易次數與 XIRR status；無根、多根或資料不足不得顯示 0%。
- 壓力測試呈現 Janus deterministic scenario、計算數值與資料日期；若使用者日後在 omniAgent 要求模型解釋，須由其使用 Janus bounded contract，Janus UI 不提供 runtime selector。

### 5.7 我的

- theme 使用 light／dark／system；字體縮放跟隨系統，不自建第二套縮放引擎。
- 投資屬性提供風險承受度、投資期間、主要目標與最低現金比例；送入 AI 前須逐次或以清楚設定 opt-in。
- 提供 Janus 私人資料的匯出與可稽核刪除，涵蓋交易、筆記、關注股及 cutover 前仍由 Janus 持有的歷史 assistant 資料；omniAgent 新資料的匯出／刪除另由其 owner boundary 處理。刪除使用 danger zone、再次驗證與明確影響範圍；`CLEANUP_PENDING` 不得顯示成功，保留期須如實揭露。
- 不放方案定價、預測戰績或公開排行榜；待產品與法遵另案確認後再新增。

### 5.8 Research Context 整合（Planned）

- 「今日」擴充 deterministic market baseline 與既有 `MarketRegimeCard`，不建立同義元件；Mart Daily Brief 仍使用同一 `analysis_as_of`，顯示 deterministic confidence、evidence、freshness 及 partial／stale／fallback／insufficient-data。
- 「關注」可在 contract 支援時顯示 candidate state、research priority、thesis freshness 與 missing-data indicator；不轉為平台推薦排行榜。
- 「個股健康檢查」在現有資訊架構納入 market regime、deterministic signal summary、research thesis 的 supporting／invalidating evidence、candidate／strategy state、可用時的 supply-chain exposure／signal、portfolio impact、provenance 與 freshness。AI summary 不得蓋過 canonical data。
- 「個人記帳與筆記」保留 append-only／revision semantics；research state 可連結 note，但 trade ledger 與 thesis 不合併為同一模型。
- Janus ResearchContext 由 bounded API／MCP 向外部 consumer 提供 source、as-of、freshness、provenance、owner scope 與 missing／stale state；私人部分仍需使用者明確授權，Janus UI 不新增聊天面板。

### 5.9 Loading／效能契約

- 主導航頁應保持 persistent state；切換「今日／關注／記帳／我的」不得因 widget recreation 無條件重建所有 Future／重送全部 API。
- 不在 `build()` 內建立會因 rebuild 重送 request 的 `Future.wait(...)`；首次載入、refresh、route revisit 的 request lifecycle 必須明確。
- Composite screen 採 section-level loading／partial，不讓單一慢 endpoint 造成整頁永久 spinner；已持久化資料可先顯示，再 stale-while-revalidate。
- Backend interactive path 應量測 auth、DB connect/query、Iceberg scan、endpoint fan-out 與 p50／p95 後再優化；沒有 runtime evidence 前不得把 CPU／RAM、DB bloat 或 index 說成既定 root cause。
- 高頻 read path 優先使用 bounded DB read model／cache／connection pool；若直接 Iceberg scan 造成可量測延遲，再以 aggregate endpoint／projection 改善。GET 不應執行可移往 batch/controller 的無關 retirement write。
- `min-instances=0` 可作為 idle-cost 選擇並接受 cold-start trade-off；它只解釋 idle 後 first request，不應拿來解釋所有持續性 latency。

### 5.10 數值顯示契約

- 統一 typed formatter，避免各 widget raw interpolation。
- 股價語意（現價、估值、平均成本、成交單價、目標價等）固定 2 位小數。
- 金額、股數、比例依產品契約四捨五入整數、comma 千分位；負數以括號顯示。
- 股票代號、日期、版本、hash 與十進位交易輸入保留原語意，不套會計格式。
- targeted／golden regression 應覆蓋上述格式，避免新畫面回歸。