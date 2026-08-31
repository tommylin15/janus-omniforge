# Janus × OmniForge — UI Specification

版本：1.1
範圍：Next.js 公開網站、Admin UI、responsive、a11y 與 API/UI data contract

## 1. UI 原則

- UI 只呈現後端／Mart 已持久化資料，不在前端重算分數或補資料。
- blocked report 不渲染；null 不顯示 0。
- 明確區分 loading、error、empty、unavailable、partial、stale、fallback、blocked。
- confidence 固定標示為「資料／分析信心度，非獲利機率」。
- 不輸出保證獲利、確定買賣指示或無依據目標價。
- 所有來源只取當前資源／當前日期自己的 provenance。

## 2. 視覺系統

- 深色主題，zinc 作背景、邊框、中立與資料不足。
- 台股慣例：上漲 emerald、下跌 red。
- amber：warning、partial、fallback、attention；不得表示安全。
- red：blocking、critical/high、disposition、停資停券。
- 系統字型優先，不依賴 Google Fonts。
- 一般文字 WCAG AA 4.5:1；大字 3:1；focus indicator 3:1。

## 3. Responsive Layout

| 裝置 | Layout | Navigation | History |
|---|---|---|---|
| Mobile | 單欄 | StickyHeader + BottomNav | Bottom sheet |
| iPad | 兩欄可用 | StickyHeader；必要時 BottomNav | Centered modal |
| Desktop | 多欄 grid，無水平 overflow | Header navigation | Centered modal |

- 支援 safe area、`viewport-fit=cover`、`100dvh`。
- 所有主要控制、日期、圖表 toggle、展開按鈕至少 44×44 CSS px。
- BottomNav 主要項目高度至少 56px。

## 4. 全域殼層

### StickyHeader

- 品牌、首頁、個股、話題、收藏、登入／Admin 入口。
- safe-area top；鍵盤 focus 可見。
- Admin 與 public 使用一致品牌但權限／導覽分離。

### BottomNav

- 首頁、個股、話題、收藏。
- 未完成項目顯示 coming soon／disabled，不可只 `console.log`。
- safe-area bottom，不遮擋頁面內容。

### Global status

- API unavailable 顯示可理解訊息，不呈現 upstream traceback。
- 可選擇顯示最新資料日、更新時間與來源健康摘要。

## 5. 公開頁面

### 5.1 首頁 `/`

元件：

1. Market status／資料日期。
2. `SearchFilter`：代號、名稱、題材。
3. `TopicCard`：真實摘要與 `/stocks/{symbol}` 連結。
4. Market／source health 精簡狀態。
5. `EmptyState`。

規則：

- 停用股票不出現在搜尋與題材。
- 不生成示例股票冒充正式資料。
- 搜尋條件可寫入 query string。

### 5.2 個股頁 `/stocks/[symbol]`

固定順序：

1. `StockHeader`
2. `KLineChart`
3. `MetricsGrid`
4. `SentimentBar`
5. `AggregationEvidence`
6. `MarketActivityPanel`
7. 五張 `AnalystCard`
8. `CompanyEventTimeline`
9. `ReportHistoryModal`
10. `ReportSources`
11. `ComplianceDisclaimer`

未知／停用股票：404。已啟用但沒有 report：顯示「等待下一次批次」，不得啟動即時分析。

## 6. 元件契約

### StockHeader

- symbol、真實 name、market。
- close、change、change percent；null 顯示資料暫缺。
- 明確顯示 `market_data.as_of` 實際交易日。
- 顯示 report `analysis_as_of`，不可暗示即時報價。

### KLineChart

- D／W／M period。
- MA 5／10／20／60／120／240（依資料可用性）。
- OHLCV、必要技術指標 tooltip。
- loading、error、empty、request race protection。
- Canvas 提供同步 OHLCV table／摘要。
- tooltip 支援 hover、focus、Enter、touch、Escape，不使用 title-only。
- 手勢不得造成錯誤頁面捲動。

### MetricsGrid／SentimentBar

- 偏多、偏空、中立、資料不足四態。
- aggregate score=null 時不顯示 0、勝率或方向暗示。
- 開發期 completeness 30% gate 的 insufficient 狀態需明示。

### AggregationEvidence

- 同時顯示 bull、bear、contradictions、contributions。
- 不隱藏反向證據。
- 顯示 effective weight、quality effect、governance version。

### MarketActivityPanel

- Mobile 兩欄、desktop 四欄。
- 融資融券、借券、當沖、注意／處置。
- DB 數量以股；UI 可顯示張，tooltip 保留股數。
- healthy-empty：「目前沒有資料」。
- source unavailable：「資料暫缺」。

### AnalystCard

共通：角色、direction、nullable score、confidence、summary、missing data、evidence。

