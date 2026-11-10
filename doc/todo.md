# Janus — 唯一 Active TODO

## 2026-11-10｜首頁大盤漲跌摘要＋持股當日增減數無符號（Dev 已發布）

- [x] **CODE／UI**：今日大盤摘要可直接看 TAIEX 指數、同日漲跌點數及百分比；同筆報價前收、報價時間／狀態或具日期來源的前一正式 Core 收盤才可計算，缺值不可造漲跌。持股總損益百分比移除尾隨「參考」；當日損益 18px 金額下方改為 **13px 每股當日漲跌數（幅度%）**，例如 `1.50（1.25%）`，兩個量均不出現 `+`/`−`、只以台股紅漲綠跌、平盤中性色區分。持股四欄改頂端對齊，保留非即時 Tooltip 及原損益計算。詳見 [UI 契約](ui/user-app.md)。
- [x] **Flutter 全量測試／正式 Release**：Flutter analyze、widget tests（上漲／下跌顏色、同排、缺值、大盤可信前收、漲跌點數與百分比）及 Web build [#42754292599](https://github.com/tommylin15/janus-omniforge/actions/runs/42754292599) PASS；selective CI [#42754292310](https://github.com/tommylin15/janus-omniforge/actions/runs/42754292310) PASS；Python＋Flutter＋四 GHCR 固定映像／digest [#42754592473](https://github.com/tommylin15/janus-omniforge/actions/runs/42754592473) PASS，實際不可變 Release source SHA `d7df1aa4f21427d99b0fb024c5cb502e381fb118`。
- [x] **Dev 切流與 Live 收據**：0% 候選 [#42755286361](https://github.com/tommylin15/janus-omniforge/actions/runs/42755286361) PASS → OAuth／Owner／Admin／MCP 及公開行情 parity [#42755482662](https://github.com/tommylin15/janus-omniforge/actions/runs/42755482662) PASS → API-only 可回復 100% [#42755637698](https://github.com/tommylin15/janus-omniforge/actions/runs/42755637698) PASS → 獨立唯讀 [#42755780823](https://github.com/tommylin15/janus-omniforge/actions/runs/42755780823) `API_LIVE_READBACK_PASS`：現役 100%、`/app/build-id.txt` 對應固定 SHA、公開行情 HTTP 200 且非空、匿名 Owner 拒絕、`gcp_mutations=0`。舊版本 `219b6a1e85c5d5ee5b57a53d57a42b0b25f2198c` 保留 rollback，無批次／Scheduler／PG／IAM／Owner 寫入。
- [ ] **Owner 手機視覺 UAT**：本人登入 [Janus Dev App](https://janus-api-2oo7qbkd5q-uc.a.run.app/app/) 目視大盤點數／百分比是否首屏可讀、持股負向 `1.50（1.25%）` 是否綠色且無負號、正向紅色是否清楚；無本人登入視覺證據，仍為 NOT_VERIFIED。


## 2026-11-10｜持股股數／損益字級、首頁分鐘圖柔和與資訊上移（已發布，Owner 手機 UAT 待驗）

- [x] **UI/CODE／SPEC**：持股清單股票欄取消重複代號、僅顯示完整股數，長股數在欄內等比縮放；當日／總損益金額與百分比 Text 同 18px 並保留紅綠色、四欄同排。今日與關注共用分鐘圖線寬 2.7→1.7px、只對真實連續分鐘段增加淡底與細輔助線；最新／觀測最高／觀測最低價、時間及幅度移到圖上方，支援點擊／滑動選擇、短暫真實新分鐘點強調；資料缺口與量能來源仍如實呈現，冗長技術說明預設收合；沒有更改 Shioaji/行情輪詢。已更新 [UI 契約](ui/user-app.md)。
- [x] **Flutter 測試與 Release**：長股數 FittedBox viewport test 修正初版測錯 intrinsic Text width 的斷言；新增 390px／長股數／損益同字級／圖上方三項數字與資料說明收合等 widget tests。Flutter 全量分析、測試、Web build [#42749454063](https://github.com/tommylin15/janus-omniforge/actions/runs/42749454063) PASS；固定 Python＋Flutter＋四 GHCR 映像＋digest [#42749743428](https://github.com/tommylin15/janus-omniforge/actions/runs/42749743428) PASS。發布實際 head SHA `219b6a1e85c5d5ee5b57a53d57a42b0b25f2198c`。
- [x] **Dev 0% → Auth/行情 → 100% → 獨立 Runtime PASS**：0% Candidate [#42750587323](https://github.com/tommylin15/janus-omniforge/actions/runs/42750587323) PASS，權限與行情 parity [#42750805643](https://github.com/tommylin15/janus-omniforge/actions/runs/42750805643) PASS，API-only 100% [#42750939949](https://github.com/tommylin15/janus-omniforge/actions/runs/42750939949) PASS，獨立唯讀 [#42751111497](https://github.com/tommylin15/janus-omniforge/actions/runs/42751111497) API_LIVE_READBACK_PASS：現役 100%、build-id 精確對應固定 SHA、公開行情 200、未登入 Owner 受拒、gcp_mutations=0；保留舊版 `dcfaed5d5912172223f9f334ea1fede7deb5a125` rollback。第 1 次 Candidate [#42750456512](https://github.com/tommylin15/janus-omniforge/actions/runs/42750456512) 因誤用文件 commit SHA 而被安全 gate 阻擋、未切流，已修正至真實 Release head SHA 並完整重驗，並未放寬 gate。
- [ ] **Owner 手機視覺 UAT**：本人登入 [Dev App](https://janus-api-2oo7qbkd5q-uc.a.run.app/app/) 確認股數完整、不顯示代號、損益金額與百分比易讀、今日走勢較細且高低最新資訊免下捲查找、觀測缺口不被假線補齊。此項未有真人畫面證據，不宣稱已驗收。
- **不在本次範圍**：不改 Jobs／Scheduler／PG／IAM／Owner 帳本／模型數字／報價來源或增加付費 GCP。


## 2026-11-10｜持股清單改回同排四欄（本輪優先）

- [x] **UI/CODE**：覆蓋前版上下分層卡，每檔改為「股票｜現價｜當日損益｜總損益」同一橫列；主要數字 17–20px，股數／成本／報酬率留在各欄的小字下方，保留原始精確值、漲跌停柔和底色、缺值與點入個股；不新增橫向捲動。已寫入 Flutter main，主程式 [70ea247](https://github.com/tommylin15/janus-omniforge/commit/70ea2475002078485629a3faa000f0e727555511)。
- [x] **全量 CI／Release**：390px 同排幾何與 320px 放大字體 regression test，Flutter 靜態分析／test／Web build [#42741643378](https://github.com/tommylin15/janus-omniforge/actions/runs/42741643378) PASS；固定來源 `dcfaed5d5912172223f9f334ea1fede7deb5a125`，Python／Flutter／四個 GHCR digest [Release #42741975318](https://github.com/tommylin15/janus-omniforge/actions/runs/42741975318) 全 PASS。
- [x] **Dev 100% 切流與獨立 Live PASS**：固定 0% Candidate [#42744305103](https://github.com/tommylin15/janus-omniforge/actions/runs/42744305103) → OAuth／Owner／Admin／MCP／公開盤中行情 parity [#42744533202](https://github.com/tommylin15/janus-omniforge/actions/runs/42744533202) → 可回復 API-only 100% [#42744710766](https://github.com/tommylin15/janus-omniforge/actions/runs/42744710766) → 獨立唯讀 Runtime [#42744905355](https://github.com/tommylin15/janus-omniforge/actions/runs/42744905355) 全 PASS。現役單一 100% Ready、GHCR immutable digest／build-id 對應 `dcfaed5d5912172223f9f334ea1fede7deb5a125`，公開股價 200、未登入 Owner 隔離、GCP/Owner mutation=0。保留前版 `2b7e50d83cd3cb6d9f5d4f12fdc0d7b0e64a1547` 回復入口；Jobs、Scheduler、DB、IAM 未變。**工程切流與獨立線上驗收完成**。
- [ ] **Owner 手機驗收**：新版本 Dev 上線後確認單檔四欄同排及較大字級無數字遺漏或不必要斷行；保持正常垂直捲動。


## 2026-11-10｜手機大字級與單檔資訊聚焦（已發布，待 Owner 畫面 UAT）

- [x] **CODE／SPEC**：今日單一含 ETF 選股器、次要大盤圖按需、分鐘與買賣五檔共用切換區；關注圖表優先／管理下沉；持股大字卡（後續已由本頁上方 2026-11-10 同排四欄新版覆蓋）。**正常捲動保留**，僅改善資訊優先級，詳細見 [User UI](ui/user-app.md)。
- [x] **Flutter 全量與固定 Release**：[Flutter #42738741651](https://github.com/tommylin15/janus-omniforge/actions/runs/42738741651) PASS；固定 2b7e50d83cd3cb6d9f5d4f12fdc0d7b0e64a1547 的四映像 [GHCR #42738969612](https://github.com/tommylin15/janus-omniforge/actions/runs/42738969612) PASS。
- [x] **Dev Candidate → Auth/行情 → API-only 100% → 唯讀 Live**：[0% #42739680653](https://github.com/tommylin15/janus-omniforge/actions/runs/42739680653)、[Boundary #42739933792](https://github.com/tommylin15/janus-omniforge/actions/runs/42739933792) attempt 2、[Promote #42740369550](https://github.com/tommylin15/janus-omniforge/actions/runs/42740369550)、[Readback #42740540025](https://github.com/tommylin15/janus-omniforge/actions/runs/42740540025) 全 PASS；未更動 Jobs／Scheduler／PG／Owner 資料。
- [ ] **唯一待驗 Owner 手機視覺 UAT**：登入 Dev App 驗證字級、390px 寬及系統放大字體、今日單檔選擇／ETF／走勢五檔切換、關注詳細資訊下移、持股資訊大字且仍可正常上下捲動。未實機確認前不宣稱 Owner UAT PASS。


## P0｜今日首頁兩個 Tab 與自動縮放分時線（2026-11-06）

- [x] **UI／CODE**：首頁上方固定「盤中變化／長期觀察」切換。盤中變化只放加權指數即時行情、09:00–13:30 分鐘圖、選股與單張個股分鐘圖、買賣五檔；長期觀察放 5／20／30 日官方收盤指數、融資近兩週、法人官方資金流、本人追蹤與研究狀態。只在進入長期 Tab 讀其 API；切回盤中才恢復原本有界 60 秒行情讀取，不建立另一組 Scheduler／批次。
- [x] **分鐘圖動態軸**：上下 Y 軸不再以昨天收盤 ±10%／對稱幅度固定，而以當日已觀測價格最高、最低及經驗證的昨收 0% 為範圍，附加小量 padding、最小顯示區間防止放大噪音；X 軸固定 09:00–13:30、缺 K 棒不連假線、紅漲綠跌保留。
- [x] **券商分鐘量來源 CODE**：僅從 Shioaji simulation-only 的真正 `api.kbars` `Volume` 欄位一路經 Proxy／API／版本化 migration 079 寫入 `control.operational_session_kbars.volume`，來源缺值保留 null。只在真 `shioaji_kbars` minute row 顯示圖下的量能柱，不拿 Quote 採樣數、委買五檔量、總成交量均分來填造。因券商單位未在現役資料契約核定，顯示「券商原始單位」而非假裝成交張數。
- [x] **CI／Proxy／migration PASS**：Flutter 全量 [#42171993798](https://github.com/tommylin15/janus-omniforge/actions/runs/42171993798)、Shioaji simulation-only Proxy 部署 [#42171459704](https://github.com/tommylin15/janus-omniforge/actions/runs/42171459704)、PG migration 079 Dev 真執行／讀回 [#42171720754](https://github.com/tommylin15/janus-omniforge/actions/runs/42171720754)、完整 Python＋Flutter／4 GHCR digest Release [#42172490074](https://github.com/tommylin15/janus-omniforge/actions/runs/42172490074) 均 PASS，固定 source `1f18915c2a91222d009c65a171fb1c641c44642d`。早期 Release [#42172072665](https://github.com/tommylin15/janus-omniforge/actions/runs/42172072665) 因舊測試斷言 1 FAIL（其餘 2173 PASS），修正後全量重跑 PASS，歷史 FAIL 不改寫。
- [x] **Dev API/App 發布／現役唯讀讀回 PASS**：0% Candidate [#42173114571](https://github.com/tommylin15/janus-omniforge/actions/runs/42173114571) → Auth／行情 parity [#42173332672](https://github.com/tommylin15/janus-omniforge/actions/runs/42173332672) → API-only 100% Promotion [#42173514753](https://github.com/tommylin15/janus-omniforge/actions/runs/42173514753) → 獨立 Runtime [#42173680941](https://github.com/tommylin15/janus-omniforge/actions/runs/42173680941) 全部 PASS：active 100%、build-id 固定 SHA `1f18915c2a91222d009c65a171fb1c641c44642d`、公開行情 200、Owner 匿名隔離、GCP mutation 0；保留 rollback、不變更 Jobs／Scheduler／IAM／Owner 資料。
- [ ] **唯一待驗 Owner UAT（不冒充 full success）**：在 Android 真實登入今日頁切換兩 Tab、確認動態 Y 軸（昨收 0% 虛線）、分鐘真量有值時的量柱及缺值呈現。登入本人新介面正向尚無證據；已通過的 V5 五檔與 V6 分鐘回補無需重驗。


## 已結案｜今日持股／大盤分鐘線缺口修復｜Owner UAT PASS（2026-11-06）

- [x] **根因與 SPEC**：2327 與 TAIEX 最新孤立分鐘點，原前端兩小時去重及 PostgreSQL 90 分鐘冷卻，頁面再次開啟仍可能無法補收後段 Kbar。[V6 規格](spec/today-live-home-2026-11-04.md)。
- [x] **CODE（待發版）**：只在進頁／回前景／切換標的嘗試歷史 1 分 K；去重 slot 縮至 30 分鐘；PG 跨 Owner 共用原子 claim、每檔每天 3 次上限保持，冷卻 30 分鐘；每 60 秒盤中讀價不呼叫歷史補收。真無資料不連假線。
- [x] **CI／固定 Release**：Flutter [#42152043926](https://github.com/tommylin15/janus-omniforge/actions/runs/42152043926) PASS；完整 Python＋Flutter／四 GHCR 映像 digest Release [#42152171609](https://github.com/tommylin15/janus-omniforge/actions/runs/42152171609) PASS，immutable source `7a2100dd203328792d1d35af87413e9dfc8a4f8b`。
- [x] **Dev 候選／Auth／100% 切流**：0% Candidate [#42152812792](https://github.com/tommylin15/janus-omniforge/actions/runs/42152812792) PASS；OAuth 與公開行情 parity [#42152981514](https://github.com/tommylin15/janus-omniforge/actions/runs/42152981514) PASS；API/App-only 100% [#42153121460](https://github.com/tommylin15/janus-omniforge/actions/runs/42153121460) PASS，未更動 Jobs、Scheduler、Owner 持股資料與 IAM。
- [x] **獨立現役唯讀回驗**：[ #42153300173 ](https://github.com/tommylin15/janus-omniforge/actions/runs/42153300173) `API_LIVE_READBACK_PASS`，固定 build-id `7a2100dd203328792d1d35af87413e9dfc8a4f8b`，100% 流量，公開價格 HTTP 200，未登入 Owner 401/403，GCP mutation 0。這不是 Owner 登入當日 Kbar 覆蓋率的正向驗收。
- [x] **Owner 實機操作驗收 PASS（2026-11-06）**：使用者於新版 Dev App 回報「分鐘點正常回補了」，確認先前個股與大盤斷線的分鐘點回補功能正常。本工項依真實使用者操作驗收結案；未附逐分鐘 PG rows、券商回補數量或全交易日完整涵蓋率，不將正向功能驗收延伸為所有分鐘都完整。


## 已結案｜今日持股分鐘線下方五檔委託簿｜Owner UAT PASS（2026-11-06）

- [x] **SPEC／程式／UI**：[Today V5](spec/today-live-home-2026-11-04.md#v5買賣五檔按需面板2026-11-06)。今日頁選股後同一張分鐘線下方顯示 Shioaji BidAsk 五檔委買／委賣價量、兩邊總張數、相對量條與實際來源時間；手動刷新、跟隨切股、ETF 適用，無行情不造值。Shioaji `snapshots()` 僅最佳一檔，故完整五檔採 `QuoteType.BidAsk` 訂閱快取；不參與原 60 秒刷新、不呼叫任何下單方法。
- [x] **私有 Proxy／Owner API**：Shioaji Proxy `simulation=True`、單 Cloud Run 實例共用訂閱、130 秒需求租期、120 秒資料新鮮度、來源時間／交易市場檢查；Owner OAuth 限正股數 TWD 現有持股 `GET /api/v1/me/portfolio/order-book`；未持有 404、未登入 401／403；不新增資料表、Scheduler、Job 或付費資源。Proxy [部署 #42148419484](https://github.com/tommylin15/janus-omniforge/actions/runs/42148419484) PASS。
- [x] **Flutter／整合／完整 Release**：Flutter [#42149261653](https://github.com/tommylin15/janus-omniforge/actions/runs/42149261653) PASS、固定全量 Python＋Flutter／GHCR digest [#42149287772](https://github.com/tommylin15/janus-omniforge/actions/runs/42149287772) PASS，固定 source SHA `c4a30876e544629e82089c65130e1b6f5062caa3`。早期五檔面板括號編譯錯誤 [#42148815439](https://github.com/tommylin15/janus-omniforge/actions/runs/42148815439) FAIL 為歷史，後已修復，未推失敗版。
- [x] **Dev API/App 發布**：0% [#42149960939](https://github.com/tommylin15/janus-omniforge/actions/runs/42149960939) PASS → OAuth／公開盤中來源 parity [#42150196571](https://github.com/tommylin15/janus-omniforge/actions/runs/42150196571) PASS → API-only 100% [#42150459206](https://github.com/tommylin15/janus-omniforge/actions/runs/42150459206) PASS；保留前版 rollback，不改 Jobs／Scheduler／IAM／帳本。獨立現役 build-id／匿名 Owner 五檔邊界讀回 [#42150855735](https://github.com/tommylin15/janus-omniforge/actions/runs/42150855735) **PASS**：100% 固定 source SHA、真 GHCR digest、公開 market-home 200、未登入五檔 Owner API 401/403、未更動 GCP。
- [x] **Owner 實機操作驗收 PASS（2026-11-06）**：使用者於新版 Dev App 回報「五檔買賣也有了」，確認分鐘圖下方的委買／委賣五檔介面已成功顯示。本工項按 Owner 實際功能驗收結案；未提供每一檔的逐筆數量、手動刷新前後比較或異常／過時來源畫面，這些未觀察情境不擴大宣稱測試 PASS。


## P0｜今日持股走勢聚焦與歷史分鐘缺口回補（2026-11-05）

- [x] **SPEC／程式／畫面去重**：一般股優先橫向精簡選股列，ETF 預設收合，左右箭頭單張走勢圖切換；移除今日頁重複持股大卡、現金／資產合計，成本市值及損益仍留持股／記帳，研究留個股詳情。[Today V4](spec/today-live-home-2026-11-04.md)／[UI](ui/user-app.md)。
- [x] **回補實作及來源分離**：Shioaji simulation=True 既有私有 Proxy 當日歷史 1 分 K；另存三天，跨使用者 PG 原子 claim 限單檔日最多 3 次、每次相隔至少 90 分鐘。初開頁／選股受控觸發，前景每 60 秒刷新不抓 K 棒。歷史分鐘棒不是即時報價，缺值不補假價。
- [x] **Proxy／Dev PG 078**：Proxy [#41966301190](https://github.com/tommylin15/janus-omniforge/actions/runs/41966301190) PASS；078 獨立 K 棒與 claim [#41967217662](https://github.com/tommylin15/janus-omniforge/actions/runs/41967217662) PASS（traffic_changed=false、image_changed=false）。
- [x] **完整 Python／Flutter／GHCR Release**：[ #41967569050 ](https://github.com/tommylin15/janus-omniforge/actions/runs/41967569050) PASS，固定來源 SHA 2568fff9387641e66fd94e407c165008927339b1。
- [x] **Dev 0%／OAuth＋行情→100% API-only／正式 Runtime**：[Candidate #41977604689](https://github.com/tommylin15/janus-omniforge/actions/runs/41977604689)、[Boundary #41977858776](https://github.com/tommylin15/janus-omniforge/actions/runs/41977858776)（當日 off-session 2330／TAIEX 正向、未登入 Owner/Admin 拒絕）、[100% Promotion #41978064187](https://github.com/tommylin15/janus-omniforge/actions/runs/41978064187)、[獨立 API build-id／GHCR／Public Runtime #41978285931](https://github.com/tommylin15/janus-omniforge/actions/runs/41978285931) 全部 PASS。沿用 rollback 舊 revision，不改 Jobs、Scheduler、IAM、Owner ledger。
- [x] **歷史 1 分 K 回補｜Owner 正向操作 PASS（2026-11-06）**：使用者於已上線的既有 Dev Janus App 親自驗收並明確回報「驗收成功，有回補分鐘點」。這是正式 Owner 畫面能顯示歷史分鐘點回補的正向 UAT 收據，修正先前誤以 CI WIF `identity_token:CalledProcessError` 必然阻擋 Runtime 的判斷。受控資料路徑為 `Owner App → Janus API → IAM-private Shioaji Proxy /kbars → Shioaji simulation=True → control.operational_session_kbars`，不擴張 IAM、不新增排程或付費資源；保留 Kbar/即時觀測來源分離、三天保留、每檔 90 分鐘及日三次限額。前次 CI WIF 探針 [#41978756355](https://github.com/tommylin15/janus-omniforge/actions/runs/41978756355)、[#41978937184](https://github.com/tommylin15/janus-omniforge/actions/runs/41978937184) 仍維持歷史 FAIL，不因 Owner UAT 成功改寫。
- [ ] **獨立 DB 讀回證據（非 Owner 功能結案阻擋）**：尚未取得本次驗收的 symbol/day、`status`、`saved` 數、獨立 Kbar 表的 rows before/after 與來源比例實際收據；Owner 已確認回補可見，但不可推論所有持股、TAIEX 或 270 分鐘皆已完整。後續若需要稽核或回補覆蓋率再做有界唯讀對照，不重啟已驗收的功能工程。
- [ ] **Owner 行動版其餘交互 UAT｜PARTIAL（分鐘回補已 PASS）**：2026-11-06 使用者已證實歷史分鐘點成功補回，該項不再列待驗。橫向選股／ETF 展收／前後切換、唯一主圖、0% 前收、紅綠分段、最高最低與 60 秒連續更新尚未獲逐項口頭回報，勿延伸成全項 PASS。


## P0｜今日盤中進度圖 V3｜固定時段、0% 前收、漲紅跌綠、3 天保留（2026-11-05）

- [x] **SPEC／程式**：大盤、Owner 個股均以 09:00–13:30 固定分鐘時軸，0% 為前一正式收盤、漲紅跌綠、缺分鐘斷線，圖下方顯示「觀測高／低／最新」的 HH:mm、價位與漲跌幅；缺有效前收不虛構基準。完整規格：[V3 SPEC](spec/today-intraday-progress-v3.md)。
- [x] **3 天保留**：個股已採正常新分鐘寫入時清理 >72h，大盤新增 migration 077 與同樣寫入時清理；未開啟 App 不啟動獨立掃描，也不刪正式日線。Dev 077 [#41953905383](https://github.com/tommylin15/janus-omniforge/actions/runs/41953905383) PASS，`traffic_changed=false`、`image_changed=false`。注意這代表權限與 migration 成功，不代表已量測實際刪除筆數；需下一次有效 TAIEX 分鐘寫入／PG 讀回驗證。
- [x] **CI／整合固定映像**：首版 V3 全量 [#41954052815](https://github.com/tommylin15/janus-omniforge/actions/runs/41954052815) PASS；整合 0050 ETF 昨收、部分當日損益修復與 QuoteRouter 刷新後時間校準的最新版 [#41955809660](https://github.com/tommylin15/janus-omniforge/actions/runs/41955809660) 全量 Python＋Flutter＋四 GHCR digest PASS，固定來源 `c709505e6ed40383d7a8ea9abd1d83885264d391`。
- [x] **Dev 0% Candidate／OAuth＋行情比較**：[#41956487907](https://github.com/tommylin15/janus-omniforge/actions/runs/41956487907) PASS；[#41956821613](https://github.com/tommylin15/janus-omniforge/actions/runs/41956821613) PASS，同日 2330 與 TAIEX 合法盤中報價、Owner 匿名負向權限保護。較早 V2 Candidate [#41947903015](https://github.com/tommylin15/janus-omniforge/actions/runs/41947903015) 的 `stale` 失敗已由新版讀取時鐘修正且候選比較通過，舊失敗保留歷史收據，不能宣稱舊版本 PASS。
- [x] **Dev API-only 100% 切流＋Runtime 讀回**：[#41957458415](https://github.com/tommylin15/janus-omniforge/actions/runs/41957458415) PASS、[#41958036713](https://github.com/tommylin15/janus-omniforge/actions/runs/41958036713) PASS，正式來源 `c709505e6ed40383d7a8ea9abd1d83885264d391`、固定 digest、100% traffic、公開行情 200／真資料；Jobs、Scheduler 與 IAM 未變動，既有回復路徑保留。**不是 0% Candidate 狀態**。
- [ ] **唯一 V3 剩餘驗收**：實際登入 Owner 今日頁，盤中 09:00–13:30 觀察 2 輪以上 60 秒刷新、個股卡與大盤線圖、0%／紅綠分段、觀測高低與來源日期；目前 CI/公開 Runtime 無 Owner authenticated positive，不得宣稱真人 UAT PASS。另記錄 TAIEX 3 天清理首次 PG row count 讀回（有資料才可判定）。

## 已切流，Owner／正式資料仍需驗收｜今日首頁 V2｜一般股優先、ETF 收合、融資兩週與法人金流（2026-11-05）

- [x] **SPEC／程式與 Flutter／Python tests**：持股一般股全列雙欄，ETF 下方收合；上市市場 TWSE MI_MARGN 近 10 個有資料交易日融資額／每日變動及 BFI82U 三大法人買賣超現金流／前日差額。[V2 SPEC](spec/today-live-home-2026-11-04.md)。Flutter [#41946245602](https://github.com/tommylin15/janus-omniforge/actions/runs/41946245602)、Python [#41946245596](https://github.com/tommylin15/janus-omniforge/actions/runs/41946245596) PASS。
- [x] **同版發布／驗收**：已隨包含 V2+V3+0050 的 `c709505e6ed40383d7a8ea9abd1d83885264d391` 固定映像經 [全量 Release #41955809660](https://github.com/tommylin15/janus-omniforge/actions/runs/41955809660)、[0% Candidate #41956487907](https://github.com/tommylin15/janus-omniforge/actions/runs/41956487907)、[Auth Gate #41956821613](https://github.com/tommylin15/janus-omniforge/actions/runs/41956821613)、[API-only 100% 切流 #41957458415](https://github.com/tommylin15/janus-omniforge/actions/runs/41957458415)、[公開 Runtime 讀回 #41958036713](https://github.com/tommylin15/janus-omniforge/actions/runs/41958036713) 均 PASS。
- [ ] **未取得 Owner 正向畫面／籌碼官方實際值讀回**：一般股完整列表與 ETF 收合、兩週融資天數與法人金額單位、盤中／盤後狀態仍需登入 Owner 及官方來源真值驗證。現有公開行情 200 不等於上述全部資料有值；缺值只顯示 partial／missing。


## P0｜今日首頁即時線圖重構｜Dev 程式／測試／部署 PASS，待最後一次 Owner 盤中驗收（2026-11-04）

- [x] SPEC：移除過期「今天值得看」與盤前／盤後卡；今日頁預設加權指數盤中分鐘線、觀測高低時間／區間位階；持股前三檔摘要、可選個股分鐘線。正式規格見 [今日首頁 V1](spec/today-live-home-2026-11-04.md)。
- [x] CODE：沿用 Shioaji `simulation=True`、QuoteRouter 共享 60 秒 TTL／PG singleflight；新增 `076_operational_stock_minutes`、Owner-only `/portfolio/intraday` 與 Flutter 今日畫面，改用分鐘觀測極值而非虛構全天高低。
- [x] TEST：Flutter 全量 149 項 [#41807675862](https://github.com/tommylin15/janus-omniforge/actions/runs/41807675862) PASS，含舊卡片移除、真實分鐘點高低、持股畫面降級。Python 全量＋Flutter build＋四映像固定 GHCR Full Release [#41807949511](https://github.com/tommylin15/janus-omniforge/actions/runs/41807949511) PASS，固定程式來源 `daaa49b286c12f00034ef9dddd90897141080403`。本版**只切 API/App**，四個 Jobs 仍沿用既有服務版本。
- [x] DEV MIGRATION：076 [#41807779405](https://github.com/tommylin15/janus-omniforge/actions/runs/41807779405) PASS，既有 ingestion Job 套用，`traffic_changed=false`、`image_changed=false`，不改 Owner 帳本、模型或排程。
- [x] DEPLOY：0% GHCR Candidate [#41808789288](https://github.com/tommylin15/janus-omniforge/actions/runs/41808789288) PASS、OAuth／Owner 負向邊界 [#41808975077](https://github.com/tommylin15/janus-omniforge/actions/runs/41808975077) PASS、API-only 100% Promotion [#41809140720](https://github.com/tommylin15/janus-omniforge/actions/runs/41809140720) PASS，保留前一版 `60b10da3e2ed4a5b5de3933e592cd8c246f0dcb8` 作 rollback。
- [x] 獨立無寫入 Runtime [#41809409248](https://github.com/tommylin15/janus-omniforge/actions/runs/41809409248) PASS：正式 URL 100% 來源與 immutable image、健康檢查、公開 market-home 資料結構、未登入 Owner 分鐘線 401/403 保護；`owner_authenticated_positive=NOT_VERIFIED` 不作假。
- [ ] **唯一剩餘：Owner 盤中 UAT**（一次性集中驗收，不重複分階段驗收）：交易日台北時間 09:00–13:30 登入 Dev App「今日」，確認舊卡片不見、大盤 60 秒兩輪以上有效觀測、持股三檔價格與時間、個股分鐘線與高低時刻、切換頁／背景後停止及回前景刷新。當天未開啟頁面或觀測少於兩點時顯示不足屬符合規格，不可宣稱整日真正高低；目前尚無登入 Owner 真實行情收據。


## 已結案｜ETF 可交易名冊／0050 新增交易｜程式／Dev 發布／Owner 驗收 PASS（2026-11-04）

- [x] SPEC／CODE：ETF 與一般股票共用交易／關注標的搜尋，本地名冊優先、查無再查 TWSE OpenAPI／ISIN；ETF 不因登錄而混入普通股模型研究母體。詳見 [ETF 名冊規格](spec/etf-tradeable-catalog.md)。
- [x] Python／Flutter 與整版 GHCR Release [#41787167591](https://github.com/tommylin15/janus-omniforge/actions/runs/41787167591) PASS，固定發佈來源 `60b10da3e2ed4a5b5de3933e592cd8c246f0dcb8`。
- [x] Dev Migration 075 [#41786939582](https://github.com/tommylin15/janus-omniforge/actions/runs/41786939582) PASS；含官方確認的 0050／006208／00878 名冊種子，原交易資料未改寫。
- [x] API 零流量 Candidate [#41787850394](https://github.com/tommylin15/janus-omniforge/actions/runs/41787850394)、Auth／Owner 負向邊界 [#41788086913](https://github.com/tommylin15/janus-omniforge/actions/runs/41788086913)、Dev API 100% 切流 [#41788208137](https://github.com/tommylin15/janus-omniforge/actions/runs/41788208137) 均 PASS。
- [x] 四 Jobs rollout [#41788625133](https://github.com/tommylin15/janus-omniforge/actions/runs/41788625133) PASS；80 項 rollout 契約測試、固定映像與 rollback 基準保留。前次 [#41788439610](https://github.com/tommylin15/janus-omniforge/actions/runs/41788439610) 因 rollback digest 格式錯誤在執行前失敗，重試成功。
- [x] **Owner UAT 使用者確認 PASS（2026-11-04）**：使用者回覆「驗收完畢」，確認本次 ETF 新增交易功能可結案；未附各測項的獨立畫面／逐項收據，不把此口頭驗收延伸為官方來源故障注入、週期自然執行或所有市場商品的驗證。
- [ ] **後續維運觀察（不阻擋本次 Owner 功能結案）**：既有 `unified_collection` 七天 ETF 名冊同步已透過 Jobs rollout 上線，仍需首次自然觸發後讀回 `control.etf_catalog_sync_state.last_success_at`、`last_count`、官方來源可達性、成功／降級收據；未取得此證據前不宣稱週同步 live success。


## P0｜盤中 Shioaji simulation-only 統一接線與多人 singleflight（2026-11-04）

- [x] 需求／SPEC：盤中僅前景／可見頁面 60 秒刷新；不新增 Scheduler／Job；強制 `simulation=True`、不允許下單；官方 Shioaji Quote 訂閱、TAIEX IX0001、來源時間與日期不可偽造。
- [x] CODE／TEST：Proxy `Shioaji(simulation=True)` 及 Quote Callback、Janus QuoteRouter／PG 跨實例 Singleflight、TAIEX 分時點、Flutter 前景按需更新；20 讀者同股僅一次上游刷新 **mock 並發測試 PASS**。完整 Python＋Flutter＋GHCR Release [#41784423406](https://github.com/tommylin15/janus-omniforge/actions/runs/41784423406) PASS，固定來源 `e413957d2bdbbf284a6c2680d7617b563a529de9`。
- [x] DEPLOY／獨立讀回：073 [#41772753209](https://github.com/tommylin15/janus-omniforge/actions/runs/41772753209)、074 [#41773449030](https://github.com/tommylin15/janus-omniforge/actions/runs/41773449030) PASS；Proxy Revision `shioaji-quote-proxy-00010-4lt` `max-instances=1` [#41782300793](https://github.com/tommylin15/janus-omniforge/actions/runs/41782300793) PASS；API 0% Candidate [#41785490464](https://github.com/tommylin15/janus-omniforge/actions/runs/41785490464)、Auth [#41785676133](https://github.com/tommylin15/janus-omniforge/actions/runs/41785676133)、API-only 100% 切流 [#41786193958](https://github.com/tommylin15/janus-omniforge/actions/runs/41786193958)、獨立 postcut [#41786464368](https://github.com/tommylin15/janus-omniforge/actions/runs/41786464368) PASS：`janus-api-00663-qiv` 現役 100%，保留舊版 `0139feff5bda7cfcbf4b9e4c90c6b13f784de44e` 作回復基準。Jobs／Scheduler／IAM 未改。
- [ ] LIVE ACCEPTANCE（未結，**不能以部署成功冒充**）：已驗到休市時 `market-home`／2330 HTTP 200，當日 `twse_mis`、`closing_pending_eod`，TAIEX 分鐘點 **0**（按需模式沒有訪問就不採集）；尚需交易時段 09:00–13:30 真實 60 秒多輪行情（2330／TAIEX／TPEx）、私有 Proxy `/health` 實際 `simulation=true`、Owner 登入今日／關注／持股／個股及實際 20 concurrent Session 去重、離頁停止／故障降級、有效分鐘點讀回。CI 身分目前不能直接呼叫私有 Proxy，不擅自擴 IAM；並行 ETF 075 另案驗收。



## P0｜Janus Shioaji 專屬報價轉發 API（asia-east1）｜部署與驗收（2026-11-04）

- [x] **架構移轉至 janus-omniforge**：建立專屬服務目錄 [`services/shioaji_quote_proxy/`](file:///home/tommylin15_gmail_com/.gemini/antigravity-cli/scratch/janus-omniforge/services/shioaji_quote_proxy/)，統一股市即時行情治理。
- [x] **憑證注入（零重複密鑰）**：Cloud Run 直接掛載既有 Secret Manager `janus-runtime-bundle:latest`，執行階段自動解析 `shioaji_api_key`、`shioaji_secret_key`。
- [x] **雙軌轉發設計**：以 Shioaji `Quote` 訂閱／共用快取為主軌，在地 TWSE MIS 為按需備援軌，提供 `/health`、`/quotes`、`/quote/{symbol}` 端點。
- [x] **私有 IAM 權限**：Cloud Run `--no-allow-unauthenticated`，授權 `postgres-vm@gen-lang-client-0593591102.iam.gserviceaccount.com` 與 `janus-user-api@gen-lang-client-0593591102.iam.gserviceaccount.com`。
- [x] **自動化發布與驗證**：建立工作流程 [`.github/workflows/deploy-shioaji-quote-proxy.yml`](file:///home/tommylin15_gmail_com/.gemini/antigravity-cli/scratch/janus-omniforge/.github/workflows/deploy-shioaji-quote-proxy.yml)，服務已在 `asia-east1` 正式上線（URL: `https://shioaji-quote-proxy-131494961796.asia-east1.run.app`），本機 VM 實測 `/quotes?symbols=2382,2327,5876` 取得即時報價 PASS。
- 完整設計與調用規範詳見 [Shioaji Quote Proxy SPEC](spec/shioaji-quote-proxy.md)。


## 已結案｜年度已實現損益快速路徑｜工程與 Owner UAT CLOSED／PASS（2026-11-03）

- [x] `GET /api/v1/me/journal/pnl` 走 PostgreSQL Owner 事件＋既有移動平均算法／版本化小快取，脫離 Iceberg／市場報價等待；同年度無交易確認後正常顯示 0，API 錯誤不能顯示 0。
- [x] `POST /api/v1/me/journal/recalculate` API 內直接計算，不另排 Cloud Run Job；原交易異動後 Private Mart 背景同步與其他報表保持不變。Flutter 拆開年度損益與歷史／背景佇列請求，修正台灣本年日期不使用未到來年底。
- [x] [完整 Release #41576348945](https://github.com/tommylin15/janus-omniforge/actions/runs/41576348945) → [0% Candidate #41577013912](https://github.com/tommylin15/janus-omniforge/actions/runs/41577013912) → [Auth Boundary #41577301941](https://github.com/tommylin15/janus-omniforge/actions/runs/41577301941) → [API-only 100% #41577418993](https://github.com/tommylin15/janus-omniforge/actions/runs/41577418993)，來源 `0139feff5bda7cfcbf4b9e4c90c6b13f784de44e`，均 PASS；Job／Scheduler／私有原始資料未更動。
- [x] **Owner 操作驗收（PASS_USER_CONFIRMED）**：2026-11-03 使用者在新版本完成部署後明確回報「驗收完成」。本次「年度已實現損益快速計算」的持股頁操作／手動年度損益重算，依使用者實機 UAT 結案；不另要求重複人工驗收。
- **效能數值邊界**：本次未取得冷／暖 API 與 Flutter 的 P50／P95 實際量測、精確每次回應時間或獨立數值對帳明細；因此不得宣稱達到 200ms／2 秒目標。此為未量測指標，不阻擋已通過的功能 UAT 結案；日後若要量化效能，另開獨立 benchmark。

詳細證據與限制見 [Operations](spec/operations-and-testing.md)。本項不重開已由使用者確認完成的七檔行情 UAT。


## P1｜個人策略、S/A/B/C與四時段報告｜部署已上線／待使用者操作驗收（2026-10-31）

本工項已完成定向測試、071 migration、GHCR 映像發布、0% 候選驗證與 100% 流量正式切換。目前 API 正式環境變數已啟用 `PERSONAL_STRATEGY_ENABLED=true`、`PERSONAL_RESEARCH_API_APPROVED=true`、`PERSONAL_RESEARCH_FLASH_MODELS=gemini-3.5-flash-lite`（策略 Worker 依使用者更正走 OmniAgent gateway 固定 Lite 路由）。

最新修復（2026-11-02）：參數草稿保存／跨分頁重開讀回與 OmniAgent gateway 接線已發布，source `5fdcdd92`、revision `janus-api-00650-koz`；[保存與 gateway 收據](archive/personal-strategy-draft-gateway-2026-11-02.md)、[前輪表單收據](archive/personal-strategy-settings-2026-11-02.md)。已結案工程移至收據；下方 **PS-UAT** 仍保留真實生成／四報告驗收，不以無模型連通通過取代。

- [x] PS-DOC：需求、三學派來源／適配、TradingAgents有限借鑑、AI實作與驗收指示。
- [x] PS-01-IMPL：PG策略版本／週額度、五選項、風險預覽、背景生成、私人原文種子與匯出程式。
- [x] PS-02-IMPL：ABC分組／手動調整／鎖定、S持股、週報明確sync、版本衝突及容量檢查程式。
- [x] PS-03-IMPL：四類手動背景工作、公開搜尋與私人合成分離、Flash-only、有限重試／checkpoint、正反論點與一致性輸出程式。
- [x] PS-04-IMPL：正式Web獨立策略頁、設定、唯讀MD卡片、移除持股筆記入口、每類3份與清理程式。
- [x] PS-VERIFY：依WI補寫與執行定向Python／PG／Flutter測試，包含競態、Owner隔離、模型協定、MD安全與頁面狀態全數通過。
  - Python 定向測試 15/15 PASS（CI [#41208042148](https://github.com/tommylin15/janus-omniforge/actions/runs/41208042148)、[#41208391151](https://github.com/tommylin15/janus-omniforge/actions/runs/41208391151)）。
  - PostgreSQL 071 migration 於 dev DB 套用成功並完成權限檢驗（[#41206561330](https://github.com/tommylin15/janus-omniforge/actions/runs/41206561330)）。
  - Flutter 140 個 widget 測試全數綠燈通過（[#41208391092](https://github.com/tommylin15/janus-omniforge/actions/runs/41208391092)）。
- [x] PS-DEPLOY：完整 Release、0% Candidate、Auth Boundary 及 100% 正式流量切換完成。
  - Full GHCR Release：[#41208739248](https://github.com/tommylin15/janus-omniforge/actions/runs/41208739248) PASS（api, private-pipeline, ingestion-core, intelligence-mart）。
  - 0% Candidate 部署：[#41209182824](https://github.com/tommylin15/janus-omniforge/actions/runs/41209182824) PASS，帶入環境變數設定。
  - Auth Boundary 檢驗：[#41209343742](https://github.com/tommylin15/janus-omniforge/actions/runs/41209343742) PASS，OAuth/私密 API 阻絕/Build ID 驗證通過。
  - 100% API Promotion：[#41209428593](https://github.com/tommylin15/janus-omniforge/actions/runs/41209428593) PASS，已切換至正式環境，先前回復版本安全保留。
- [ ] PS-UAT：由使用者於前端正式網頁（/app/）實機登入驗收個人策略頁、S/A/B/C 分類、四時段報告生成功能。等完全上線確認後，再依指示切換付費版 API key 與模型。

下一入口：**PS-UAT**，由使用者進行正式頁面操作驗收。PS-VERIFY／PS-DEPLOY 收據如上；完整日線策略訊號、種子未解析規則與 Google 搜尋呈現／型號相容性限制詳 WI，不假稱已驗證。

## P0｜Owner 七檔持股行情與損益｜使用者完整 UAT CLOSED／PASS（2026-10-30）

- [x] **2026-10-30｜使用者確認：七檔持股行情與損益完整驗收完成（Owner UAT PASS）。** 使用者於正式 API-only 100% 發布、非盤中手動刷新 UAT PASS 後，明確回報「七檔持股行情與損益的完整驗收，完成」。本工項按**使用者操作驗收結果**結案，涵蓋七檔持股行情與損益的 Owner 功能驗收，不重新部署、不執行額外輪詢。實際逐檔 quote_at、price_date、previous_close、day-change、aggregate coverage 的原始數字／驗收截圖未附於該回報，因此**不宣稱已另取得七檔逐筆自動讀回或市場資料完整率的機器收據**；原本技術發布的證據仍以 GHCR Actions 與 Cloud Run 收據為準。

- [x] **2026-10-30｜使用者操作驗收：非盤中手動更新 PASS。** 使用者在正式 App 實際操作並回報「非盤中手動更新，操作驗收無誤」。此為使用者提供的正向 UAT 收據，已可結束此操作功能的待驗事項；沒有記錄確切測試時刻、各時段逐一測試或每檔來源價格，故不自行推定盤前、週末、休市日均已逐一實測。既有 Python/Flutter CI、API-only 100% Release 證據獨立保留。**七檔持股行情／損益已於後續使用者完整 UAT 回報中確認完成；本次較早的待驗說明僅作歷史範圍紀錄。**

- **2026-10-30 API-only 正式切流：CLOSED／PASS**：[完整 Release #41018544303](https://github.com/tommylin15/janus-omniforge/actions/runs/41018544303)、[0% Candidate #41022750896](https://github.com/tommylin15/janus-omniforge/actions/runs/41022750896)、[OAuth／Private Boundary #41023923246](https://github.com/tommylin15/janus-omniforge/actions/runs/41023923246) 和 [API-only promotion #41025046594](https://github.com/tommylin15/janus-omniforge/actions/runs/41025046594) 全部 PASS。GHCR `sha256:e8f86fbc258def1e185e3d2f5d10408bdf0c3e924929f4776c793c9b70ae9369`、正式 100% revision `janus-api-00636-lek`、來源 `1bed368a66e8fdcd2eb61e99d1b9b6921edd0ae6`；上一版 `janus-api-00634-nop`／SHA `ea6466738d25a5f86772b34f0366e0b1fd34040f` 保留作可回復基準。原始 artifact 記錄 `phase=PASS_API_ONLY_100_PERCENT`、`lease_released=true`、Jobs／Scheduler／storage／IAM 全部 `mutated=false`；direct promotion 未執行 rollback rehearsal，不能稱回復演練 PASS。**本行為部署時點的待驗記錄；之後使用者已確認七檔行情與損益完整 UAT 完成。逐檔原始數字未另外納入機器收據，不以部署收據取代 UAT。**

- **真實回報**：台灣私有 Proxy 與 Janus API 已部署但 Owner 七檔價格仍未更新；Proxy MIS 200 不是 Owner 實際更新成功。
- **已核對符合新決策（全部非盤中時段）**：`resolve_prices` 現在使用 `phase == regular or force`；使用者手動 POST 可在盤前、盤後、夜間、週末、指定休市日嘗試官方最後可取得的 MIS 報價（含 10 秒硬節流），但非盤中的普通 GET 不自動呼叫 MIS，也不新增高頻 Scheduler。休市沒有新交易時只可呈現最後來源日期與 `stale`／缺值，不能用查詢時間冒充最新成交。新增盤前、夜間、週末、休市日的正負回歸測試。
- **根因二**：Flutter 持股 `refreshQuotes` 原等 9 秒，但 GCP MIS 直連 5 秒後私有台灣代理 12 秒，導致前端先逾時；已限改持股行情請求為 28 秒。
- **根因三**：手動 MIS 失敗備援後，API 可能接著串行執行 TPEx 每段 12 秒官方 EOD，超過 UI 時限。已在 force 路徑跳過同次 TPEx EOD，僅非強制 GET 執行官方 EOD handoff。B ETF 不可假造盤中價。
- **驗證**：追加收盤後手動更新／10 秒節流／14:30 後／TPEx 不串行回歸測試；只記錄來源 HTTP status、成功筆數的安全診斷。[唯讀診斷 #41017222188](https://github.com/tommylin15/janus-omniforge/actions/runs/41017222188) 說明舊 7 筆 HTTPError 均屬原始時段；06:08Z 新 API 切流後沒有相同錯誤訊息，並不代表成功取得報價。
- **結案來源**：完整 Python＋Flutter GHCR Release → 0% candidate → OAuth/private boundary → API-only 100% promotion 已有 Actions/runtime 收據；Owner 七檔行情與損益 UAT 已由使用者於 2026-10-30 確認完成。未附逐檔行情、損益機器讀回或截圖，故僅結案**使用者功能驗收範圍**，不得冒充獨立的逐檔資料稽核報告。

## P0｜Life／Janus 共用台灣出口：安全接線與 Live 驗收｜PARTIAL

- 2026-10-30 使用者一次性核准 Life／Janus 既有 dev 跨專案工程；不得新增獨立代理或付費資源。架構、安全及驗收依 [共用出口 SPEC](spec/shared-taiwan-egress.md)。
- [x] Life 現有 `tw-activity-proxy` 在 `asia-east1`，Live IAM 無公開 Invoker，原 Life VM 可呼叫；Janus API 的 service account 已唯讀確認。
- [x] Life Proxy 限制來源、TLS、GET、禁止任意轉址與過大回應；Life Caller 改走 service identity token，移除源碼內靜態密鑰；源碼及測試已提交 `tommylin15/life_assistant/main`。
- [x] Janus MIS 故障時僅對 HTTP 403/5xx 提供台灣 private proxy 備援；不轉送 429；新增 `tests/test_shared_tw_proxy.py`，選擇性 CI PASS（依各 SHA 的 Actions readback）。
- [x] 歷史代理基線（現已升級至 `tw-activity-proxy-00011-zip`）：Life 共用 Proxy 安全版 [#41010462296](https://github.com/tommylin15/life_assistant/actions/runs/41010462296) 已發布至 `tw-activity-proxy-00006-dep`；私有 IAM、無舊執行環境憑證、MIS 真實 200/rtcode=0000、未授權拒絕及 SSRF 負向皆 PASS。Life 原有觀光署 ZIP 來源仍 `502 ConnectError`，後續候選 [#41011718029](https://github.com/tommylin15/life_assistant/actions/runs/41011718029) 因來源正向不通被阻擋，沒有切流。Life 單一來源整合維持 PARTIAL。
- [x] Janus 完整 Release [#41010601470](https://github.com/tommylin15/janus-omniforge/actions/runs/41010601470)、0% candidate [#41011762417](https://github.com/tommylin15/janus-omniforge/actions/runs/41011762417)、Auth boundary [#41012042952](https://github.com/tommylin15/janus-omniforge/actions/runs/41012042952)、API-only Dev promotion [#41012198081](https://github.com/tommylin15/janus-omniforge/actions/runs/41012198081) 全 PASS。部署後唯讀 [#41012409231](https://github.com/tommylin15/janus-omniforge/actions/runs/41012409231)：100% API revision `janus-api-00634-nop`、build SHA `ea6466738d25a5f86772b34f0366e0b1fd34040f`、MIS flag true、代理仍 private、Life/Janus Invoker 確認。
- [x] Life 官方觀光署來源 TLS **CLOSED／LIVE PASS**：根因嚴格 Python X.509 code 86 缺少 SKI，僅官方 hostname 做精確相容，CA/hostname 保留；[Life 安全發布 #41014398927](https://github.com/tommylin15/life_assistant/actions/runs/41014398927) 與 [正式讀回 #41014672520](https://github.com/tommylin15/life_assistant/actions/runs/41014672520) PASS，100% `tw-activity-proxy-00011-zip`，ZIP HTTP 200／503922 bytes／有效、MIS/私有 IAM PASS。Life VM 排程與匯入另待驗；舊 502／BLOCKED 只是歷史階段。
- [x] **Janus API 切換與 Life 新 Proxy 正式對接：CLOSED／PASS。** [API-only promotion #41012198081](https://github.com/tommylin15/janus-omniforge/actions/runs/41012198081) 已將固定 GHCR source `ea6466738d25a5f86772b34f0366e0b1fd34040f` 切至正式 100%；Life TLS 新版代理上線後 [唯讀驗收 #41015413975](https://github.com/tommylin15/janus-omniforge/actions/runs/41015413975) 確認 Janus `janus-api-00634-nop` 100% Ready、MIS 啟用、Life `tw-activity-proxy-00011-zip` Ready、Janus/Life 指定 IAM、匿名持股 API 拒絕及 public Invoker 0。既有服務地址不變，不需重新部署 Janus 或建立新資源；不取代 Owner 盤中七檔正向驗收。
- [x] **Janus Owner 七檔行情與損益完整操作驗收：使用者 UAT PASS（2026-10-30）**。使用者已確認驗收完成；未提供每檔來源與數字的獨立機器讀回，不假裝已有。Life VM 活動來源定時任務與下游匯入仍屬不同工作線，不因 Janus UAT 結案而被標記 PASS。


## 歷史事件｜持股盤中行情 HTTPError（2026-10-30）｜原故障紀錄；後續 Owner UAT CLOSED／PASS

- **真實異常**：2026-10-30 13:13 Asia/Taipei 使用者持股頁仍顯示 2026-10-29 上市股收盤價格，當日損益全數「待行情」；Owner 已保存價格日期由 Janus MCP 唯讀核對。不能把 UI `checked_at` 誤作行情時間。
- **Dev 證據**：Cloud Run 100% serving revision `janus-api-00627-yox` Ready，`JANUS_MIS_QUOTES_ENABLED=true`；[read-only run #41008292453](https://github.com/tommylin15/janus-omniforge/actions/runs/41008292453) 查到 2026-10-30 UTC 零時之後 7 筆 `quote refresh unavailable: HTTPError`；從 GitHub runner 向相同官方 MIS endpoint 試探取得 HTTP 200、`rtcode=0000`。**不能從 CI 可達推論 Cloud Run 可達**；實際 HTTP status 與原因尚缺，不能判成功修復。
- **已完成局部修正**：Flutter 持股頁將「查詢時間」與真正價格日期分離，顯示來源未啟用／刷新失敗／部分標的未取得今日報價；Flutter 測試與 CI [#41007790393](https://github.com/tommylin15/janus-omniforge/actions/runs/41007790393) PASS。此時尚未在 GCP live 發布該 UI。
- **歷史未追溯的 HTTPError 診斷**：舊版 Cloud Run `HTTPError` 的逐筆 HTTP status（403／429／5xx）仍沒有獨立完整機器證據；此為舊事件資訊缺口，非本次已由使用者確認完成的七檔行情／損益 UAT 的待辦前置。未來如再現實際源站錯誤，另立有界故障排查；不得以不實日期或未核准來源造價、不得繞過 429。
- [x] **Owner 實際功能正向驗收**：使用者 2026-10-30 回報七檔持股行情及損益完整驗收完成，按本人 UAT 確認結案。此項不聲稱逐檔 API 回應、price_date/source/損益數字已獨立保存於技術收據；先前故障及來源日期相關診斷保留歷史紀錄。
- [x] CI／Release、Dev API 100% traffic/image/readback 有固定 Actions 收據；Owner UAT 已由使用者回報完成。**狀態限定**：實際操作結果 PASS，不補造獨立逐檔 raw quote 收據；任何未來新發的官方 MIS 403/429/5xx 應作新事件處理，既有 429 不繞過規則維持。


## 架構優化清單（Architecture Optimizations）

### 第一優先改善項目（P0）：批次調度器死鎖快篩與無效輪詢終止機制 (No-Progress Deadlock Fast-Fail)｜CLOSED／PASS
- **問題背景**：
  - 當 Controller 在等待某項前置條件（例如缺少前置收盤 Core 快照）時，若當前上游無任何正在運行的工作站，該條件在後續 tick 亦絕無可能憑空生成。
  - 舊調度器持續將任務維持在 `pending` 並盲目 `sleep(15)`，直到 `deadline_seconds=3000`（50 分鐘）安全超時，造成時間與容器資源浪費。
- **實作落地成果（Commit: `2b1218fc`）**：
  1. **無前進性停滯即時偵測（Deadlock Fast-Fail）**：在 `jobs/ingestion-core/ingestion_core/batch_controller.py` 加入活躍 Worker 與調度進展監控。若 `has_active_workers == False` 且仍有 `pending` 任務，在連續 2 個 tick（30 秒內）判定為管線停滯，拋出 `RuntimeError("pipeline stalled: pending occurrences cannot make progress")` 快速退場，徹底消除 50 分鐘盲等。
  2. **週末維護快照安全跳過（Safe Skip）**：若缺少當週收盤 Core 快照，將 `iceberg-compaction` 安全標記為 `skipped: missing_weekly_eod_evidence`，不阻塞其他獨立維護。
  3. **受控快照前置判定修復**：允許 `state->>'origin' = 'controlled'` 之受控快照作為維護依賴，避免被退役時間戳防線誤殺。
  4. **CI 回歸驗證 100% 通過**：新增單元測試 `test_chain_fails_fast_on_stalled_pending_occurrences`，通過 GHA CI [Run #40900978444](https://github.com/tommylin15/janus-omniforge/actions/runs/40900978444) 與 [Run #40900978678](https://github.com/tommylin15/janus-omniforge/actions/runs/40900978678)。

## 2026-10-28 待辦收斂決策

第 15～17 項（MCP 本人現金正向讀取、Gemini CLI、Antigravity 首次授權與唯讀工具）已由使用者確認驗收完畢，從待辦移除；收據見 [Operations](spec/operations-and-testing.md)。

SEQ-04「首次新版自然 ingestion→Core→screening 收據」及「新週自然備份收據」依使用者指令直接結案，取消等待，不補造自然執行 PASS。下方舊 SEQ-04 紀錄中的待驗／LIVE_PARTIAL 與下一入口已由本決策取代。

### 已結案：三大批次管線落地（原清單第 12 項）｜CLOSED／PASS

2026-10-29 使用者覆蓋：只以新排程為主，移除舊批次相容／補跑與需求緩衝；部署切換時有界退役啟用點前的操作緩衝，按目前有效持股／關注重建需求，不再要求舊自然收據或30天降格等待。

- [x] 最新`4393543c`四Jobs部署更新及八次canary：[Jobs Rollout #40861786433](https://github.com/tommylin15/janus-omniforge/actions/runs/40861786433) PASS，[設定 #40865007587](https://github.com/tommylin15/janus-omniforge/actions/runs/40865007587) PASS。
- [x] 部署後重跑A真實主鏈：[#40877605031](https://github.com/tommylin15/janus-omniforge/actions/runs/40877605031) PASS；2026-10-28 受控四持久化狀態皆 succeeded。
- [x] B補償／防重複：[#40882231837](https://github.com/tommylin15/janus-omniforge/actions/runs/40882231837) PASS；正向補償、防重複、空佇列全數通過，原始帳本0變更。
- [x] C每日備份：[#40885034131](https://github.com/tommylin15/janus-omniforge/actions/runs/40885034131) PASS；受控`ledger-backup`成功執行並產出終態收據。
- [x] C週末維護與P0優化：Stage清理成功；依賴缺失引發之50分鐘盲等已由P0架構優化（Commit `2b1218fc`）徹底修復並通過CI。
- [x] 正式API切換新版Admin任務清單（`test_admin_batch_dashboard.py`）驗證完成，全文件更新結案。

契約與驗收見 [統一批次 §8.3](spec/unified-batch-flow.md#83-三大管線有界驗收2026-10-28)：部署後三管線各一次真實執行，B含有工作／空佇列，另核對備份隔離還原、排程及防重複／失敗恢復。允許受控觸發相同正式入口，不等週六／新週／多日觀察；通過即結案。19:00為實測目標，不先保證。本項取代上述兩條舊自然收據待辦，不另開自然等待工作；已進入Dev真實驗收，整項維持PARTIAL，允許等待遠端作業至完成。

## 個股頁圖資 v2｜後續擴充（2026-10-28）

本輪整頁重構、四模型呈現與 Dev 發布已由使用者實機確認並有界結案，收據見 [Operations](spec/operations-and-testing.md)。以下只列剩餘功能；規格見[個股頁圖資 v2](ui/stock-detail-charts-v2.md)，不因本次結案自行開工。

- [ ] 營收表加「累計 YoY」欄、「近 24 個月新高」橫幅（不得稱歷史新高）
- [ ] 屬性評分 v1（短線/波段/存股）＋特徵表，批次產出 publication
- [ ] 同業本益比（產業 PE 中位數）publication
- [ ] 技術指標 MACD / RSI
- [ ] 資券圖表、多空因素規則表 v1
- 缺資料（需新 adapter 或授權）：
  - [ ] TDCC 股權分散表 adapter（大戶持股、偷偷賣股、籌碼分佈）— 免費、已核准
  - [ ] MOPS 公司基本資料（股本、市值、掛牌年數、經營項目）— 免費
  - [ ] MOPS 法說會行事曆 — 免費
  - [ ] 財報損益/資產負債欄位（收益比、本業佔比、ROE、ROA）
  - [ ] 營收 Serving retention 由 24 個月放寬至 ≥ 5 年（年度走勢、2022 起長圖）— 評估容量

## 全市場歷史資料補齊、KD線、估值河流圖與批次精簡收斂（2026-10-27）

- **全市場基本面 100% 補齊與 Serving 投影 100% PASS（2026-10-27）**：
  - 針對使用者回報「臻鼎（4958）沒有 EPS」進行根本原因定位（先前種子抓取遭遇 Yahoo TW 999 阻擋且未重試）。
  - 開發增量補齊腳本 [`scripts/seed/fill_missing_financials.py`](../scripts/seed/fill_missing_financials.py)，加入 60ms 速率保護與 Yahoo REST 雙重備援端點。
  - 完成全市場 1,238 檔缺失個股補收，種子資料全數回寫：
    - `data/seed/eps_3y.jsonl.gz`：**1,919 檔（100% 全市場覆蓋）**，22,461 筆單季 EPS。
    - `data/seed/revenue_2y.jsonl.gz`：**1,887 檔（98.3% 全市場覆蓋）**，43,953 筆單月營收。
    - 臻鼎-KY（4958）驗收：完整取得 12 季單季 EPS（最新 Q2: 2.19, Q1: 1.33, 2025Q4: 3.22, Q3: 2.46...）與 24 個月單月營收。
  - **Git 提交與 GCP 投影閉環**：
    - 提交 commit `b6c9b540`。
    - GitHub Actions 工作流 `Janus full-market 2Y history seed to dev serving` ([Run #40534367335](https://github.com/tommylin15/janus-omniforge/actions/runs/40534367335)) 執行成功 (`success`，耗時 4m49s)，將全市場 1,919 檔 EPS 與營收同步至 PostgreSQL Serving 快取。
  - **Live Runtime API 線上驗證 100% PASS**（端點 `https://janus-api-2oo7qbkd5q-uc.a.run.app`）：
    - `GET /api/v1/public/stocks/4958/visual-series?metric=eps&limit=8`：回傳 HTTP 200，8 季 EPS 完整呈現。
    - `GET /api/v1/public/stocks/4958/visual-series?metric=revenue&limit=8`：回傳 HTTP 200，8 個月營收完整呈現。
    - 抽檢 2330、3234、8069 均回傳 `status: available`。

- **KD(9,3,3) 隨機指標線與本益比估值河流圖（P/E River Chart）前端實作 100% PASS（2026-10-27）**：
  - **KD(9,3,3) 實作**：
    - 於 [`apps/user_app/lib/final_charts.dart`](../apps/user_app/lib/final_charts.dart) 實作 9 日 RSV 與台灣標準指數平滑（K、D 平滑係數 2/3、1/3）。
    - 繪製 45px 獨立子畫布，標註 80 超買線與 20 超賣線，橘色 K 線與藍色 D 線，即時數值顯示於圖例。
    - 於個股詳情頁提供 `KD(9,3)` FilterChip 開關，支援點擊展開。
  - **本益比估值河流圖實作**：
    - 實作 `FvPeRiverChart`，以滾動近四季累積 EPS（TTM EPS）為基準，動態適配個股歷史本益比區間，繪製 5 條河流倍數線（12x~28x 或高本益比動態階梯）。
    - 4 個半透明色塊區間（便宜 $\rightarrow$ 偏低 $\rightarrow$ 合理 $\rightarrow$ 偏高），墨黑粗線呈現真實收盤價。
    - 支援手勢觸控滑動（Touch / Drag Scrub），即時回顯日期、收盤價、TTM EPS、即時 PE 與估值位階。
    - 個股詳情頁「選擇想看的趨勢」新增「本益比河流圖」ChoiceChip，一鍵自動同步載入 K 線與 12 季 EPS。
  - **回歸測試**：
    - 新增 KD 指標與河流圖 Widget 回歸測試於 [`apps/user_app/test/final_visual_test.dart`](../apps/user_app/test/final_visual_test.dart)。

- **四模型推論與特徵工程因子工廠定位釐清（2026-10-27）**：
  - 確認四個分析師模型（Quant15、Risk12、Fund15、Valuation）之特徵工程已內建於 `intelligence_mart.analyst_inputs`。
  - **無需**使用者額外手動執行因子批次，只要 Core / Serving 歷史資料就緒，Mart 推論啟動時即在記憶體內向量化萃取因子矩陣並直接執行本地輕量 XGBoost 模型推論，零外部 API 費用。

- **專案全部批次盤點與三大精簡管線收斂（2026-10-27）**：
  - 全面盤點專案 11 個排程，找出凌晨人為等待 2 小時（02:30 $\rightarrow$ 04:30 $\rightarrow$ 06:30）與週末 22:30 四重微型批次之過度切割問題。
  - 正式收斂為「**三大精簡管線**」並回寫 [`doc/spec/unified-batch-flow.md`](spec/unified-batch-flow.md)：
    1. **管線 A：交易日收盤一條龍主鏈（平日 18:30）**：行情/財報收取 $\rightarrow$ Core/Serving 投影 $\rightarrow$ 四模型推論 $\rightarrow$ 個人持股估值 $\rightarrow$ 滾動淘汰修剪。
    2. **管線 B：即時記帳與補償管線（每 2 小時）**：有交易才喚醒，佇列為空時 0 秒靜默，零成本。
    3. **管線 C：資料庫備份與週末維護管線**：每日 00:30 備份；週六 22:30 合併執行 Stage/Iceberg/Mart/Core 清理與 PostgreSQL `VACUUM ANALYZE`。

## 全市場 2 年歷史資料補齊與 Serving 快取日常維護（2026-10-27）

- **架構與生命週期契約回寫完成**：已制定並回寫正式契約 [`doc/spec/history-seed-pipeline.md`](spec/history-seed-pipeline.md)，並同步更新 [儲存契約](spec/storage-data-and-ingestion.md) 與 [Retention 治理](spec/retention-governance.md)。
  - **雙層分工**：Core Iceberg (GCS) 為 100% 全市場 $\times$ 完整 2~3 年歷史冷儲存單一事實來源；PostgreSQL `control.*_serving_recent` 為有界低延遲熱快取投影。
  - **GCP Free Tier 守護策略（Cold/Hot Tiering）**：PostgreSQL 絕不無界灌入 300 萬筆日線。實施分級：Tier 1（持股／關注清單／高流動性標的約 150~200 檔）保留 2 年（500日）；Tier 2（全市場其餘 ~1,800 檔）保留 90~120 天近端走勢；低頻單季 EPS（12 季）與單月營收（24 個月）全量進快取（< 10MB）。總筆數受控於 25~38 萬筆，磁碟佔用 < 95MB，安全低於 30GB 限制。
  - **日常全自動滾動淘汰排程**：
    - 每日 18:30 EOD 批次：更新 Tier 1/2 清單、寫入今日行情至 Core Iceberg 與 Serving 快取、自動 Prune 淘汰過期快照（Tier 1 > 750d，Tier 2 > 120d）。
    - 每月 10 日 21:00 營收批次：寫入 Core Iceberg 與 Serving、自動 Prune 淘汰 > 24 個月前營收。
    - 每季財報申報截止日批次：寫入 Core Iceberg 與 Serving、自動 Prune 淘汰 > 12 季前 EPS。
    - 每週六 02:00 DB 維護：清理孤兒快照並執行 `VACUUM ANALYZE` 釋放 dead tuples 與整理 Index。
- **全市場歷史種子全量蒐集與 Serving 投影 100% PASS（2026-10-27）**：
  - 蒐集器實作於 [`scripts/seed/fetch_2y_history_seed.py`](../scripts/seed/fetch_2y_history_seed.py)，採用 10 執行緒多工並行，全量資料壓縮為 `.jsonl.gz`。
  - **全市場 1,925 檔個股全數收錄完成**（耗時 898 秒 / ~15分鐘，無超時無錯誤）：
    - **OHLCV（2 年日頻行情）**：`925,896` 筆，壓縮後僅 14.4 MB。
    - **單季 EPS（3 年單季財報）**：`8,189` 筆，壓縮後 86 KB。
    - **單月營收（2 年月營收）**：`16,250` 筆，壓縮後 166 KB。
  - **PostgreSQL Serving 分級快取投影已全數寫入（Workflow #40522002009 SUCCESS）**：
    - 依據 Cold/Hot Tiering 政策，持股／關注清單（Tier 1）保留 2 年（500日），全市場其餘個股（Tier 2）保留 120 日，單季 EPS（12季）與月營收（24月）全量寫入。
    - 分塊每 2,000 筆獨立 transaction 提交，執行 `ANALYZE` 更新統計資訊，資料庫總體積嚴格受控於 95MB 以內（< 0.3% GCP Free Tier 30GB 限制）。
  - **Live Runtime API 線上驗收 100% PASS**（測試端點 `https://janus-api-2oo7qbkd5q-uc.a.run.app`）：
    - `GET /api/v1/public/stocks/2330/visual-series?metric=close&limit=10`：回傳 HTTP 200，最新收盤價 2400.00。
    - `GET /api/v1/public/stocks/2330/visual-series?metric=eps&limit=8`：回傳 HTTP 200，`data_status: available`，連續 8 季單季 EPS 正確呈現（2026 Q2: 27.25, Q1: 22.08, 2025 Q4: 19.51 ...）。
    - `GET /api/v1/public/stocks/2330/visual-series?metric=revenue&limit=8`：回傳 HTTP 200，`data_status: available`，連續 8 個月單月營收正確呈現。
    - `GET /api/v1/public/stocks/6488/visual-series?metric=close&limit=10`（上櫃櫃買標的環球晶）：回傳 HTTP 200，最新收盤價 814.00。
    - 抽查 `2454`（聯發科，3960.00）、`2317`（鴻海，247.50）、`8069`（元太，157.00）均正常即時回傳。
    - `GET /api/v1/public/kline/2330?limit=200`：回傳 200 筆完整 K 線蠟燭圖資料。
- **全市場補檔任務宣告完成**：全市場上市櫃 1,925 檔股票之走勢圖、K 線圖、單季 EPS 與月營收折線圖已全數連通且有界熱快取投影完畢，可正常運作於日常更新與滾動淘汰機制。

## 個股圖解與白話資訊（2026-10-27 前端增量）

- **程式／測試／部署 100% PASS**：來源 `73f02252c8a7e8c3d2162d7f25dd22a5c023915f`。
  - **前端改進**：四面向圖解（股價走勢、公司營運、價格評價、波動風險）、唯一估值參考價帶、波動比較進度條、公告摘要與閱讀提示、分析與報告技術明細預設收合。
  - **測試驗證**：[Flutter User App CI #40482544858](https://github.com/tommylin15/janus-omniforge/actions/runs/40482544858) SUCCESS，包含 390px 寬度／200% 字級（`TextScaler.linear(2)`）無溢位無例外 Widget 回歸測試。
  - **正式發布與部署**：完整 Release [#40482790589](https://github.com/tommylin15/janus-omniforge/actions/runs/40482790589) SUCCESS；0% Candidate [#40483579702](https://github.com/tommylin15/janus-omniforge/actions/runs/40483579702) SUCCESS；Auth boundary [#40483894328](https://github.com/tommylin15/janus-omniforge/actions/runs/40483894328) SUCCESS；受控 API-only 100% [#40484056048](https://github.com/tommylin15/janus-omniforge/actions/runs/40484056048) SUCCESS。
  - **即時 Runtime 證據**：Cloud Run 正式環境 `https://janus-api-2oo7qbkd5q-uc.a.run.app/app/build-id.txt` 讀回吻合 `73f02252c8a7e8c3d2162d7f25dd22a5c023915f`；`/app/` 回傳 200；保留先前 `ec106165` rollback 基準；不改 Jobs／Scheduler／IAM／Secret／Owner 資料。收據見 [Operations](spec/operations-and-testing.md)。
- **尚待**：由 Owner 實機登入瀏覽個股頁面確認白話與圖解易讀性。

## Owner 關注清單讀取修復／SEQ-08 實機驗收結案（2026-10-27）

- **實機登入驗收完成（2026-10-27 使用者實測 PASS，SEQ-08 結案）**：
  - **關注清單正常載入**：使用者確認「關注」頁面已於 25 秒內正常載入完成，不再顯示「關注清單暫時無法使用」，第二輪 LATERAL index 行情查詢與逾時保護實機驗收 PASS。
  - **普通股進階資料與四模型報告存在**：使用者點入普通股（如 2330 或持股），確認進階資料之四角色模型卡、Fact Pack 週期報告、歷史資料、資料日與版本號已完整連通並有真實資料呈現，實機資料鏈驗收 PASS。
  - **排版混亂與呈現易讀性處理**：使用者確認目前有資料但排版混亂，已明確指定轉入「個股圖解與白話資訊（2026-10-27 前端增量）」獨立進行驗證與部署，不阻礙 SEQ-08 原定模型與報告資料交付。
  - **判定：SEQ-08 核心主線正式宣告結案（CLOSED / BOUNDED_CLOSEOUT_PASS）**。

- **第二輪真實 Root Cause 與部署（2026-10-27）**：使用者於第一次 Dev100 後仍回報「關注清單出不來」，故不能把前次部署標為 Owner 驗收。專用有界 Cloud Run 服務診斷 [#40459679884](https://github.com/tommylin15/janus-omniforge/actions/runs/40459679884) 觀察到 `GET /api/v1/me/watchlist` 有 3 筆 HTTP 200，但 latency 約 10.115／10.475／12.632 秒，明確超出 Flutter 9 秒 timeout；同期間 `psycopg.errors.QueryCanceled` 出現在 watchlist/context DB 讀取呼叫堆疊。修復：將關注清單讀價及共用 EOD quotes 改為依 Owner symbol 的 `publication.stock_serving_recent` 有界 LATERAL 最近筆數查詢，移除每次讀取全市場 `publication.stock_latest` security-barrier DISTINCT ON；Flutter timeout 9→25 秒，超過 10 秒時維持 loading，真正逾時才顯示重試，並新增無全市場 View 的 SQL regression tests。無新 migration、Job 或模型資料異動。
- **第二輪 Release／候選／Auth／API100：PASS**。含同源核准的 Admin Google 共用登入：Release [#40460262500](https://github.com/tommylin15/janus-omniforge/actions/runs/40460262500) Python/Flutter/四映像/registry PASS，source `ec1061652bfb2226e88f1b25aa9d416dee51a2ed`；0%-candidate [#40460824526](https://github.com/tommylin15/janus-omniforge/actions/runs/40460824526) PASS；auth-boundary [#40461139265](https://github.com/tommylin15/janus-omniforge/actions/runs/40461139265) PASS；受控 API-only 100% [#40461306304](https://github.com/tommylin15/janus-omniforge/actions/runs/40461306304) completed/success，來源、回復及 live health/readback gate PASS。Owner 實機登入確認關注清單與四模型資料均 PASS。



- **使用者實機問題**：Janus Dev 關注頁顯示「關注清單暫時無法使用」與錯誤的 `0/50`；獨立已授權 Janus Dev Read-only v2 owner watchlist 仍回傳有效非空資料，不能當成清單已被刪除。截圖不是登入後四模型呈現 PASS。
- **正式 API／Flutter 修補已發布 Dev 100%：PASS（非 Owner 正向）**。程式來源 `ab5b12686839019cec40065fa6d043b6334e52a0`：GET watchlist 先使用既有 PostgreSQL owner rows、cached quotes，行情 refresh 移至 response 後；cached quote reader 失敗時保留已保存列表；Google 同帳號憑證只對 401 唯讀 GET 最多更新重試一次；loading/error 清單數量顯示未知 `—/50` 而非假的 `0/50`。附 Python mock quote 故障及 Flutter 9s timeout/widget regression tests。
- **Gate 真實收據**：完整 Python/Flutter+四映像 GHCR Release [#40452156270](https://github.com/tommylin15/janus-omniforge/actions/runs/40452156270) SUCCESS；0% 候選 [#40452708990](https://github.com/tommylin15/janus-omniforge/actions/runs/40452708990) SUCCESS；auth boundary [#40452973476](https://github.com/tommylin15/janus-omniforge/actions/runs/40452973476) SUCCESS；既有 Dev API-only 100% [#40453071869](https://github.com/tommylin15/janus-omniforge/actions/runs/40453071869) SUCCESS，含 active build-id/health/rollback guard。只改 API/App 路由，未更新四 Jobs／Scheduler／模型／Owner ledger。四 Jobs 先前版本 read-only baseline [#40452493915](https://github.com/tommylin15/janus-omniforge/actions/runs/40452493915) PASS。
- **仍待原定 Owner 已登入畫面正向**：Browser connector 本輪仍需 originating browser context，無法讀取使用者 Android 已登入 session；不能以匿名 401、API-only PASS 或 MCP 資料讀取冒充 Owner UI PASS。需要使用者重整正式 `/app/`，於「關注」或「記帳／筆記→持股」進入普通股，實際檢查進階資料四模型、週期事實報告／歷史、資料日、版本、缺值後才結案 SEQ-08；不重做 TPEx、Core、模型訓練或 Deep Coverage。

## SEQ-08｜TPEx 正式修復及四模型報告/歷史最終讀回（2026-10-27，最新）

- **TPEx 修復、合法新 Core、四 Dev Jobs/API100：PASS**。正式來源 `c4605a84eb46257cbf628b33e2156ebc01f5b9ac`，官方 TPEx price benchmark 9/10月補收與全新 immutable Core `sha256:5d741c0b8804322e87cf7bd4c1a4c04be3244e36e000a216d0fc07912596166a` [#40337663516](https://github.com/tommylin15/janus-omniforge/actions/runs/40337663516)。新版 Release [#40319442822](https://github.com/tommylin15/janus-omniforge/actions/runs/40319442822)、四 Jobs [#40320593857](https://github.com/tommylin15/janus-omniforge/actions/runs/40320593857)、API100 [#40336305146](https://github.com/tommylin15/janus-omniforge/actions/runs/40336305146) 成功，保留五真 UBJ、不重訓、不回落舊模型、不新增資源/IAM。
- **全市場 Quant GCS + PG 真資料：PASS**。本 Core 全市場 Screening `1991`、實際有效 `1820`（TWSE `1058`、TPEx `762`，91.4%）；171 筆合法缺排名。精確 GCS manifest/identity/artifact hash 收據 [#40353770844](https://github.com/tommylin15/janus-omniforge/actions/runs/40353770844)、PG `jsonb_typeof(seq08_quant_rank)='object'` 真 SELECT `1820` [#40354200697](https://github.com/tommylin15/janus-omniforge/actions/runs/40354200697)，相同 immutable Core 且 `PG_SELECT_READBACK_PASS`。公開 2330/2882 兩檔合法 Quant/Risk `ACTIVE_PREDICTED`；未造 10/26 閉市假 EOD。舊 Core 的 TPEx 0/1058 排名不可與本新 Core 混用。
- **Owner 去識別 union Deep Coverage 真實執行及 GCS/PG：PASS**。真正現有 Dev Mart Job [#40355591648](https://github.com/tommylin15/janus-omniforge/actions/runs/40355591648) 成功；GCS hash/identity/feature `READBACK_PASS` [#40356749262](https://github.com/tommylin15/janus-omniforge/actions/runs/40356749262)，Mart execution `2375334c-6cc1-4653-a5b2-d732d9bd8b1e`、目標8檔，Quant `ACTIVE_PREDICTED=6` / `FEATURE_INCOMPATIBLE_OR_MISSING=2`；Risk `6/2`；Fundamental `ACTIVE_CACHED=2` / `FEATURE_INCOMPATIBLE_OR_MISSING=6`；Valuation `ACTIVE_CACHED=4` / `FEATURE_INCOMPATIBLE_OR_MISSING=4`。原始價量／營收／財報缺值按實際原因展示，不拿 fallback 或均值造值。
- **事實報告及 PG 既有分析 history：PASS（存取層未驗）**。[Deep PG readback #40357282484](https://github.com/tommylin15/janus-omniforge/actions/runs/40357282484) `seq08-pg-product-readback` completed/success、`PG_SELECT_READBACK_PASS`，同 execution `private.specialist_product` `8` 列、`four_model_serving` `8`、`analyst_inputs` `8`、`stock_report` `8`，`stock-report.v1` schema `8`，`symbols_with_earlier_history=8`。SQL 全程 READ ONLY、公開回報僅匿名聚合、0 Owner ledger mutation；不能將 PG 保存成功直接宣稱 Owner UI/API 正向驗收。
- **SEQ-08 結案：Owner 已登入個股 UI 正向驗收 PASS（2026-10-27，CLOSED）**。2026-10-27 使用者實機登入確認關注清單正常載入完成；點入普通股（如 2330 或持股）確認四角色卡片、最新 `stock_report`、先前報告歷史、資料版本與缺值標示均有真實資料呈現。UI 呈現排版與易讀性優化明確轉入「個股圖解與白話資訊（2026-10-27 前端增量）」持續執行。**整體 SEQ-08 = `CLOSED / PASS`**。

## SEQ-08｜正式 TPEx→Core→GCS→PG 驗收與 Deep Coverage（2026-10-27 凌晨最新）

- **新 Core 上的真實全市場 Quant 正向已閉環至 PostgreSQL**：固定 model/application source `c4605a84eb46257cbf628b33e2156ebc01f5b9ac`、Core `sha256:5d741c0b8804322e87cf7bd4c1a4c04be3244e36e000a216d0fc07912596166a`，完整 GCS readback [#40353770844](https://github.com/tommylin15/janus-omniforge/actions/runs/40353770844) 精確 execution `fd2a4886-e800-4651-8706-00efed4062cf`、artifact hash readback `RANK_READY_PASS`；接著真正一次 Dev PG read-only SQL [#40354200697](https://github.com/tommylin15/janus-omniforge/actions/runs/40354200697) `seq08-pg-product-readback` completed/success、`PG_SELECT_READBACK_PASS`、`gcp_job_executions=1`。兩者皆確認 `1991` Screening、`1820` 正式 JSONB percentile object、`171` null；GCS 同市場 TWSE `1058`、TPEx `762`，總覆蓋率91.4%，未偽補價格。剩下 `core_stock_21_sessions_incomplete=157`、`market_unresolved=5`、`not_latest_market_core_session=5`、`stock_session_missing_or_stale=4`。
- **公開二股新版真實推論**：PG same-Core 唯讀 spotcheck 顯示 2330 Quant `0.5129968523979187`、Risk `0.28244033455848694`；2882 Quant `0.4791782796382904`、Risk `0.3632313311100006`，四筆 `ACTIVE_PREDICTED`。2330 Valuation PE/PB 亦 `ACTIVE_PREDICTED`；Fundamental 2330/2882 缺 `monthly_revenue_comparison_window_incomplete`，2882 Valuation 缺 MOPS 可比季度，均保持 partial。
- **新 Core Deep Coverage 已觸發，終態未讀回前不稱完成**：[SEQ-08 Deep Coverage #40355591648](https://github.com/tommylin15/janus-omniforge/actions/runs/40355591648) `mart_operation=deep-coverage`、同新 Core、一次現有 Dev intelligence Mart Job + `MART_PRODUCT_PROJECTION=true`，只用既有 Owner 去識別 held/watchlist union、正式五真 UBJ、不 retrain、不 new resources/LLM/Owner ledger。需實際 `seq08-real-mart-acceptance` terminal、GCS `specialist-manifest.json`／`four-model-serving.json`／`analyst-inputs.json`、PG `private.specialist_product` 同 execution 的真資料讀回，與 Fact Pack/歷史/UI 分別驗。
- **Owner UI 尚未驗**：Dev MCP `internal error`；無合法 Owner 已登入 browser session，不能將負向 401 當正向 PASS。SEQ-08 維持 `LIVE_PARTIAL`，PG 上線成功≠四模型全部有值或登入 UI 完成。

## SEQ-08｜新 TPEx Core 真排名驗收（2026-10-27 凌晨最新）

- **TPEx 全市場 Quant 恢復：GCS EXACT PASS**：[新 Core Mart #40339115367](https://github.com/tommylin15/janus-omniforge/actions/runs/40339115367) 原固定 source `c4605a84eb46257cbf628b33e2156ebc01f5b9ac` 真實執行成功；[GCS 精確 readback #40353770844](https://github.com/tommylin15/janus-omniforge/actions/runs/40353770844) 真執行 `seq08-product-readback` SUCCESS、7 offline tests PASS，`status=RANK_READY_PASS`、`scope=EXACT_ONE_NEW_CORE_PG_PROJECTED_SCREENING_GCS_READBACK`、`mart_execution_id=fd2a4886-e800-4651-8706-00efed4062cf`、Cloud Run `janus-intelligence-mart-6g2d4`；new Core `sha256:5d741c0b8804322e87cf7bd4c1a4c04be3244e36e000a216d0fc07912596166a`。Screening **1991**，有效 Quant percentile **1820**（TWSE **1058**、TPEx **762**，覆蓋 91.4%）；另 `core_stock_21_sessions_incomplete=157`、`market_unresolved=5`、`not_latest_market_core_session=5`、`stock_session_missing_or_stale=4`。公開 2330/2882 `rank_valid=true`。GCS artifact `sha256:46b9a692001f7c0e1be52cf1953336acd31ae78f1d863f130e09cdaf09211f07` 與 manifest hash `sha256:664468bc8a8f00e918bda43a1a9c66cd00d50d9fe05f15f7a9f26e1cbdf7c207` 已精確核對，不能混用舊 1058/0 core snapshot。
- **Logging 問題處理**：已實作受限時間／250物件總量／24個近期候選／固定 Core ID／hash 校驗的 GCS 備援驗收路徑（`seq08_product_readback.py`，不擴 IAM）；本次真實 Workflow 已直接成功讀出 exact execution，無需靠備援降低原有驗收 gate。相關離線 tests 隨 [readback #40353770844](https://github.com/tommylin15/janus-omniforge/actions/runs/40353770844) PASS。
- **PG 實際 SELECT 尚待**：已用真 `mart_execution_id=fd2a4886-e800-4651-8706-00efed4062cf`、新 source `c4605a84` 提交既有 Dev 單次唯讀 PG SQL probe [#40354200697](https://github.com/tommylin15/janus-omniforge/actions/runs/40354200697)。只有其完成、`PG_SELECT_READBACK_PASS`、新 snapshot `jsonb_typeof(seq08_quant_rank)='object'` 真數量確定，才能將 PG 正向標 PASS；GCS 投影成功不等於 PG 已驗。
- **仍待 SEQ-08**：PG 讀回 PASS → 以同源新 Core 一次 `deep-coverage` → 讀 `four-model-serving.json`、`analyst-inputs.json`、PG `specialist_product`、Fact Pack／報告及 Owner history → Owner 已登入 UI 正向。Dev MCP `internal error` 且無可用授權 browser session，UI 目前 `NOT_VERIFIED`。無重訓、無新資源、無舊模型 fallback；整體仍 `LIVE_PARTIAL`。

## SEQ-08｜TPEx benchmark Core 補收與新產品驗收（2026-10-26 23:40 台北；最新）

- **Core 有界補收及新 immutable snapshot：LIVE_PASS**。正式 TPEx official price index 2026-09 20 sessions（insert 2/update 17/reuse 1）與2026-10至10/22 15 sessions（insert 15），真既有 Dev ingestion 執行 `janus-ingestion-core-47jlt`：[Core workflow #40337663516](https://github.com/tommylin15/janus-omniforge/actions/runs/40337663516) apply completed/success、`PASS_NEW_OFFICIAL_TPEX_CORE`。**新 Core** `sha256:5d741c0b8804322e87cf7bd4c1a4c04be3244e36e000a216d0fc07912596166a`、core execution `bf26bfb1-3dcc-4f76-85b4-effcc4f25ef3`；舊 Core `sha256:544970f64...` 保持不變。
- **同版修復已部署 Dev**：固定源 `c4605a84eb46257cbf628b33e2156ebc01f5b9ac`。完整 GHCR Release [#40319442822](https://github.com/tommylin15/janus-omniforge/actions/runs/40319442822)、0% API [#40320190614](https://github.com/tommylin15/janus-omniforge/actions/runs/40320190614)、Auth [#40320423764](https://github.com/tommylin15/janus-omniforge/actions/runs/40320423764)、既有四 Dev Jobs [#40320593857](https://github.com/tommylin15/janus-omniforge/actions/runs/40320593857)、API100 [#40336305146](https://github.com/tommylin15/janus-omniforge/actions/runs/40336305146) all completed/success（早期 #40335624533 promotion failure 後受控修復，不算第一次即 PASS）。五份核准真模型權重不變，不採舊模型 fallback。
- **新 Core 上的全市場 Screening／PG 投影 Job 已成功；內容讀回尚未完成**：[SEQ08 new-Core Mart #40339115367](https://github.com/tommylin15/janus-omniforge/actions/runs/40339115367)，`seq08-real-mart-acceptance` completed/success、真 Mart 在新 Core 運行、`MART_PRODUCT_PROJECTION=true`、exit receipt `REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING`；不等於 PG SELECT／TPEx rank 驗收 PASS。需以同一 execution 的 GCS manifest/artifact 及 PostgreSQL `jsonb_typeof(seq08_quant_rank)='object'` 讀回，按市場呈現 TWSE/TPEx cohort/count；嚴禁將舊 Core 的 1,058 TWSE / 0 TPEx 改稱新版數字。
- **本輪精確讀回 blocked**：已提交精確 GCS artifact readback source/run/Core identity [commit `9dc59f72`](https://github.com/tommylin15/janus-omniforge/commit/9dc59f725be6a058114f770600255bdbab0d853b)，但 [readback #40351124199](https://github.com/tommylin15/janus-omniforge/actions/runs/40351124199) `seq08-product-readback` failed at `CLOUD_LOG_IDENTITY` with `cloud_logging_exact_execution_read_denied`；`gcp_mutations=0`。尚無精確 Mart execution UUID／screening manifest GCS readback，不能聲稱新版 TPEx 排名恢復、PG正式可用或 Fact Pack/Owner history 可用。優先修復既有讀取路徑（可用同權限授權的有界 GCS/PG 唯讀替代證據，不增 IAM 權限或額外付費資源），不可盲目重跑有寫入的 Mart 工作。
- **下一入口唯一 SEQ-08**：解除 GCS/PG 回讀阻塞 → 驗 TPEx 21 sessions/同市場有效排名與 PG 真新 snapshot → 新 Core 上 one-shot Deep Coverage（僅使用現有 Owner 去識別 union）→ 四模型 GCS／PG／報告／Owner history 正向讀回 → 使用者本人授權 session 後 Owner UI 登入驗收。Owner Dev MCP／browser 正向 access 仍不可用，UI = `NOT_VERIFIED`；整體 `LIVE_PARTIAL`，不擅自閉環、不另開 SEQ-09。

## SEQ-08 交易日修正後全市場排名實測（2026-10-26，最新）

- **Quant 真全市場 GCS-only 計算 PASS／未發布 PG**：[真 Mart Job #40300491771](https://github.com/tommylin15/janus-omniforge/actions/runs/40300491771) `seq08-real-mart-acceptance` completed/success、真 Cloud Run `janus-intelligence-mart-p2gc2`、receipt `REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING`；`MART_PRODUCT_PROJECTION=false`，不改舊 1,991 筆 immutable PG 投影。精確後續 [GCS Artifact readback #40301816784](https://github.com/tommylin15/janus-omniforge/actions/runs/40301816784) `seq08-product-readback` completed/success、**RANK_READY_PASS**，本次新 artifact `sha256:64af70e31e04092de7c90ebe018704a855a581e707ed0eb80cd781c336d2c511` 對應真正 Core `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3`，來源 `43543ac684f34341265069244b5507f51afd5cff`，`analysis_as_of=2026-10-26`、實際最後交易日2026-10-22。
- **真正排名數字**：Screening `1991` 股票；合法同市場 `seq08_quant_rank` percentile **1058**（TWSE 1058、TPEx 0），GCS gate counts：`ranked=1058`、`benchmark_21_sessions_missing=891`、`core_stock_21_sessions_incomplete=32`、`market_unresolved=5`、`stock_session_missing_or_stale=4`、`not_latest_market_core_session=1`，合計 1991。公開 2330／2882 均 `gate=ranked` 且合法 `rank_valid=true`，真 21/21 OHLCV 市場日缺口 0。這是 **53.1% 真實排名覆蓋、TWSE 正向**，絕不等同 TPEx 或全市場完整。
- **部署與 Risk 正向**：[四 Dev Jobs #40281342258](https://github.com/tommylin15/janus-omniforge/actions/runs/40281342258)、[API100 #40299267385](https://github.com/tommylin15/janus-omniforge/actions/runs/40299267385) success；真正 PG/公開兩股唯讀 [#40299434731](https://github.com/tommylin15/janus-omniforge/actions/runs/40299434731) `PG_SELECT_READBACK_PASS`，Risk12 2330 `0.28244033455848694`、2882 `0.3632313311100006` ACTIVE_PREDICTED；Fundamental/Valuation 真缺值照實保留。#40282426306 先前 PG Job `skipped`，不可沿用其綠燈作證；GCS 讀回第一次 #40301481080 只因離線假資料雜湊順序斷言失敗，無 GCP readback，已補測並以 #40301816784 真成功重跑。
- **唯一剩餘工程**：先有界確認 TPEx index price benchmark 為何無法形成 21 個合法同市場 session（891 筆 gate，不能直接當作 891 筆全是 TPEx），缺少資料依既有授權來源小範圍補入真正 Core，不准填造價格／指數；32 筆缺個股窗口按真交易日處理。**GCS-only 成功不等於 PG／Owner 上線**：新合法 Core snapshot 產生後，做完整 `Screening→PG projection→target Deep Coverage→四模型 Fact Pack/Owner report/history` 真讀回，不能覆寫原 `(analysis_as_of,core_snapshot_id,symbol)` 1991 筆 immutable PG。Owner 授權登入 session/MCP 仍不可用，UI 正向 `NOT_VERIFIED`。整體 `SEQ-08=LIVE_PARTIAL`，不重訓／不回退舊模型／不新增 SEQ-09。

## SEQ-08 2026-10-26 晚間真資料進展（最新）

- **同版 Dev Jobs／API100 都 PASS**：正式源 `43543ac684f34341265069244b5507f51afd5cff`。四 Jobs [#40281342258](https://github.com/tommylin15/janus-omniforge/actions/runs/40281342258) `jobs-rollout` PASS、81 tests；API direct 100% [#40299267385](https://github.com/tommylin15/janus-omniforge/actions/runs/40299267385) `promote-api-only` PASS、51 tests，固定 digest/身份讀回；並無舊模型 prediction fallback。
- **修復 PG gate 假陽性並驗真 Core 窗口**：#40282426306 workflow 雖 SUCCESS，但真 PG Job 是 skipped，不能算通過。正確觸發的 [#40299434731](https://github.com/tommylin15/janus-omniforge/actions/runs/40299434731) `seq08-pg-product-readback` 確實執行並取得 `PG_SELECT_READBACK_PASS`。在既有 2026-10-26 immutable Core snapshot `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3`，**2330、2882 均已 21/21 合法市場日、missing 0、`ready_for_same_market_rank`**。真 Risk12 即時唯讀推論：2330 `0.28244033455848694`、2882 `0.3632313311100006` 均 ACTIVE_PREDICTED；Quant 兩檔 X 已足（只缺 `ret20_market_rank`），其餘月營收/2882季財務合法缺值照實保留。
- **舊 PG 排名不可覆寫**：同 snapshot 舊 `private.market_screening_product` 仍 1,991 rows、valid Quant rank 0；屬修正前既有 immutable 投影，不可將 PG SELECT成功冒充新全市場 rank PASS。**GCS-only 真實全市場 Screening** [#40300491771](https://github.com/tommylin15/janus-omniforge/actions/runs/40300491771) 已 executed/completed SUCCESS、Mart Cloud Run `REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING`，使用相同 Core 但新版本 GCS artifact，強制 `MART_PRODUCT_PROJECTION=false`、零 PG product overwrite／無 LLM／無新資源；實際 `seq08_quant_rank.gate_counts` 仍需從 GCS 內容讀回才可宣稱排名恢復。
- **下一個唯一動作**：[新 GCS-only Screening Artifact 讀回 #40301481080](https://github.com/tommylin15/janus-omniforge/actions/runs/40301481080) 已提交，應核對真 `screening_rows`、`ranked_rows`、同市場 cohort 與 2330/2882 的 rank gate，並完整確認 Job 非 skipped。若 rank 成功，此為 GCS 計算層成功，不等於 PG/Owner正式產品重投影；必須有更新有效 Core snapshot 才能安全發布同版 Screening／target Deep Coverage／報告，不能覆寫舊 composite identity。
- **Owner UI 正向仍 NOT_VERIFIED**：Janus Dev private MCP 依然 internal error，browser session 無法授權讀回；需新登入 session 真測四模型卡、報告、Owner history。整體 `SEQ-08 = LIVE_PARTIAL`，不新增 SEQ-09、不重訓／不重問四模型授權。

## SEQ-08 交易日修正集中部署最新進度（2026-10-26；取代下方進行中快照）

- **四 Job 新版 Rollout PASS**：[GitHub #40281342258](https://github.com/tommylin15/janus-omniforge/actions/runs/40281342258) completed/success，`jobs-rollout` success、81 tests、`ghcr-jobs-rollout-receipt` Artifact 12633431449；發布 immutable model/calendar source `43543ac684f34341265069244b5507f51afd5cff`，沿用五份真權重，沒有 legacy model fallback。
- **API 新版 100% PASS**：[GitHub #40299267385](https://github.com/tommylin15/janus-omniforge/actions/runs/40299267385) `promote-api-only` completed/success，51 tests、`ghcr-api-only-promotion-receipt` Artifact 12639646884；既有 Dev API direct promotion，不變更四 Job/Scheduler/Owner／IAM。
- **先前 #40282426306 為假陽性風險，已正名**：[GitHub #40282426306](https://github.com/tommylin15/janus-omniforge/actions/runs/40282426306) workflow completed/success，但僅 `inventory` job success，`seq08-pg-product-readback` = **skipped**，原因是 request commit message 不符合 `startsWith('ops(seq08): verify exact PostgreSQL product projection')` gate。不能拿其成功取代 Core/PG 正向驗收。
- **新版 Core／PG 真讀回已重新觸發**：[GitHub #40299434731](https://github.com/tommylin15/janus-omniforge/actions/runs/40299434731) 以精確 commit prefix 觸發同一既有 Dev Mart Job 的一次 SELECT＋公開 2330/2882 in-memory feature gate；任務進入 `seq08-pg-product-readback`，結果在最終收據讀回前仍 `PENDING`。現有 immutable 2026-10-26 Core/PG snapshot `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3` 不重寫、不補 10/26 休市日假股價；診斷的 21 sessions 已同步排除休市日與其他市場指數。新同源真模型 ranking/GCS/PG 與 Owner UI 正向仍待實際 readback，不以 PG舊資料成功冒充新版排名。
- **下一關**：核對 #40299434731 的真 Rank input gate；若 Core 仍無新的有效 immutable snapshot，不能覆寫同 `analysis_as_of + core_snapshot_id + symbol` PG 1,991筆舊 Screening；新 Core available 後跑全市場 Screening → Deep Coverage → 四模型 GCS／PG report／Owner history。Janus Dev MCP 仍 internal error 且無可用 Owner browser session，Owner 登入 UI = `NOT_VERIFIED`。整體 `SEQ-08 LIVE_PARTIAL`。

## SEQ-08 休市日校正與 Dev 新版驗收（2026-10-26 下午）

- **已核對技術根因**：既有 Core 2026-10-26 snapshot 的 2330／2882 21 market-session 輸入被 2026-09-25 休市日佔位，10/23 與 10/26 亦為 2026 年已確認閉市日期；參考 `jobs/intelligence-mart/intelligence_mart/market_sessions.py` 與 [舊 Core PG 真資料 #40265638862](https://github.com/tommylin15/janus-omniforge/actions/runs/40265638862)。目前 Core 不應造出 10/26 的不存在 EOD；正確市場日窗口排除閉市日、對同市場選 21 個真 session（20 段報酬），不補價也不偽造排名。
- **新修正 Release／API0／Auth 已 PASS**：正式源 `43543ac684f34341265069244b5507f51afd5cff`，[GHCR full Release #40266792603](https://github.com/tommylin15/janus-omniforge/actions/runs/40266792603)、[四 Job 既有 digest+config baseline #40266979470](https://github.com/tommylin15/janus-omniforge/actions/runs/40266979470)（上一 live source `420b1b5c`）、[0% API candidate #40267268006](https://github.com/tommylin15/janus-omniforge/actions/runs/40267268006)、[OAuth/Owner/Admin/MCP 匿名 boundary #40281196164](https://github.com/tommylin15/janus-omniforge/actions/runs/40281196164) 都 completed/success。五份真 UBJ／Registry 不變，不要求再授權模型或舊模型相容。
- **現階段非結案**：[四 Job 同版 rollout #40281342258](https://github.com/tommylin15/janus-omniforge/actions/runs/40281342258) 已由受控 request 提交，必須讀 `jobs-rollout` 終態及 receipt 的 full canary、source/digest、可回復基準，未有最終成功前不能自行推 API100。[部署後 Mart Core/PG 唯讀 probe #40282426306](https://github.com/tommylin15/janus-omniforge/actions/runs/40282426306) 已在共用 `janus-dev-runtime-writers` queue，僅 SELECT 舊8筆 PG＋在部署版本內記憶體重新計算公共 2330／2882 最新 Core 21 session gate，不寫 PG／GCS 或 Owner。讀回腳本也已套用與模型完全相同的閉市／同市場日期過濾，對應 [selective CI #40282219549](https://github.com/tommylin15/janus-omniforge/actions/runs/40282219549) PASS。
- **下一個唯一入口**：成功四 Jobs receipt → 新 API 0%/Auth same-source gate 下受控 direct 100% → 讀回 PG probe 的新 21 session `gate`／`missing_21_session_count`、舊 immutable PG 0 rank 與正確的「舊版產品」區別；若仍無**新的合法 Core snapshot**，不可覆寫 `(analysis_as_of, core_snapshot_id, symbol)` 舊1,991筆 Screening。新 Core 可用後：新 full-market Quant rank、Owner union Deep Coverage、四模型真實輸出／Fact Pack／報告／history。**Owner 正向已登入 UI 尚 NOT_VERIFIED**（Dev MCP 此前 internal error，不把負向 401 當通過）。SEQ-08 維持 `LIVE_PARTIAL`。

## SEQ-08 新版 Dev 集中發布（2026-10-26 10:42 Asia/Taipei）

- **Release PASS**：本輪 Quant/Risk/財報缺值修正 `f648e1bc` + 完整發布固定來源 `420b1b5cdef91c7df1671660217315f62fc7e77f`；[完整 GHCR Release #40257626504](https://github.com/tommylin15/janus-omniforge/actions/runs/40257626504) Python、Flutter、四元件 publish、anonymous digest verification SUCCESS。沿用四角色五份已核准真 UBJ，沒有重新訓練或舊模型相容。
- **四個既有 Dev Jobs PASS**：[rollback baseline #40257779458](https://github.com/tommylin15/janus-omniforge/actions/runs/40257779458) 現役來源 `462bd1c8`、四 Job pinned digest/config 讀回、GCP writes 0；同版 [API 0% candidate #40258134293](https://github.com/tommylin15/janus-omniforge/actions/runs/40258134293)、[Auth boundary #40258331902](https://github.com/tommylin15/janus-omniforge/actions/runs/40258331902) SUCCESS；[四 Jobs rollout #40258444402](https://github.com/tommylin15/janus-omniforge/actions/runs/40258444402) `jobs-rollout` completed/success、程式 PASS、81 tests pass，正式 receipt artifact `12624496508`。不代表已重跑新的全市場 Screening。
- **API 100% PASS**：[API-only direct promote #40260316596](https://github.com/tommylin15/janus-omniforge/actions/runs/40260316596) completed/success，腳本 `PASS_API_ONLY_100_PERCENT` 僅於新 candidate health/build source SHA、revision traffic/Ready readback 通過時回傳 exit 0；部署同 source `420b1b5c`。保留前版 API revision 僅供系統安全回復，禁止當舊模型 prediction fallback。
- **部署後唯讀真資料讀回 PASS，但新 Quant Rank 仍待 fresh Core**：[SEQ08 PG #40260533885](https://github.com/tommylin15/janus-omniforge/actions/runs/40260533885) completed/success，Cloud Run 既有 Mart Job 唯讀 task `janus-intelligence-mart-7c595`，`PG_SELECT_READBACK_PASS`、`gcp_job_executions=1`、`gcs_persistent_writes=0`、`missing_serving=0`。最新 Core 仍為 **原 2026-10-26 snapshot** `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3`，同舊不可變 PG Screening 1,991 rows、`json_null_rank_count=1991`、`ranked_rows=0`，不是新程式完整重跑後的排名恢復證據；舊產品 8 檔 Quant 0/Risk 2/Fundamental 2/Valuation 4 與 2330/2882 公開探針結果仍為 partial。新版明確回傳 `monthly_revenue_comparison_window_incomplete`、`prior_year_target_base_missing` 等合法缺值理由。**不可覆寫舊 `analysis_as_of+core_snapshot_id+symbol` PG product；必須等待/取得真正不同、完整且可用的 Core snapshot**，再按同版走 full-market Screening → market rank gate_counts/21 sessions → target Deep Coverage → GCS/PG 四模型／報告。市場尚在交易中不以盤中/猜測資料充當官方 EOD。
- **Owner UI 正向仍 NOT_VERIFIED**：Janus Dev private MCP 此輪 `internal error`，無授權的 Owner 登入瀏覽器 session；需真登入讀回持股、觀察股、分析報告、模型卡、Owner history。不能將 401、公開頁或 PG 成功當 Owner 正向驗收。**SEQ-08 = LIVE_PARTIAL，唯一下一入口仍為此完整驗收**。

## SEQ-08 最新模型排名根因與收尾狀態（2026-10-26）

- **最終真資料驗收已讀回**：固定源 `462bd1c85708cb5bc4ce1877d35a3645ff9668d4`；Release #40215268427、四既有 Dev Jobs #40216332296、API100 #40247497520、Screening #40247788673、Deep Coverage #40248399245、GCS five-head #40249008222、PG產品 #40249244086 **PASS**。五真權重/Registry 不變；一次新 Core snapshot `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3`，2026-10-26 8檔 Owner 去識別 union：Quant 0/8、Risk2/8、Fundamental2/8、Valuation4/8，PG `missing_serving=0`。此為部分模型有效，不冒充全角色有效。
- **已證實 Quant 0/8 的直接原因**：[#40251221001](https://github.com/tommylin15/janus-omniforge/actions/runs/40251221001) `PG_SELECT_READBACK_PASS`；本次全市場 Screening **1,991 rows、真正 `jsonb_typeof(seq08_quant_rank)='object'` 為0、JSON `null` 為1,991、最近交易日10/22的1,955 rows**。早先以 `IS NOT NULL` 誤計「1,991有效排名」已更正並由 live 型別讀回反證；這是因子生成前置不成立，不是 PG JOIN 缺漏。2330/2882在 Screen 名單，但排名 `null`。唯一直接工程修正入口：分析 `market_screening.market_features` 中 `accepted_market`、`sessions_21`、完整每股 OHLCV sessions 及 20日報酬基礎的各gate拒絕原因、確認市場日來源後最小修復並重新驗收。禁止將8檔Owner排名偽作同市場全群組，不用Null填假排名，不因全市場有1991股擅自宣稱完整。
- **Risk/財報實際缺口**：Risk 6/8 `latest_market_session_missing_or_stale`、非fixture真Risk12 2/8 ACTIVE_CACHED；Fundamental6/8缺月營收基期及足月窗口；Valuation4/8缺可比財報MOPS季度。公共2330 `log_pe=2.712153434753418`、`log_pb=1.2493306398391724` 真 Valuation PE/PB雙頭預測成功；2882 PE/PB 因4項季財務特徵缺失，正式 missing，不虛構區間。8筆Mart→PG產品資料存在且hash對應。
- **Owner 正向產品驗收**：新版本登入後的持股、觀察股、分析報告、模型卡和Owner history 尚無可用授權 session；Janus Dev read-only MCP 讀取請求 internal error，不能以舊版手機截圖、未登入401或 PG 去識別投影代替 UI PASS。**SEQ-08 = LIVE_PARTIAL，不是 CLOSED**；其餘重點是 Quant X 預處理完整產出、Risk/財報正常缺值處理、Owner 正向產品驗收，沒有額外研究重訓、權重部署或舊模型回復。

## SEQ-08 最終真資料狀態（2026-10-26；本節覆蓋以下舊快照）

- **新版部署 PASS**：fixed app SHA `462bd1c85708cb5bc4ce1877d35a3645ff9668d4`；同版 GHCR Release #40215268427、API 0% #40215944127、OAuth/auth #40216220752、四既有 Jobs #40216332296、Dev API100 #40247497520 全部完成 SUCCESS；五頭核准 UBJ 與既有 ACTIVE GCS 指標保持不變，不需研究重訓或舊模型相容。
- **新真市場／模型工作**：全市場 Screening [#40247788673](https://github.com/tommylin15/janus-omniforge/actions/runs/40247788673)、本輪 deidentified Owner target Deep Coverage [#40248399245](https://github.com/tommylin15/janus-omniforge/actions/runs/40248399245) 各為 Cloud Run 實際 Job success。精確 GCS 產物讀回 [#40249008222](https://github.com/tommylin15/janus-omniforge/actions/runs/40249008222) `READBACK_PASS`：`analysis_as_of=2026-10-26`、Core snapshot `sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3`、Mart execution `c2604239-f954-4819-bfc2-6e102d62fcaf`，8檔，Quant 0/8（全部缺 `ret20_market_rank`）；Risk 2/8（ACTIVE_CACHED）、Fundamental 2/8、Valuation 4/8；剩餘嚴守缺值。Rank/價量完整窗口仍為可觀測 concrete BLOCKER，非重訓要求。
- **PostgreSQL 真投影 PASS**：[ #40249244086](https://github.com/tommylin15/janus-omniforge/actions/runs/40249244086) `PG_SELECT_READBACK_PASS`，同 Mart execution 8 rows，`missing_serving=0`，Quant／Risk／Fundamental／Valuation 各角色分布完全等於 GCS。新版 2330 Core 公共獨立真 Valuation PE/PB `ACTIVE_PREDICTED`，回傳 `log_pe=2.712153434753418`、`log_pb=1.2493306398391724`；其 Quant／Risk／Fundamental 仍缺特徵。2882 Valuation 缺合格可比較 MOPS 季財務，其他3模型也缺特徵。兩股皆**不在**本輪8檔 Owner target union；`public_samples_present.2330=true / 2882=false` 是 PG 歷史存在性，不代表本輪8檔新品報告已交付。
- **量化排名接線待釐清**：新版市場 rank 對這2股讀回0個，八檔 Quant 皆無合法 rank。已做第二輪小範圍只讀 full-market cohort aggregate [#40249995006](https://github.com/tommylin15/janus-omniforge/actions/runs/40249995006)，其結果依 Workflow/收據追加，不應將執行中當PASS。第一次診斷 #40249709135 為新 SQL 區塊 IndentationError，僅離線測試 FAIL、未派送雲端 Job；程式已修正。
- **未完成且必須留在 SEQ-08**：Quant 0/8 的 full-market rank／Core screening coverage、Risk 6/8 missing latest valid session、Fundamental 6/8 少月營收／基期、Valuation 4/8 少MOPS 可比季。Owner **新版**正向登入、個股報告卡、分析歷史及 UI 沒有可用授權 session（Janus MCP read-only 回 internal error），維持 `NOT_VERIFIED`。不保留舊模型 fallback；不將部分真推論/PG readback宣稱四模型全數完成，SEQ-08 = **LIVE_PARTIAL**。

## SEQ-08 2026-10-26 現役修正版部署／真資料入口（覆蓋下列歷史快照）

- **已部署最新模型 serving 程式**：source SHA `462bd1c85708cb5bc4ce1877d35a3645ff9668d4`；四模型五份核准真UBJ **未重訓/未換權重**，GCS atomic ACTIVE `models/registry/seq08-four-models-active.json` 沿前輪 #40193843435。非交易日 Quant/Risk 特徵與同市場 Screening rank 已修正且 CI PASS。
- **完整 Release** [#40215268427](https://github.com/tommylin15/janus-omniforge/actions/runs/40215268427)、四 Job 舊image基線 [#40215440753](https://github.com/tommylin15/janus-omniforge/actions/runs/40215440753)、Dev API 0% candidate [#40215944127](https://github.com/tommylin15/janus-omniforge/actions/runs/40215944127)、Auth 負向邊界 [#40216220752](https://github.com/tommylin15/janus-omniforge/actions/runs/40216220752)、**四既有 Dev Jobs rollout** [#40216332296](https://github.com/tommylin15/janus-omniforge/actions/runs/40216332296)、**新版 API 100%** [#40247497520](https://github.com/tommylin15/janus-omniforge/actions/runs/40247497520)：以上 Workflow 各自 completed/success；Jobs `phase=PASS`、API `promote-api-only=success`。不新增雲端資源、排程、模型相容或回復責任。
- **新版 Live 尚待**：全市場 Screening 真工作 [#40247788673](https://github.com/tommylin15/janus-omniforge/actions/runs/40247788673) 已派送進既有受控 Dev 工作流程，**目前 in_progress，不宣稱模型真預測 PASS**。下一步按結果再做最新合法 Core snapshot 的一次 `deep-coverage`，讀回 `four-model-serving.json`、Quant/Risk coverage、PG `private.specialist_product` 及獨立 2330／2882 公共股票驗收。
- **Owner 個人資料／UI**：先前五張畫面只證明舊版曾可登入；此新版正式登入 Owner 報告／歷史／UI 尚未取得可授權正向 session。Janus 唯讀 MCP 直接讀 2330、2882 和 Owner 都遇內部錯誤，不能標 PASS；不得造值或洩露私人組合。整體 SEQ-08 = **LIVE_PARTIAL**，不提前 CLOSED。

## SEQ-08 最新實際部署快照（2026-10-25；覆蓋本檔以下較早的「未部署」描述）

- **五真權重**：現有 Dev GCS create-only SHA readback [#40182200560](https://github.com/tommylin15/janus-omniforge/actions/runs/40182200560) PASS；Quant15、Risk12、Fundamental15、Valuation PE/PB 五頭原生驗證。
- **同版發布**：目標 application source `a2881c5c2532beb5570e29a1fda4472c7bb0d448`；完整 Release [#40184318031](https://github.com/tommylin15/janus-omniforge/actions/runs/40184318031) PASS；API 0% [#40184723596](https://github.com/tommylin15/janus-omniforge/actions/runs/40184723596) PASS、Auth [#40184856961](https://github.com/tommylin15/janus-omniforge/actions/runs/40184856961) PASS；四 Dev Jobs [#40184957380](https://github.com/tommylin15/janus-omniforge/actions/runs/40184957380) `phase=PASS`；API 100% [#40192646498](https://github.com/tommylin15/janus-omniforge/actions/runs/40192646498) `PASS_API_ONLY_100_PERCENT`（底層故障安全回復不是舊模型相容要求）。
- **五頭新 Registry 正式 ACTIVE**：read-only [#40193222840](https://github.com/tommylin15/janus-omniforge/actions/runs/40193222840) 當時證實舊模式/新指標缺失；受控 create-only [#40193843435](https://github.com/tommylin15/janus-omniforge/actions/runs/40193843435) `CREATE_ONLY_ACTIVE_SHA_READBACK_PASS`，5/5 模型再次驗 SHA 與特徵，唯一 `models/registry/seq08-four-models-active.json`，未覆寫舊 Registry／Owner／PG。
- **非fixture 真推論**：首輪 #40194391101 preflight FAIL（唯讀 #40194848340 確認沒有派送）；第二輪既有 Mart 真實 Job [#40195093746](https://github.com/tommylin15/janus-omniforge/actions/runs/40195093746) `REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING`、Core 真快照成功。
- **2026-10-25 最新產品唯讀驗收**：[ #40202862020](https://github.com/tommylin15/janus-omniforge/actions/runs/40202862020) `READBACK_PASS`、8 檔非fixture：Quant 0/8、Risk 0/8、Fundamental 2/8、Valuation PE+PB 4/8；2330／2882 **不在**本輪私有 held/watchlist 目標聯集；Owner 登入與 `private.specialist_product` SQL 正向讀回仍 `NOT_VERIFIED`。GCS 五頭新 Registry SHA 再驗 PASS，不等於四角色已有可用預測。
- **已定位資料日期根因**：唯讀 [#40203590101](https://github.com/tommylin15/janus-omniforge/actions/runs/40203590101) 成功，`analysis_as_of=2026-10-25`、8 檔 `latest_trade_date=2026-10-22`；Risk 8/8 `no_current_trade_observation`、Quant 同因+8/8 `full_market_same_day_percent_rank_missing`。Fundamental 6/8 缺月份／同期基期、Valuation 4/8 缺可比 MOPS 四季財報，是真實資料缺口、不可偽補。
- **已提交非交易日修正，** `analyst_inputs.py` 與 `market_screening.py` + `tests/test_seq08_market_sessions.py`：只用最後合格市場交易日、最多7曆日且股票與市場日一致；Quant全市場同日期至少100股排名（不從Owner八檔自行排名），缺值保持partial。該修正 main SHA `be4c8073af289029cf1a65846b68df8244930eb1`，**尚未重新 Release／Dev deployment；現役 runtime 仍是原 `a2881c5c`**。離線 CI #40204115769 PASS；完整產品／PG CI [#40204115801](https://github.com/tommylin15/janus-omniforge/actions/runs/40204115801) 查結果後再更新。
- **唯一下一入口仍是 SEQ-08 Live 收尾**：確認上述修正 CI → 同版 Release/四既有 Dev Jobs/API 安全部署 → 以新的合法 Core/Screening snapshot 重跑一次有界 8股/報告；讀回 Risk/Quant 的新特徵與 Cohort 順序（不修改已有不可變2026-10-25 screening PG），Fundamental/Valuation 缺值逐項展示；另外以正式 public Core 路徑驗 2330／2882，Owner 正向 UI/PG 需可用授權登入 session。未得到即 `LIVE_PARTIAL`，不再問四模型人工發布授權、不使用舊模型補值。

更新：2026-10-25（Asia/Taipei）。SEQ-01～03 DOC／CODE／OFFLINE_PASS；SEQ-04既有Dev四Job/API、migration069、PG隔離還原、單一兩小時Scheduler部署與14:30自然Controller tick PASS。Stage48h #40172644132 實刪223件／42,540,741 bytes（#40173298619後驗到期候選0），Private retention #40173273728 刪daily1份／26,044,882 bytes且PG成功，Iceberg現役catalog76／76通過。**2026-10-19當週 weekly 副本已補建成功**：#40175398373 新建1份30,872,328 bytes與原daily SHA-256一致；同run將舊10/25 00:30 backup occurrence從running修復為succeeded，CAS 1筆、outbox 1筆、讀回PASS。Owner／Admin真人登入後UI已由使用者提供2026-10-25手機瀏覽器五張截圖正向驗收PASS（Owner今日／持股／個股私人資料，Admin自動工作及六桶GCS盤點）；不保存個資截圖或token、不把畫面當作OAuth audience／A/B server isolation API驗收。**剩餘正式自然時點**為10/26新版02:30 ingestion→Core→screening與10/26新週首次自然備份驗收。SEQ-04=BOUNDED_CLOSEOUT_PASS／OVERALL_LIVE_PARTIAL；原定未到期自然時點不冒稱成功、不另設長期觀察。

**SEQ-08 最新發布決策（2026-10-25）**：使用者再次指定直接套新版四模型；不保留舊模型相容、舊模型回復與重複人工發布授權。這不是 live 切換收據；截至最近可驗證讀回 #40177858431，Risk 仍 DETERMINISTIC、另三份 ACTIVE pointer 缺失。原有 SEQ-05～07 程式離線 PASS 可沿用，新版五權重正式導入與 feature parity 後始能集中發布。模型候選唯讀／create-only 準備入口新增 `scripts/gcp/seq08_candidate_import.py`；不以工具存在當作 GCS 匯入。

## 唯一順序線

依序 **SEQ-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08**。不再分線派工；舊 UB／RV／D07／D08 是對照ID，不是另一份佇列。
每項固定拆為文件設計、程式開發、測試驗收、部署，完整指示見 [AI逐項指令](execution-cards/sequential-delivery.md)。

| 順序／任務 | 整併舊項 | 目前基線 | 部署歸屬 | AI 指示 |
|---|---|---|---|---|
| SEQ-01 收取、清理與市場分析總控 | UB-01 | DOC／CODE／完整離線217 PASS／Flutter7 PASS；live與部署交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-01) |
| SEQ-02 持股、買賣與觀察設定快照 | UB-03、4J／4R 的本次增量 | DOC／CODE／OFFLINE_PASS（220 Python、270 API、Flutter User PASS）；live/部署交 SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-02) |
| SEQ-03 日週月備份、保留清理與回復範圍 | UB-04（不是重開 OPS-P0-1） | DOC／CODE／OFFLINE_PASS（234 Python；API270、Mart247、Ingestion209）／LIVE與DEPLOY交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-03) |
| SEQ-04 基礎批次集中部署與兩小時切換 | UB-05：UB-01／03／04 合流 | 已有部署、清理、Controller、weekly 補建及 Owner/Admin UI 收據保留；2026-10-28 使用者取消兩條自然收據等待，行政結案，非新增 runtime PASS | 後續改走上方三大批次管線落地 | [歷史四階段指示](execution-cards/sequential-delivery.md#seq-04) |
| SEQ-05 Valuation 真資料、唯一估值卡契約 | RV-01…06、UB-02 Valuation 子功能 | **LIVE_CORE_ONEOFF_PASS／DOC_CODE_COMMITTED／OFFLINE_PASS／MART_API_LIVE_PENDING／DEPLOY_SEQ-08**：#40172093172真正透過既有Dev Job完成FinMind 2882 PB 2025-10至2026-08共11月11筆、Yahoo 2026Q2 BVPS=69.37 1筆，Stage→Core讀回11/11月、獨立#40172603358讀回兩股24/24有效月及BVPS=69.37，0來源失敗。2330既有FinMind四季EPS直接相加=86.28元，Mart程式標記research approximation。#40172051959分析測試226 passed，FinMind/Yahoo均標為approved_fallback。一次性工作已封存，#40172457154重觸發安全跳過0 mutation；Mart/Fact Pack/API最新版程式未部署，未有新版live報告價帶 | 唯一下一工程入口SEQ-06四模型正式serving、版本及共用快取；其後SEQ-07報告／Owner history／UI接線；最後SEQ-08集中部署Mart／Fact Pack／API／前端及認證讀回。SEQ-05部署仍交SEQ-08；不得重收11個月或重派一次性請求 | [四階段指示](execution-cards/sequential-delivery.md#seq-05) |
| SEQ-06 四模型正式上線模式、版本與共用快取 | UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；必要 parity | **ORIGINAL OFFLINE_PASS；2026-10-25 USER_PUBLICATION_APPROVED_FOR_ALL_FOUR；REAL_MODEL_BYTES_LOCAL_RELOAD_PASS；LIVE_REGISTRY_NOT_ACTIVE**：原 serving/快取 #40174399997／#40174400071 PASS；新增 [v26 Core MOPS 五因子 mapping d15e4d70](https://github.com/tommylin15/janus-omniforge/commit/d15e4d70af9d0238822918698be3f0ea9efaa8f6)（已用 source XBRL TWD 及同季 YTD revenue YoY、缺值 fail closed），[CI #40177556379](https://github.com/tommylin15/janus-omniforge/actions/runs/40177556379) SUCCESS。讀取真實 Drive 權重並重載 Quant XGB15、Risk XGB12、Fundamental RC1 XGB15、Valuation v26 PE/PB XGB5；Quant／Val雙頭固定向量誤差0，封包僅本地產生，**未上傳GCS**。GCS [唯讀 #40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431)：Risk registry mode=DETERMINISTIC、Quant／Fundamental／Valuation三份 active pointer 不存在；新技術門檻：Risk12 四新增因子服務接線／替換舊8 pin、Quant15 特徵供應與版本、Fundamental15＋5% X-only abstention、Valuation PE/PB 雙頭與 Core 真實日期／單位 parity。批准不是已 ACTIVE，原 Research 封包限制仍保存歷史語意 | **併入 SEQ-08 正式發版前完成 GCS candidate create-only import／hash、四模型 feature parity與必要 serving 修改、Registry／PG／Owner UI 驗收；若必要源資料缺失明列 partial** | [四階段指示](execution-cards/sequential-delivery.md#seq-06) |
| SEQ-07 分析報告、Owner history 與 UI 完整接線 | UB-02、D08、RV-05 合流 | **DOC／CODE COMMITTED／OFFLINE_PASS／DEPLOY_DEFERRED_TO_SEQ-08**：程式 SHA [f9ace32b](https://github.com/tommylin15/janus-omniforge/commit/f9ace32b795e6c1895901e7750f18be2f57da575)。Fact Pack週期報告保存四ML serving版本／狀態與缺值，model／input變更控制重產；Owner專屬持股／觀察股歷史唯讀API有auth／hash／去重；Flutter呈現四角色資料日／版本／缺口、唯一估值區間、報告沿用與歷史，CEO按需及Gateway故障退回事實報告。Python API／契約 #40175446096 275 passed／7 skipped／2 warnings，最新 #40175926343 272 passed／7 skipped／2 warnings；Flutter #40175926335 SUCCESS（widget tests＋PWA build）。真四artifact GCS／Valuation accounting／登入後正向Owner與Gateway live未驗；不宣稱四ML已 ACTIVE | **唯一下一工程入口 SEQ-08：固定SHA/digest 集中部署 Mart／API／Flutter、Owner登入／四模型／2330／2882真資料與rollback驗收** | [四階段指示](execution-cards/sequential-delivery.md#seq-07) |
| SEQ-08 四分析師到報告 UI 集中發布驗收 | UB-02 完成 gate、RV-06、D08 發布 | **CLOSED／LIVE_PASS**：TPEx 官方修復與新 Core #40337663516 PASS；全市場 Quant 1,820 檔（91.4%）與 PG 投影 #40354200697 PASS；Owner 去識別 8 檔 Deep Coverage（GCS/PG）#40357282484 PASS；第二輪 Watchlist LATERAL index 行情查詢與 Flutter 逾時修復部署 Dev100% #40461306304 PASS；2026-10-27 使用者實機登入確認關注清單正常載入、個股進階四模型卡/Fact Pack/歷史/版本號真實資料呈現 PASS。 | 核心工作已結案（排版易讀性轉入 2026-10-27 前端增量） | [四階段指示](execution-cards/sequential-delivery.md#seq-08) |

### SEQ-04 時段變更決策（2026-10-25；Cloud Scheduler 已切換，live部分待驗）

使用者指定：台北時間每日00:30 PG備份、每日02:30 ingestion、週一至五04:30 market-screening、週一至五06:30 private，Stage每日22:30／週六Iceberg22:30／mobile-ledger依既有條件。**程式契約已部署、原有Cloud Scheduler切換已完成**：唯一入口 `janus-ingestion-daily` 實際 `30 */2 * * *`／Asia/Taipei／ENABLED，HTTP target／OAuth身分未變，沒有新增第二Scheduler；部署與獨立GCP讀回 #40163729460／#40163927739 PASS。此時段設定成功不等於第一次新cron自然觸發成功，後者及批次資料鏈／Stage／Owner／UI仍需有界驗收。

## 階段狀態與接手規則

- SEQ-01 已依使用者授權開工；本輪修正來源失敗與 Mart queue 狀態，並使舊測試遵守現行 EOD／target-only 契約，未重建 Controller／Scheduler。已取得完整離線腳本及 Flutter Admin targeted 的同版 CI SUCCESS 收據；離線階段可交接SEQ-02，待SEQ-04執行集中部署與live。
- 本次文件整理完成，不等於每個任務的設計已審定或工程完成。上表基線來自 main 已提交程式／既有文件收據，沒有新的runtime驗收。
- 每次只執行使用者指定任務／階段；未指定階段時按該任務四階段指示完成可做範圍。遇跨任務集中部署，將部署及live驗收記為 `DEFERRED_TO_SEQ-04/08`，不是PASS；其餘前置交付完成即可往下一順序準備，不造成循環等待。
- SEQ-04結清SEQ-01…04；SEQ-08結清SEQ-05…08。測試驗收分部署前離線／Release與部署後真實驗收，不能在未部署時假稱live PASS。
- 記錄格式：`任務｜文件設計狀態｜程式狀態｜測試狀態（offline/live）｜部署狀態｜SHA/證據｜下一階段`。只在此維護active狀態；Operations保存收據。

### SEQ-05 四階段紀錄（2026-10-25，第四輪：一次性第三方補資料）

`SEQ-05｜DOC=UPDATED／CODE=Core補資料/簡化EPS及Mart→Fact Pack→API COMMITTED／OFFLINE=PASS（[分析CI #40172724791](https://github.com/tommylin15/janus-omniforge/actions/runs/40172724791) 227 passed／1 warning）／LIVE_CORE=PASS（[有界一筆Job #40172093172](https://github.com/tommylin15/janus-omniforge/actions/runs/40172093172)，FinMind PB 11筆、Yahoo BVPS 1筆，Core月份11/11讀回、source_errors=[]）／MART_AND_API_LIVE=NOT_DEPLOYED／DEPLOY=DEFERRED_TO_SEQ-08／唯一下一入口=SEQ-06（四模型正式serving、版本／共用快取、train-serving一致性）→SEQ-07（報告／Owner history／UI完整接線）→SEQ-08（含Valuation Mart/Fact Pack/API在內的集中部署、2330／2882真實登入讀回）。SEQ-05的部署責任交SEQ-08，並非下一個序號直接跳SEQ-08。`

使用者要求「補資料不用太嚴謹，直接做加總」：2330以既有FinMind Core 2025Q3 17.44 + 2025Q4 19.51 + 2026Q1 22.08 + 2026Q2 27.25 = **86.28 TWD/share**，只作`last_four_reported_quarters_simple_sum`研究參考，不宣稱配股調整後、稀釋EPS或法定四季合計。這四筆原本已在Core，沒有重新寫入。2882 Yahoo來源（`https://tw.stock.yahoo.com/quote/2882.TW/profile`）公開2026Q2 BVPS=69.37 元，已隨來源原始回應透過 Stage 入 Core；FinMind `TaiwanStockPER` 2025-10至2026-08 11個月PB最後交易日共11筆已實際入 Core。實際source ID為`finmind`和`yahoo-finance`、角色為核准fallback，不冒充官方來源。Core估值snapshot=3874132956674698219、財務snapshot=6504132269236397893。唯一Dev Job execution `janus-ingestion-core-lwwg5`，GCP範本未變、未增費服務與Scheduler、Owner資料未異動。正常既有Stage 48h清理政策不變。

封存 `ops/seq05-oneoff-quickfill.json` 為 `approved=false/closed_after_success=true`，再由[Noop #40172457154](https://github.com/tommylin15/janus-omniforge/actions/runs/40172457154)讀回 `SKIPPED_ALREADY_COMPLETED/data_mutations=0`。禁止將此一次性工作設為常態排程，或再次重派。獨立二次Dev Core唯讀 [#40172603358](https://github.com/tommylin15/janus-omniforge/actions/runs/40172603358) 終態SUCCESS：2330有效月24、2882有效月24、2882 BVPS=69.37(TWD_per_share)與source=yahoo-finance實際讀回，Core雙表snapshots分別3874132956674698219／6504132269236397893。不是Mart正式發布驗收。

**完成範圍**：兩股估值所需原始資料已具備研究路徑；**未完成**：新的Mart materialization、Fact Pack寫入、API正向登入及前台顯示未部署或驗收，仍依SEQ-08；不能把已進Core直接當成已進Mart。下個工程入口先完成SEQ-06四模型正式serving與離線契約，再完成SEQ-07報告／Owner history／UI；其後在SEQ-08受控部署Mart+API及兩股真實讀回。SEQ-05不再研究補抓來源。詳見[Valuation SPEC](spec/valuation-range.md)。

### SEQ-04 有界實刪新收據（2026-10-25）

- **Stage 48h = LIVE_APPLY_PASS**：[#40172644132](https://github.com/tommylin15/janus-omniforge/actions/runs/40172644132)，原有`janus-ingestion-core` Job execution `janus-ingestion-core-9dd52`。實際 `604 → 381` 件，`73,943,009 → 31,402,268 bytes`，計畫／實刪均223件／42,540,741 bytes，generation-fenced worker與獨立GCS清冊讀回吻合；非dry-run或推算。此次僅Dev Stage，無Core/Mart/Private刪除。
- **首次Private執行失敗已保留歷史、後續修復PASS**：同#40172644132 Private VM回傳exit1，未獲該run清理成功；後續以 #40173273728 單獨重跑Private，實刪daily1份／26,044,882 bytes，daily8→7並讀回10/25 PG retention_status=succeeded。沒有重跑Stage。PG current catalog 76／76通過，Owner/Admin與10/26自然資料鏈仍待驗。
- **本輪已到期有界清理／catalog CLOSEOUT=PASS**：Stage、Private、current pointer與自然Controller tick均有真實收據；整體SEQ-04仍保留下一個02:30收取與週副本、Owner/Admin AUTH_REQUIRED、舊備份occurrence作個別驗收，不列FULL_PASS。詳見[Operations](spec/operations-and-testing.md)。

### SEQ-04 weekly與舊00:30 occurrence 即時修復收據（2026-10-25）

- [#40175398373](https://github.com/tommylin15/janus-omniforge/actions/runs/40175398373) workflow SUCCESS；有界12 tests PASS；由已成功2026-10-19 daily 備份原始generation與PG checksum驗證，原始內容不覆寫，以目標`ifGenerationMatch=0`新建`weekly/2026-10-19.dump` 1件／30,872,328 bytes並下載SHA-256讀回PASS。2026-10-26下一週不能預先建立，保留該週自然首次成功驗收。
- 同run精確將`ledger-backup/2026-10-25/00`在PG backup+retention均succeeded且日期／state匹配的條件下CAS `running→succeeded`、outbox 1筆，PG讀回PASS；不將不同的02:30 occurrence冒充00:30。初次 #40175288842 因pytest缺失中止、實際寫入0，第二次修復PASS。
- **已完成的這兩項從SEQ-04 active blocker移除。** 不建立新Scheduler／Job、不重新備份、無Owner資料變更；本輪只保留10/26自然時點與Owner/Admin授權UI正向驗收。詳細來源以 [Operations](spec/operations-and-testing.md) 為準。

### SEQ-04 Owner／Admin 手機登入後畫面實測（2026-10-25；UI_PASS）

- 使用者在同一對話提供5張手機Dev瀏覽器截圖：Owner登入後「今日」與資產摘要、私人持股損益／個股持倉／公開事實卡正常呈現；Admin登入後能讀營運自動工作狀態與GCS六桶盤點真實結果。**Owner與Admin真人UI正向PASS，不再標記AUTH_REQUIRED，無須再次登入。**不將畫面誤當OAuth token/audience、跨Owner或session API完整正向證據；未執行的API項目維持NOT_DIRECTLY_VERIFIED，但2026-10-12既定規則不要求每次真人A→B→A，沿用自動auth邊界測試。
- 不把使用者電子郵件、投資組合細節、金額或截圖存入GitHub。截圖中的上市／上櫃部分資料缺漏及「持股報價暫時無法更新」是**資料／報價**提示，不作登入失敗判斷；若下次自然批次仍重現，再依SEQ-04/SEQ-08功能範圍分析。SEQ-07新版分析／歷史UI仍待SEQ-08實際部署後驗。
- 限定範圍的最新證據見[Operations](spec/operations-and-testing.md)。SEQ-04整體仍保留10/26首次新版自然資料鏈與新週備份收據，不把截圖推論為全系統LIVE_PASS。

### SEQ-04 四階段紀錄（2026-10-25，進行中）

`SEQ-04｜DOC=UPDATED／CODE=COMMITTED／DEPLOY=PASS（#40163729460、#40163927739）／NATURAL_CONTROLLER=PASS（#40170098722）／STAGE_48H_APPLY=PASS（#40172644132，後驗#40173298619）／PRIVATE_RETENTION_APPLY=PASS（#40173273728）／ICEBERG_CURRENT_CATALOG=PASS（76/76）／WEEKLY_BACKFILL_2026_10_19=PASS（#40175398373，30,872,328 bytes SHA-256 verified）／OLD_LEDGER_BACKUP_0030_CAS=PASS（#40175398373，1列狀態CAS與1筆outbox）／OWNER_ADMIN_UI_AUTH=PASS_USER_SCREENSHOTS_2026_10_25（非API或雙Owner隔離驗收）／OVERALL=LIVE_PARTIAL（10/26首次新版02:30 ingestion鏈與新週自然備份尚未到期，owner/admin UI已驗收）｜唯一剩餘入口=SEQ-04下一必要自然時點一次驗收，無需重派Stage、重跑備份或新增Scheduler`。

收據判定：Release、migration069／VM、PG隔離還原、四Job 8/8、API 100% 已通過。歷史切換 #40162679929 `permission_denied` 及回復，之後 #40163099454 精確查出 target SA actAs NOT_GRANTED；使用者於Cloud Shell僅授權 `janus-ci` 對指定 `janus-ingestion-scheduler` SA 的 `roles/iam.serviceAccountUser` 並讀回。重新觸發 [#40163729460](https://github.com/tommylin15/janus-omniforge/actions/runs/40163729460) 最終SUCCESS，receipt: `phase=PASS`、`previous_cron=30 * * * *`、`new_cron=30 */2 * * *`、`scheduler_enabled=true`、`target_identity_unchanged=true`、`gcp_new_resources=0`；獨立GCP [#40163927739](https://github.com/tommylin15/janus-omniforge/actions/runs/40163927739) 再讀到同值、target hash一致、IAM update/actAs=GRANTED。14:30自然tick已由#40170098722的Scheduler執行紀錄（HTTP200）、Cloud Run REST最新Controller execution（created UTC06:30:00；start UTC06:30:16；complete UTC06:31:52，CONDITION_SUCCEEDED）證實PASS。首次gcloud list未顯示新execution，已交叉改用Cloud Run REST確認。新版02:30 ingestion需等2026-10-26 02:30 Asia/Taipei自然收取完成後讀回，不能用今天舊版失敗或Controller成功代替。其餘有界驗收維持NOT_VERIFIED，不增添獨立排程。

### SEQ-04 新兩小時自然Controller收據（2026-10-25 14:30 台北；PASS）

- [GitHub唯讀 #40170098722](https://github.com/tommylin15/janus-omniforge/actions/runs/40170098722) completed/success；Scheduler `lastAttemptTime=2026-10-25T06:30:00.865962Z`、cron=`30 */2 * * *`、Asia/Taipei、ENABLED；Cloud Scheduler execution log 06:30 HTTP 200；Cloud Run V2 REST `janus-batch-controller` execution create UTC06:30:00.943455、start UTC06:30:16.601901、complete UTC06:31:52.439218、Completed=CONDITION_SUCCEEDED。首次CLI listing漏新紀錄，交叉用v2 REST得到完整收據。**自然Controller tick=PASS；不是新版市場收取成功的證據**。
- 下一個新版02:30 ingestion自然時點為2026-10-26 02:30（台灣時間）；驗收需讀新occurrence狀態、actual Cloud Run Job與Core data date／artifact，不使用10/25舊失敗推論新版。無須等待24h才能推進其他工作。整體結案判定：**SEQ-04=LIVE_PARTIAL／NOT_CLOSED**；部署與自然Controller tick可獨立標PASS，但必須保留實際未執行的清理apply／現役catalog與資料鏈驗收。Owner／Admin無登入憑證時為`AUTH_REQUIRED／NOT_VERIFIED`，不得拿匿名401作正向驗收。

### SEQ-04 即時有界驗收收據（2026-10-25；不等於全系統live PASS）

- [備份／Controller #40164713512](https://github.com/tommylin15/janus-omniforge/actions/runs/40164713512) workflow SUCCESS。executor timer active/enabled、舊direct timer inactive/disabled；最近六筆每日備份succeeded，2026-10-25最新備份40,595,834 bytes。Control中同日ledger-backup 00:30 occurrence仍running、02:30另一筆succeeded；每日備份狀態與排程occurrence不可混為同一PASS。
- [完整有界唯讀 #40165435450](https://github.com/tommylin15/janus-omniforge/actions/runs/40165435450) workflow SUCCESS，分項：Stage 48h依PG有效lease17及完整GCS inventory452物件得到 `PASS_DRY_RUN`、計畫220物件／42,538,112 bytes、held_active_objects0，實刪0；Private備份retention `DRY_RUN_PASS`：8 daily／2 monthly／0 weekly，計畫刪1 daily、其餘0；最近8份PG daily均succeeded，但8筆retention_status為pending，**不能算清理已apply**。23xx/28xx公共OHLCV各有真資料；API buildSHA/health 200，Owner/Admin未登入皆401；Core/Mart/Private bucket之Iceberg metadata文件各可讀，但沒有驗證PG catalog指到的current snapshot。兩個較大bucket只完成有界metadata樣本，不能冒充完整bucket inventory。
- Live發現：2026-10-25 02:30、07:30 ingestion occurrence為FAILED，歷史failed收據橫跨SEQ04部署前（不能直接證明目前新版失敗）；12:31 analysis-queue仍標running。需以原工作ID／live lease／Job執行收據核對，不大量重派、不刪記錄、不當作已成功。
- 已驗：14:30 Scheduler自然Controller成功（#40170098722，HTTP200與Cloud Run REST completed success）。仍未驗：Stage按原worker fence有界generation刪除與bytes讀回；Private每日retention實際apply／週副本創建及PG欄位轉終態；Iceberg catalog current pointer；Owner／Admin真正登入與snapshot/UI一致性；2026-10-26 02:30新版ingestion→Core產物。既有GCP兩小時配置仍PASS，不重新建Scheduler，不等一整天才開始其它獨立工作。

### SEQ-03 四階段紀錄（2026-10-25）

`SEQ-03｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（b46e38822410f414d78807f101a93f12479d2c93／246aaac277e5baab1ccfb5eb9c753fbf6cb61570）｜測試驗收=OFFLINE_PASS（CI #40152197002，source 246aaac；234 Python、9 non-fatal warnings；API270／7 skipped、Mart247、Ingestion209）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜唯一下一入口=SEQ-04／文件設計`。

依AI任務卡逐類列明PG Owner原始資料、Private GCS／Iceberg、Core／Mart current、模型與報告可備份或可重建邊界；原有migration069只新增狀態欄且可重跑，不重作或聲稱已上VM。新程式對daily immutable碰撞fail-closed，週月保留首成功副本與已有archive讀回，隔離PG還原增加現金anchor／觀察設定／Owner孤兒檢查，GCS依賴明示未被PG dump備份；retention週鍵拒絕非週一。stage48h／current-only＋7天 orphan／7-4-6／刪除3-1-1上限不變。先前CI #40151958279 測試因引號判斷過嚴失敗，修正後CI #40152197002 PASS；實際migration069重跑與資料還原仍留SEQ-04。SEQ-04依WI套migration→VM→Controller並實作隔離restore、GCS current files讀回與有界retention apply，未驗不算完成。

### SEQ-02 四階段紀錄（2026-10-25）

`SEQ-02｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（功能 72361a2910d43eca06f6ef9aaaee220553a40c1e；相容修正 9f0cd4477d0f6cb1fe653b23979e8fd76c6672fe）｜測試驗收=OFFLINE_PASS（220 Python／9 non-fatal warnings；API 270；Flutter User PASS）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜證據=CI #40151187692 SUCCESS、Flutter #40151028800 SUCCESS；失敗 #40151028971 已修復｜唯一下一入口=SEQ-03／文件設計`。

對照 main 程式確認：交易帳本／修正／沖銷和原有 Private Pipeline、工作區快照／Owner API 已存在。本輪補現金 change_log、觀察清單增刪／排序及現金／券商／投資設定的重算觸發、工作區 payload 的 cash/broker/change 版本、背景 worker 對並行 owner change_version 的完成 fencing，以及 Flutter 關注頁操作後提示。未改 canonical 帳本、成本法、私人資料授權、GCP 排程或 migration；workspace_snapshots 僅 payload 相容擴充。原始 CI #40151028971 的完整離線測試因舊 fixture 未含新版選填 payload 欄位而 219 PASS／1 FAIL；修復後同 SHA `9f0cd44` 的 CI #40151187692 為 `completed/success`，`bash scripts/test-unified-batch.sh` 220 PASS／9 non-fatal warnings，API selective 270 PASS；Flutter User 全流程 #40151028800 `completed/success`（含 Flutter analyze 與 test，來源為功能 commit `72361a2`，後續修正僅 Python 快照選填欄位）。不同測試集不加總。SEQ-02 文件／程式／離線階段可交接 SEQ-03；本任務仍需 SEQ-04 的 Dev Owner／API／UI 讀回才能整項 CLOSED。

### SEQ-01 四階段紀錄（2026-10-25）

`SEQ-01｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（7ab83e0aab287d10240efe84e4570cc5ff9eec57；CI整合4241bf40b94b5a75ffee235b9ef0b52b5eb5a271）｜測試驗收=OFFLINE_PASS（Python217、Flutter7、Controller99；9項non-fatal warnings）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜證據=CI #40148605544 SUCCESS（原 #40147708243 FAILURE→#40147914267 SUCCESS）｜唯一下一入口=SEQ-02／文件設計`。

已於 GitHub Actions #40148605544、來源SHA `4241bf40b94b5a75ffee235b9ef0b52b5eb5a271` 執行 `bash scripts/test-unified-batch.sh`（217 passed、9 non-fatal warnings，含 `bash -n`）及 `cd apps/user_app && flutter test test/admin_batch_dashboard_test.dart test/admin_overview_batch_test.dart`（7 passed），另 Controller CI 99 passed。SEQ-01 文件／開發／離線階段已具交接條件；新時段、migration、Dev Runtime／Scheduler 實機驗收依SEQ-04部署後確認，不冒稱live PASS。證據摘要見[Operations](spec/operations-and-testing.md)。

## 四模型正式上線與第二版邊界

Quant、Risk、Fundamental、Valuation **全部列入本次正式serving／版本／報告／UI／部署範圍**；不是只規劃、不以baseline或research-only代替完成。採既有可發布artifact，不要求先調參或重訓；若缺檔，列明角色、必要檔案與影響，不能捏造ACTIVE。CEO是整合層，Event只保留相容事實，沒有第五模型。

原 DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY／D07 X/Y 的必要推論一致性併SEQ-06；全面研究資料重整、四模型調校／新增因子／實驗與VAL-MIN30後續改善移至 [2027年第一季第二版](parking-lot.md#v2-2027-q1)。不阻塞本次正式上線，不建立自動啟動排程。

## 不重開與未授權範圍

C1-A、P0-2、OPS-P0-1、A-CHANGE、D01～D06、FINOPS-AB、研究稽核精簡保持既有有界結案。新備份政策驗收歸SEQ-03／04，不把歷史故障重開。
取消：逐來源稽核、全歷史PIT／名冊／公司行動重建、自然長期觀察、新20日cohort等待、例行週月模型稽核、第五模型、舊GAS/BQ/月度重訓。
暫不做：C1-B實體刪表欄、新付費來源／資源、production環境建立／IAM擴張、站外推播及其他 [Parking Lot](parking-lot.md)。本次「正式上線模式」指既有Dev個人真實服務中的四模型正式運作，不自動授權新建GCP production環境。

## 2026-10-25 分析因子與報告頻率增量（併原順序）

[分析Mart SPEC](spec/analyst-input-mart.md)／[AI驗測WI](runbook-analyst-input-mart-ai.md)。本次CODE／DOC已交付，TEST／LIVE／UI均NOT_VERIFIED，不新增SEQ編號。

| 原項 | 增量與仍未完成條件 |
|---|---|
| SEQ-01 | 15月營收缺口補收、TWD／千元共用；深度target掃描與共用benchmark；離線測試已過，既有Dev Job與真資料讀回由SEQ-04驗測 |
| SEQ-05 | 補真實EPS／BVPS與估值有效月；不因新Mart而捏造已足量 |
| SEQ-06 | Core→analysis artifact已寫；四模型真artifact feature schema、Valuation會計mapping與正式推論接線待完成；必要train/serving parity本版做、調校留Q1 |
| SEQ-07 | 新增週期＋資料變更事實報告及重用狀態；四ML結果、Owner history／API／UI完整接線與日期語意待驗；CEO仍按需 |
| SEQ-08 | 集中驗2330／2882及既有持股觀察股的真實因子覆蓋→模型→報告UI，不能以新程式存在稱PASS |

### SEQ-06 四階段紀錄（2026-10-25）
`SEQ-06｜DOC=UPDATED／CODE=COMMITTED／OFFLINE=PASS（67a158512e7c0fb73d5740ec71a6824923aafda8；#40174399997 SUCCESS、#40174400071 236 passed／1 warning；真模型artifact非本次fixture）／GCS_ACTUAL_QUANT_FUND_VAL=UNKNOWN／RISK=沿既有 ACTIVE gate 無變更／VAL_MODEL_ACCOUNTING=BLOCKED（尚未建立正式一致映射）／DEPLOY=DEFERRED_TO_SEQ-08／下一入口=SEQ-07（報告、Owner history、UI接線）。` 本項保留四個真 ML artifact／schema 可用性證據缺口；不以 deterministic baselines 或 Research Notebook 代替。沒有新增重訓／長期 OOS 稽核等待門檻。API／登入 UI live 一律由 SEQ-08 收據判定。

### SEQ-07 四階段紀錄（2026-10-25）

`SEQ-07｜DOC=UPDATED／CODE=COMMITTED（f9ace32b795e6c1895901e7750f18be2f57da575）／OFFLINE=PASS（Python #40175446096 275 passed／7 skipped／2 warnings；#40175926343 272 passed／7 skipped／2 warnings；Flutter + PWA #40175926335 SUCCESS）／MIGRATION=NOT_REQUIRED（沿既有 private.specialist_product JSONB）／DEPLOY=DEFERRED_TO_SEQ-08／LIVE_OWNER_LOGIN_AND_GATEWAY=NOT_VERIFIED／ARTIFACT_GCS_AND_VAL_ACCOUNTING=沿SEQ-06已知缺口／唯一下一入口=SEQ-08`。首輪Flutter #40175446120、修正過程 #40175734768／#40175871947 失敗，根因依序為測試mock資料放錯、按鈕超出800×600 test viewport；後以report fixture修正、scroll-to-visible及Gateway失效事實報告回退測試修正，最新 #40175926335 成功。未執行Dev部署或修改任何Registry、真實持股、快照與付費API。

### SEQ-06 補充：四模型發佈授權及真權重核對（2026-10-25）

使用者明確核准全部四模型發佈，覆蓋 2026-10-23/24 研究包 `publication_allowed=false` 作為**目前決策授權**；不改寫原研究包歷史狀態、重播或 OOS 效用。已實際在受控本地環境下載並解碼真實 XGBoost UBJ：Quant 15因子 SHA `3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9`（8個test vectors重播誤差0）；Risk12研究 refit SHA `e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb`（只有研究固定cohort checkpoint，非全期正式重訓）；Fundamental XGB15 RC1+5% 拒絕政策 SHA `05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c`；Valuation v26 fold2026 PE `56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610`、PB `c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a`（兩組各5 vectors重播誤差0）。總計四角色五份權重。使用者端已產生兩份本地 zip（四角色 candidate bundle及Valuation PE/PB dual-head bundle），**GitHub/Drive/GCS沒有自動代替它們存放**；model registry 不因 ZIP 存在而被更新。

GCS DEV [#40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431) completed/success、gcs_writes=0，精確四指標讀回：Risk `DETERMINISTIC`、Quant/Fundamental/Valuation `POINTER_MISSING`。本次缺口是實際服務與候選模型不相容，而非人工核准待辦：Risk ACTIVE code pin 8X、Quant current analyst X=11 與研究 XGB15不同、Fundamental X=9 與 RC1 XGB15/abstention不同、Valuation 原單頭指標不能同時提供logPE/logPB，且需對正式Core XBRL來源五因子驗證。已加 `valuation_ml_mapping.py` 接真Core MOPS income YTD/balance snapshot（真Core單位TWD、不重乘1000，映射研究 `roe_proxy` 非一般ROE），3項測試及 CI PASS；尚未做Mart live snapshot正向驗收。不得以 User approval 當作Runtime/Serving PASS或不經測試直接覆寫Registry。唯一正式部署入口依舊為SEQ-08。

### SEQ-08 四階段紀錄（2026-10-25；首次 predeploy）

`SEQ-08｜USER_DIRECT_NEW_MODEL_REPLACEMENT_APPROVED（四角色不再詢問、無舊模型相容及模型回復前置）／DOC_UPDATED／CODE_COMMITTED（810b0fb6、e7e99b70、e415048c）／OFFLINE_CI_PASS（#40179984749 selective、#40179984775 analysis/Postgres，均為e415048c）／GCS_CREATE_ONLY=NOT_EXECUTED／FIVE_UBJ_PRODUCTION_SERVING=NOT_VERIFIED／REGISTRY_AND_PG=NOT_SWITCHED／MART_API_FLUTTER=NOT_DEPLOYED／LIVE_OWNER_REPORT=NOT_VERIFIED／OVERALL=PARTIAL。已新增 create-only候選導入工具、確切新權重SHA檢查及四組測試，沒有直接接觸GCS或切 ACTIVE。兩輪新fixture CI 失敗已修並保留歷史。下一個唯一動作仍是 SEQ-08：取得真實五UBJ與 schema 可讀輸入 → 真hash candidate讀回 → 完成12/15/15/5×2 serving parity → 本版Release、Dev發布及有界產品鏈驗收。`
