# Janus WBS 6 — API、Flutter 與 Admin

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](../spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-05
狀態：Active responsibility／acceptance contract；執行順序以 `../todo.md` 為準

本文件只保存 WBS-6 的責任與驗收邊界。API 細節依 `../spec/api-and-delivery.md`，User UI 依 `../ui/user-app.md` 與 Final Visual Contract，Admin UI 依 `../ui/admin.md`。目前實作／完成狀態以 GitHub `main`、tests／deployment／runtime evidence 為準。

## 6.0 Dev 使用環境

- GCP `dev` 是目前個人真實 parallel-live environment；API、Flutter、Admin、MCP 各自通過 auth／data／runtime／integration acceptance 後即可真實使用。
- mock／fixture／localhost 只供快速回歸與故障注入，不得代替 GCP dev URL、真實 OAuth／owner、persisted data、Job／Scheduler／MCP 的主要 evidence。
- `Production Profile` 是分析設定的 active/released 狀態，不等於 Production GCP environment。

本輪交付先完整持股與快速交易損益，再通用圖表／四頁整合；責任與量測 acceptance 依 [持股優先契約](../spec/holdings-first.md)。模型報告後置，不阻塞本輪。

## 6.1 FastAPI

- `services/api` 為 Janus 共用 HTTP boundary。
- `/api/v1/public/*`、`/api/v1/me/*`、`/api/v1/admin/*` 分離 router、response model、auth、rate limit、CORS 與 audit。
- 身分只取自驗證 token／server binding，不接受 client 指定 `user_id`／`owner_id`。
- public 只回可發布資料；private 只回 authenticated owner；Admin 每次 request 都由 backend enforce Admin authorization。
- 404／missing 不觸發 scraper、Agent 或 LLM；API request 不在同步 request 內執行長任務。
- raw payload、secret、token、traceback、private artifact locator、GCS object URI 不出現在一般 response。

## 6.2 Flutter User App

`apps/user_app` 使用 Flutter Material 3 與平台原生元件；沒有明確需要時不引入大型第三方 state／UI framework。

主要 User navigation：

- 今日
- 關注
- 記帳／筆記
- 我的

User App 不提供 generic Chat／Ask Janus／provider runtime／Skills／approval UI。omniAgent 是通用對話產品；Janus 只提供投資資料與 bounded context。

### 6.2.1 Stock Detail

primary content 順序依 `../ui/user-app.md`：

`StockHeader` → 個人持股／成本／估值日 → 短價量圖 → 通用圖表總覽入口 → 中性資料說明（五角色有效後才加入分析報告） → 筆記／籌碼／事件 → evidence／sources → disclaimer。2026-10-11 新規範以 [A 正式 UI 規格](../ui/visual-first-four-pages.md) 和 [B 工程工作單](../ui/visual-first-delivery.md) 為準，四圖是最低基礎值。

Advanced section 可顯示：

- 完整 K 線／估值進階指標（價量微圖／圖表入口須先於 Advanced）；
- deterministic Fact Pack；
- 五 specialist persisted outputs；
- 最新 On-demand CEO report；
- analysis/data as-of、freshness/material delta；
- immutable history／provenance。

五 specialist 是 Python／SQL／ML production outputs，不是每日五個 LLM role。CEO 只在有 `ceo_analysis.request` 或等價 capability 時提供「分析／重新分析」；重新分析建立新 immutable execution/report，不覆寫舊報告，也不由 page load 自動觸發。

### 6.2.2 Final Visual Convergence

`WBS-6-USER-FINAL-VISUAL-CONVERGENCE` 的 presentation target 由：

- `../ui/user-app.md`
- `../ui/reference/user-app-final/README.md`
- `today.png`
- `watchlist.png`
- `ledger.png`
- `stock-detail.png`

共同定義。

**A 組 completion gate：** Today／Watchlist／Ledger／Stock Detail 的非 AI 主體 UI 必須先在既有 GCP dev、真實登入、真實 authenticated owner、真實資料與真實 API/runtime 下明顯收斂至 Final Visual Contract。進入真實驗收不代表 implementation 已完成；真實畫面若仍明顯像 legacy UI，或與 reference 的核心資訊架構差異很大，視為 A 組 acceptance failure／implementation gap，不得降級成後續 cosmetic task。

A 組至少驗證：

- section order；
- card hierarchy；
- 資訊密度；
- spacing 與主要色彩；
- mobile layout 與 390px 級寬度結構；
- loading／empty／error／partial／stale／missing 不破壞主要 hierarchy；
- 非 AI primary information 不因 specialist／CEO 尚未就緒而保留舊 layout。

AI-only 區塊尚未完成時可 bounded unavailable／hidden／partial；B／C 可負責 specialist outputs、CEO、capability/history/freshness 與最終 AI integration，但 A 組不得把基本四頁 non-AI presentation convergence 延後到 B／C。

完整 Final Visual Convergence 完成至少要求：

- 四張 PNG binary 在固定 repository path；
- targeted／golden／screenshot regression 覆蓋主要 hierarchy 與 loading／empty／error／partial／stale／missing；
- 390×844 級手機 viewport 無 overflow；
- GCP dev 真實 authenticated owner／persisted data browser acceptance；
- sample/mock data 不進 canonical runtime；
- backend capability 未完成時顯示 bounded unavailable／hidden，不以 placeholder 冒充成功。

### 6.2.3 Ledger canonical consistency／refresh

Ledger 的「持股／紀錄／報表」不是三套各自成立的 holdings semantics。四格摘要只在持股顯示；三個 subview 使用的資料應共享同一 canonical position／valuation state，或能清楚追溯至同一 canonical state 與不同 as-of／freshness checkpoint。

一致性 acceptance 至少包含：

- shares；
- cost／average cost；
- market value；
- unrealized PnL；
- realized PnL；
- YTD realized PnL；
- valuation date；
- as-of／data freshness；
- pending transaction／pending Private Mart 狀態。

不得出現同一 owner、同一時間、同一資產在「持股／紀錄／報表」看到不同版本 summary，卻沒有 freshness／as-of 說明。若「持股」已取得新資料而「紀錄／報表」上方 summary 仍為舊 snapshot，直接視為 A 組 UI/data-state acceptance failure；需排查 tab-local state、provider/repository、cache invalidation、tab refresh、legacy endpoint、不同 position source 或 valuation semantics，而不是先假設「整個 batch 尚未跑」。

YTD realized PnL 屬 A 組 non-AI capability。必須依 implementation/runtime evidence 查明 canonical source、交易後更新時點與 refresh chain；有已實現交易時不得長期缺值，當年度確定沒有已實現交易時才依正式 contract 顯示 `0`，資料不足／尚待更新則顯示 bounded empty／unavailable／pending，不以假 `0` 掩蓋 unknown。

Reports 必須只讀 canonical backend／Private Mart aggregation，並明確呈現 valuation/as-of/freshness。需追查 report API、transaction source、position projection、aggregation table/view/materialization、可能的 Job／Scheduler／trigger、cache TTL／invalidation 與 transaction 入帳後更新鏈路，最後以 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。未查明前不得用「可能等批次」作結論。

交易新增、修改、同步或 position projection 更新後，acceptance 必須驗證 Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 均可刷新，舊 cache 不長時間殘留，且 valuation/as-of 足以判斷 freshness。若採 batch，runtime contract／evidence 需指出 Job 名稱、Scheduler／trigger、頻率、source table、target projection、freshness SLA 與 failure 行為；非 batch 則記錄真正 refresh/invalidation chain。

## 6.3 Admin v2｜四頁營運後台（WBS-6-ADMIN-OPERATIONAL-CONVERGENCE）

唯一 active frontend 為 `apps/user_app` Flutter／PWA，既有 `/api/v1/admin/*` 與 server-side 授權不變。[2026-10-17 Admin v2 決策](../decision-2026-10-17-admin-v2.md) 取代 2026-10-03 的**六頁導航／功能位置**，其授權、audit、retention/owner 安全邊界繼續有效。**目前只是目標契約，不能當成程式已改版。**

**四個主導覽目標（不得另加獨立 AI／個股／市場主頁）：**

1. `總覽`：actionable-exceptions-first；批次／Private Mart／snapshot／DQ／storage／AI 異常摘要及安全 drill-down。
2. `批次`：唯一 Controller 控制面的可觀察／安全操作 UI；effective schedule、occurrence、workload 真實終態、備份、Private recalculation、Compaction/Cleanup。
3. `資料品質`：DRL-01、source health、TWSE／TPEx、原 Stock Workbench 的健康與核准 gap repair、原市場資訊、Stage/Core/Mart/必要 Private retention/storage。
4. `系統設定`：原 AI 分析的模型／評估／CEO profile／Gateway 子頁、Worker、設定版本、授權、稽核與低頻儲存設定。

**功能遷移不等於功能退役**：原「個股」和「市場資訊」作為「資料品質」可搜尋詳細區；原「AI 分析」成為「系統設定 → AI 模型與 Gateway」可深連結子頁；原「資料治理」的資料健康／容量在「資料品質」，Private 操作在「批次」，低頻 versioned 配置在「系統設定」。既有 accepted shell、stock search、execution/retry lineage、source health、Mart read、週六 DQ readpath 保留可用；刪 UI／API 前先查 caller、权限、audit、rollback。

### 6.3.1 主體重構順序與嚴格範圍

**唯一 active queue 是 [TODO ADMIN-V2](../todo.md)**，不得回填新需求到 D01～D06：

- **A0 已核准文件：**統一 TODO、WBS、UI、D07、D08；不代表實作、測試、發布。
- **A1 Shell：**四頁導航／deep link／390px 與 desktop accessibility、Auth；不得重建 User App。
- **A2 Controller 運營整合：**只讀承接 D01 Private Mart、D02 snapshot、D04 effective scheduling／backup、D05 deployed SHA/digest/Jobs readback；safe retry 走既有 backend fence。
- **A3 資料品質：**承接 DRL-01、D02／D03 的資料缺口、stock/market、來源與合法期間；維持現行資料／分析／UI 一條鏈。
- **A4 治理／設定：**承接 D06 Iceberg maintenance/objects/bytes/受引用保護清理，以及 D04 worker／backup；無可信資料時 unknown。
- **A4-U 單一使用者使用分析：**非阻塞 User App 共用事件收集、後端驗證身分／allowlisted schema、每日 user-feature PostgreSQL 聚合、Admin 查看單人操作次數／活躍時間／短期時間線。只在 ADMIN-V2 新增，MVP 不要求 Iceberg 與新 Job。
- **A5 驗收：**targeted API／Flutter/CI、auth/owner 隔離、真實 GCP dev Admin readback、排程終態與控制面防重、同 SHA 受控發布／回復、手機與桌面；A4-U 另驗事件批次冪等、閒置／背景計時、個人資料隔離、前台效能回歸與保留清理。

D01～D06 的 task、驗收 gate 和後置工作**不因本 WBS 增加**。等它們適用的核心依賴穩定即可開始 A1～A5；D06 全面 I/O matched measurement、DRL 歷史 TTM／五年 PE/PB 不列為 Admin v2 前置阻擋，未知則 unknown。D07／D08 的 **Admin UI 只接入本四頁容器**，不再平行開發六頁 Admin。

### 6.3.2 總覽／批次契約

- 總覽正常工作不洗版；顯示需處理原因、影響與最後更新，可 deep link 到批次／資料／AI。
- 批次以 backend + Controller 的 **effective definitions/occurrences**、persisted execution/workload terminal 為準；不在 UI hard-code 2026-10-03 的七種 Job，真實缺少 `deployment_status` 證據不能從 `unknown` 推成健康。
- `created/enqueued`、`dispatched`、`running`、`succeeded`、`failed`、`partial`、`unknown` 清楚分離；顯示 schedule、trigger、duration、last update、last success，並有 bounded 最近三天／歷史分頁。
- Manual batch/retry 後端 allowlist + authorization + idempotency + duplicate/dependency/exclusive guard + audit；unsafe/unknown 不盲重送。清理不可直接無保護一鍵執行。

### 6.3.3 資料品質契約

- 分上市櫃顯示市場官方 coverage：TWSE 合格 ≥90%／TPEx ≥70%，連同分母及 as-of；不把 TPEx ETF 混入四碼上市櫃股票母體。
- DRL-01 同一份來源只讀顯示持股／關注 ≥120 合格交易日、13 月營收 fiscal_month/YoY、2026Q1/Q2 合格 EPS；舊四連季/TTM 維持 `NOT_CERTIFIED/WAIVED_FOR_MVP`，五年 PE/PB 後置；資料不足不令既有合法單值消失。
- Stock Workbench 保留 approved dataset gap 修復、來源／snapshot/PIT/provenance 細節；市場 master 依官方 TWSE+TPEx full universe，audit 現有 TWSE-only admin upsert／legacy 500 swap，不能自行擴任意人工寫入權。
- Stage/Core/Mart/必要 Private、quarantine/retention、objects/bytes、compact/cleanup/protected refs、同負載 I/O 實測；無 telemetry 時 `unknown`。不在 page load 全桶掃描，不新增 metadata catalog 或第二 controller。
- Admin 不複製前台股價、持股、KD/ATR、合理價圖表或 transaction flows。

### 6.3.4 系統設定與 D07／D08 消費契約

- 模型／Gateway 從實際 effective runtime/readback 取得 provider/model、capability、quota、cooldown、usage、cost/audit；不因 legacy `Codex CLI → OpenRouter → Gemini` 文字推定當前 route 或啟用付費模型。
- D07 VF-09 五角色 versions/champion、quality/evaluation、baseline/OOS、dirty/reuse、validated artifacts →「系統設定 → AI 模型 → Specialist 品質」，原始數值來源與 missing 狀態可連到「資料品質」；不要求在 D07 新建主導覽。
- D08 Manual CEO/Gateway profiles/capability/immutable report audit → 同一「系統設定 → AI 模型與 Gateway」子頁；正式 Owner 報告仍在 User history。D07 有效 Fact Pack 及 D08 原 acceptance 不被 Admin 導覽變動降低。
- Private worker (2–8)／versioned settings、必要授權和 audit 只管理已核准設定；Public retention 不類推 Private。

### 6.3.4a 總覽使用分析與單人追蹤（A4-U）

- 單一入口：`總覽 → 使用分析 → 使用者列表／單人詳情`。全站日／週／月和每位使用者的 7／30／90 天 feature/page views、操作 success/fail、有效停留時間及最近活動日；短期時間線至多最近 7 天，且只含允許的事件類型／功能／粗時戳，不記金融正文。
- User token 驗證後綁定 stable `user_id`；Admin read 使用獨立授權，不能由 client 任意指定 owner，不能用 middleware request log 反推個人完整使用歷程。
- Flutter 同一 `UsageTracker` hook 覆蓋核心 User／Admin 導覽與重要行為；記憶體聚合、非阻塞批次送出與上限丟棄；IndexedStack、背景或超時閒置不可造成虛假活躍秒數。
- PostgreSQL 小量 `usage_user_feature_daily` 與限期收據／短期 timeline，idempotent batch write；原始事件短期保留、個人 daily 有界保留、每月 summary 按需歸檔。不得逐 action 寫 Iceberg／GCS snapshot，無需要不新建 Scheduler；監看 e2-micro 資料庫容量及 API latency。
- 完整 schema／預設保留、資料保護通知、安全例外與建議 API 見 [Admin v2 §4.1](../decision-2026-10-17-admin-v2.md)。缺回報不得標成「無使用」；Admin 閱讀個人紀錄須 audit，User/MCP 不得查他人紀錄。

### 6.3.5 完成判定

文件 A0 完成 ≠ Admin v2 工程完成。A1～A5 需逐項對應 GitHub main code、targeted tests/CI、authenticated Admin runtime、真實資料／Jobs/Controller readback、390px/desktop、owner/auth safety、受控部署與 rollback；缺證據維持 PARTIAL／BLOCKED。

## 6.4 Manual action／auth boundary

- Flutter visibility 不是 security boundary。
- retry／rerun 只允許 backend 判定安全的 action；retry 建立新 execution 並保留 lineage。
- manual batch action 經 backend allowlist、authorization、idempotency／duplicate guard、dependency／exclusive guard 與 audit。
- cleanup／retention 等具刪除效果的作業不在首頁提供高風險一鍵操作。
- Admin 一般營運頁不得瀏覽使用者交易正文／持股內容；Private operations 只顯示必要的去識別化／aggregate metadata。

## 6.5 Janus ChatGPT MCP

Janus ChatGPT connector 是 external authenticated consumer，首選 existing `janus-api` `/mcp` boundary，不新增另一個 Chat runtime。2026-10-09 使用者撤除 MCP 個人交易／股息記錄功能，取代 2026-10-06 的 MCP ledger write 核准；目前 MCP 只允許讀取。

logical tools：

- `janus_sources` — read-only，scope `janus.sources.read`
- `janus_market_context` — read-only，scope `janus.market.read`
- `janus_private_context` — read-only，scope `janus.private.read`

舊外掛即使仍暴露 `janus_private_ledger_append`，server 必須拒絕且不得寫入資料；新 OAuth 不接受 `janus.private.write`。private output 維持 owner scope、bounds、sanitization、provenance 與 disclosure。User App 記帳不受影響。

MCP 不提供 generic mutation、resources／prompts／subscriptions／approval runtime／conversation snapshot storage，除非未來另有 active contract。

### 6.5.1 Mobile ledger ingress

因目前 ChatGPT mobile 不載入自訂 MCP tool，手機一般對話改走原生 Google Drive connector + 私人 Sheet queue；不新增第二個 Chat runtime 或另一套 canonical ledger。

- queue 固定為 `janusChatGPT/Janus Mobile Ledger Queue`，只接受 append-only `PENDING` request。
- owner 不來自 row；Private Pipeline 以 Drive file owner email 查既有 Janus user，必須唯一命中。
- `request_id` 是 stable idempotency key；交易值、fee、tax 必須明確，不猜缺值。
- existing hourly batch controller 條件式 dispatch existing Private Pipeline；正常 21:30 Private slot 同時 consume queue，避免另建 Scheduler。
- Google Drive／Sheets outage 只延後 mobile ingress，不阻斷原 Private Mart；domain invalid row 回寫 sanitized error code。
- acceptance 必須包含 native mobile Drive write、兩個 workload identity 的 live queue probe、canonical ledger readback、duplicate guard 與 Private Mart refresh readback。

## 6.6 ResearchContext（Planned）

ResearchContext 只在 active TODO 啟動後實作，沿用 existing `janus-api` 的 typed、bounded、owner-scoped、PIT/provenance-aware contract；概念 section 可含 market／company／supply_chain／private／quality。

- 各 section 同一 `analysis_as_of`；
- 明示 missing／stale／partial；
- private scope 由 authenticated principal 綁定；
- 不輸出 SQL、credential、GCS locator、raw payload；
- UI 與 MCP 共用同一 bounded semantics；
- Google Drive 不作 runtime dependency。

## 6.7 Acceptance

WBS-6 任何 slice 宣稱完成時，至少需有與範圍相稱的：

- backend contract／migration（如適用）；
- auth／audience negative tests；
- Flutter targeted tests；
- CI／build；
- dev deployment；
- GCP dev authenticated real-path interaction；
- persisted data／execution／report readback；
- loading／empty／error／partial／stale／missing／blocked semantics；
- zero-secret／zero-cross-owner leakage。

A 組不得因 API 成功、migration 成功、auth 正常、backend deployment、Flutter/widget tests、build 或 Cloud Run revision 更新任一單項成功就標成 `done`。A 組結案需同時取得 GCP dev 真實登入／真實資料下四頁非 AI 主體 UI 的 Final Visual convergence，以及真實驗收發現之 UI/data-state/functional gaps 完成修正與同 URL 重驗的 evidence；若四頁仍明顯未收斂，A 組維持 `partial`。

真實驗收失敗即為 implementation 工作輸入；acceptance closure 採「定位 → 修正 → 測試 → commit/push → dev 部署 → 同一 GCP dev URL 重驗」。

> **A 組不是「部署完成後做驗收」，而是「在真實 GCP dev 驗收中持續發現並關閉 implementation gap」；Today、Watchlist、Ledger、Stock Detail 的非 AI 主體 UI 必須在真實登入與真實資料下明顯收斂至 Final Visual Contract，且 Holdings／Records／Reports 必須共用一致、可追溯且可刷新之 canonical position state，否則 A 組維持 partial。**

文件 rename、widget 完成、Flutter build 或 API 200 都不能單獨宣稱 full completion。