- 安全渲染 Markdown 標題、清單、粗體，不執行 HTML。
- Fundamental：規則集、營收／獲利、quality flags、正負因素。
- Valuation：PE、PB、ROE、D/E、valuation score。
- Positioning：5／20／60、crowding、smart-money divergence；crowding 不用綠色。
- Quant：relative strength、volume Z、volatility、drawdown、Beta、ATR、turnover／liquidity。
- Event Risk：risk score、governance flags、catalysts、risk events；manual review 不使用確定性樣式。

Evidence 欄位：metric、value、unit、source、provenance ID、observed／published／fetched time。

### CompanyEventTimeline

- 位於五張 AnalystCard 後、Disclaimer 前。
- 依 `published_at DESC`。
- 相同類型且語意近似只顯示最新版；有實質變更的更正公告保留。
- 收合只顯示標題與發布時間。
- 展開顯示 type、severity、effective、observed、fetched、body、source。
- critical／high red；medium amber；low zinc；unknown「待分類」。
- cursor 載入更多；附件不存在不顯示按鈕。

### ReportHistoryModal

- 最多五份，日期由新到舊。
- 從角色卡開啟時只顯示該角色在所選日期的內容。
- 日期切換同步切換 report、provenance、source references。
- legacy 欄位 null／unknown，不借用最新資料。
- Mobile bottom sheet；iPad／desktop modal。

### ReportSources

- 只使用當前 report provenance。
- 依 source name 去重；fallback 明示。
- 最多顯示三則核准新聞原文。
- 不顯示 raw object URI、query string 或不安全 URL。

### ComplianceDisclaimer

- analysis as of。
- Aggregator confidence，明示非獲利機率。
- data quality、missing data、blocking／warning。
- governance version。
- risk disclosure、來源採用範圍、標準免責聲明。

## 7. UI 狀態語意

| 狀態 | 使用者文案 | 視覺 |
|---|---|---|
| loading | 資料載入中 | skeleton／spinner |
| empty | 目前沒有資料 | zinc |
| unavailable | 資料來源暫時無法使用 | amber |
| partial | 部分資料可用 | amber + 缺失清單 |
| stale | 資料日期較舊 | amber + 實際日期 |
| fallback | 使用備援來源 | 低調 badge + source |
| insufficient_data | 資料完整度不足，無法評估 | zinc，不顯示方向 |
| blocked | 報告未通過發布審查 | 公開端不回傳；Admin red |
| error | 服務暫時發生問題 | 安全文案，不顯示 traceback |

## 8. Hook／API 契約

`useStockAgent` 讀取 `/api/v1/stocks/{symbol}/report`：

- 200：保存 report。
- 404：顯示等待下一次批次或不存在，依 error code 區分。
- network／5xx：服務錯誤。
- 不使用 SSE，不啟動即時推論。

其他 hooks 只負責 API 讀取、取消競態與狀態呈現。

主要 public endpoints：

- `/api/v1/health`
- `/api/v1/topics`
- `/api/v1/stocks/{symbol}/summary`
- `/api/v1/stocks/{symbol}/report`
- `/api/v1/stocks/{symbol}/reports`
- `/api/v1/stocks/{symbol}/kline?period=D|W|M`
- `/api/v1/stocks/{symbol}/events?cursor=...`

## 9. Admin UI

### 9.1 `/admin/stocks`

- 頁面品牌／標題保留「資料營運中心」；若沿用左側 Admin 導覽，右側仍一次只顯示一個功能面板。
- 使用 `tablist` 分隔「股票管理」、「股票資料狀態」、「最近執行」、「資料源健康」、「核心 50 名單」、「排程與保存設定」、「資料源設定」、「AI Prompt」、「Mart 分析」。選取狀態寫入 `?tab=`，重載與分享 URL 後可還原；未選分頁不預抓大型 details。
- Desktop 顯示水平或側邊 tabs；窄螢幕可用可捲動 tablist 或等價單選導覽，但頁面標題與目前分頁名稱必須可見。tab 支援方向鍵、Home／End、Enter／Space，並正確連結 `aria-controls`／`aria-labelledby`。

「股票管理」：

- 全部股票，不套 public enabled filter；代號／名稱搜尋、每頁 10 筆。
- 新增、編輯、enabled toggle、本頁全選與跨頁保留。
- Collection 與 Analysis 分開觸發；queued 不顯示為完成。
- 有 market／report／fundamental 關聯時禁止刪除並顯示數量。

「股票資料狀態」：

- Core 最新交易日、dataset、coverage、row count、null count／ratio、DQ、quarantine、freshness、source、snapshot ID 與 updated time 使用欄列表格，不直接輸出 JSON blob。
- 表格採類 Excel 閱讀方式：sticky header、欄位對齊、排序、篩選、分頁、欄位顯示／隱藏、橫向捲動及空值 `—`；不要求 spreadsheet 公式或任意 inline edit。
- row expand／「查看」才載入明細；巢狀 quality flags、association、quarantine reason 轉成子表或 key/value definition list。raw payload、object URI、敏感 URL 與完整 upstream error 不得提供「查看 JSON」旁路。

「最近執行」：

