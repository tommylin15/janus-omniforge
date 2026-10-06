# Janus Current Status

更新：2026-10-06

用途：只回答「現在在哪裡、下一步是什麼、哪些尚未完成」。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 2026-10-06 A 組桌面 authenticated 驗收與缺陷修正

A 組仍為 `partial`。本次已取得 Chrome 真實 User／Admin 登入，不再以 browser 不可用為 blocker；真實畫面發現法人欄位、科學記號零值、個股基本資料依賴研究報告與 Admin GCS SDK 缺漏，已修正並進入既有 dev release。先前「沒有已知可直接修的 runtime gap」僅為當時 checkpoint，不代表此次驗收結果。

Mobile ledger writer／owner binding probe `janus-private-pipeline-d67xx` 成功；原 rollout `37416087045` retry success。使用者回報手機可進入且顯示效能數據，並明確要求直接視為完成；Android icon 重開／手機效能依此列為使用者驗收完成，未提供的 p95、樣本與裝置仍為未知。剩餘包含修正版部署後重驗、真實交易 mutation 與 mobile enqueue/duplicate/readback；缺真實交易欄位不得造假。詳見 [本次 checkpoint](archive/group-a-authenticated-defect-closure-2026-10-06.md)。

## 2026-10-06 B 組優先架構決策（尚未實作完成）

使用者已核准 [Iceberg canonical + BigQuery analytics hybrid](decision-2026-10-06-bigquery-analytics-over-iceberg.md) 作為 B 組 specialist／cache 的優先資料運算架構：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；不改成 BigQuery native canonical warehouse。
- PostgreSQL serving projection 與 User／Admin request-time read 保持現行架構。
- BigQuery 只作 analytics compute，優先承接 liquid-500 screening、cross-sectional feature／ranking、OOS/evaluation preprocessing 與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；大量 training input 採 SQL 縮減後 export versioned GCS Parquet。
- B 組第一優先是抽出 exact-snapshot analytics reader、保留 PyIceberg reference/fallback，再做 BigQuery fidelity/cost/performance canary；未證明固定 Core snapshot 一致前不得切 default。
- **目前只有架構與執行順序核准，沒有 evidence 顯示 BigQuery／BigLake resource 已建立或 API/IAM 已核准。** 需要新增付費 API/resource、catalog/dataset/connection 或 IAM 時仍依 PROJECT_RULES 取得明確授權。

此決策不改變 A 組目前 `partial / blocked-on-interactive-live-acceptance` 狀態，也不得拿來宣稱 B 組 specialist 已完成。

## 2026-10-06 A 組 live-auto acceptance checkpoint

A 組目前仍為 `partial`，但**所有本對話可自動完成且不需使用者本人登入／手機操作／真實 ledger mutation 的 live acceptance 已完成**。剩餘 blocker 已縮成裝置／互動式 authenticated acceptance，不再有已知可直接修的 non-live 或 read-only runtime gap。

