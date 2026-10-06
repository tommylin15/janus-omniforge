# A 組 live-auto acceptance checkpoint — 2026-10-06

判定：**自動／read-only live acceptance 可執行部分已完成；A 組整體仍為 `partial`，只剩 interactive live gates。**

## PASS

### PWA / unauthenticated security
- Inspect dev runtime run `37407568046` SUCCESS。
- canonical Cloud Run build-id：`3e29701ffae1dfe3aa9d32deb50ded03f8145c18`。
- User PWA：`id=/app/`, `start_url=/app/`, `scope=/app/`。
- Admin PWA：`id=/app/admin`, `start_url=/app/admin`, `scope=/app/`。
- unauthenticated `/api/v1/me/profile` = 401；`/api/v1/admin/data-governance` = 401。

### Current-owner canonical read consistency
- Janus Dev Read-only v2：trades newest ledger version = 24。
- positions = ledger version 24 / valuation date 2026-10-05。
- 2026 annual-pnl = ledger version 24 / valuation date 2026-10-05。
- performance = ledger version 24 / valuation date 2026-10-05。
- 因此先前 Private Mart stale readback 已解除；這是 read-side PASS，不是 write-mutation E2E。

### Effective batch trigger / Private Pipeline
- Run `37407726176` SUCCESS。
- `janus-batch-controller`：`BATCH_CONTROLLER_MODE=active`，activation boundary `2026-10-02T04:05:00Z`。
- `janus-ingestion-daily` bounded logs 持續每小時 :30 呼叫 batch controller，近期 finish HTTP 200。
- current Private batch contract：weekday 21:30 Asia/Taipei；dependency `ingestion`。
- `janus-private-pipeline-n45c6`：2026-10-05 21:33（Asia/Taipei）建立、21:36 完成、succeeded。
- old direct `janus-private-pipeline-2130` bounded logs 最後 activity = 2026-10-01；cutover 後未再觀察 direct invocation。
- stale apply entrypoint 已以 `db570130` hard-stop retired；`0df2e728` run `37408320316` targeted ingestion 137 passed，部署與 migration 全 skipped。

### Retention / cleanup
- Run `37407331976` SUCCESS。
- Stage deleted 110 objects / 32,275,833 live bytes。
- Core active bytes reduced 5,928,635。
- Mart active bytes reduced 5,932,252；specialist artifacts deleted 68。
- `billable_bytes_reclaimed` = null，維持 unknown。
- bucket-level lifecycle/retention fields currently empty；cleanup source of truth 是 application retention jobs/reference fences，不把空欄位描述成 lifecycle configured。

## 不能由本對話自動替代的最後 gates

1. Android 安裝 User/Admin 後分別從 icon 重開。
2. authenticated User/Admin 的 Today／Watchlist／Ledger／Stock Detail 約 390px 實機 visual acceptance，以及 Admin live UI readback。
3. 使用真實 owner 新增／建立更正交易後，觀察 immediate operational positions、pending、下一輪 Private Mart refresh、Holdings/Records/Reports/YTD 一致性。因 dev 是個人真實 parallel-live，本對話不自行製造假交易。
4. 真實手機 warm core p95 ≤2s、visited restore ≤300ms。

Owner isolation 有既有 2026-09-24 Owner A/B acceptance 與持續 API tests；本輪 Janus connector schema 不接受 owner override，因此沒有冒充成新的 arbitrary-owner live request。
