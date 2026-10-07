# Owner-scoped parallel Private Mart 重算控制器

日期：2026-10-07  
狀態：CLOSED — engineering/runtime PASS；authenticated Admin UI readback PASS

## 1. 目的

交易新增、更正、作廢後，Private Mart 可能暫時落後 operational ledger。User App 的「重新計算損益」不得在 API request thread 直接寫 Iceberg，也不得因單一使用者操作而重算全部 owner。

本設計建立 owner-scoped recalculation queue，使用既有 `janus-private-pipeline` Cloud Run Job 執行。沒有新增 Cloud Run Job resource；只在既有 Job 的 execution 上使用 2–8 個 task worker。

## 2. 不變治理

- ledger mutation 成功與 Private Mart 重算成功是兩件事；重算失敗不得回滾已成功的交易，也不得假裝 aggregate 已更新。
- 同一 owner 同時間最多一筆 active request；若 active 期間 ledger 又前進，只提高同一 request 的 requested ledger version。worker 完成舊版本時會把同一 request 重新排隊，直到實際 processed ledger version 追上 requested version才可成功。
- Flutter 不接受／傳送 `user_id`；owner 一律由 authenticated backend 決定。
- Private Mart canonical number 仍由 backend deterministic pipeline 產生。
- 排程型全體 reconciliation 保留原本 `PrivatePipeline.run()`；User 手動重算與 mutation immediate path 僅走 owner queue，不呼叫全體 `run()`。
- Admin UI 不顯示交易、持股或 user-to-symbol 關係，只顯示去識別化 owner ref 與 operational state。

## 3. 狀態機

`IDLE → QUEUED → RUNNING → SUCCEEDED | FAILED`

管理中止額外使用：

`RUNNING → CANCEL_REQUESTED → CANCELLED`

規則：

- `QUEUED/RUNNING/CANCEL_REQUESTED` 期間，同 owner 再次要求重算不新增第二筆 request；只把該 active request 的 `requested_ledger_version` 提升到最新版本。
- `SUCCEEDED/FAILED/CANCELLED` 為終態，之後才允許建立新 request。
- User API 回傳 safe `error_code`／`safe_message`；不得回傳 exception、secret、DSN 或 internal stack。

## 4. Queue 與 claim

PostgreSQL `private.recalculation_requests` 是 operational queue。partial unique index 保證每個 owner 只有一筆 active request。

Worker claim 使用：

`SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`

不同 Cloud Run task 可同時 claim 不同 owner；同一 owner 不會被兩個 worker 同時計算。

`private.recalculation_dispatch` 是 singleton dispatch fence。第一個 queued request 將 `active=true` 並觸發一個 shared Job execution；execution 尚在處理時，新 owner 只加入 queue，不另外無限制啟動 execution。

## 5. 並行模型

Admin 設定 `private_recalc_workers` 範圍固定 **2–8**，預設 **2**。

- Cloud Run Job resource 預設 `taskCount=1`，供正常 full reconciliation 使用。
- Job runtime `parallelism=8` 是硬上限。
- owner queue execution 由 API 透過 Cloud Run Jobs v2 `:run` override `taskCount=<admin workers>`。
- 設定變更只影響下一次 queue execution，不中途改變已啟動 execution。
- 每個 task 持續 claim queue，直到沒有待處理 request。

這裡的「worker／線程」是 Cloud Run Job task 的邏輯 worker，不是 Python process 內 thread。

## 6. 計算與 Iceberg 寫入

不同 owner 可平行執行 ledger/read/price/moving-average/risk 計算。

Private Iceberg tables 是 shared table metadata，因此 commit 階段使用 PostgreSQL advisory lock `(1835102836, 3)` 做 bounded single-writer fence：

`parallel prepare/calculation → serialized Private Iceberg write → release lock`

第一版不讓多個 owner 同時 commit 同一批 shared Iceberg tables，以降低 optimistic commit conflict。未來若 runtime evidence 證明可安全提高 write concurrency，再另行調整。

## 7. User UX

`GET /api/v1/me/journal/recalculation-status` 提供登入 owner 最新狀態。

當狀態為 `QUEUED/RUNNING/CANCEL_REQUESTED`：

- 「重新計算損益」按鈕 disabled。
- 顯示「已排隊／重算中／正在中止」。
- App 每 3 秒 bounded polling；進入終態後停止 polling 並重讀 canonical aggregate。

當 `FAILED/CANCELLED`：

- 顯示 safe message，使用者知道發生什麼事。
- 顯示「重新嘗試」。
- 不把 stale aggregate 顯示成最新值。

## 8. Admin UX

Admin「資料治理」顯示：

- configured workers（2–8）
- running / queued 數量
- active request：owner ref、requested ledger version、request id、Cloud Run execution、worker task index、attempt、safe state/message
- 最近終態

操作：

- 調整 workers 2–8：寫入 versioned `control.admin_settings`，有 audit。
- 「中止」：
  - QUEUED → 直接 CANCELLED。
  - RUNNING → CANCEL_REQUESTED；worker 在下一個 cancellation checkpoint 停止，最後寫 CANCELLED。
