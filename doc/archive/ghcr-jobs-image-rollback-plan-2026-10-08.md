# GHCR → Cloud Run Jobs：映像切換／回滾 dry-run（2026-10-08）

**狀態：PARTIAL / BLOCKED。沒有暫停 Scheduler、修改 Cloud Run Job、執行工作、更新 Service 100% 流量或清理舊資產。**

## 已實作

- `scripts/gcp/ghcr_job_cutover_plan.py` 使用經驗證的 source SHA、GHCR immutable digests、5 個現役 Job 的原始 pinned image metadata，輸出固定順序的 **image-only 四項更新計畫**及反向 rollback order。
- private-pipeline → intelligence-mart → ingestion-core → batch-controller 為規劃順序；batch-controller 與 ingestion-core 使用相同 GHCR ingestion image，但 Job 現有 command、env、secret refs、service identity 都不允許在 image-only cutover 時改動。若無法證實設定與上版一致，仍必須 fail closed。
- `janus-research-big-move-500` **不在更新名單**，原始 AR digest 保留，不能假設存在 GHCR research image。
- `automatic_apply=false`、`resource_writes=0`；`BLOCKED` 也允許輸出診斷計畫，但不可能自動成為部署指令。
- `tests/test_ghcr_job_cutover_plan.py` 加上既有 guard／retired scheduler tests，[Actions #37778770806](https://github.com/tommylin15/janus-omniforge/actions/runs/37778770806) **28 passed**。
- 同一 Actions live readback 實際驗證 **四個 pinned image mapping 可組成**；live release gate 依設計 **exit 78 / BLOCKED**，sanitized artifact 保留 `report.json`、`plan.json`。五個 blockers：
  1. `scheduler_still_enabled`。
  2. `execution_janus-private-pipeline_unfenced`（9 筆歷史未啟動、無完成終態，runner count 0；不可冒稱完成）。
  3. `durable_deployment_mutex_unverified`。
  4. `authenticated_acceptance_unverified`。
  5. `rollback_procedure_unverified`。

## Scheduler 操作角色與實際權限

GCP 已有自訂角色 `projects/gen-lang-client-0593591102/roles/janusWebSchedulerOperator`，包含 `cloudscheduler.jobs.get`、`cloudscheduler.jobs.pause`、`cloudscheduler.jobs.enable`、`cloudscheduler.jobs.update`，不含 `jobs.create`／`jobs.delete`／`jobs.run`。**角色存在≠已綁定 `janus-ci`**，需要綁定後實測並 readback；不需另外建立角色或授予 Admin。

只有 Scheduler `PAUSED` 且所有 worker／controller execution 具明確可驗證終態時，才能考慮進入 image-only 切換。切換時必須有外部發布來源的互斥、完整 rollback baseline、step-by-step readback，以及 runner 中斷時可從獨立控制端恢復 Scheduler 的 procedure。現有 GitHub workflow 的 concurrency **不是**跨舊 Cloud Build／runtime 的完整 durable lock。

## MCP 授權驗收界線

透過已連接的 `Janus Dev Read-only v2` MCP，在本會話對 source metadata、owner `positions`（response status `partial`）、`annual-pnl` 與 `performance`（response status `available`）完成實際只讀取查詢，沒有在 GitHub/log 保存任何個人金額／明細。這能佐證**既有外掛目標的 owner MCP 讀取**，**無法證明新 GHCR 0% tag revision 的同一 OAuth client、refresh-token、owner isolation 與數字 canonical parity**。因此候選版 authenticated acceptance 仍是 BLOCKED，不因已連接外掛而強制切流量。

參考：[前階段安全 gate](ghcr-jobs-safety-gate-2026-10-08.md)、[CI/CD 正式契約](../spec/cicd-v2.md)。
