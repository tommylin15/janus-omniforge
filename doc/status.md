# Janus Current Status

更新：2026-10-02

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。**確定要做**的完整未完成工作只看 [`todo.md`](todo.md)；目前**不做**但保留供日後翻找的內容見 [`parking-lot.md`](parking-lot.md)。2026-10-02 最新 Admin／User／Routing／Provider 決策見 [`decision-2026-10-02-admin-user-routing-and-provider-plan.md`](decision-2026-10-02-admin-user-routing-and-provider-plan.md)；五位分析師每日運作 gate 見 [`five-analyst-daily-operation-gate.md`](five-analyst-daily-operation-gate.md)；六個月 Pilot 新增 operational checkpoint 見 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；完整歷史 evidence 見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 現在的判定

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是 demo／mock staging。
- Janus hard split、read-only MCP／OAuth、Dev Pilot Entry 等既有 acceptance 保持有效；是否完成仍以各自 implementation／runtime evidence 判定。
- `WBS-8-DEV-PILOT-RUN` 已進入六個 calendar months operational evidence window，目前仍是 `partial`。Checkpoint 001 已記錄自然 Scheduler failure、版本化 calendar repair 與 bounded dataset acceptance；Checkpoint 002 已記錄 deployment-controller consolidation 的 manual intervention、canonical bounded deployment acceptance 與獨立 post-acceptance verification。這條 observation 只寫 evidence，不再以 active TODO checkbox 表示，也不因沒有新事件而製造待辦。
- **2026-09-26 dev deployment controller consolidation 已完成。** `janus-ingestion-core` 與 `janus-intelligence-mart` 的兩個 legacy `us-central1` Cloud Build triggers 已 guarded 刪除；cleanup run `36229366763` 先保存 rollback artifact，再精確刪除兩個 trigger。canonical GitHub deployment run `36229503909` 對 ingestion-core／intelligence-mart targeted tests、deploy、`verify-dev.sh` 全部成功，API jobs skipped。獨立 read-only post-acceptance run `36229702938` 再次確認兩個 regional triggers 仍 absent、兩個 Cloud Run Jobs 都 `Ready=True`。此項判定只代表 duplicate deployment-controller condition `RESOLVED` 與 deployment acceptance `PASS`，不等同 ingestion／Mart workload live-data acceptance。
- **2026-09-26 Janus web root routing incident 已完成修復與 dev live acceptance。** 原因是 canonical Cloud Run service root `/` 沒有 FastAPI route，直接開啟會 404；修復 commit `27c8a0b7d091bcc0e86147688b5907762b32a2ba` 已部署到 revision `janus-api-g27c8a0b7d091-config`、100% traffic，image digest `sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`。Runtime inspect run `36226506571` 實際驗證 `/` 為 307、`Location: /app`，且 `/app/` Janus entrypoint 可達。此 routing 修復不代表 User／Admin product completeness 已完成。
- **`WBS-3-FULL-MARKET-BASE-COVERAGE` 已依使用者核准的各必要資料集缺值率 <10% 門檻結案。** TWSE 上市 500 檔的官方資料缺值率為 0–3.6%；原始 inventory `partial`、逐檔 `missing`、FinMind `blocked`、離榜持股 future-feed `partial` 照實保留，但這些已接受缺口**不再列 active TODO**，也不要求為了消除 `partial` 追到 500/500。完整歷史無缺口回補仍不作為一般目標；但 2026-10-02 起，五分析師 checkpoint 明確要求的必要 history／metric／PIT evidence 已另立 `WBS-3-DATA-SUPPLEMENT-V1`，不得再以舊 coverage acceptance 豁免。
- **正式批次修復與清理仍為 partial。** 單一 Cloud Scheduler 每小時台北時間 :30 呼叫 Cloud Run 總控，原 Mart／private Scheduler 暫停保留供回復；總控防重複與 Iceberg 紀錄的手動真實驗收通過，自然批次依賴驗收待觀察。Core／Stage 清理已成功，去除 52,663 列重複財報觀測，固定快照引用保留；Mart 正式清理成功，額外減少 1,372,605 bytes；正式零模型來源 → FactPack 鏈路仍待驗收。五個指定 bucket 已改非當前版本保留 3 日、關閉 soft delete。空間與失敗／修復證據見 [operations](spec/operations-and-testing.md)。
- **User product completeness 目前仍有 committed 項目。** 2026-09-29 Private Pipeline 修復後，真實 5876 持股已有正式盤後價且 aggregate valuation／unrealized PnL 恢復發布；其他持股若缺行情 coverage 或名稱解析，UI 仍須保留 missing／stale／partial 狀態，不自行補算或用 placeholder 假裝完整。既有 MIS 盤中報價能力已完成；2026-10-02 已將目標 contract 擴充為 DB-first persisted last quote＋盤中／盤後 multi-source routing、交易後 synchronous operational position projection、操作池／broker profile 與全 UI 數值格式收斂；這些新需求仍在 active TODO。
- **Flutter Admin shell 與原 `WBS-6-ADMIN-OVERVIEW-BATCH`／`WBS-6-ADMIN-STOCK-WORKBENCH` acceptance 均已完成。** 2026-10-02 新增 operability extension 包含 actionable exception drill-down、Job Control Center、Storage／Private operations 與 routing controls；這些是新的 committed work，不反向改寫歷史 WBS 的完成範圍。
- **五位分析師每日運作 Gate 1、Fact Packs Gate 2、AI Role Contract Gate 3、AI Validation Gate 4 已完成各自 acceptance。** 這只代表可以進入 provider／CIO chain，不代表五位分析師已每天自然運作。
- **`WBS-3-DATA-SUPPLEMENT-V1` 已列入 active queue。** S0～S2 是補資料第一版；`WBS-5-MART-AI-PROVIDERS` 2026-10-02 checkpoint 中經 runtime evidence 判定 applicable 的資料需求是最低 acceptance floor。S0 不能只做分類；S1／S2 必須把必要 history、metric mapping、PIT time semantics、event severity、positioning breakdown/cross-check、官方／產業比較基準等補到可供五角色使用。若需新來源但尚未取得必要授權，WBS 保持 `partial`／`blocked`，不得降低 requirement 結案。S3～S6 仍在 Parking Lot。

