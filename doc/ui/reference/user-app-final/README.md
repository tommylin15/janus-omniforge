# Janus User App Final Visual Contract

更新：2026-10-05
狀態：**Active / normative presentation target**

本目錄定義 Janus User App 手機版的最終 presentation target。它不是 brainstorm、disposable mockup 或僅供靈感使用的 reference；後續 User App implementation 應逐步 convergence 至此處定義的四個畫面與 `doc/ui/user-app.md` 的正式資訊架構。

## 固定圖片路徑

- `doc/ui/reference/user-app-final/today.png` — 今日
- `doc/ui/reference/user-app-final/watchlist.png` — 關注
- `doc/ui/reference/user-app-final/ledger.png` — 記帳／筆記
- `doc/ui/reference/user-app-final/stock-detail.png` — 個股詳情

PNG binary 尚未 commit 前，只能說 path／contract 已固定；不得宣稱 final screenshot reference 或 visual acceptance 已完成。

### 原圖來源與完整性

2026-10-05 使用者在 Codex「查看最新工作項目」對話重新提供四張原圖，已以原始 bytes 保存至上述固定路徑，未縮圖、重畫或改色。四張皆為 941×1672；已驗證所有 PNG chunk CRC、完整解碼及來源／目的檔 bytes 相同。此結果只解除 reference 資產損壞，不代表 Flutter／golden／dev browser 已驗收。

| 原圖 | SHA-256 |
|---|---|
| 今日 | `5c742ef0c312c6682eab4de73f757ba8bced1da8b748056b26f5240499d16ffb` |
| 關注 | `9c059b288f1c2c58e08fdee5294dae3462cc8060402e43f81443ab4fa7f47f17` |
| 記帳／筆記 | `6bb87aff600febfaea2a25d62b0bf3dd33bf1cfb51b75b68b3b6305a923af344` |
| 個股詳情 | `f997cb96ba9c168f177db5f95ede05c748bb48b3be76e760cfc50c26cc256d05` |

### 實際原圖解讀

- 共通：淺藍灰背景、白色圓角卡、深藍主要文字、teal 圖示與選取狀態；卡片以留白與淡色分區建立層級。手機外框、狀態列與 Dynamic Island 是示意裝置，不是 App 元件。資料狀態有文字與圖示，不只靠顏色。
- 今日：指數雙卡 → 市場活動／法人動向 → 市場判讀 → 今日三件事 → 產業輪動／熱門話題 → 候選股健康 → 全市場篩選。390 px 寬度能容納時保留雙欄短卡；字體放大或內容過長時改單欄，順序不變。baseline 與研究區塊分開載入，圖中分析文案與走勢不得作為真實資料。
- 關注：名稱／代號搜尋 → 實際關注數／50 與新加入 500 範圍說明 → 我的關注／排序 → 股票卡。卡內先名稱／代號與資料日期，再價格／漲跌，最後持股、目標價、待追蹤標籤；離榜股票有明確警示與「仍保留關注」，不得因 GET 或 universe 變動刪除。標籤中的待追蹤是私人筆記狀態，不代表已啟用通知產品。
- 記帳／筆記：正式 aggregate 與估值日／狀態先於持股／紀錄／報表次導覽；持股卡左側是身份、股數、現價／均價，右側是損益／報酬。最近紀錄另成卡；建立交易入口與「交易已保存、批次尚待更新」語意分開。走勢只在 canonical backend 資料可用時顯示。
- 個股詳情：股票標頭 → 我的持股 → 筆記與待追蹤 → 五面向健康度 → 白話摘要 → 三項支持／三項風險 → 籌碼／公司事件 → 可展開證據來源 → 進階資料 → 免責說明。健康度、摘要與風險不應被 K 線／工程 metadata 阻擋；進階資料按需載入。
- 圖中的紅漲綠跌為台股視覺慣例，仍須搭配正負號／箭頭；股價顯示與其他數值格式以 `user-app.md` 為準。樣本價格、日期、比例、logo、sparkline 不進 runtime。
- 原圖有通知鈴與 legacy `CIO` 文字；依 2026-10-05 active scope，不實作預警／推播，分析命名採 On-demand CEO。圖中「籌碼與定位」只是 presentation 名稱，不建立第六個 specialist；五引擎仍依 active specialist SPEC。

## 權威邊界

Final Visual Contract 的權威範圍是 presentation：資訊架構、section order、component hierarchy、手機資訊密度、主要 navigation、card-based 視覺語言與跨頁一致性。

下列事項仍以 active SPEC／API／schema／Mart／Private Mart／治理契約為準：

- canonical number、PnL、valuation、price、score、confidence、publication state；
- missing／stale／partial／fallback／blocked／insufficient-data；
- auth／owner isolation／privacy／security；
- PIT／future leakage／provenance／source authorization；
- specialist／CEO 不得計算或改寫 canonical facts；
- 尚未完成的 Fact Pack、specialist、CEO、即時行情或 source capability 不得因圖片存在而假裝可用。

## Normative presentation

- 手機版以單欄、可掃描的 Material 3 card layout 為主。
- Janus 使用一致的 cyan／teal 主視覺、清楚字階、適度留白與圓角卡片。
- 底部主要 navigation 維持「今日」、「關注」、「記帳／筆記」、「我的」。
- primary information 先於 advanced information；進階資料不得搶在健康度、持股、白話摘要前。
- 手機版不得退回高密度 Excel 式表格作為主要 UX。
- loading／empty／error／partial／stale／missing 仍維持同一資訊架構，不用永久 spinner 或假資料填滿。

