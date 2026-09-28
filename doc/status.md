# Janus Current Status

更新：2026-09-28

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作見 [`todo.md`](todo.md)；六個月 Pilot 新增 operational checkpoint 見 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；Janus web root routing incident evidence 見 [`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md)；deployment controller consolidation evidence 見 [`deployment-controller-consolidation-2026-09-26.md`](deployment-controller-consolidation-2026-09-26.md)；完整歷史 evidence 見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 現在的判定

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是 demo／mock staging。
- Janus hard split、read-only MCP／OAuth、Dev Pilot Entry 等既有 acceptance 保持有效；是否完成仍以各自 implementation／runtime evidence 判定。
- `WBS-8-DEV-PILOT-RUN` 已進入六個 calendar months operational evidence window，目前仍是 `partial`。Checkpoint 001 已記錄自然 Scheduler failure、版本化 calendar repair 與 bounded dataset acceptance；Checkpoint 002 已記錄 deployment-controller consolidation 的 manual intervention、canonical bounded deployment acceptance 與獨立 post-acceptance verification。下一個關鍵 runtime boundary仍是 repair 後的自然 Scheduler recovery evidence；上述手動／bounded evidence 不可替代自然 Scheduler evidence。
- **2026-09-26 dev deployment controller consolidation 已完成。** `janus-ingestion-core` 與 `janus-intelligence-mart` 的兩個 legacy `us-central1` Cloud Build triggers 已 guarded 刪除；cleanup run `36229366763` 先保存 rollback artifact，再精確刪除兩個 trigger。canonical GitHub deployment run `36229503909` 對 ingestion-core／intelligence-mart targeted tests、deploy、`verify-dev.sh` 全部成功，API jobs skipped。獨立 read-only post-acceptance run `36229702938` 再次確認兩個 regional triggers 仍 absent、兩個 Cloud Run Jobs 都 `Ready=True`。此項判定只代表 duplicate deployment-controller condition `RESOLVED` 與 deployment acceptance `PASS`，不等同 ingestion／Mart workload live-data acceptance。
- **2026-09-26 Janus web root routing incident 已完成修復與 dev live acceptance。** 原因是 canonical Cloud Run service root `/` 沒有 FastAPI route，直接開啟會 404；修復 commit `27c8a0b7d091bcc0e86147688b5907762b32a2ba` 已部署到 revision `janus-api-g27c8a0b7d091-config`、100% traffic，image digest `sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`。Runtime inspect run `36226506571` 實際驗證 `/` 為 307、`Location: /app`，且 `/app/` Janus entrypoint 可達。此 routing 修復不代表 User／Admin product completeness 已完成。
- **進入 observation window 不代表 feature freeze，也不代表產品功能完整。** Pilot observation 與產品完整度修復是兩條可並行的工作線；前者累積長期 operational evidence，後者補齊目前 dev 真實使用仍缺少的資料與操作閉環。
- **`WBS-3-FULL-MARKET-BASE-COVERAGE` 維持 partial。** 最新有效名單為 TWSE 上市 500 檔，已在既有 2 GiB dev Job 完成 2026-09-24 一次性整批 replay：OHLCV 499/500、valuation 498/500、institutional 499/500、MOPS financials 499/500、financing 498/500、securities lending／short 499/500、day trading 482/500、TAIEX 1/1。Execution `janus-ingestion-core-8xhlx` task 成功、來源失敗 0，coverage 因官方缺檔維持 partial；完整 snapshot／inventory／hash 見 [operations evidence](spec/operations-and-testing.md)。尚須核對缺檔語意及 watchlist／離榜持股、DQ／成本等整體 acceptance。
- 使用者 2026-09-28 指示停止追補 TPEx `3718`；該 missing 屬歷史跨市場名單，新 TWSE 500 名單不包含此股，舊 TPEx 結果不作新範圍驗收。
- **Iceberg financials 手動維護已通過 dev 驗收並啟用每週排程。** 維護當時的 1 GiB Job 保留 22 個 snapshots、過期 1,299 個，刪除 448 個舊 metadata JSON，當時 11,954 列及 7 個 Core manifest 引用的 snapshots 維持可讀。GCS 有效 metadata bytes 從 361,299,847 降至 206,536,934（減少 154,762,913）；排程每週日台北時間 12:00 用同一 Job 執行，手動 dispatch dry-run 已通過，首次自然排程尚待觀察。Job 現已依使用者批准改為 2 GiB；Bucket versioning／soft delete 使實際計費空間延後下降；本程序尚未做 `.avro` orphan cleanup 或 manifest rewrite。
- **User product completeness 目前未完成。** 現有 Flutter 已有交易／持股 presentation 與 missing／stale／partial 狀態處理，但真實持股若缺行情 coverage 或名稱解析，Private Mart 仍無法產生完整 aggregate valuation／unrealized PnL；UI 不得自行補算或用 placeholder 假裝完整。
- **「今日」的 deterministic market-home API 與 User UI 均完成 dev acceptance。** Public endpoint 讀到已持久化 Core benchmark、市場活動與法人資料；各區塊保留各自資料日，日期不同時不顯示共用日期。登入後 Chrome `/app/` 顯示真實 Core 資料與「研究摘要尚未就緒」；390×844 手機 bottom navigation、1280×900 桌面 navigation rail 均驗收通過。UI commit `da3e83a69a73fa5004badc75602eb9a88642ec3d`、Flutter CI `36314185316`、dev deployment／verify `36314185317`、Ready revision `janus-api-gda3e83a69a73-config`（100% traffic）。詳見 [WBS-6-MARKET-HOME-UI archive](archive/wbs-6-market-home-ui-2026-09-27.md) 與 [operations evidence](spec/operations-and-testing.md)。
- **Admin target workspace 尚未完成。** Legacy/static surface 在 migration 期間保留；Flutter Admin shell、overview／batch 與 stock data workbench 是產品完整度工作，不因六個月 observation window 而延後到 Pilot 結束後。
- `WBS-6-TRANSACTION-UX-2` 的既有完成判定只代表該次 presentation／read-path／state acceptance 已完成，不代表全市場行情 coverage、股票名稱解析、aggregate portfolio valuation 或整體 User App 已完成。

## 兩條並行主線

### A. Product Completeness foreground

依 [`todo.md`](todo.md) 以使用者指定的整體 WBS 作為工作／驗收單位；WBS 內同來源或可共用驗收的資料集合併批次完成，不在資料集或內部步驟間停等。遇到 blocker 時先推進其餘安全且獨立的條件；目前順序為：

1. `WBS-3-FULL-MARKET-BASE-COVERAGE`：只對有效週量 500 執行基礎市場 coverage；不得把 500 檔結果宣稱為所有股票完整 coverage。
2. `WBS-6-FLUTTER-ADMIN-SHELL` → `WBS-6-ADMIN-OVERVIEW-BATCH` → `WBS-6-ADMIN-STOCK-WORKBENCH`：完成 Admin 主路徑，另增「市場資訊」以檢視／調整週量 500 進出。

Shioaji 目前僅證實既有模擬憑證可登入及送出單檔 Quote 訂閱；正式環境登入回權限相關錯誤，且 2026-09-27 非交易時段，不能據此宣稱盤中即時股價或 User 市值更新可用。

`WBS-3-LIQUID-500-ROTATION` 已完成；live Admin 換股、500 檔數量、audit 與原名單復原均通過。完成 evidence 見 [`WBS-3 archive`](archive/wbs-3-liquid-500-rotation-completed-2026-09-27.md) 與 [`operations ledger`](spec/operations-and-testing.md)。

目前 foreground WBS 仍是 **`WBS-3-FULL-MARKET-BASE-COVERAGE`**，狀態 `partial`。TWSE 500 的來源、Stage 與 Core 整批路徑已完成 dev replay；融資券／借券／當沖已接入。下一步核對官方缺檔及 watchlist／離榜持股、DQ／成本等尚未完成的整體 acceptance，不逐資料集停等。

### B. Dev Pilot operational observation

- `pilot_started_at=2026-09-24T15:29:19Z`；六個月 window 繼續累積自然 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。
- Checkpoint 不得用手動 bounded run 代替自然 Scheduler evidence；沒有新證據時維持 `not observed`／`pending`，不得補成成功。
- Observation lane 不自動授權 Production、付費 source、新 GCP service、HA／multi-region 或其他仍受 gate 的工作。

## 非 foreground 工作

Mart Fact Packs、AI role contracts／validation／providers、CIO synthesis、rerun/cache、Analysis Profile、Pilot Mart AI evaluation、Research Context evolution、完整跨裝置／A11y、Production architecture／HA／backup planning 與 P4 DQ calibration 仍保留在 TODO，但不應先於上述產品完整度缺口。

## Evidence 讀取順序

需要判斷「是否完成」時依序看：

1. GitHub `main` 的實際 code／schema／migration／workflow／tests。
2. 最新 tests／CI／Cloud Build／deployment／live runtime／trigger／workload／integration evidence。
3. 本頁做快速定位。
4. [`todo.md`](todo.md) 看完整未完成 acceptance；[`pilot-operational-evidence.md`](pilot-operational-evidence.md) 看六個月 observation 新增 checkpoint；[`deployment-controller-consolidation-2026-09-26.md`](deployment-controller-consolidation-2026-09-26.md) 看 deployment controller consolidation；[`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md) 看 web root routing incident；[`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整歷史 evidence ledger。
5. `archive/` 只用於歷史原因、已完成或被取代設計。

文件修改、commit、build 或單次 bounded success 本身，都不代表整體功能完成。
