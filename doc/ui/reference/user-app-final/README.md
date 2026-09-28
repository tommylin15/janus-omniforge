# Janus User App Final Visual Contract

狀態：**Active / normative presentation target**

本目錄定義 Janus User App 手機版的最終 presentation target。它不是 brainstorm、disposable mockup 或僅供靈感使用的 reference；後續 User App implementation 應逐步 convergence 至此處定義的四個畫面與 `doc/ui/user-app.md` 的正式資訊架構。

## 固定圖片路徑

以下四個 binary 路徑已保留，後續由可寫 binary 的 Git／GitHub 環境補入：

- `doc/ui/reference/user-app-final/today.png` — 今日
- `doc/ui/reference/user-app-final/watchlist.png` — 關注
- `doc/ui/reference/user-app-final/ledger.png` — 記帳／筆記
- `doc/ui/reference/user-app-final/stock-detail.png` — 個股詳情

**目前只有路徑與 contract 被正式固定；PNG binary 尚未 commit 前，不得宣稱 repository 已具備 final screenshot reference，也不得宣稱 visual acceptance 已完成。**

## 權威邊界

Final Visual Contract 的權威範圍是 presentation：資訊架構、區塊順序、component hierarchy、手機版資訊密度、主要導航、卡片式視覺語言與跨頁一致性。

下列事項仍以 canonical SPEC／API／schema／Mart／Private Mart／治理契約為準，圖片不得覆蓋：

- canonical number、PnL、估值、價格、score、confidence 與 publication state；
- missing／stale／partial／fallback／blocked／insufficient-data 語意；
- auth／owner isolation／privacy／security；
- PIT／future leakage／provenance／source authorization；
- LLM 不得計算或改寫 canonical facts；
- 尚未完成的 Fact Pack、五角色、CIO、即時行情或文本來源能力不得因圖片存在而假裝可用。

## Normative 與 illustrative

### Normative presentation

四張圖與本 contract 對以下項目具有規範性：

- 手機版以單欄、可掃描的 card-based Material 3 layout 為主；
- Janus 使用一致的 cyan／teal 主視覺、清楚字階、適度留白與圓角卡片；
- 底部主要導航維持四個既有入口：「今日」、「關注」、「記帳／筆記」、「我的」；
- 各頁主要 section 的順序與 hierarchy 必須符合本檔與 `doc/ui/user-app.md`；
- primary information 先於 advanced information；進階資料不得搶在健康度、持股、白話摘要等主要內容之前；
- 手機版不得退回高密度 Excel 式表格作為主要 UX；
- empty／loading／error／partial 狀態也必須維持同一資訊架構，不得用永久 spinner 或假資料填滿畫面。

### Illustrative only

下列內容只作 mockup 示意，不是 canonical requirement：

- 圖中的台積電／聯發科／中華電價格、漲跌、持股數、PnL、報酬率、法人金額；
- `2026/09/28` 等 sample date；
- sample AI prose、健康度結果、產業輪動文字、熱門話題與公司事件；
- 股票公司 logo、sparkline、裝飾圖示與 mock chart；
- 精確 pixel、陰影強度、單一 icon 樣式或尚未另行 versioned 的 microinteraction。

任何 illustrative value 都不得 hard-code 進 production／dev canonical flow。

## Visual precedence

1. Data correctness、governance、security、owner isolation：canonical SPEC／runtime contract **高於** visual target。
2. User App information architecture、screen composition 與 presentation convergence：Final Visual Contract **高於** legacy Flutter layout／臨時 presentation。
3. Sample numbers、sample stock names、sample AI prose：永遠只屬 illustrative。
4. Final Visual Contract 與 active SPEC 衝突時，不得靜默選邊；必須指出差異並先更新相應 active contract，再宣稱完成。
5. 圖片尚未 commit 或對應 capability 尚未 live accepted 時，狀態維持 pending／partial／blocked，不得把文件 target 當 implementation evidence。

## 四頁 acceptance

### 1. Today Final — `today.png`