## Illustrative only

以下永遠只作示意：

- sample 股票、價格、漲跌、持股數、PnL、return、法人金額；
- sample date；
- sample research prose、健康度、產業輪動、熱門話題、公司事件；
- logo、sparkline、裝飾 icon／chart；
- 尚未另行 versioned 的 pixel／shadow／microinteraction。

不得把 illustrative value hard-code 進 dev／production canonical flow。

## Visual precedence

1. Data correctness／governance／security／owner isolation：active SPEC／runtime contract 高於圖片。
2. User App information architecture／presentation convergence：本 Final Visual Contract 高於 legacy／temporary layout。
3. Sample values 永遠只屬 illustrative。
4. Final Visual Contract 與 active SPEC 衝突時，先更新 active contract，再宣稱完成。
5. 圖片不存在或 capability 未 live accepted 時維持 pending／partial／blocked，不把 target 當 implementation evidence。

## 四頁 acceptance

### 1. Today Final — `today.png`

- deterministic market baseline 不依賴 Daily Brief／LLM。
- benchmark、market activity、institutional 可各自呈現 date／freshness／coverage／bounded unavailable。
- Mart 可用時顯示 market regime、最多三則 Daily Brief、sector rotation、topics、candidate health；未就緒只退化對應區塊。
- candidate 可進 Stock Detail；Flutter 不重算 score。
- timeout／error 後有 bounded error／retry，不永久 spinner。
- 390 px 級手機不得 overflow。

### 2. Watchlist Final — `watchlist.png`

- 以 authenticated owner 的 active watchlist 為中心，不轉成推薦榜。
- canonical name＋symbol。
- recent persisted price／date；missing／stale 不虛構。
- held state、target price、pending note／follow-up。
- add／remove／reorder；new admission 受有效約 500 universe 與 50 active distinct-symbol guard 約束。
- 既有離榜股票保留並顯示狀態。
- 點擊進 Stock Detail；手機以 stock cards 為主。

### 3. Ledger Final — `ledger.png`

- 第一屏資料可用時優先 aggregate market value、unrealized PnL／return、YTD realized PnL、valuation date／status。
- aggregate withheld 時顯示 bounded diagnosis，不由 Flutter 忽略缺值自行加總。
- 次 navigation 至少有「持股／紀錄／報表」；手機持股使用 card hierarchy。
- 紀錄／報表保留年度 selector（目前年度與前五年）；選定年度後，紀錄細項可切換「按月份／按個股」。已清倉股票不得因不在目前持股而從歷史年度消失；兩種彙總都分開買進支出、賣出回收、股利收入、已實現損益，並可下鑽單筆交易；正式彙總由 backend／Private Mart 產生。
- 單筆交易 detail 同時保留「建立更正」與「刪除交易」。刪除是 append-only reversal-only 操作，必須二次確認；原始 ledger 仍保留 audit trail，不做實體 DELETE。
- 持股頁保留 MIS 行情更新：盤中前景／持股分頁每 30 秒 revalidate，盤後／休市進頁取一次，並提供「更新即時報價」手動入口；離頁／背景停止輪詢。
- ledger mutation 成功只表示交易已保存；Private Mart 尚未更新時明示 pending。
- 報表／圖表只讀 canonical backend／Private Mart。

### 4. Stock Detail Final — `stock-detail.png`

Primary order：

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

Advanced section 可包含 K 線、Fact Pack、五 specialist persisted outputs、On-demand CEO report、估值指標與完整 provenance，且必須位於 primary content 之後。

五 specialist 不呈現為每日五個 LLM workers。CEO report 是 persisted artifact；無 report 時不得 page load 自動呼叫 LLM。只有具 backend capability 的使用者才可顯示 `分析`／`重新分析`，每次建立新 immutable execution/report。

尚未完成 capability 用 bounded unavailable／hidden，不以 placeholder／mock 冒充。

## Cross-screen visual acceptance

宣稱 `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` 完成至少需同時具備：

- 四張 PNG binary 存在固定路徑；
- Flutter targeted／golden／screenshot regression 覆蓋主要 hierarchy 與狀態；
- 390×844 級 viewport 無 overflow、section order 正確；
- GCP dev 真實 authenticated URL／owner／persisted data screenshot acceptance；
- 四頁與本 contract 收斂；
- loading／empty／error／partial／stale／missing 不破壞主要版型；
- sample/mock data 未進 canonical runtime；
- dependency 未完成時維持 bounded unavailable／hidden。

widget、圖片、golden test 或 build 單獨成功都不構成 Final Visual Convergence 完成。

## 工程 agent 使用方式

涉及 User App presentation／layout／visual regression／Product Completeness 或四頁之一時，必須先讀：

1. `doc/PROJECT_RULES.md`
2. `doc/ui/user-app.md`
3. 本檔
4. active TODO／WBS
5. 對應 PNG（如存在）
6. 直接相關 Flutter／API／test／runtime evidence

不得重新發明另一套 User App 資訊架構；implementation 與 target 不同時視為 convergence gap，除非使用者明確修改 active contract。
