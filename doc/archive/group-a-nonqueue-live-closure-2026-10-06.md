# A 組非佇列結案 — 2026-10-06

狀態：本次授權的非佇列 A 組工作完成；交易佇列／真實 mutation／duplicate guard 由使用者另行驗收，未宣稱通過。

## 使用者決定

- 手機入口、icon 重開與手機效能：使用者回報可進入並有數據，要求直接當作完成。未提供 p95、樣本數或裝置資訊，不補造量測。
- 使用者表示「佇列我還在調整」「這塊你先不驗，我另外驗收」。停止佇列寫入、重跑與 mutation acceptance；原先佇列列號的已處理狀態不能作為本對話請求入帳證據。交易未在本次宣稱完成。

## Implementation／CI／deployment

- 真實畫面缺陷閉環：法人正式股數欄位、exact decimal 科學記號／零值、獨立 stock-master／persisted price header、section-first 更新、Google 公共憑證 cache、bounded exact-snapshot Private Mart cache、治理 GCS SDK。
- `dc6174e9ae3bd77321647964811e11b9d99b9ae1`：mobile consumer 使用既有 API writer，Mart 繼續使用 pipeline role；不新增 IAM／SQL grant。390px Watchlist 使用 Flutter 原生 long-press reorder，修正 desktop 預設拖曳圖示遮住行情。
- `7a5a1f931e7907ed9423684d432863e725bc0b04`：補齊既有公開 bucket 設定，使治理頁能讀 persisted receipts。
- Deploy `37426231912` 與最終 `37426621108` success；Flutter `37426231790` success；Portfolio contract `37426231943`、`37426620811` success。最終 dev workflow 的 API／ingestion／Mart tests、deploy／verify 均 success，未啟用模型呼叫。
- Ready `janus-api-g7a5a1f931e79-config`，100% traffic；canonical `/app/build-id.txt` 為上述完整 SHA。Image `us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api@sha256:4099bbf336666fb2b8c1f1957677dac02b1220f1653b30df9dc9b9b7bfbdf426`。
- 本機直接相關 Python 8 passed、擴大 portfolio／Admin／public runtime 67 passed；Flutter final visual 8 passed，含 Windows platform 390px overlap regression。WSL `bash -n` 與 `git diff --check` 通過。此前回歸及原 PNG references 見 authenticated defect closure／non-live closure。

## 真實 authenticated browser evidence

- Chrome 真實 User／Admin Google session；四頁使用 canonical dev URL，CSS 390×844、DPR 1.5，PNG 585×1266。已核對 hierarchy、section order、spacing、主要色彩、數字格式、資料日期與 bounded missing／unavailable；未把 desktop 模擬當手機證據。
- Today：市場基礎資料獨立於 unavailable 研究內容，法人明示淨股數。
- Watchlist：中文 identity、價格／行情日、持有／未持有、配額與離榜保留說明；價格 badge 不再重疊拖曳圖示。實際離榜保留異常情境由 targeted regression 覆蓋，未造 live 離榜資料。
- Ledger：Holdings／Records／Reports 上方共用同一版本摘要；正式 YTD、monthly realized PnL 與年度績效可見，未在前端重算。交易後 mutation／duplicate guard 明確由使用者接手，不以 read-only evidence 代替。
- Stock Detail：中文名稱與 persisted 行情先載入，持股資料可見；AI-only 區塊明確未就緒，開頁沒有 LLM 呼叫。
- Admin 六頁：actionable 總覽與 DQ；backend batch 定義／排程／執行；中文搜尋與 stock health；有效 500 檔及版本／進出名單；Specialist／CEO 明確未啟用；治理容量與保留政策。歷史失敗、未知部署 metadata 不偽裝成功。
- 治理讀回 Stage 8,609 objects／464,597,479 bytes、Core 6,553／120,063,849，maintenance 2026-10-05T16:50:33.216Z；Mart 1,413／17,487,021，maintenance 2026-10-05T15:38:18.784Z。這是 persisted receipt 時點，不是即時 billable inventory；noncurrent／soft-deleted／billable bytes 仍未知。Private retention 未定義，僅去識別化 operations metadata。
- 私人截圖保存在本機 artifact：`today.png`、`watchlist.png`、`ledger.png`、`stock-detail.png`，不提交持股／交易截圖或其他私人資料到 GitHub。