- 首屏有「今日」，並沿用既有四個主要導航。
- deterministic market baseline 不依賴 Daily Brief／LLM 完成才可見。
- 加權指數、櫃買指數、市場活動、法人資料可各自呈現日期、freshness、coverage 與 bounded unavailable state。
- Mart 可用時顯示市場判讀、最多三則今日重點、產業輪動、熱門話題與候選股健康；未就緒時只退化相應研究區塊。
- 候選股可進入個股詳情；Flutter 不自行重算 score。
- loading 不得永久阻塞整頁；timeout／error 後應有 bounded error／retry state。
- 390 px 級手機寬度不得 overflow，主要區塊順序與 `today.png` 一致。

### 2. Watchlist Final — `watchlist.png`

- 頁面以使用者自己的 active watchlist 為中心，不轉為平台推薦榜。
- 主要識別顯示 canonical 股票名稱＋代號。
- 顯示最近已持久化行情與資料日期；資料缺失時顯示 bounded missing／stale，而不是虛構價格。
- 顯示持股狀態、目標價、待完成筆記／追蹤事項；可新增／取消／排序。
- 新加入受目前有效 500 檔與 50 distinct active symbols guard 約束；既有離榜股票保留並明示離榜狀態。
- 點擊股票可進入個股詳情。
- 手機版以可掃描 stock cards 為 presentation target，不以高密度表格取代。

### 3. Ledger Final — `ledger.png`

- 第一屏在資料可用時優先顯示 aggregate market value、unrealized PnL、unrealized return、本年 realized PnL、valuation date／status。
- aggregate withheld 時顯示 affected symbols／count 或等價 bounded diagnosis，不由 Flutter 忽略缺值後自行加總。
- 次導航至少有「持股／紀錄／報表」；手機版持股使用兩到三行 card hierarchy。
- 持股顯示 canonical 股票名稱／代號、股數、現價／均價、未實現損益／return 與資料狀態。
- 紀錄遵守 `年份 → 月份 → 單筆交易`；買進支出、賣出回收、股利收入、已實現損益不得混為同一 cash-flow 語意。
- 支援買進／賣出／現金股利／股票股利；成功寫 ledger 後顯示「交易已儲存，等待投資組合批次更新」。
- 報表與圖表只讀 canonical backend／Private Mart；Flutter 不建立新的會計口徑。

### 4. Stock Detail Final — `stock-detail.png`

主要內容順序固定為：

1. `StockHeader`
2. 個人持股、成本與估值日期
3. 個人筆記與待追蹤事項
4. `StockHealthCard`
5. `AiPlainLanguageCard`
6. 三項「為什麼」與三項「要注意什麼」
7. `ChipsStatusCard`
8. `CompanyEventTimeline`
9. 可收合的 `EvidenceAndSources`
10. `ComplianceDisclaimer`

K 線、deterministic Fact Pack、五角色 validated analysis、CIO、估值指標與完整 provenance 屬進階資料，預設位於 primary content 之後且可收合。尚未完成的 capability 不得以 placeholder／mock 冒充；可用時只讀 persisted／validated artifact。

## Cross-screen visual acceptance

宣稱 `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` 完成時，至少要同時具備：

- 對應 PNG binary 已存在上述固定路徑；
- Flutter targeted／golden／screenshot regression 覆蓋主要 hierarchy 與狀態；
- 390×844 級手機 viewport 無 overflow、主要 section order 正確；
- GCP dev 真實 authenticated URL／owner／persisted data 的 screenshot acceptance；
- today／watchlist／ledger／stock-detail 四頁 presentation 與此 contract 收斂；
- loading／empty／error／partial／stale／missing path 不破壞主要版型；
- sample/mock data 未進入 canonical runtime；
- dependency 未完成的 advanced section 維持 bounded unavailable／hidden，而不是 full-success presentation。

單純把 widget 寫完、圖片放進 repository、golden test 通過或 build 成功，都不能單獨宣稱 Final Visual Convergence 完成。

## Codex／工程 agent 使用方式

凡任務涉及 Janus User App presentation、layout、visual regression、Product Completeness 或四頁之一，必須先讀：

1. `doc/PROJECT_RULES.md`
2. `doc/ui/user-app.md`
3. 本檔 `doc/ui/reference/user-app-final/README.md`
4. 對應 active TODO／WBS
5. 對應 PNG（若 binary 已存在）
6. 直接相關 Flutter/API/test/runtime evidence

工程 agent 不得重新發明另一套 User App 資訊架構；若 implementation 與此 target 不同，應視為 convergence gap，除非使用者明確修改 active contract。