- 「回寫失敗」：Admin 必須輸入 User 可見理由，立即將 request 標成 FAILED。舊 worker lease 後續不能覆寫終態。
- 不提供「kill shared execution」作為單一 owner 的一般中止方式，避免一併殺掉其他 owner。

## 9. Failure / recovery

- Cloud Run dispatch HTTP 失敗：request 立即 FAILED，dispatch fence 釋放，User 可重試。
- Cloud Run `:run` 已接受但 5 分鐘內沒有任何 worker claim：判定 `DISPATCH_TIMEOUT`，仍在 QUEUED 的 request 轉 FAILED 並釋放 dispatch fence，避免無限排隊。
- Worker 計算／Iceberg write 失敗：該 owner request FAILED；其他 owner 繼續。
- Worker crash：Cloud Run max retry 維持 bounded。worker 在 cancellation/write checkpoint 更新 heartbeat；`RUNNING/CANCEL_REQUESTED` 若 35 分鐘無 heartbeat（高於 30 分鐘 task timeout）會被 reaper 轉成 `FAILED/CANCELLED`，safe message 告知 User worker 中斷或逾時，可重新嘗試。terminal state 會使晚到的舊 lease 無法覆寫。
- Admin cancel/force-fail 若使 queue 已無 active request，dispatch fence 要同步釋放。
- 正常 scheduled full reconciliation 仍是 durability/reconciliation fallback，但不能取代 User-visible queue state。

## 10. Security / privacy / cost

- API 只取得既有 `janus-private-pipeline` Job 的 resource-scoped `roles/run.invoker`。
- Cloud Run execution override 不包含 owner UUID、股票代號或交易資料。
- Admin 列表只顯示 truncated owner ref。
- 不新增 GCP resource；沿用既有 dev Job。
- concurrency 硬限制 8，預設 2，避免無界 fan-out。

## 11. Acceptance criteria

必須同時有以下 evidence 才能標示完成：

1. migration 048 成功，active-owner unique index 與 ACL acceptance PASS。
2. Python tests：同 owner 去重、SKIP LOCKED、多 owner worker、cancel/force-fail、serialized write、2–8 validation PASS。
3. Flutter tests：User active 時按鈕 disabled、FAILED 顯示原因並可 retry；Admin 顯示 worker/task、可改 2–8、可中止／回寫失敗。
4. CI / Flutter / Portfolio completeness PASS。
5. `janus-private-pipeline` runtime default taskCount=1、parallelism=8，queue execution 可用 2–8 task override。
6. API revision Ready 且 dev traffic 100%。
7. 真實 owner 手動重算：第二次 request 不建立另一 active request；Private Mart 最終追上 requested ledger version，或若失敗，User status 必須轉 FAILED 並顯示 safe reason。
8. Admin live readback 能看到 execution/task 與 queue state；不得暴露完整 owner identity／symbol relation。

## 12. 2026-10-07 Dev live acceptance evidence

本設計已完成，不再是 pending 規劃。完成證據如下：

- migration 048：Deploy dev run `37556657369`，job `112585424355`，**success**。
- Flutter / Admin UI contract：run `37553539023`，**69/69 PASS**；Portfolio Completeness `37553538956` success。
- API / Private Pipeline：Deploy dev run `37557807555` success；API revision `janus-api-ga4e9660efbe7-config` Ready / 100% traffic；image `sha256:1cfa56a6b4aad5b695f17341820e9542ad4eef4cc2349892d0ff6a221734f507`。
- ingestion acceptance runtime：Deploy dev run `37561186852` success。
- owner queue live canary：workflow `37568678701` success。
  - seed：`janus-ingestion-core-ht6tf`
  - owner queue：`janus-private-pipeline-6ktlc`
  - DB verify：`janus-ingestion-core-hkq7x`
  - `execution_tasks=2`
  - persistent `default_tasks=1`
  - `max_parallelism=8`
  - DB verify 強制檢查：same-owner active unique fence、request `SUCCEEDED`、attempt=1、worker task index ∈ {0,1}、execution match、requested ledger version=current ledger version、queue 無 active request、dispatch inactive。
- live private readback：trade 最新 ledger v164；positions 與 2026 annual PnL 亦為 ledger v164，valuation date `2026-10-06`。
- canary 使用既有 Cloud Run runtimes 與既有資料庫連線路徑，不新增 GCP resource，不擴 IAP 權限；acceptance helper 不輸出 owner UUID／symbol／trade／holding。

Acceptance criteria 1–8 均已有對應 evidence。2026-10-07 使用者已用真實 Admin Google 登入完成 dev Admin「資料治理」UI readback，確認 worker 數量控制（2–8）、queue／worker 狀態與管理操作區塊可見並明確回覆「通過」。因此 authenticated Admin UI gate = **PASS**，本項整體狀態為 **CLOSED**。
