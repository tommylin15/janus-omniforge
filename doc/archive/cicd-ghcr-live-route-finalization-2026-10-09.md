# Janus 新版 GHCR 發布收尾證據 — 2026-10-09（Asia/Taipei）

狀態：**forward-only live route repair PASS；整體 CI/CD PARTIAL**。

## 版本與有效範圍

- Source full release SHA：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361`；[完整 GHCR Release #37876247130](https://github.com/tommylin15/janus-omniforge/actions/runs/37876247130) SUCCESS，包含當次完整 Python／Flutter／四映像 anonymous pull／digest gates。後續 `main` operational script／文件 commits **沒有重新產生此版容器**，不得稱為最新 `main` 已全部部署。
- 0% 候選與 owner 真實 Google A → B → A、PnL／私人 API bounded 隔離已有 [當次 owner acceptance](cicd-owner-browser-acceptance-2026-10-09.md)；本輪不重做真人 OAuth。
- [Jobs forward recovery #37915584159](https://github.com/tommylin15/janus-omniforge/actions/runs/37915584159) SUCCESS：四個既有 Jobs 的 GHCR image readback、八個不同 execution canary PASS、唯一 Scheduler `janus-ingestion-daily` 已恢復 `ENABLED`。Research Job 維持原狀；`original_private_full_config_verified=false`、`private_job_config_parity=NOT_VERIFIED`、舊 AR image rollback **未演練**（依使用者本次 forward-only 明確豁免）。
- [Live inventory #37936885425](https://github.com/tommylin15/janus-omniforge/actions/runs/37936885425)：正式 Cloud Run API 路由 `janus-api-00451-cuw` 100%，`mcp-oauth`／`mcp-adapter`／`preview` 等 tags 有讀回；不等於固定 preview 的日常發布自動化已完成。

## Service routing 修復

- 原正式 promotion [#37936648808](https://github.com/tommylin15/janus-omniforge/actions/runs/37936648808) 與 finalization [#37937768802](https://github.com/tommylin15/janus-omniforge/actions/runs/37937768802) 均 FAIL／exit 78，且舊 revision rollback 不可驗。診斷 [#37942375130](https://github.com/tommylin15/janus-omniforge/actions/runs/37942375130) 及 [#37942992033](https://github.com/tommylin15/janus-omniforge/actions/runs/37942992033) 證明：**Service** `Ready=False`／`RoutesReady=False`，reason `ContainerImageImportFailed`；但現役 GHCR **Revision Ready=True**、Service template 已是正確 GHCR digest、generation reconciled，latestCreated/latestReady 均為此候選。原 owner lease 因 gate 不過而保留，未強制釋放。
- 專用 guarded single-use [same-revision repair #37943709614](https://github.com/tommylin15/janus-omniforge/actions/runs/37943709614) **SUCCESS**：檢查原始 owner lease、完整 Jobs proof、Scheduler／execution、immutable revision digest、正式健康／build SHA／401／MCP metadata；只重新宣告 **同一現役 `janus-api-00451-cuw=100`**，沒有改映像、部署新 revision、改其它 traffic tags 或重跑 Jobs。更新前後 readback：`Ready=False → True`、`RoutesReady=False → True`、`ConfigurationsReady=True` 不變，generation reconciled，原 template 仍 GHCR。
- 修復收據 `phase=PASS_SAME_REVISION_ROUTE_RECONCILED`、`lease_released=true`；後續獨立 GitHub `refs/tags/janus-ghcr-deploy-global-v1` 查詢 404（租約 ref 不存在）。本輪沒有 AR/GCS 清理、DB/backup/owner ledger 異動。
- [Selective CI #37943491894](https://github.com/tommylin15/janus-omniforge/actions/runs/37943491894) SUCCESS；單次 routing repair PASS 是這個受控工作包的 evidence，**不能自動替代未來每次 Release 的完整 gate／回滾 rehearsal**。

## 尚未宣稱完成

1. `janus-private-pipeline` 舊版完整 config parity 尚無可驗證基準，狀態維持 **NOT_VERIFIED**；不得由 GHCR digest／八次 canary 反推完整 config 相同。
2. 舊 AR revision／Job image 回滾未驗，已接受本次 forward-only 例外；**不要寫成已通過回滾演練**。
3. 固定 preview `preview` tag 的「候選全 SHA 驗證 → 單 tag 更新 → 固定 URL readback → 失敗恢復」發布自動化目前只有 [runbook](../runbook-dev-deploy.md) 契約，尚無完整 workflow/live acceptance。
4. 新版 CI/CD 已有這次受控真實發布與復原證據，但 generic repeatable release/rollback 並非由這個一次性 repair workflow 證明，整體仍 **PARTIAL**。

歷史工作紀錄：見 [舊 status 完整快照](cicd-status-pre-forward-repair-2026-10-09.md) 與 [舊 TODO 快照](cicd-todo-prior-checkpoints-2026-10-09.md)。
