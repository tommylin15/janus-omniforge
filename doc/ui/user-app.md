# Janus UI — User App 頁面

更新：2026-10-05

## 5. User App 頁面

本文件只保存目前有效的 User App 資訊架構與狀態語意。被取代的「五個生成式 role／CIO」UI 不再是 active contract；現行研究架構為 persisted 五 specialist + authorized manual On-demand CEO。

## 5.0 Final Visual Contract

手機版最終 presentation target 由 [`reference/user-app-final/README.md`](reference/user-app-final/README.md) 定義，固定四張圖：

- `reference/user-app-final/today.png` — 今日
- `reference/user-app-final/watchlist.png` — 關注
- `reference/user-app-final/ledger.png` — 記帳／筆記
- `reference/user-app-final/stock-detail.png` — 個股詳情

圖片規範資訊架構、section order、card hierarchy、手機資訊密度與視覺語言；sample price、PnL、法人金額、日期、AI prose、健康度、logo、sparkline、mock chart 只作 illustrative，不得 hard-code 或當 canonical data。

資料正確性、missing／stale／partial／blocked、auth／owner isolation、PIT／provenance、source authorization、canonical number、publication 與 LLM boundary 以 active SPEC／WBS／runtime contract 為準。PNG 未 commit 或 live acceptance 未完成時不得宣稱 final visual convergence 完成。

對 A 組而言，Final Visual Contract 不是後續 cosmetic polish。Today／Watchlist／Ledger／Stock Detail 的**非 AI 主體 UI**必須在既有 GCP dev、真實登入、真實 owner、真實資料與真實 API/runtime 下先明顯收斂；至少包含 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout、390px 級版面，以及 loading／empty／error／partial／stale／missing 不破壞主要 hierarchy。若真實畫面仍明顯像 legacy UI，即為 A 組 acceptance failure／implementation gap。

Specialist／CEO 等 AI-only 區塊未就緒時，可以 bounded unavailable／hidden／partial；不得因 AI 尚未完成而保留舊版非 AI layout。A 組的真實驗收發現 UI/data-state/functional gap 後，需回到 implementation 修正並重新部署／重驗，不能只留下報告。

## 5.1 今日

「今日」是市場入口，先顯示 deterministic published market baseline；Mart／研究內容是 enhancement，不得反過來阻擋 baseline。

首屏順序：

1. `MarketSnapshotCard`
2. `MarketActivityCard`
3. `InstitutionalFlowCard`
4. `MarketRegimeCard`（Mart 可用時）
5. `DailyBriefCard`（最多三則）
6. `SectorRotationList`／`HotTopicList`／`CandidateHealthList`（各自 persisted data 可用時）
7. 各區塊自己的日期、freshness、coverage、partial／stale／fallback／missing 與 disclaimer

Deterministic market cards 可保留 source-specific `as_of`／trade date；Mart 子產品必須使用同一 `analysis_as_of`，不得把不同日期的最新版拼成「今日分析」。

單一 dependency timeout／error 不得造成永久 spinner；`mart_daily_brief` 未就緒只退化研究區塊，不讓 deterministic baseline 整頁不可用。

## 5.2 關注

以 authenticated owner 的 active watchlist 為中心，不顯示平台推薦榜，也不因搜尋／page load 觸發 scraper、Agent 或 LLM。

- 搜尋支援股票代號與中文名稱，使用 canonical stock-master search contract。
- 新加入受目前有效約 500 market universe 與最多 50 active distinct symbols guard 約束。
- 既有關注離開 500 時保留並標明狀態，不因 universe 變更自動刪除。
- 顯示 canonical name＋symbol、recent persisted price／date、held state、target price、pending note／follow-up、bounded missing／stale。
- add／remove／reorder、target price／note 都走 backend contract；Flutter 不自行建立 owner mapping 或 admission 規則。
- 點擊股票進 Stock Detail。

## 5.3 個股詳情

Primary content 固定順序：