- **PWA／安全負向：PASS。** Inspect run `37407568046` 直接讀 canonical Cloud Run URL：build-id `3e29701ffae1dfe3aa9d32deb50ded03f8145c18`；User manifest `id/start_url=/app/`，Admin manifest `id/start_url=/app/admin`；未登入 `/api/v1/me/profile` 與 `/api/v1/admin/data-governance` 都回 401。
- **Private canonical read consistency：PASS。** Janus Dev Read-only v2 最新 owner readback：trades、positions、2026 annual-pnl、performance 均對齊 `ledger_version=24`；derived private Mart valuation date 對齊 `2026-10-05`。先前 stale Mart 狀態已消失。
- **Batch／Private Pipeline runtime：PASS（read-only evidence）。** Inspect run `37407726176` 證明 `janus-batch-controller` 為 `BATCH_CONTROLLER_MODE=active`；`janus-ingestion-daily` 每小時 :30 觸發 controller 且近期 HTTP 200。有效 `private` batch contract 為平日 21:30 Asia/Taipei、依賴 ingestion。`janus-private-pipeline-n45c6` 於 2026-10-05 21:33 台北時間建立、21:36 完成且 succeeded；舊 direct `janus-private-pipeline-2130` Scheduler 在 bounded 7-day logs 的最後活動停在 2026-10-01。
- **重複 trigger 防護：PASS。** commit `db570130` 將舊 `apply-private-pipeline-schedulers-dev.sh` 改為 retired hard-stop；commit `0df2e728` 校正有效 controller slot 為 21:30。Deploy run `37408320316` targeted ingestion 137 passed，所有 deploy/migration jobs skipped，未造成 runtime mutation。
- **Storage retention／cleanup：PASS（billable reclaimed unknown）。** Inspect run `37407331976` 讀回最新 apply receipts：Stage deleted 110 objects / 32,275,833 live bytes；Core active bytes reduced 5,928,635；Mart active bytes reduced 5,932,252，specialist artifacts deleted 68。receipts 的 `billable_bytes_reclaimed=null`，因此成本回收量維持 unknown，不補 0。bucket-level lifecycle/retention fields 為空；目前正式 retention spec 是由 retention jobs + reference fences 執行，不把空 bucket lifecycle 假裝成已設定。
- **真機效能量測能力：implementation/deploy PASS，實機樣本待驗。** Main `21413e5634fb68a89e3ca503fe1a7f1192862d4e` 新增 `?perf=1` 診斷層，量測 Today／Watchlist／Ledger／Stock Detail 核心資料完成時間與已訪問 tab restore frame；只記毫秒與 page label，不記 owner／symbol／token／payload。Flutter run `37412540230` analyze、60 tests、PWA、production web build 全部成功；Deploy run `37412540399` success，revision `janus-api-g21413e5634fb-config` Ready／100% traffic，image digest `sha256:e02b923ce63db76a5105450a46d312f704b23af3f5b3360af09202974aca8731`，verify match `21413e56`。
- **MCP write：backend/runtime PASS，ChatGPT session tool registration 仍 partial。** `mcp-adapter`／`mcp-oauth` tags 正確保留在 write-capable `d494acb4` revision；使用者已回報完成授權，但本對話當下 tool registry 仍未暴露 `janus_private_ledger_append`。因此沒有用 read-only connector 冒充 write acceptance，也沒有建立測試交易；需在 ChatGPT registry refresh 後再做 duplicate-guard/readback 與一筆使用者明確提供的真實 ledger fact。

目前剩餘 A 組只含：

1. Android 實際安裝 User/Admin 後由兩個 icon 重開，確認裝置端不再把 Admin 導回 User。
2. authenticated User/Admin 真實瀏覽器四頁約 390px visual acceptance，及 Admin live UI readback。
3. 真實 owner 新增／建立更正交易後的 pending → Private Mart refreshed → Holdings／Records／Reports／YTD 一致性；MCP write acceptance 併入此 gate，缺真實交易欄位不得自行造假。
4. 真實裝置以 `/app/?perf=1` 取得 warm core p95 ≤2 秒、visited restore ≤300ms 的樣本與裝置證據；量測 instrumentation 已部署，僅剩實機 data。

因此目前不是工程卡住，而是 `blocked-on-interactive-live-acceptance`；在上述證據完成前不得標 A 組 done。

## 2026-10-06 A 組 non-live closure checkpoint

A 組仍判定為 `partial`，但邊界已收斂：**目前已知且可在非登入／非實機條件下直接修正的 A 組 implementation gap 已關閉；剩餘項目是需要真實 authenticated User／Admin、實際手機/PWA、真實 owner mutation、效能與儲存證據才能完成的 live acceptance。** 不得把這句解讀成 A 組已完成。

已關閉的 non-live implementation：