## Runtime／效能／營運邊界

- 未登入 `/api/v1/me/profile`、`/api/v1/admin/data-governance` 各 401。
- Public market-home 三次 desktop HTTP elapsed 7.361／0.330／0.299 秒；暖 cache 改善可見，但兩筆暖機值不是 p95，不宣稱量測達到手機 SLO。先前 uncached baseline 14.473／8.110／7.248 秒不可與手機樣本混用。
- 既有 hourly Scheduler ENABLED，Asia/Taipei `30 * * * *`；沿用既有 controller／Private Pipeline。既有公開 retention apply/readback、serving projection 042、Quote Router／Broker Profile、owner/audience safety evidence 由前述 closure／canonical CI 延續，不重跑清理。
- 本輪 controller 診斷 `janus-batch-controller-5wn8l` success；早前 120 秒逾時與 queue DB role failure 均保留為歷史失敗。未永久提高資源或 timeout，未新增 Scheduler／Cloud Run／付費資源／production deployment。

## 封存的 A 組 acceptance 索引

以下是結案前的原 acceptance，checkbox 是歷史狀態；目前狀態以上文與 active TODO 為準。

## A 組新增／明確化 acceptance

> 2026-10-06 使用者最新驗收指示：手機已可進入並顯示效能數據，使用者要求「這個直接當作完成」。Android 入口／icon 重開與手機效能 gate 因此結案，不再要求補手機樣本；未提供的 p95／樣本數／裝置資訊不記為已量測達標。下列歷史 checkpoint 的手機 pending 敘述由本指示取代；其餘 live UI、deployment 與真實 mutation acceptance 不受影響。

> 2026-10-06 desktop authenticated checkpoint：已可使用 Chrome 真實 User／Admin。本次畫面驗收發現並修正法人欄位、科學記號零值、個股 baseline 與治理 SDK 缺漏；修正版部署後證據仍待取得，A 維持 partial。Mobile queue writer／owner binding probe 成功；Android、真實 mutation/mobile enqueue、手機效能 gate 保留。見 [`archive/group-a-authenticated-defect-closure-2026-10-06.md`](../archive/group-a-authenticated-defect-closure-2026-10-06.md)。

A 組目前狀態定義：**部分功能已完成並進入 GCP dev 真實驗收，仍可能由真實驗收發現 implementation gap；發現後必須回到實作修正。** 進入驗收不等於 implementation 已全部完成，也不等於只剩 acceptance。

> 2026-10-06 non-live closure：已知可直接由 code／tests／migration／deployment 關閉的 A 組缺口（Final Visual production path、Admin PWA identity、YTD 三態、Ledger correction/refresh、Admin Private operations、canonical-data charts）已完成並部署。下列 checkbox 仍不勾選，因其 acceptance 包含 authenticated browser／real owner mutation／performance／scheduler/storage live evidence。證據見 [`archive/group-a-nonlive-closure-2026-10-06.md`](../archive/group-a-nonlive-closure-2026-10-06.md)。

> 2026-10-06 live-auto closure：PWA runtime identity／未登入負向、current-owner canonical read consistency、batch-controller→Private Pipeline trigger／failure-recovery evidence、retention apply receipts 已取得；舊 direct Private schedulers 已退役且 137 targeted ingestion tests passed。**目前剩餘 A gate 僅為 Android 安裝重開、authenticated 四頁/Admin UI、真實 owner transaction mutation chain、真機效能。** 詳見 [`archive/group-a-live-auto-acceptance-2026-10-06.md`](../archive/group-a-live-auto-acceptance-2026-10-06.md)。