1. `StockHeader`
2. 個人持股、成本與估值日期
3. 個人筆記與待追蹤事項
4. `StockHealthCard`
5. `AiPlainLanguageCard`
6. 三項「為什麼」與三項「要注意什麼」
7. `ChipsStatusCard`
8. `CompanyEventTimeline`
9. 可收合 `EvidenceAndSources`
10. `ComplianceDisclaimer`

K 線、deterministic Fact Pack、五 specialist outputs、CEO report、估值指標與完整 provenance 屬 Advanced section，預設位於 primary content 後且可收合。

### 5.3.1 五 specialist

五 specialist 是 persisted Python／SQL／ML production outputs：

- Fundamental
- Valuation
- Quant
- Risk／Regime
- Event／Catalyst

User 只讀已持久化／validated artifact；plain-language 來自 structured output + SHAP／rules／templates，正常 path 不需要 LLM API。

每個 specialist 顯示與產品有關的：

- analysis/data as-of；
- status／freshness；
- 主要 metrics／drivers；
- missing／stale／partial；
- evidence／provenance；
- what changed（如有）。

模型版本、input hash、snapshot、完整 feature contribution 等工程資訊放 Advanced detail，不搶 primary UX。

### 5.3.2 On-demand CEO

CEO report 是 symbol-level persisted research artifact，不是 page-load narrator。

- 沒有有效 CEO report：顯示「尚無 CEO 分析」或 bounded unavailable；不得自動呼叫 LLM。
- 有 report：顯示 report as-of、產生時間、specialist freshness/material delta、status、主要 thesis／risks／unknowns。
- 只有 backend capability（例如 `ceo_analysis.request`）允許的使用者才顯示 `分析`／`重新分析`。
- 點擊後建立新的 immutable execution；舊 report 保留，不原地覆寫。
- request 需受 in-flight、quota／cooldown、profile／provider approval 等 backend guard；Flutter visibility 不代表 authorization。
- CEO 不計算或覆寫 canonical number，validator failure 顯示 structured partial／blocked。

### 5.3.3 歷史

歷史可依 `analysis_as_of`／execution／artifact version 檢視：

- facts／Fact Pack；
- specialist outputs；
- CEO reports；
- provenance／source references。

歷史 artifact immutable；不得借用最新資料回填舊 artifact 的 null／unknown。

未知／停用股票顯示 404；已啟用但資料或 specialist 尚未產生時顯示 bounded waiting／unavailable，不以 placeholder 冒充完成。

## 5.4 個人記帳與筆記

本頁是 P0 主功能，不依賴公開 Mart／LLM。使用 segmented control 切換「記帳／筆記」；進入記帳預設次導航為 **持股**，Ledger 次導航至少包含 **持股／紀錄／報表**。

### 5.4.1 Ledger／operational projection

- 交易與更正使用 append-only ledger／correction semantics。
- mutation 成功表示 ledger 已持久化；backend 同步更新 deterministic operational position projection，讓 shares／average cost／cash impact 可立即反映。
- Flutter 不計算 authoritative holdings、PnL、exposure、performance。
- Private Mart 仍擁有 canonical valuation／PnL／exposure／performance／reconciliation；若尚未追上，UI 明示 valuation date／checkpoint／pending。
- 正式 aggregate 若因 missing／stale／valuation-date mismatch 不可靠，backend withheld 並回 bounded diagnosis；Flutter 不忽略缺值自行加總。
- 「持股／紀錄／報表」上方 holdings summary 必須共享同一 canonical position／valuation semantics，或能清楚追溯至同一 canonical state 與不同 as-of／freshness checkpoint。tab 切換不得因各自 state、provider/repository、cache 或舊 endpoint 而顯示不同版本的無說明 snapshot。

Ledger／Holdings 一致性至少涵蓋 shares、cost／average cost、market value、unrealized PnL、realized PnL、YTD realized PnL、valuation date、as-of／data freshness、pending transaction／pending Private Mart。若不同 subview 的數值不同，UI 必須能表達其正式 freshness／as-of 差異；不能讓使用者看到無解釋的互相矛盾摘要。