- 最近 50 次 persisted execution；row click／「查看」才讀結構化 details。
- execution item 以 source、dataset、target date、processed／success／failure／retry、Stage／Core commit、safe message 欄位顯示，不以 JSON 作主要內容。

「資料源健康」、「核心 50 名單」、「排程與保存設定」、「資料源設定」各自只呈現對應資料與控制，按鈕不得跨面板造成用途不明。

「AI Prompt」：

- 以角色、scope（全域／產業／個股）、scope key、revision、狀態、effective time、updated by 篩選。
- 編輯五角色的 versioned prompt template；支援 draft、diff、validation、preview resolved template、activate、retire、optimistic lock 與 audit。個股 override 優先於產業，產業優先於全域。
- 顯示本次 execution 將使用的 resolved revision ID；prompt 不得包含 secret、未核准 evidence、解除 Validator／publication policy 的指令。保存或預覽不直接啟動分析。

「Mart 分析」：

- 分成「產業分析」與「個股分析」資料表，讀取已持久化的 `mart_industry_analysis`／`mart_symbol_analysis`。
- 可依 analysis date、industry、symbol、角色、prompt revision、analysis outcome 與 publication status 篩選；明細顯示 summary、score、confidence、missing data、evidence reference、Core／Mart snapshot 與版本。
- 歷史 prompt revision 與分析 artifact 只能檢視，不可原地改寫；重新分析必須建立新的 queued execution。

### 9.2 `/admin/governance`

- Typed editing。
- Group validation。
- Diff preview。
- Immutable revision history。
- Optimistic lock。
- 顯示 approved／development-default／pending。
- Workflow 使用 immutable snapshot，不讀取未提交表單。

### 9.3 `/admin/data-sources`

- 只讀 persisted telemetry，不在 page load 呼叫上游。
- source + dataset 卡片：status、sample count、success rate、latency、last fetched、latest observation。
- 顯示 empty、schema drift、fallback、rate limit。
- 顯示安全 batch 摘要，不顯示 query、raw payload、URI、完整 error、帳號或 secret。
- 同一能力亦可嵌入「資料營運中心 → 資料源健康／資料源設定」分頁；不得因此移除資料營運中心入口。
- 候選 adapter 審查表顯示 license／terms 證據、robots／API policy、rate limit、retention／刪除／再發布、穩定性量測、欄位與內容重複度、成本、安全、reviewer、decision time、reason 與 version。
- 只有 `official`／`approved_fallback` 可啟用；`candidate`／`blocked` 的 cadence 控制 disabled 並說明缺少的審查項目。Anue 10 分鐘排程在核准前不得執行；FinData-compatible／twstock 同樣遵守此 gate。

### 9.4 `/admin/reports`

- 篩選 blocked／manual review／insufficient／publishable。
- 顯示 evidence、blocking reason、governance version。
- block／unblock／approve 需要理由、操作者與 audit trail。
- 不可直接修改原始 evidence 或 deterministic score。

## 10. Dialog 與 A11y

- `role=dialog`、`aria-modal=true`、`aria-labelledby`。
- 開啟後焦點進入 dialog；Tab／Shift+Tab 循環。
- Escape、close、backdrop 行為一致。
- 關閉後恢復 opener focus。
- 保存／恢復 body overflow 與 overscroll behavior。
- iOS rubber-band 不穿透背景。
- 事件長文保留換行，展開控制有 `aria-expanded`。

## 11. 四階閱讀模式（後續）

| 模式 | 內容 |
|---|---|
| 小白 | 白話健康度、名詞 tooltip、強化風險警語 |
| 一般 | 個股、Podcast、雙鏈與標籤 |
| 分析師 | source conflict、雙向證據、PIT 5／20／60 |
| Auditor | 三種時間、hash、品質折減、治理版本、audit |

所有模式讀取同一份 report，不得在前端重算或產生不同分數。

## 12. UI Release Checklist

- [ ] Mobile／iPad／desktop 無水平 overflow。
- [ ] 所有主要控制 ≥44×44。
- [ ] K 線替代表格、keyboard、touch、Escape 通過。
- [ ] Modal focus trap、restore、scroll lock 通過。
- [ ] empty／unavailable／partial／stale／fallback 文案正確。
- [ ] blocked 不公開；null 不顯示 0。
- [ ] report history 日期與 provenance 同步。
- [ ] 實際色彩通過 WCAG AA。
- [ ] iOS Safari、Android Chrome、iPad Safari 實機通過。
- [ ] VoiceOver、TalkBack 完整路徑通過。
- [ ] raw payload、secret、敏感 URL、traceback 不出現在 DOM／network response。
- [ ] 資料營運中心九個分頁一次只顯示一個 panel，query-string deep link、鍵盤 tabs 與 responsive 導覽通過。
- [ ] 股票狀態、execution、DQ／quarantine 與 Mart 分析均以結構化表格呈現，沒有 raw JSON 主視圖。
- [ ] Prompt revision 的 draft／diff／activate／retire 與來源候選審查 gate 有 audit，保存不觸發 Job。
