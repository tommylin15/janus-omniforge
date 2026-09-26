# Janus UI — User App 頁面

## 5. User App 頁面

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

`mart_daily_brief` 缺失、error 或尚未產生時，只讓 Mart／AI 研究區塊顯示「研究摘要尚未就緒」；不得讓 deterministic market baseline 整頁退化成「今日市場資料尚未就緒」。

### 5.2 關注

本頁取代原平台精選名單／探索主功能，以使用者主動關注的個股為中心；不得因搜尋或 page load 觸發 scraper、Agent 或 LLM。

- 搜尋股票代號或名稱後可加入／取消關注、排序、設定目標價並新增筆記；停用股票不出現。
- 預設只顯示自己的 active watchlist、最近已持久化行情、持股狀態、待完成筆記與資料日期，不顯示平台推薦榜。
- 股票主要識別優先顯示 canonical 股票名稱＋代號；名稱缺失是資料 completeness 問題，不以空白名稱當成完整狀態。
- MVP 最多 50 個 active distinct symbols；達上限時顯示 quota 說明，不以「50 大」命名。
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

歷史分析（Planned）可切換 `analysis_as_of`、execution 與 snapshot，並檢視舊 facts、roles 與 CIO；歷史 artifact immutable。單角色重跑由 Admin 操作，完成後 User 只看到新的 immutable result 與資料日期，不把 partial success 顯示成完整分析。

### 5.4 個人記帳與筆記

- 交易或更正 API 成功只代表 ledger 已持久化；UI 顯示「交易已儲存，等待投資組合批次更新」，positions／PnL／exposure／performance 仍以最新成功 Private Mart 的 valuation date 為準。
- 本頁是 P0 User App 主功能，不依賴公開 Mart／LLM；使用 segmented control 切換「記帳／筆記」。
- 與市場探索分頁，現行能力可顯示「目前持股」、「本年已實現損益」與「待完成筆記」摘要；正式數值不得由 Flutter 自算。
- 持股與交易主要識別優先顯示 canonical 股票名稱＋代號；若 stock master 無法解析名稱，應顯示 bounded partial／data issue，而不是把只有代號的狀態誤認為產品完整。
- 交易類型：買進、賣出、現金股利、股票股利；依類型顯示日期、股票代號／名稱、股數、成交單價、股利金額、手續費、證券交易稅、幣別與備註，不顯示無關欄位。
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
5. 次導航「持股／紀錄／報表」；手機不得把三者塞成同一高密度表格。

「紀錄」的目標資訊架構為 `年份 → 月份 accordion → 單筆交易`。月份摘要不得把所有金流混成「收入／支出」，至少分開：

- 買進支出
- 賣出回收
- 股利收入
- 已實現損益

`cash flow` 與 `PnL` 是不同語意：賣出回收金額不等於獲利，股利收入也不得在沒有正式 contract 時直接冒充交易 realized PnL。正式 canonical 數值由 backend／Private Mart 提供；Flutter 可以做純視覺 grouping，但不得自行建立新的會計口徑。

單筆交易列優先顯示日期、交易類型、股票名稱／代號、適用時的「股數 × 成交單價」與淨現金流。點入 detail 後再顯示成交總額、手續費、證券交易稅、幣別、備註、必要的 ledger／valuation 資訊，以及「建立更正」。append-only ledger 與 correction／replacement 語意不變。

手機版可採明顯的 FAB「＋」作為快速新增入口；先選買進／賣出／現金股利／股票股利，再依 event type 顯示必要欄位。不得顯示不適用欄位，也不得因便利性改變 backend validation 或 ledger contract。

「持股」在手機優先使用兩到三行卡片，而非橫向多欄表格；在資料可用時顯示股票名稱／代號、持有股數、現價／均價、今日漲跌、未實現損益／報酬率，點擊後進 Janus 個股詳情並銜接持股、成本、筆記與研究內容。正式估值與損益仍只讀 Private Mart。

「報表」可逐步納入持股占比、現金比例、年度已實現損益、股利、費用／稅、交易次數與年度比較；產業曝險只在正式 exposure contract 就緒後顯示。圓餅圖等圖表是次要呈現，不取代可讀數值與資料日期。

以下參考 App 功能**不直接採納**：

- 券商手續費折數不得取代 ledger 實際 fee；若日後提供，只能是輸入輔助。
- 不提供任意切換 FIFO／移動平均等成本法；目前 canonical MVP 維持移動平均法。
- 不提供「是否計入賣出費用」等會改變 canonical PnL 的自由 toggle。
- 預計交易／scenario 不得直接寫入正式 ledger 或實際損益。

#### 5.4.2 持股完整度（Active Product Completeness contract）

- 所有 active positions 必須能對應 canonical stock master 的股票名稱與代號；無法解析時標示 partial／data issue 並保留可追蹤原因。
- Private Mart 對每檔持股提供 shares、average cost、market price／value、price date／valuation date、unrealized PnL／return 與 price status；User UI 只讀正式欄位。
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