- Final Visual production path 已使用 `lib/final_visual.dart`；Today／Watchlist／Ledger／Stock Detail 均為新版 presentation layer。Today 已移除「櫃買指數」。
- User／Admin 仍共用一套 Flutter build，但有不同 PWA identity：User `id/start_url=/app/`；Admin `id/start_url=/app/admin`，`/app/admin` 回傳獨立 Admin shell／manifest，不再因安裝 manifest 導回 User。
- Ledger YTD realized P&L 已區分 authoritative value／confirmed zero／pending／unavailable；新增與 append-only correction 都會顯示 pending 並 reload 全 Ledger data future，Holdings／Records／Reports 不再各持一套 summary state。
- Ledger Records 已恢復「建立更正」流程；Reports 直接使用 canonical annual/monthly aggregates。
- Admin 資料治理已加入去識別化 Private Pipeline operational aggregate；migration `045_private_pipeline_operations` 已成功，Private Pipeline seed execution 成功，不暴露 user／symbol／trade／holdings body。
- Final Visual 已加入 canonical-data visualization：Stock Detail K 線＋成交量、五面向健康度 bars、Ledger 月度已實現損益圖；圖表只視覺化 backend 欄位，不在 Flutter 重算 canonical holdings／PnL／exposure。

最新 CI／runtime evidence：

- Flutter run `37405203811`：analyze、58 tests、PWA metadata、`flutter build web -t lib/final_visual.dart --base-href /app/` 全部成功。
- Deploy run `37405204175`：成功；Cloud Run latest Ready revision `janus-api-g3e29701ffae1-config`，100% traffic，image digest `sha256:801e157899e99c38f2ca3d059a6b246d8391d9299a84b6018c26612465296f68`；verify 確認 Flutter User/Admin workspace、distinct PWA manifests 與 web build 都對應 `3e29701ffae1dfe3aa9d32deb50ded03f8145c18`。
- migration 045／Private Pipeline operational seed 與 Admin PWA rollout 的前置 deploy run `37398213942` 已在 retry attempt 2 完整成功；先前 429 為 verify transient，未重跑已成功 migration。

剩餘 **live-only** A acceptance：

- Android／Chrome 真實安裝後分別從 User 與 Admin icon 重開，確認 Admin 不再落回 User。
- 真實 Google User／Admin 登入、owner isolation／未登入拒絕與四頁約 390px 實機 Final Visual 對照。
- 真實 owner 新增／建立更正交易後，驗證 operational positions 即時、Private Mart pending → refreshed、Holdings／Records／Reports／YTD canonical consistency。
- 實機暖機核心資訊 p95 ≤2 秒、已訪問頁恢復 ≤300ms 的樣本與裝置證據。
- Scheduler／Private Pipeline 真實時序、failure/retry receipt，以及 GCS lifecycle／cleanup／billable/reclaimed-cost evidence。
- Admin 真實登入後確認 effective batches、資料治理與 Private Pipeline aggregate 的 live readback。

完整 checkpoint 見 [`archive/group-a-nonlive-closure-2026-10-06.md`](archive/group-a-nonlive-closure-2026-10-06.md)。

## 2026-10-05 Cloud 交接狀態

A 組目前判定為 `partial`。正確語意是：**部分功能已完成並進入 GCP dev 真實驗收，仍可能透過真實驗收發現 implementation gap；發現後必須回到實作修正。** 不得把目前狀態解讀成「implementation 已全部完成，只剩驗收」，也不得依部署成功勾選整組 acceptance。

使用者最新指示仍以既有 GCP dev 真實環境為主：真實登入、真實使用者、真實資料、真實 API/runtime。A 組驗收不是單純 read-only verification；若 UI、data state 或功能在真實驗收失敗，必須完成「定位 → 修正 → 測試 → commit/push → dev 部署 → 使用同一 GCP dev URL 重驗」閉環。這不自動擴展到 B／C 的 specialist／CEO scope，但 A 組非 AI 主體 implementation gap 不能因已進驗收而延後。

四張使用者提供的原始 PNG 已恢復並通過 CRC／解壓驗證，reference 資產 blocker 已解除；但圖片存在不等於 Flutter／GCP dev 已收斂。Today、Watchlist、Ledger、Stock Detail 的 Final Visual Contract 是 A 組正式結案 gate：在真實 authenticated owner 與 persisted data 下，非 AI 主體 UI 必須明顯收斂其 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout 與 390px 級版面；loading／empty／error／partial／stale／missing 不得破壞主要 layout。若目前真實畫面仍明顯像 legacy UI，視為 acceptance failure／implementation gap，不是後續 cosmetic polish。AI-only 區塊可 bounded unavailable／hidden／partial，但不得用 AI 尚未完成作為保留舊版非 AI layout 的理由。

