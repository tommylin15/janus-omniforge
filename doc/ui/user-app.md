# Janus UI — User App 頁面

## 5. User App 頁面

### 5.1 今日

P0 個人工作台尚未啟用本頁；以下契約留待公開 Mart 階段。

首屏固定順序：

1. `MarketRegimeCard`：一句話市場狀態、資料日期與信心度。
2. `DailyBriefCard`：最多三則今日重點，並列支持因素與風險因素。
3. `SectorRotationList`：前三個升溫／降溫板塊；先用可讀排名，泡泡圖放在「看完整輪動」次頁。
4. `HotTopicList`：最多五個熱門話題，顯示來源數與不確定性，不用聲量假裝正確性。
5. `CandidateHealthList`：最多五張候選股健康卡。
6. 資料日期、partial／stale／fallback 與標準免責聲明。

首頁只讀同一 `analysis_as_of` 的 `mart_daily_brief`；任一子產品日期不同時顯示 partial，不得把不同日期的最新版拼成「今日」。

### 5.2 關注

本頁取代原平台精選名單／探索主功能，以使用者主動關注的個股為中心；不得因搜尋或 page load 觸發 scraper、Agent 或 LLM。

- 搜尋股票代號或名稱後可加入／取消關注、排序、設定目標價並新增筆記；停用股票不出現。
- 預設只顯示自己的 active watchlist、最近已持久化行情、持股狀態、待完成筆記與資料日期，不顯示平台推薦榜。
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

K 線、deterministic Fact Pack、五角色 validated analysis、CIO、估值指標與完整
provenance 屬「進階資料」，預設收合且不得先於健康度與白話摘要。未知／停用股票顯示
404；已啟用但沒有 report 顯示「等待下一次批次」，不得啟動即時分析。AI 文案只讀
validated evidence，不可把 confidence 當獲利機率或把缺失資料補成 0。

歷史分析（Planned）可切換 `analysis_as_of`、execution 與 snapshot，並檢視舊 facts、
roles 與 CIO；歷史 artifact immutable。單角色重跑由 Admin 操作，完成後 User 只看到
新的 immutable result 與資料日期，不把 partial success 顯示成完整分析。

### 5.4 個人記帳與筆記

- 交易或更正 API 成功只代表 ledger 已持久化；UI 顯示「交易已儲存，等待投資組合批次更新」，positions／PnL／exposure／performance 仍以最新成功 Private Mart 的 valuation date 為準。

- 本頁是 P0 User App 主功能，不依賴公開 Mart／LLM；使用 segmented control 切換「記帳／筆記」。
- 與市場探索分頁，進入後先顯示「目前持股」、「本年已實現損益」與「待完成筆記」三張摘要卡。
- 交易類型：買進、賣出、現金股利、股票股利；依類型顯示日期、股票代號／名稱、股數、成交單價、股利金額、手續費、證券交易稅、幣別與備註，不顯示無關欄位。
- 使用十進位輸入、明確單位與即時格式驗證；不得用浮點數造成金額誤差，也不得預填虛構價格。
- 歷史明細支援股票與年份篩選；修正既有交易時呈現「建立更正」而非無痕覆寫。
- 年度報表顯示已實現損益、費用、交易次數與年度比較。未實現損益必須標示估值日期與缺價狀態。
- 預設成本法為移動平均法並顯示在報表；尚未核准 FIFO 前不提供切換。
- 一般筆記使用單一 revision model，可獨立存在或連結股票／交易；列表提供文字、股票、年份與待追蹤狀態篩選，修改時保留歷史版本。
- 所有 empty／loading／error 狀態不得洩漏其他使用者是否存在資料。

### 5.5 跨專案 UI 邊界

Janus User App 不提供 Chat／Ask Janus／provider／runtime／MCP／Skills／approval 產品入口。generic 對話介面與其 UI 規格由 omniAgent 持有；Janus 僅透過 authenticated bounded API／MCP 提供使用者明確授權的投資 context。Janus 舊 Chat API／live UI deployment 在獨立 cutover 驗收前仍是相容性路徑，不以本次 source 拆分宣稱已切換。

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

- 「今日」擴充既有 `MarketRegimeCard`，不建立同義元件；與 Daily Brief 使用同一 `analysis_as_of`，顯示 deterministic confidence、evidence、freshness 及 partial／stale／fallback／insufficient-data。
- 「關注」可在 contract 支援時顯示 candidate state、research priority、thesis freshness 與 missing-data indicator；不轉為平台推薦排行榜。
- 「個股健康檢查」在現有資訊架構納入 market regime、deterministic signal summary、research thesis 的 supporting／invalidating evidence、candidate／strategy state、可用時的 supply-chain exposure／signal、portfolio impact、provenance 與 freshness。AI summary 不得蓋過 canonical data。
- 「個人記帳與筆記」保留 append-only／revision semantics；research state 可連結 note，但 trade ledger 與 thesis 不合併為同一模型。
- Janus ResearchContext 由 bounded API／MCP 向外部 consumer 提供 source、as-of、freshness、provenance、owner scope 與 missing／stale state；私人部分仍需使用者明確授權，Janus UI 不新增聊天面板。
