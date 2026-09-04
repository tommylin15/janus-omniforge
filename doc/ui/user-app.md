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
10. 「詢問 AI」入口與 `ComplianceDisclaimer`

K 線、五角色明細、估值指標與完整 provenance 屬「進階資料」，預設收合且不得先於健康度與白話摘要。未知／停用股票顯示 404；已啟用但沒有 report 顯示「等待下一次批次」，不得啟動即時分析。

### 5.4 個人記帳與筆記

- 本頁是 P0 User App 主功能，不依賴公開 Mart／LLM；使用 segmented control 切換「記帳／筆記」。
- 與市場探索分頁，進入後先顯示「目前持股」、「本年已實現損益」與「待完成筆記」三張摘要卡。
- 交易類型：買進、賣出、現金股利、股票股利；依類型顯示日期、股票代號／名稱、股數、成交單價、股利金額、手續費、證券交易稅、幣別與備註，不顯示無關欄位。
- 使用十進位輸入、明確單位與即時格式驗證；不得用浮點數造成金額誤差，也不得預填虛構價格。
- 歷史明細支援股票與年份篩選；修正既有交易時呈現「建立更正」而非無痕覆寫。
- 年度報表顯示已實現損益、費用、交易次數與年度比較。未實現損益必須標示估值日期與缺價狀態。
- 預設成本法為移動平均法並顯示在報表；尚未核准 FIFO 前不提供切換。
- 一般筆記使用單一 revision model，可獨立存在或連結股票／交易；列表提供文字、股票、年份與待追蹤狀態篩選，修改時保留歷史版本。
- 所有 empty／loading／error 狀態不得洩漏其他使用者是否存在資料。

### 5.5 AI 聊天室

- engine selector 固定顯示 `Codex`、`ChatGPT`、`Gemini`；Codex／ChatGPT 共用 Codex App Server subscription login，但採不同 agentic／conversation profile，UI 不宣稱存在兩個官方 App Server。
- Codex／ChatGPT 顯示連結訂閱、登出、plan 與 rate-limit 狀態；不得要求 OpenAI API key。Gemini 顯示 grounding 與成本狀態，未通過 billing gate 時 disabled。
- 每個 conversation 固定 engine；切換時提示建立新 conversation／fork。訊息顯示 engine、model、資料日期、選用的持股／筆記 context、search 狀態與可點擊 citations。
- 允許使用者明確選取持股、交易、筆記或關注股加入 context；預設不自動送出全部私人資料。
- 所有 profile 只讀，禁止 shell、檔案寫入、Admin、交易／筆記／watchlist mutation 與下單。缺 citation、資料不足、額度耗盡或 provider unavailable 顯示明確狀態，不靜默切換引擎。

### 5.6 資產與風險（P1）

- 顯示總資產、現金水位、持股、估值日期與缺價狀態；正式數值只讀 Private Mart。
- 曝險先用可讀的現金／產業比例列表與總和，圖表為次要呈現；一檔股票跨產業時顯示版本化分攤說明。
- 年度績效顯示已實現損益、股利、費稅、交易次數與 XIRR status；無根、多根或資料不足不得顯示 0%。
- 壓力測試先選 deterministic scenario，再選 Codex／ChatGPT／Gemini profile 解釋結果；模型文案與計算數值分區呈現。

### 5.7 我的

- theme 使用 light／dark／system；字體縮放跟隨系統，不自建第二套縮放引擎。
- 投資屬性提供風險承受度、投資期間、主要目標與最低現金比例；送入 AI 前須逐次或以清楚設定 opt-in。
- 提供「匯出我的私人資料」與「永久刪除私人資料」，涵蓋交易、筆記、關注股、對話與 Codex local thread/auth state。刪除使用 danger zone、再次驗證與明確影響範圍，不以單次誤觸直接執行。
- 不放方案定價、預測戰績或公開排行榜；待產品與法遵另案確認後再新增。
