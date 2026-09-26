# Janus Current Status

更新：2026-09-26

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作見 [`todo.md`](todo.md)；六個月 Pilot 新增 operational checkpoint 見 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；Janus web root routing incident evidence 見 [`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md)；完整歷史 evidence 見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 現在的判定

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是 demo／mock staging。
- Janus hard split、read-only MCP／OAuth、Dev Pilot Entry 等既有 acceptance 保持有效；是否完成仍以各自 implementation／runtime evidence 判定。
- `WBS-8-DEV-PILOT-RUN` 已進入六個 calendar months operational evidence window，目前仍是 `partial`。第一份 checkpoint 已記錄自然 Scheduler failure、版本化 calendar repair 與 bounded dataset acceptance；下一個關鍵 runtime boundary 是 repair 後的自然 Scheduler recovery evidence。
- **2026-09-26 Janus web root routing incident 已完成修復與 dev live acceptance。** 原因是 canonical Cloud Run service root `/` 沒有 FastAPI route，直接開啟會 404；修復 commit `27c8a0b7d091bcc0e86147688b5907762b32a2ba` 已部署到 revision `janus-api-g27c8a0b7d091-config`、100% traffic，image digest `sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`。Runtime inspect run `36226506571` 實際驗證 `/` 為 307、`Location: /app`，且 `/app/` Janus entrypoint 可達。此 routing 修復不代表 User／Admin product completeness 已完成。
- **進入 observation window 不代表 feature freeze，也不代表產品功能完整。** Pilot observation 與產品完整度修復是兩條可並行的工作線；前者累積長期 operational evidence，後者補齊目前 dev 真實使用仍缺少的資料與操作閉環。
- **User product completeness 目前未完成。** 現有 Flutter 已有交易／持股 presentation 與 missing／stale／partial 狀態處理，但真實持股若缺行情 coverage 或名稱解析，Private Mart 仍無法產生完整 aggregate valuation／unrealized PnL；UI 不得自行補算或用 placeholder 假裝完整。
- **「今日」目前不能只以 `mart_daily_brief` 是否存在決定整頁是否有市場資料。** 目標契約改為先呈現 deterministic published market baseline；Mart／AI brief 是疊加層，缺少時只降級該區塊，不應讓已存在的 Core 市場資料在首頁完全不可見。
- **Admin target workspace 尚未完成。** Legacy/static surface 在 migration 期間保留；Flutter Admin shell、overview／batch 與 stock data workbench 是產品完整度工作，不因六個月 observation window 而延後到 Pilot 結束後。
- `WBS-6-TRANSACTION-UX-2` 的既有完成判定只代表該次 presentation／read-path／state acceptance 已完成，不代表全市場行情 coverage、股票名稱解析、aggregate portfolio valuation 或整體 User App 已完成。

## 兩條並行主線

### A. Product Completeness foreground

依 [`todo.md`](todo.md) 一次只執行一個原子項目；目前順序為：

1. `WBS-6-PORTFOLIO-COMPLETENESS`：真實持股名稱、行情 coverage、Private Mart aggregate valuation／PnL 與可診斷 missing-state 閉環。
2. `WBS-6-MARKET-HOME-DATA`：建立不依賴 LLM／Daily Brief 的 deterministic market-home bounded contract。
3. `WBS-6-MARKET-HOME-UI`：讓「今日」先顯示 market baseline，再疊加 Mart／AI 內容。
4. `WBS-3-FULL-MARKET-BASE-COVERAGE`：把 bounded canary universe 推進到當日 enabled stock master 的基礎市場 coverage。
5. `WBS-6-FLUTTER-ADMIN-SHELL` → `WBS-6-ADMIN-OVERVIEW-BATCH` → `WBS-6-ADMIN-STOCK-WORKBENCH`：完成不進 GCP／DB 也能定位與處理資料營運問題的 Admin 主路徑。

下一個 foreground 原子項目是 **`WBS-6-PORTFOLIO-COMPLETENESS`**。

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
4. [`todo.md`](todo.md) 看完整未完成 acceptance；[`pilot-operational-evidence.md`](pilot-operational-evidence.md) 看六個月 observation 新增 checkpoint；[`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md) 看 web root routing incident；[`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整歷史 evidence ledger。
5. `archive/` 只用於歷史原因、已完成或被取代設計。

文件修改、commit、build 或單次 bounded success 本身，都不代表整體功能完成。
