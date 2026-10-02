# Janus Current Status

更新：2026-10-02

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作見 [`todo.md`](todo.md)；五位分析師每日運作 gate 見 [`five-analyst-daily-operation-gate.md`](five-analyst-daily-operation-gate.md)；六個月 Pilot 新增 operational checkpoint 見 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；Janus web root routing incident evidence 見 [`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md)；deployment controller consolidation evidence 見 [`deployment-controller-consolidation-2026-09-26.md`](deployment-controller-consolidation-2026-09-26.md)；完整歷史 evidence 見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 現在的判定

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是 demo／mock staging。
- Janus hard split、read-only MCP／OAuth、Dev Pilot Entry 等既有 acceptance 保持有效；是否完成仍以各自 implementation／runtime evidence 判定。
- `WBS-8-DEV-PILOT-RUN` 已進入六個 calendar months operational evidence window，目前仍是 `partial`。Checkpoint 001 已記錄自然 Scheduler failure、版本化 calendar repair 與 bounded dataset acceptance；Checkpoint 002 已記錄 deployment-controller consolidation 的 manual intervention、canonical bounded deployment acceptance 與獨立 post-acceptance verification。下一個關鍵 runtime boundary仍是 repair 後的自然 Scheduler recovery evidence；上述手動／bounded evidence 不可替代自然 Scheduler evidence。
- **2026-09-26 dev deployment controller consolidation 已完成。** `janus-ingestion-core` 與 `janus-intelligence-mart` 的兩個 legacy `us-central1` Cloud Build triggers 已 guarded 刪除；cleanup run `36229366763` 先保存 rollback artifact，再精確刪除兩個 trigger。canonical GitHub deployment run `36229503909` 對 ingestion-core／intelligence-mart targeted tests、deploy、`verify-dev.sh` 全部成功，API jobs skipped。獨立 read-only post-acceptance run `36229702938` 再次確認兩個 regional triggers 仍 absent、兩個 Cloud Run Jobs 都 `Ready=True`。此項判定只代表 duplicate deployment-controller condition `RESOLVED` 與 deployment acceptance `PASS`，不等同 ingestion／Mart workload live-data acceptance。
- **2026-09-26 Janus web root routing incident 已完成修復與 dev live acceptance。** 原因是 canonical Cloud Run service root `/` 沒有 FastAPI route，直接開啟會 404；修復 commit `27c8a0b7d091bcc0e86147688b5907762b32a2ba` 已部署到 revision `janus-api-g27c8a0b7d091-config`、100% traffic，image digest `sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`。Runtime inspect run `36226506571` 實際驗證 `/` 為 307、`Location: /app`，且 `/app/` Janus entrypoint 可達。此 routing 修復不代表 User／Admin product completeness 已完成。
- **進入 observation window 不代表 feature freeze，也不代表產品功能完整。** Pilot observation 與產品完整度／five-analyst capability 是可並行的工作線；前者累積長期 operational evidence，後者補齊目前 dev 真實使用與每日研究仍缺少的資料、操作與分析閉環。
- **`WBS-3-FULL-MARKET-BASE-COVERAGE` 已依使用者核准的各必要資料集缺值率 <10% 門檻結案。** TWSE 上市 500 檔的官方資料缺值率為 0–3.6%；整批 dev replay、官方缺檔、watchlist／離榜持股、Private Mart、DQ／quarantine 與 bounded 資源使用量均已核對。原始 inventory `partial`、逐檔 `missing`、FinMind `blocked`、離榜持股 future-feed 註冊 `partial` 照實保留；不宣稱 500/500 或未驗證的帳單零費用。詳見 [結案紀錄](archive/wbs-3-full-market-base-coverage-completed-2026-09-29.md)。
- 使用者 2026-09-28 指示停止追補 TPEx `3718`；該 missing 屬歷史跨市場名單，新 TWSE 500 名單不包含此股，舊 TPEx 結果不作新範圍驗收。
- **Iceberg financials 手動維護已通過 dev 驗收並啟用每週排程。** 維護當時的 1 GiB Job 保留 22 個 snapshots、過期 1,299 個，刪除 448 個舊 metadata JSON，當時 11,954 列及 7 個 Core manifest 引用的 snapshots 維持可讀。GCS 有效 metadata bytes 從 361,299,847 降至 206,536,934（減少 154,762,913）；排程每週日台北時間 12:00 用同一 Job 執行，手動 dispatch dry-run 已通過，首次自然排程尚待觀察。Job 現已依使用者批准改為 2 GiB；Bucket versioning／soft delete 使實際計費空間延後下降；本程序尚未做 `.avro` orphan cleanup 或 manifest rewrite。
- **User product completeness 目前仍有 blocked 項目。** 2026-09-29 Private Pipeline 修復後，真實 5876 持股已有正式盤後價且 aggregate valuation／unrealized PnL 恢復發布；其他持股若缺行情 coverage 或名稱解析，UI 仍須保留 missing／stale／partial 狀態，不自行補算或用 placeholder 假裝完整。持股 MIS 盤中／盤後報價已完成；其餘未核准來源仍受來源授權 gate 限制。
- **「今日」的 deterministic market-home API 與 User UI 均完成 dev acceptance。** Public endpoint 讀到已持久化 Core benchmark、市場活動與法人資料；各區塊保留各自資料日，日期不同時不顯示共用日期。登入後 Chrome `/app/` 顯示真實 Core 資料與「研究摘要尚未就緒」；390×844 手機 bottom navigation、1280×900 桌面 navigation rail 均驗收通過。UI commit `da3e83a69a73fa5004badc75602eb9a88642ec3d`、Flutter CI `36314185316`、dev deployment／verify `36314185317`、Ready revision `janus-api-gda3e83a69a73-config`（100% traffic）。詳見 [WBS-6-MARKET-HOME-UI archive](archive/wbs-6-market-home-ui-2026-09-27.md) 與 [operations evidence](spec/operations-and-testing.md)。
- **Flutter Admin shell 已完成 dev acceptance。** 單一 `apps/user_app` codebase 以 `/app/admin`／explicit Admin workspace 提供中文 `總覽／批次／個股／市場資訊／AI 分析／進階管理` 導覽，desktop `NavigationRail` 與 390×844 mobile `NavigationDrawer` regression 均通過；User／Admin OAuth audience 分離，`/api/v1/admin/*` security boundary 仍由 backend `GoogleAdminAuthenticator` 執行。commit `2c1b2babdd1548cb79373f7fd8c46739a4073923` 的 Flutter CI `36561885167` success，canonical dev workflow `36561885101` 的 API tests、deploy 與 live verify success；Cloud Run revision `janus-api-g2c1b2babdd15-config` Ready、100% traffic，image digest `sha256:9b1a2eb392f6ba348f1cf55ee8fce8f988f31da5512d0603fa922c96c0f408dd`。legacy `/admin/stocks` static rollback surface 仍存在。詳見 [結案紀錄](archive/wbs-6-flutter-admin-shell-completed-2026-09-29.md)。
- **`WBS-6-ADMIN-OVERVIEW-BATCH` 已完成 dev acceptance。** Flutter Overview 現在只把 failed／partial／retrying execution、異常 Core source health 與 blocked／review-required／invalid Mart 項目放進 priority area；successful execution 不佔首頁主要空間，`partial` 明確不算完成。Overview／Batch 共用 execution detail，直接顯示 persisted `trace_id`、immutable execution lineage、逐項 `safe_message`、retry count 與 backend `retry_classification`；只有 `retryable` failed item 能從 UI 建立 narrow retry，安全邊界仍由 backend Admin service 決定。首次 commit `187c895b6203f5443ae0e21a489e6ebd6dd633e4` 的 Flutter run `36564380741` 因 4 個 widget regression 失敗，未當成功；修正 commit `9bf00f1fe6bd63ffd284023688a7a803fb13487d` 的 Flutter run `36565040429` 全綠，canonical dev workflow `36565040400` 的 API tests、deploy 與 live verify success。Cloud Build `10b6b6c9-f638-45bd-8187-8e29ccfbf4cd` success，revision `janus-api-g9bf00f1fe6bd-config` Ready、100% traffic，image digest `sha256:2f89421ab200ef9d22e681e76de8d840a2a60d226264788a97914af7dce27d22`。詳見 [結案紀錄](archive/wbs-6-admin-overview-batch-completed-2026-09-29.md)。
- **`WBS-6-ADMIN-STOCK-WORKBENCH` 已完成 dev acceptance。** 個股工作台支援代號／中文名搜尋，顯示 persisted dataset health、row count、coverage／gap、latest date，以及 advanced read-only source／execution／snapshot／provenance lineage。Gap repair 只允許同 dataset、enabled、collection-enabled 且來源授權狀態為 `official`／`approved_fallback` 的既有 config，並且只建立目前 symbol 的 bounded collection execution；沒有已核准 config 時 fail closed。Fact Pack／五角色／CIO 未完成前，UI 不提供會誤導成 advanced AI capability 已可用的 rerun／historical-role 操作。第一版 commit `7946e953cfd5fa3ced4d21dd51ed006708ce0cee` 的 Flutter run `36568576560` 為 38 passed / 2 failed，未當成功；經 `739a64384aa88319c76415e07720e552d30f40a5` 與 `9cceb3d1aa8777543f491393cda2c6fbe941a560` 修正後，Flutter run `36569491143` 全綠，canonical dev workflow `36569491137` success。Cloud Build `6ddfab32-02dd-44b9-b821-efb298ebe164` success，revision `janus-api-g9cceb3d1aa87-config` Ready、100% traffic，image digest `sha256:32517542be77d2c85b25cff35e95f9bd491a377878fb86f4f2d38dcd76cdcd2b`；live verifier 明確匹配 `9cceb3d1...`。詳見 [結案紀錄](archive/wbs-6-admin-stock-workbench-completed-2026-09-29.md)。
- **五位分析師每日運作 Gate 1 已完成。** `five-analyst-daily-operation-gate.md` 所列七個 Product Completeness prerequisite 現在全部有正式完成證據；這只代表可以進入 Fact Pack／AI role chain，不代表五位分析師已開始每天工作。
- **`WBS-5-MART-FACT-PACKS` 已完成 Gate 2。** 修復 Pilot outcome 的必要欄位 ACL 與 transaction recovery 後，原 target 與五筆舊 analysis 均恢復 succeeded；五包 contract、69 項本機測試、dev deploy／verify、十份 persisted schema／hash 驗證與真實 pinned Core replay 通過。資料不足的 report 保持 `insufficient_data / blocked`；該次僅驗收事實包；後續角色／validator 完成證據見下。詳見 [結案紀錄](archive/wbs-5-mart-fact-packs-2026-09-30.md)。
- **`WBS-5-MART-AI-ROLE-CONTRACT` 已完成 Gate 3。** 五角色／CIO schema、locked guardrail、六份 versioned prompts 與 immutable lineage 已建立；79 項本機測試、53 項 Mart CI、canonical dev deployment／verify、pinned 真實 Mart snapshot 的 create-only contract／六份 structured failure acceptance 與獨立 GCS readback 全部通過。格式通過僅 `schema_validated / pending`；provider／CIO synthesis／自然每日工作仍未完成；validator 狀態見下。詳見 [結案紀錄](archive/wbs-5-mart-ai-role-contract-2026-09-30.md)。
- **`WBS-5-MART-AI-VALIDATION` 已完成 Gate 4。** Provider-neutral validator、78 項 Mart tests／CI、4 項 registry tests、dev deploy／verify、pinned 真實快照的 5 validated／10 blocked fixtures 與獨立 30-object hash／lineage readback 通過。資料不足仍不是完整研究成功，沒有 provider 呼叫或 publication 寫入。詳見 [結案紀錄](archive/wbs-5-mart-ai-validation-2026-09-30.md)。
- `WBS-6-TRANSACTION-UX-2` 的既有完成判定只代表該次 presentation／read-path／state acceptance 已完成，不代表全市場行情 coverage、股票名稱解析、aggregate portfolio valuation 或整體 User App 已完成。

## 兩條並行主線

### A. Foreground

依 [`todo.md`](todo.md) 以整個 WBS 作為工作／驗收單位；遇到 blocker 時先推進其餘安全且獨立的條件。目前：

1. **`WBS-5-MART-AI-PROVIDERS` 目前 partial。** Sol 閘門及單股五次呼叫已核准，GCP 固定 `gpt-6.1-sol`／`low` 的五角色輸出、17-object readback 與九類 DB 投影驗收通過；validator 3 validated／insufficient_data、2 blocked，未完整成功。跨批次 auth 續期保存與 target/provider 同 execution 驗收仍待安全／新增 bounded quota 決策；詳見 [checkpoint](archive/wbs-5-mart-ai-providers-checkpoint-2026-10-01.md)。前項 [v1 compatibility](archive/wbs-5-mart-v2-compat-2026-10-01.md) 已結案，自然每日 AI 批次仍未啟用。
   2026-10-02 本機接續：已讀回定位／量化失敗成品，修正五角色 versioned prompt 的 claim coverage／numeric token／missing-key 說明，新增同 execution target＋Core＋provider 有界驗收入口。本機相關驗證 110 passed／3 deselected（Linux subprocess tests）；WSL 啟動失敗，未補成通過。此批 auth／prompt／驗收入口待 CI／dev 部署與真實驗收，尚未新增模型呼叫；使用者已核准且已建立獨立 auth Secret／最小 IAM，最多十次呼叫方案見 [provider runbook](runbook-mart-ai-providers.md#2026-10-02-接續方案已核准驗收狀態見-statuscheckpoint)；本次 auth 實作／dev 部署與驗收進行中。
2. **`WBS-6-PORTFOLIO-INTRADAY-QUOTE` 已完成。** 2026-10-01 使用已核准 MIS 路徑完成持股盤中／盤後報價、既有 dev 部署與 authenticated UI／30 秒前景更新驗收；詳見 [MIS 結案紀錄](archive/wbs-6-portfolio-intraday-quote-2026-10-01.md)。舊 Shioaji blocker 不再代表本 WBS 狀態；休市日曆仍需維護，MIS 快取非持久化。

使用者 2026-09-30 已將 Codex 五分析師研究路線納入 active planning：**GCP 既有批次自主
使用 Codex CLI 優先／必要 worker bridge，Gemini／OpenRouter 作受控 fallback**；不是
OpenAI API，也不重開通用 Chat runtime。細節見 [研究契約](spec/intelligence-and-governance.md#gcp-批次-codex-分析師研究路線active-planning尚未實作)。
Codex CLI wrapper／provider orchestration 已有程式碼與 CI；GCP 真實五角色整合、auth lifecycle 與 daily runtime 尚待獨立驗收，不能由 compatibility smoke 推定完成。
個股 AI 範圍已指定為 active 關注＋有效持股 symbol 聯集並去重；500 檔保留資料網與
deterministic screening，持股離榜仍在 target。Admission／quota／private isolation 已有實作，真實整合 acceptance 尚未完成。

`WBS-3-LIQUID-500-ROTATION` 已完成；live Admin 換股、500 檔數量、audit 與原名單復原均通過。完成 evidence 見 [`WBS-3 archive`](archive/wbs-3-liquid-500-rotation-completed-2026-09-27.md) 與 [`operations ledger`](spec/operations-and-testing.md)。

`WBS-3-FULL-MARKET-BASE-COVERAGE`、`WBS-6-FLUTTER-ADMIN-SHELL`、`WBS-6-ADMIN-OVERVIEW-BATCH`、`WBS-6-ADMIN-STOCK-WORKBENCH`、`WBS-5-MART-FACT-PACKS`、`WBS-5-MART-AI-ROLE-CONTRACT` 與 `WBS-5-MART-AI-VALIDATION` 均已完成。後續 Mart provider 等 planned slices 依 TODO／WBS dependency 與模型閘門執行。

### B. Dev Pilot operational observation

- `pilot_started_at=2026-09-24T15:29:19Z`；六個月 window 繼續累積自然 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。
- Checkpoint 不得用手動 bounded run 代替自然 Scheduler evidence；沒有新證據時維持 `not observed`／`pending`，不得補成成功。
- Observation lane 不自動授權 Production、付費 source、新 GCP service、HA／multi-region 或其他仍受 gate 的工作。

## 非 foreground 工作

AI providers、CIO synthesis、rerun/cache、Analysis Profile、Pilot Mart AI evaluation、Research Context evolution、完整跨裝置／A11y、Production architecture／HA／backup planning 與 P4 DQ calibration 仍保留在 TODO；其 dependency 與排序以 active TODO 和 `five-analyst-daily-operation-gate.md` 為準。

## Evidence 讀取順序

需要判斷「是否完成」時依序看：

1. GitHub `main` 的實際 code／schema／migration／workflow／tests。
2. 最新 tests／CI／Cloud Build／deployment／live runtime／trigger／workload／integration evidence。
3. 本頁做快速定位。
4. [`todo.md`](todo.md) 看完整未完成 acceptance；[`five-analyst-daily-operation-gate.md`](five-analyst-daily-operation-gate.md) 看每日分析師里程碑；[`pilot-operational-evidence.md`](pilot-operational-evidence.md) 看六個月 observation 新增 checkpoint；[`deployment-controller-consolidation-2026-09-26.md`](deployment-controller-consolidation-2026-09-26.md) 看 deployment controller consolidation；[`janus-web-root-acceptance-2026-09-26.md`](janus-web-root-acceptance-2026-09-26.md) 看 web root routing incident；[`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整歷史 evidence ledger。
5. `archive/` 只用於歷史原因、已完成或被取代設計。

文件修改、commit、build 或單次 bounded success 本身，都不代表整體功能完成。