目前變更涵蓋個股分區載入／重試、延後 K 線、主頁狀態保留、隱藏持股頁停止輪詢、離榜關注保留與中文搜尋／行情投影、Admin 排程批次／資料治理，以及 migration 043 的既有角色唯讀權限。Broker Profile、完整 Quote Router／last-quote persistence、其餘版型／資料治理欄位、效能 profiling 與 A 組 live acceptance 尚未完成；B／C 尚未由此次變更完成。

部署前本機證據：Flutter 全部 47 tests passed；`flutter analyze --no-fatal-infos lib test` exit 0（35 info）；Python 87 targeted tests passed，另 public-runtime 等前一輪 63 passed；workflow YAML 與 `git diff --check` 通過。這些不是 GCP live acceptance。

### A 組真實驗收新發現：Ledger／個人持股

2026-10-05 使用者在既有 GCP dev 真實畫面回報以下 acceptance failures／待查項。這些現象已足以使 A 組維持 `partial`，但 root cause 尚未完成 code/runtime tracing，因此不得自行猜成正常 batch delay：

- **YTD realized P&L：`unknown/partial`。** 個人持股中的「本年已實現損益」尚未明確出現或更新。需查明是否已完整實作、canonical source、交易後更新時點，以及即時／event-driven／batch/materialization 的真實鏈路；當年度無已實現交易時的 `0`／empty／unavailable 語意也需由正式 contract 與 backend evidence 確認。
- **Ledger Holdings／Records／Reports summary synchronization：`partial`，A 組 acceptance failure。** 切到「記錄／報表」時，上方持股資訊仍顯示舊資料，未與「持股」同步。需排查各 tab 獨立 state、provider/repository 共用、cache invalidation、tab refresh、舊 endpoint、position source 與 valuation/as-of semantics。若「持股」已有新資料而其他 subview 仍舊，不能用「整個批次尚未跑」概括。
- **Reports refresh／aggregation：`unknown/partial`。** 報表沒有跟著目前持股／交易資料更新。需追查 report API、transaction source、position projection、aggregation source、DB table/view/materialized projection、Job／Scheduler／trigger、cache TTL／invalidation、valuation/as-of 與 transaction 入帳後更新鏈路；依 evidence 最終判定 `implemented`／`partial`／`missing`／`blocked`。
- **Canonical consistency／refresh acceptance：待驗證。** Holdings、Records、Reports 對 shares、cost、market value、unrealized／realized／YTD realized P&L、valuation date、as-of/freshness、pending transaction／pending Private Mart 應共享或可追溯至同一 canonical position state。交易新增／修改／同步或 projection 更新後，三個 subview 與 YTD realized P&L 都必須可判斷是否已刷新；舊 cache 不得長時間無說明殘留。

若實際更新鏈路採 batch，後續 acceptance evidence 必須列出 Job 名稱、Scheduler／trigger、頻率、source table、target projection、freshness SLA 與 failure 行為；若不是 batch，也必須記錄真正的 refresh/invalidation chain。尚未查明前狀態維持 `unknown/partial`，不得以「可能等批次」取代 root-cause。

Cloud 接續入口：先讀本文件、PROJECT_RULES、README、TODO 的 A 組與 codex-execution-plan。核對部署／043 migration 與 runtime revision，再做真實 API／auth／owner、authenticated browser、四頁截圖與效能、既有維護 receipt／Job 證據驗收。驗收發現的 A 組 implementation gap 直接修正並重新部署／重驗；缺 credentials／登入／瀏覽器能力時列 blocker，mock 不得冒充 live evidence。本地驗收維持暫停，不重做 042 或已成功的 043，不自動擴展至 B／C。

部署與 immutable digest 證據見 [A 組部署 checkpoint](archive/group-a-deployment-checkpoint-2026-10-05.md)：Ingestion／043、Private Pipeline 與 API／Flutter PWA 已成功部署；剩餘 GCP dev 驗收與驗收發現之 implementation gap closure 仍屬 A 組未完成範圍。

### 2026-10-05 Quote Router／Broker Profile 與 runtime freshness evidence