### 5.4.2 持股

第一屏資料可用時優先顯示：

- aggregate market value；
- unrealized PnL／return；
- YTD realized PnL；
- valuation date／status。

手機持股用可掃描 card：canonical name／symbol、shares、market price／average cost、unrealized PnL／return、price／valuation status。operational shares／cost 與 Private Mart valuation／PnL 的資料時間必須分開呈現。

持股分頁保留既有 MIS 行情更新：盤中且 App 位於前景／持股分頁時每 30 秒 revalidate；盤後／休市進入持股分頁只取一次，並保留可見的「更新即時報價」手動入口。離開持股、App 進背景或市場關閉後停止輪詢；更新失敗保留最後成功資料並明示報價狀態，不以失敗回應覆寫 canonical EOD／Private Mart。

YTD realized PnL 必須有明確 display semantics：

- 當年度確定沒有已實現交易，且 canonical aggregate 可確認零值時，顯示 `0`；
- 資料不足、projection／Private Mart 尚待刷新、valuation/as-of 不一致時，顯示 bounded empty／unavailable／pending，而不是用假 `0` 補值；
- 已有已實現交易且 authoritative aggregate 可用時，不得長期缺值或完全不顯示。

### 5.4.3 紀錄

資訊架構：`年份 → 月份 → 單筆交易`。

月份摘要至少分開：

- 買進支出
- 賣出回收
- 股利收入
- 已實現損益

cash flow 與 PnL 不得混為同義。年度紀錄細項提供「按月份／按個股」切換；按個股彙總同樣分開買進支出、賣出回收、股利收入、已實現損益與交易筆數，且必須由 backend／Private Mart 使用同一 moving-average、fee／tax 與 correction semantics 產生，不由 Flutter 從目前畫面交易自行計算 authoritative aggregate。單筆顯示日期、event type、canonical name／symbol、適用時的 shares × price、net cash flow；detail 再顯示總額、fee、tax、currency、note、ledger metadata 與「建立更正」。

交易類型目前為買進、賣出、現金股利、股票股利；backend 負責 fee／tax rule 與 persisted rule/profile version。

切換到「紀錄」時，上方 holdings summary 仍讀共用 canonical state；Records 本身顯示 ledger transactions 與其 own as-of，但不得因 subview local state 保留過期 holdings snapshot。若 transaction mutation 已成功而 aggregate 尚未刷新，需明示 pending／checkpoint，不得默默顯示舊摘要。

### 5.4.4 報表／refresh semantics

- 報表／圖表只讀 canonical backend／Private Mart aggregate，不由 Flutter 從局部交易或目前畫面資料自行重算正式 PnL／performance。
- 報表頁上方 holdings summary 與「持股／紀錄」共用同一 canonical state；不得因 tab 切換維持不同版本的舊 summary。
- 報表需顯示可判讀的 valuation date／as-of／freshness／pending／stale 狀態。若 aggregation 尚未追上 transaction／position projection，應顯示 bounded pending，而不是把舊數值當最新。
- 交易新增、修改、同步或 position projection 更新後，Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 都必須進入一致的 refresh／invalidation 流程；舊 cache 不得長時間殘留而沒有 freshness 說明。
- 真正更新機制以 backend/runtime contract 為準。若採 batch，正式 evidence 應能指出 Job、Scheduler／trigger、頻率、source table、target projection、freshness SLA 與 failure 行為；若非 batch，應能追溯 event-driven／synchronous／materialization 的實際鏈路。UI 不得在 root cause 未查明前把 stale report 解釋成「正常等待批次」。
- Reports acceptance 必須追查並對齊 report API、transaction source、position projection、report aggregation source、DB table/view/materialized projection、cache TTL/invalidation 與 transaction 入帳後更新鏈路；最後以 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。