## 目前執行順序

唯一權威排序見 [`todo.md`](todo.md)：

1. `WBS-5-MART-AI-PROVIDERS` — 目前 foreground / partial。
2. `WBS-3-DATA-SUPPLEMENT-V1` — S0～S2 補資料第一版；Provider checkpoint applicable needs 是最低 acceptance floor。
3. `WBS-5-MART-CIO-SYNTHESIS`。
4. `WBS-5-MART-RERUN-CACHE`。
5. `WBS-6-ADMIN-ANALYSIS-PROFILE`。
6. Admin operational convergence。
7. User operational convergence。
8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE`。

`WBS-5-MART-AI-PROVIDERS` 最新 evidence：2026-10-02 第二個 GCP cold-start execution 的五角色均 `validated/insufficient_data`；19-object 獨立 readback、單股 same-execution Core／target／provider lineage 與 immutable replay 通過。兩批共用完十次核准 invocation；auth version 1→1，rotation 未觀察。Canonical Linux CI 137 passed、Mart deploy／verify success。Provider default route 為 **Codex CLI → OpenRouter → Gemini**，本次 effective route 僅 Codex；OpenRouter `$0` actual request 與 Gemini Free Tier／billing probe 被自動審核擋下，兩者保持 blocked。剩餘 auth lifecycle、全 target／情境 acceptance 與持續批次額度未完成，WBS 保持 partial；詳見 [checkpoint 與 2327 缺資料明細](archive/wbs-5-mart-ai-providers-checkpoint-2026-10-02.md)。五份 validated／insufficient_data 不等於完整研究或五分析師自然每日運作已可用。

## 不再列 active TODO 的內容

Pilot observation、Production go/no-go／HA／paid backup、全市場完整歷史無缺口回補、分 K／Tick、S3 News、S4 Supply-chain、S5 Broker Research／Consensus／Target Price、S6 Social／Podcast／Alternative sources、Pilot Mart AI evaluation 擴張、PIT/outcome 校準、完整 device／A11y matrix、P4 DQ roadmap、其餘 Research Context roadmap 等留在 [`parking-lot.md`](parking-lot.md)。

這些內容不是「偷偷延後的欠債」；目前判定就是**不做**，不計入專案未完成度。只有使用者日後明確改成「做」，才重新放回 `todo.md` 並取得順序與 acceptance。若 S0 證實某個 Parking Lot 類型是滿足 checkpoint minimum floor 唯一合理且可核准的 bounded source，只拉該必要 source 進 S1／S2，不等於整個後續 roadmap 啟動。

## Evidence 讀取順序

需要判斷「是否完成」時依序看：

1. GitHub `main` 的實際 code／schema／migration／workflow／tests。
2. 最新 tests／CI／Cloud Build／deployment／live runtime／trigger／workload／integration evidence。
3. 本頁做快速定位。
4. [`todo.md`](todo.md) 看確定要做的未完成 acceptance；[`parking-lot.md`](parking-lot.md) 只供翻找目前不做的內容；[`wbs/wbs-3-data-supplement-v1.md`](wbs/wbs-3-data-supplement-v1.md) 看補資料第一版與 checkpoint minimum floor；[`decision-2026-10-02-admin-user-routing-and-provider-plan.md`](decision-2026-10-02-admin-user-routing-and-provider-plan.md) 看本次對話整合決策；[`pilot-operational-evidence.md`](pilot-operational-evidence.md) 看自然 observation；[`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整歷史 evidence ledger。
5. `archive/` 只用於歷史原因、已完成或被取代設計。

文件修改、commit、build 或單次 bounded success 本身，都不代表整體功能完成。