- Main `2d8a7bf6c916f8901bb29779d48dfbe753a52420` 已加入 operational last successful quote、owner-scoped immutable Broker Profile revisions、API／Flutter UI、export/delete lifecycle 及正式 migration 044。Python targeted tests 146 passed；Flutter tests 48 passed。宣告現金仍是 declared snapshot，不是 canonical cash ledger；尚不含自動計費與 per-trade fee-rule snapshot。
- Deploy run `37305142870` 已成功，migration 044 execution `janus-ingestion-core-8j8t5` succeeded；API revision `janus-api-g2d8a7bf6c916-config` Ready／100% traffic、live build-id match。完整 immutable digest 與驗收邊界見 [Quote／Broker runtime checkpoint](archive/group-a-quotes-broker-checkpoint-2026-10-05.md)。
- Authenticated Janus Dev Read-only v2 真實 owner readback：trades 最新 ledger version 24；positions／2026 annual-pnl 卻回傳 version 10、valuation date 2026-09-24，並標示 available。Cloud Run traffic evidence 確認 connector 的既有 `mcp-adapter` tag 仍指向 `janus-api-mcpownerbfix20260924`，不是目前 canonical revision；因此不得把此結果當成最新 Flutter Ledger defect evidence。GitHub main 的共用 `ContextSourceService` 仍缺少相同 freshness gate，故補齊此讀路徑。
- 修正：所有 private Mart context（investment-profile 除外）先比較當前 owner ledger version，舊或缺少 version 的資料 withholding，回傳 pending／private_mart_stale、空 records 與 current ledger version，避免舊持股或零損益冒充最新。修正 main `5d37e5fb6c8bd05562e110a5538f673ed8ef2150`，相關 47 tests passed；remote API tests 147 passed，run `37306165330` success，API `janus-api-g5d37e5fb6c8b-config` Ready／100% traffic、live build-id match。Canonical authenticated path 仍需真實登入重驗。舊 tagged connector 不構成此修正的部署後證據；未變更其 OAuth tag、issuer 或權限。
- 四頁 Final Visual Contract、390px、交易 refresh/invalidation、YTD realized P&L、效能及 Admin acceptance 仍未完成；A 組維持 partial。

## 現行產品決策

Janus 採 **Token-first 五 specialist + On-demand CEO**：

- 五 specialist production 主路徑使用 Python／SQL／ML，不是每日五個生成式 LLM workers。
- 約 500 檔只做低成本 market screening／discovery；完整五 specialist 只做 `active watchlist ∪ effective holdings`。
- specialist 依 input change／dirty dependency incremental update；無變化 reuse。
- retrain／calibration／reconciliation 第一版月度。
- specialist 白話文由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只保留給 authorized manual On-demand CEO／approved rare escalation。
- CEO report 是 immutable symbol-level research artifact；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 DB-backed capability（例如 `ceo_analysis.request`）、specialist model/evaluation、CEO provider/profile、quota/cooldown、usage/cost/audit。

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

被取代的每日五 LLM／CIO 規劃只留在 `archive/`／Git history，不再是 active completion gate。

## Admin 現行範圍

唯一 active Admin frontend 是 Flutter／PWA。主導覽目標：

- 總覽
- 批次
- 個股
- 市場資訊
- AI 分析
- 資料治理

Admin operational convergence 不重做整個 shell；`資料治理` 是正式目標名稱。詳細 contract：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

## 已存在、可重用的能力

- GCP `dev` 是個人真實 parallel-live environment。
- WBS-3 full-market base coverage／data supplement 已有 500 market coverage、12Q／12M、fixed Core snapshots、Fact Packs、daily incremental、Saturday quality evidence。
- PostgreSQL serving projection migration `042_stock_serving_projection` 已在 dev 完成；`ohlcv`／`valuation`／`events` 共 `78,079 / 78,079` eligible rows 已 materialize，public API 以 `publication.stock_serving_recent` 為 stock-detail hot path、Iceberg 為 fallback，且 live Cloud Logging 已驗證 `source=serving_projection`。完成證據見 [`archive/stock-serving-projection-042-completed-2026-10-04.md`](archive/stock-serving-projection-042-completed-2026-10-04.md)。
- 既有 provider adapters／routing／auth／free-billing gate／validator 的 bounded dev evidence 可重用於 CEO provider path，但**不代表** specialist-engine 或 On-demand CEO 已完成。
- User API 已有 Google OIDC owner boundary；Admin 有獨立 Google admin allowlist。
- Stock Detail 已有 persisted report、positions、notes、Kline/events、analysis feedback 等 read-path basis，可供後續 specialist／CEO integration。
- Flutter Admin shell、Overview／Batch、Stock Workbench 的既有 acceptance 保留；新的 operational convergence 仍在 TODO。
- legacy static Admin 已退役，不再是 parity／release gate。

