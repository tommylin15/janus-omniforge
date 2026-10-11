# 合併產品候選驗收 checkpoint（2026-10-11）

狀態：**PARTIAL；正式 dev 未切流，尚非整批產品結案。** 本次使用者授權先完成 B9 產品／C 組／剩餘持股與首屏，再集中驗收上版；500 檔歷史與模型研究後置。

## 已取得證據

來源 `5e1bb2f1645cd3885f16221699f64b48c9601bbb` 的 [完整 Release #38114690850](https://github.com/tommylin15/janus-omniforge/actions/runs/38114690850) 通過 1037 Python tests（2 項 legacy deselected）、Flutter、四公開 GHCR 映像與匿名拉取。Migration 051／050 的 [#38111640031](https://github.com/tommylin15/janus-omniforge/actions/runs/38111640031)／[#38111915613](https://github.com/tommylin15/janus-omniforge/actions/runs/38111915613) PASS；隔離 PostgreSQL CI 證明 ACL、owner、併發、idempotency 與 cancel terminal 契約，不能冒充 live CEO 整合驗收。

使用者明確核准受限 CEO dev Job 及該 Job 專屬 API 執行／讀取權限、無法確認 Free Tier 的執行費用。[worker #38115526978](https://github.com/tommylin15/janus-omniforge/actions/runs/38115526978) 已完成既有 Job 的受控更新並保留公開 rollback digest；1 CPU／1 GiB／480 秒／retry 0／無 Scheduler。早先空事件寫成 0 的 runtime 失敗保留，修正缺值語意與快取版本後再驗收。

[候選 #38115607687](https://github.com/tommylin15/janus-omniforge/actions/runs/38115607687) 建立 `janus-api-00463-dam`（0%）；[runtime #38115742279](https://github.com/tommylin15/janus-omniforge/actions/runs/38115742279) 將固定 preview 指向該候選，兩次 dedicated worker 基準執行成功，第一次 10 computed／15 reused，第二次 0 computed／25 reused，兩次均 4954 rows、0 LLM；租約釋放。正式 dev 保留 `janus-api-00457-wed` 100%，四排程 Job image 未更新。

已對新 preview 的 A 帳號實測 390×844 持股、固定導覽、個股詳情、persisted 五角色基準、報表、筆記與 CEO 未授權狀態。真實缺值顯示 unavailable／missing，不把模型品質或同日市場來源缺口補為成功。持股 core 8 個有界樣本 P50 489.5ms／P95 950ms；snapshot TTFB 7 個樣本中位 481ms／P95 653ms。Today 第一次 8037ms 另保留，不能宣稱全站冷啟動或效能結案。私密畫面與 canonical 數值只留工作區驗收資料，未放 GitHub。

候選 MCP 的 OAuth metadata／PKCE／有效與無效 redirect／未登入 401／三個唯讀工具宣告已驗證；連接器 A private positions 與 User App 相符。未呼叫 ledger write；未宣稱新版 B authenticated MCP owner isolation 已通過。

## 後續修正與未決 gate

畫面發現行情 ledger version 位於 API response 頂層，UI 從 aggregate 讀取而顯示缺值。來源 `2c920782bc45736ffb0749d7ec0800d19f0ab153` 修正同一份 response 的版本傳递，Flutter 回歸 PASS；同時修正舊 writer fence 對確認零 trigger／零 active build 的誤擋，仍拒絕未知／啟用 trigger 或 active build；73 項 Python 回歸 PASS。

新來源 [完整 Release #38118061761](https://github.com/tommylin15/janus-omniforge/actions/runs/38118061761) 的 1044 Python tests（2 legacy deselected）、Flutter、四公開映像與匿名拉取均 PASS；舊來源證據不能直接當新版候選 PASS。[唯讀 preflight #38118063739](https://github.com/tommylin15/janus-omniforge/actions/runs/38118063739) 已確認 Job ready／terminal executions／四 runtime identities actAs／update-canary IAM／Scheduler／legacy writer fence PASS。整份診斷仍 BLOCKED，唯一失敗是範圍外 `janus-research-big-move-500` 舊 AR rollback image 404；四個更新目標的可回復基準另由正式 rollout guard 驗證，不更新 research 或以 workflow success 偽造整份 PASS。

Admin 使用獨立登入設定，Google popup 仍需本人完成；新版 A→B→A owner proof、已核准 profile／capability 的 live CEO execution／immutable history 仍未取得。完成新版候選與上述整批驗收後，才能更新四排程 Jobs、驗證 canary／rollback、切換 API 正式 dev 流量。

新版 [候選 #38118406366](https://github.com/tommylin15/janus-omniforge/actions/runs/38118406366) 與 [受限 worker 更新 #38118539210](https://github.com/tommylin15/janus-omniforge/actions/runs/38118539210) PASS。候選／preview `janus-api-00465-feq` 為 0%，正式 dev 仍 `janus-api-00457-wed` 100%。新版 bootstrap full SHA 已由 browser DOM 核對；A 登入保留，390px 真實持股頁已顯示正確 ledger version，canonical 數值與原先一致。新版候選 OAuth metadata／PKCE／redirect／未登入 401／三個唯讀 MCP tools 再驗 PASS；未呼叫 ledger write，未宣稱 B authenticated MCP PASS。

新版 [runtime #38118621503](https://github.com/tommylin15/janus-omniforge/actions/runs/38118621503) PASS：`janus-ceo-analysis-4mrcn`／`janus-ceo-analysis-dvrfw` 均 succeededCount=1，completionTime 分別為 2026-10-11T06:41:54.396475Z／2026-10-11T06:45:34.446964Z；兩次均 bounded deep-coverage、LLM tokens 0，租約已釋放。這是 persisted 基準驗收，並非登入後 on-demand CEO provider PASS。

## 續接驗收（2026-10-11）

原對話 `01a12875-caa4-7960-9b21-4534543876c8` 最後的使用者回覆已完成新版 preview A→B→A checklist（含 B 無法讀取 A 私人資料／已知 A 紀錄，以及返回 A 的持股、交易與損益一致）。Owner receipt 使用本次來源與候選，標示 USER_ATTESTED，不冒充 B credential machine replay。Admin 於本次續接重新登入成功，profile 與五角色版本可讀回。

使用者另於本次明確核准本人受限 CEO 權限（每日 1 次、冷卻 300 秒）、既有三 provider/model/free-only gates 與一次有界 provider 驗收。Admin capability v1 與 default profile v2 已由真實候選 UI 保存並讀回；不保存 email、token 或私人數值到公開證據。第一個 UI 指令未確認，唯讀 history 證明無保存請求；受控重試取得 HTTP 202／dispatched，唯一 request `392cad00-13e3-4e7c-9266-01420d32557a`。目前 QUEUED，重新分析已停用，尚非 CEO PASS。

未提交的 candidate 自動更新 preview 提案因缺少失敗回復而移除，原差異留於本機工作資料備份；沿用已有 rollback 的 `ghcr-preview-publish-dev.yml`／`ghcr_preview_publish.py`。相關 33 tests PASS。四排程 Jobs 與正式 dev 流量仍未變更。