- [ ] **四頁 Final Visual Contract 是 A 組正式結案 gate。** Today／Watchlist／Ledger／Stock Detail 必須在既有 GCP dev 的真實登入、真實使用者、真實資料、真實 API/runtime 下，非 AI 主體 UI 明顯收斂至 [`ui/reference/user-app-final/`](../ui/reference/user-app-final/)；至少核對 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout、390px 寬度版面，以及 loading／empty／error／partial／stale／missing 不破壞主要 layout。若真實畫面仍明顯像 legacy UI、與四張 reference 差異很大，視為 A 組 acceptance failure／implementation gap，不是後續 cosmetic polish。
- [ ] **A 組不得把基本 UI convergence 延後到 B／C。** Specialist outputs、CEO analysis、AI-dependent content、capability/history/freshness 與最終 AI integration 可由 B／C 完成；AI-only 區塊未就緒時可 bounded unavailable／hidden／partial，但不得因此保留舊版非 AI layout。
- [ ] **A 組完成不得由單一技術成功條件推定。** API 200、migration、auth、backend deploy、Flutter/widget tests、build 或 Cloud Run revision 更新都不能單獨使 A 組 `done`；四頁非 AI 主體 UI 尚未在真實 GCP dev 明顯收斂，狀態維持 `partial`。
- [ ] **真實驗收失敗必須形成工程閉環。** 對 UI、data state 或功能缺陷完成「定位 → 修正 → 測試 → commit/push → dev 部署 → 使用同一 GCP dev URL 重驗」；驗收失敗是 implementation 工作輸入，不只留報告或修正建議。
- [ ] 修正個股頁 build 內建立 request future／整頁 Future.wait／無效 retry；section-first、進階按需載入；已訪問頁保留狀態，隱藏／背景停止輪詢，owner 切換清除私人 cache。
- [ ] 關注股離榜保留並標示；GET 不 retirement write／隱藏離榜股；同步核對 DB function／trigger、quota、Deep Coverage 及所有 caller。
- [ ] 重用已完成 042 serving projection，驗證 freshness／分頁／fallback；依 profiling 改善剩餘 Iceberg scan/filter、摘要、lock、DB connection、驗證憑證 cache 與重複 user upsert，不建立第二套 canonical store。
- [ ] Quote Router／persisted last quote／Broker Profile 完成；041 transaction position projection 重用並補剩餘整合驗收，不重做已完成 migration／backfill。
- [ ] 四頁 UI／formatter／中文搜尋與 partial 白話狀態收斂；修復可追溯的 PNG reference，缺原始資產時只保留受影響 visual blocker。
- [ ] **Ledger YTD realized P&L。** 查明是否已完整實作本年已實現損益、canonical source（transaction／position projection／DB aggregate／serving layer）、交易後更新時點與 refresh 方式；當年度確定無已實現交易時依正式 contract 顯示 `0`，資料不足／尚待刷新時用 empty／unavailable／pending 的明確語意，不得以假 `0` 補值；有已實現交易時不得長期缺值或完全不顯示。此功能不依賴 AI，若不完整即為 A 組 gap。
- [ ] **Ledger Holdings／Records／Reports summary 同步。** 三個 subview 上方 holdings summary 必須共用同一 canonical position/holdings semantics 或可追溯至同一 canonical position state；不得因 tab 各自 state、provider/repository、cache、refresh、舊 endpoint、不同 position source 或 valuation/as-of 語意而顯示不同版本的舊 snapshot。若「持股」已有新資料而「紀錄／報表」仍舊，直接列 A 組 UI/data-state acceptance failure，不以「整個批次尚未跑」概括。
- [ ] **Ledger Reports refresh／aggregation chain。** 明確追查 report API、transaction source、position projection、report aggregation、DB table/view/materialized projection、可能的 batch/job、scheduler/trigger、cache TTL/invalidation、valuation date/as-of 與 transaction 入帳後更新鏈路；最後依 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。root cause 未查明前不得寫成「正常等待批次」。
- [ ] **Ledger／Holdings canonical consistency。** 同一使用者、同一時間、同一資產的 shares、cost、market value、unrealized PnL、realized PnL、YTD realized PnL、valuation date、as-of/data freshness、pending transaction／pending Private Mart 必須一致或有可追溯的時間／freshness 差異說明；不得在持股／紀錄／報表出現無說明的不同版本摘要。
- [ ] **交易異動後 refresh/invalidation acceptance。** 新增／修改／同步交易或 position projection 更新後，驗證 Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 都會刷新，舊 cache 不長時間殘留，valuation/as-of 可判斷是否更新。若採 batch，文件與 runtime evidence 必須指出 Job、Scheduler/trigger、頻率、source table、target projection、freshness SLA、failure 行為；若非 batch，同樣寫清真正更新鏈路。
- [ ] **ChatGPT ledger write：desktop MCP + mobile ingress。** Desktop/web MCP implementation／CI／dev rollout 已完成：main `d494acb43b4ed079aabb6540203f654ec64e65fe`、Deploy dev run `37410282220` success、MCP tagged acceptance success；但目前 ChatGPT mobile 不載入自訂 MCP，因此手機改走 native Google Drive connector → `janusChatGPT/Janus Mobile Ledger Queue` → existing hourly batch controller → existing Private Pipeline → canonical ledger。mobile bridge 必須維持：owner 不可由 row 指定、Drive owner 唯一映射既有 Janus user、fee/tax/交易值不得猜、stable request_id idempotency、最多 20 pending／999-request bounded scan、provider outage fail-defer、domain error sanitized、不新增 Scheduler／Cloud Run resource、不影響原 21:30 Private Mart。**剩餘 gate**：CI/live workload probes、手機 native Drive enqueue、真實 owner canonical append/readback、duplicate guard、Private Mart refresh；不得自行製造測試交易。
- [ ] Admin 以 backend effective jobs 呈現，資料治理取代 placeholder；容量區分 live／noncurrent／soft-deleted，未知不補零；本人缺價／coverage 與 Admin 去識別化摘要分離。
- [ ] 依既定資料容忍度顯示上市 500 範圍、缺值、時間與非嚴格 PIT 限制，保留價格／單位／身份／來源／交易正確性；現有報酬涉及 corporate action 時明示不可比，不新增完整調整價平台。
- [ ] 完成前後效能紀錄、Job duration／peak RSS／retry／cache／storage／可取得的成本證據；暖機核心資訊 p95 ≤2 秒、已訪問頁恢復 ≤300ms 作驗收目標，記錄樣本與裝置，未達列剩餘瓶頸。**量測 instrumentation 已於 `21413e56` 部署：`/app/?perf=1` 顯示 core／restore p95 與樣本數；Flutter run `37412540230`、Deploy run `37412540399` success。剩餘為真實手機樣本，不再缺量測機制。**
- [ ] 檢查 cleanup 成本與回收效益、有效 GCS retention 設定；避免空轉／重複執行，不自行改 retention 時限、提高付費資源或新增 IAM／服務。
- [ ] 對齊舊 coverage inventory、status、batch 清單與已完成／待驗證工作；沿用既有 042 完成證據，041／compaction／retrain 依最新 evidence 判定，不把程式存在當 live 完成。

> **A 組不是「部署完成後做驗收」，而是「在真實 GCP dev 驗收中持續發現並關閉 implementation gap」；Today、Watchlist、Ledger、Stock Detail 的非 AI 主體 UI 必須在真實登入與真實資料下明顯收斂至 Final Visual Contract，且 Holdings／Records／Reports 必須共用一致、可追溯且可刷新之 canonical position state，否則 A 組維持 partial。**