### 5.4.5 Broker Profile／cash

私人 Broker Profile 可保存 current cash／cash strategy、fee discount multiplier、minimum fee 與 rule/profile version。現金優先由可稽核 cash ledger（opening/deposit/withdrawal/trade/dividend）推導；任何 CASH_IN／CASH_OUT／adjustment 仍須 append-only／audit。

目前 canonical cost method 維持移動平均法；未核准 FIFO 前不提供任意切換。scenario／預計交易不得直接寫正式 ledger／PnL。

### 5.4.6 Notes

一般筆記使用 revision model，可獨立存在或連結股票／交易；支援文字、股票、年份與 pending follow-up filter。修改保留歷史版本。

## 5.5 行情 read path

行情採 DB-first／stale-while-revalidate：先顯示 latest successful operational quote／valuation read model，再由 backend 依 market session／approved routing refresh。

routing 是 backend versioned contract，不由 Flutter hard-code。未核准 source 必須跳過／blocked；source、quote_at、received_at、session、freshness、status 需可追溯。盤中 operational quote 不覆寫 canonical Core OHLCV 或 Private Mart EOD valuation。

缺值明示 missing；不得用掛單價、舊正式估值或 0 偽裝成交價。

## 5.6 資產與風險

- 顯示總資產、現金水位、持股、估值日期與缺價狀態；正式數值只讀 Private Mart。
- exposure 先以可讀比例／列表呈現；跨產業 membership 需版本化分攤說明。
- 年度績效顯示 realized PnL、dividend、fees/tax、trade count、XIRR status；無根、多根或資料不足不得顯示 0%。
- stress test 顯示 deterministic scenario 與 data as-of；Janus UI 不提供模型 runtime selector。

## 5.7 我的

- theme：light／dark／system；字體縮放跟隨系統。
- 投資屬性可含 risk tolerance、horizon、primary goal、minimum cash ratio；提供給外部 AI 前需明確 opt-in。
- 提供 Janus 私人資料匯出與可稽核刪除；`CLEANUP_PENDING` 不得顯示完成。
- 不放方案定價、公開績效排行榜、預測戰績或券商同步控制。

## 5.8 Research Context（Planned）

在既有資訊架構中增量呈現：

- market regime／deterministic signal summary；
- research thesis supporting／invalidating evidence；
- candidate／strategy state；
- 可用時的 supply-chain exposure／signal；
- portfolio impact；
- provenance／freshness／missing data。

不另建聊天面板；Janus ResearchContext 由 bounded API／MCP 提供。private section 仍受 owner auth 與明確授權。

## 5.9 Loading／效能

- 主 navigation 頁保持 persistent state；切頁不無條件重送全部 API。
- 不在 widget `build()` 內建立會因 rebuild 重送的 request future。
- composite screen 使用 section-level loading／partial；已持久化資料可先顯示再 revalidate。
- backend latency root cause 必須先量測 auth、DB、Iceberg、fan-out、p50／p95；沒有 evidence 不預設 CPU／RAM／index 是原因。
- high-frequency read 優先 bounded DB read model／cache／connection pool；GET 不做與讀取無關的 retirement write。

## 5.10 數值顯示

- 使用共用 typed formatter，不讓各 widget raw interpolation。
- 股價語意固定 2 位小數。
- 金額、股數、比例依產品契約四捨五入整數、comma 千分位；負數用括號。
- symbol、日期、version、hash、decimal trade input 保留原語意。
- targeted／golden regression 覆蓋主要格式。

## 5.11 跨專案邊界

Janus User App 不提供 Chat／Ask Janus／provider／runtime／MCP／Skills／approval 產品入口。generic conversation UI 由 omniAgent 持有；Janus 透過 authenticated bounded API／MCP 提供投資 context。

任何 UI completion 都必須依真實 backend capability 呈現；missing／stale／partial／unavailable／blocked 不得用 sample／placeholder 補成成功。
