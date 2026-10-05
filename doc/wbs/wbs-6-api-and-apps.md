# Janus WBS 6 — API、Flutter 與 Admin

更新：2026-10-05
狀態：Active responsibility／acceptance contract；執行順序以 `../todo.md` 為準

本文件只保存 WBS-6 的責任與驗收邊界。API 細節依 `../spec/api-and-delivery.md`，User UI 依 `../ui/user-app.md` 與 Final Visual Contract，Admin UI 依 `../ui/admin.md`。目前實作／完成狀態以 GitHub `main`、tests／deployment／runtime evidence 為準。

## 6.0 Dev 使用環境

- GCP `dev` 是目前個人真實 parallel-live environment；API、Flutter、Admin、MCP 各自通過 auth／data／runtime／integration acceptance 後即可真實使用。
- mock／fixture／localhost 只供快速回歸與故障注入，不得代替 GCP dev URL、真實 OAuth／owner、persisted data、Job／Scheduler／MCP 的主要 evidence。
- `Production Profile` 是分析設定的 active/released 狀態，不等於 Production GCP environment。

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

`StockHeader` → 個人持股／成本／估值日 → 筆記／待追蹤 → `StockHealthCard` → 白話研究摘要 → why／risk → 籌碼 → 公司事件 → evidence／sources → disclaimer。

Advanced section 可顯示：

- K 線／估值指標；
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

Ledger 的「持股／紀錄／報表」不是三套各自成立的 holdings semantics。三個 subview 上方 holdings summary 應共享同一 canonical position／valuation state，或能清楚追溯至同一 canonical state 與不同 as-of／freshness checkpoint。

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

## 6.3 Admin UI

唯一 active Admin frontend 是 `apps/user_app` Flutter／PWA。2026-10-02 已退役的 legacy static HTML／JS Admin 只保留 archive 歷史，不作 fallback、parity gate 或 active runtime。

主導覽目標：

- `總覽`
- `批次`
- `個股`
- `市場資訊`
- `AI 分析`
- `資料治理`

這次 operational convergence 是**精簡強化既有 Admin**，不是重做整個 shell，也不取消 `個股`／`市場資訊`／`AI 分析`。

### 6.3.1 既有 accepted baseline

以下既有成果保持有效，但不代表新的 operational convergence 已完成：

- Flutter Admin shell；
- actionable Overview／Batch 基礎；
- Stock Workbench 基礎；
- persisted execution detail、retry classification、retry lineage；
- source health／Mart persisted read；
- 週六資料品質結果的 Admin read path。

### 6.3.2 總覽／批次

- 總覽維持 actionable-exceptions-first，只突出需要處理的 batch／DQ／storage／retention／AI anomaly；正常 execution 不佔主要空間。
- 批次使用簡單表格／清單，不要求大型 DAG。
- 每列至少顯示 effective schedule／trigger、latest state、duration／last update、latest success，以及 `查看`、安全 `重試`／`手動執行`。
- 預設最近 3 天 execution／occurrence，更早歷史以 bounded date/cursor 取得。
- `enqueue`／dispatch 成功不等於 workload 成功。

目前 controller 的固定 batch：

- `ingestion`
- `data-supplement`
- `mart`
- `data-quality`
- `private`
- `core-cleanup`
- `mart-cleanup`

未來 specialist／monthly retrain／CEO execution 只有 runtime 真正存在後才顯示。

### 6.3.3 資料治理

`資料治理` 取代原 `進階管理` placeholder，第一版只做單一精簡頁：

- Stage／Core／Mart／必要 Private 摘要；
- active retention contract；
- coverage／freshness／DQ／quarantine；
- live objects／active bytes；
- maintenance／cleanup；
- protected references／snapshot 摘要；
- storage growth／anomaly。

Public retention 依 `../spec/retention-governance.md`；Private 沒有另外核准 contract 時顯示 `未定義／unknown`，不得套用 Public 規則推測。

第一版不要求 OpenMetadata、DataHub、Airflow、Kestra、Prefect、第二套 scheduler／control plane、metadata catalog、lineage graph 或大型 chart。

### 6.3.4 AI 分析／Analysis Profile

`AI 分析` 保留為獨立主功能。

Admin 後續管理：

- specialist champion／model／version／evaluation；
- dirty dependency／reuse／reconciliation；
- monthly retrain／calibration evidence；
- blocked／partial／insufficient-data；
- CEO provider approval／auth／health；
- CEO model／profile／route；
- DB-backed user capability（例如 `ceo_analysis.request`）；
- quota／cooldown；
- usage／cost／audit；
- immutable CEO report history。

`Codex CLI → OpenRouter → Gemini` 只屬 On-demand CEO／approved escalation，不代表五 specialist daily route。

### 6.3.5 個股／市場資訊／Routing

- `個股` 保留 Stock Workbench、dataset health、gap repair、history、specialist/CEO persisted artifact 檢視。
- `市場資訊` 保留約 500 universe、ranking、進入／退出、來源與 coverage 狀態。
- Deep Coverage 只顯示去識別化 symbol demand，不顯示 user-to-symbol mapping。
- provider／market-source priority 是 backend versioned contract，不由 Flutter hard-code。CEO route 放 `AI 分析`；market route 放 `市場資訊`／`資料治理` detail。

## 6.4 Manual action／auth boundary

- Flutter visibility 不是 security boundary。
- retry／rerun 只允許 backend 判定安全的 action；retry 建立新 execution 並保留 lineage。
- manual batch action 經 backend allowlist、authorization、idempotency／duplicate guard、dependency／exclusive guard 與 audit。
- cleanup／retention 等具刪除效果的作業不在首頁提供高風險一鍵操作。
- Admin 一般營運頁不得瀏覽使用者交易正文／持股內容；Private operations 只顯示必要的去識別化／aggregate metadata。

## 6.5 Janus ChatGPT MCP

Janus ChatGPT connector 是 external authenticated read-only consumer，首選 existing `janus-api` `/mcp` boundary，不新增另一個 Chat runtime。

第一版 logical tools：

- `janus_sources`
- `janus_market_context`
- `janus_private_context`

不得接受 arbitrary SQL、table、GCS URI、object path、client-selected owner 或 mutation。owner 由 OAuth token 的 server-side binding 決定；private output 需遵守 owner scope、bounds、sanitization、provenance 與 disclosure。

MCP 不提供 resources／prompts／subscriptions／write confirmation／conversation snapshot storage，除非未來另有 active contract。

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