## Active 執行順序

唯一權威排序見 [`todo.md`](todo.md)：

1. **A：操作體驗／效能／資料營運** — User 非 CEO 功能、Admin operational convergence、四頁非 AI 相依版型、效能／FinOps 與文件對齊。
2. **B：specialist／增量快取** — 合併 `WBS-5-MART-SPECIALIST-ENGINES` 與 `WBS-5-MART-RERUN-CACHE`。
3. **C：CEO／權限／最終整合** — 合併 provider、CEO synthesis（原 CIO tracking ID）、Admin profile、User AI integration 與 Final Visual 剩餘 acceptance。

執行指令見 [`codex-execution-plan.md`](codex-execution-plan.md)。同組先整合程式再集中驗收，原 WBS acceptance 不取消。預警與通知由 Parking Lot 管理，另存 [`future-market-alerts.md`](future-market-alerts.md)，目前不執行。

042 serving projection 重用已有完成證據；公開資料清理依 operations 已有 apply/readback 只補剩餘項，041／compaction／retrain 核對最新證據。此次只是待辦整合，不宣稱任何未完成 capability 已完成。

## 模型／framework 方向

- Fundamental：deterministic financial features + LightGBM。
- Valuation：deterministic valuation + LightGBM／CatBoost benchmark。
- Quant：LightGBM baseline + Microsoft Qlib DoubleEnsemble challenger。
- Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- Event／Catalyst：parser／rules + Hugging Face Transformers multilingual local classifier。
- Explanation：SHAP／feature contribution + deterministic templates。

AutoGluon、FinBERT、FinGPT 只作 benchmark／research challenger；production champion 必須由 Janus Taiwan PIT walk-forward OOS evidence 決定。

## 尚未完成的關鍵 acceptance

- A 組四頁非 AI 主體 Final Visual convergence、Ledger canonical consistency／YTD realized P&L／Reports refresh chain 與真實 GCP dev defect closure 尚未完成；因此 A 組維持 `partial`。
- 五 specialist 的完整真實 dev／OOS、完整 ML baseline、dirty dependency、monthly retrain／reconciliation 尚未完成整體驗收。
- On-demand CEO command／capability／immutable report history 尚未完成。
- Admin specialist model/evaluation + CEO capability/profile controls 尚未完成。
- User Stock Detail manual Analyze/Re-analyze + freshness/history 尚未完成。
- Admin `資料治理`、batch operational convergence 尚未完成 live authenticated browser acceptance。

因此目前不得宣稱「A 組已完成」、「Token-first 五 specialist production 已完整完成」、「manual CEO 已可用」或「新版 Admin operational convergence 已完成」。

> **A 組不是「部署完成後做驗收」，而是「在真實 GCP dev 驗收中持續發現並關閉 implementation gap」；Today、Watchlist、Ledger、Stock Detail 的非 AI 主體 UI 必須在真實登入與真實資料下明顯收斂至 Final Visual Contract，且 Holdings／Records／Reports 必須共用一致、可追溯且可刷新之 canonical position state，否則 A 組維持 partial。**

## Evidence 讀取順序

1. GitHub `main` code／schema／migration／workflow／tests。
2. 最新 CI／deployment／live runtime／trigger／workload／integration evidence。
3. [`todo.md`](todo.md) 看 active acceptance。
4. Active SPEC／WBS／UI contract。
5. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 `archive/` 查歷史 evidence。

文件修改、commit、build、upstream benchmark 或單次 bounded success 都不代表功能完成。
