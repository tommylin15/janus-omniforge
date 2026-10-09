# Janus Current Status

更新：2026-10-09 22:26（Asia/Taipei）

權威順序：GitHub `main` implementation → tests／CI → GCP live runtime → [驗收證據](archive/cicd-ghcr-live-route-finalization-2026-10-09.md) → 本短入口。歷史完整狀態已原文保存於 [archive](archive/cicd-status-pre-forward-repair-2026-10-09.md)，不應以舊快照覆蓋最新判定。

## 新版 GitHub Actions → GHCR → Cloud Run：PARTIAL（本次 forward-only 修復 PASS）

- **Release source**：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361` 的 [完整測試／四 GHCR 公開 digest #37876247130](https://github.com/tommylin15/janus-omniforge/actions/runs/37876247130) PASS。後續 `main` 的 workflow／診斷／文件 commits 並非已重新 build/publish 的容器來源。
- **Jobs**：[forward-only recovery #37915584159](https://github.com/tommylin15/janus-omniforge/actions/runs/37915584159) PASS，四個既有 Job 使用 pinned GHCR image、8 個不同 execution canary PASS，Scheduler `janus-ingestion-daily` 已恢復 `ENABLED`；Research Job 未更新。唯獨 Private Pipeline 原始完整設定一致性 **NOT_VERIFIED**。
- **API**：`janus-api-00451-cuw` 已服務 100% GHCR 正式流量；Google A → B → A 真實 owner 隔離驗收已由較早的同來源候選完成。舊 AR rollback rehearsal 未執行，使用者針對本次允許 forward-only；此項不當作 rollback PASS。
- **Service Ready 與鎖**：在 [route repair #37943709614](https://github.com/tommylin15/janus-omniforge/actions/runs/37943709614) 以原始 owner lease 受控重申同一個 GHCR 100% Revision，Service `Ready`／`RoutesReady` 從 `False / ContainerImageImportFailed` 轉為 `True`，Revision Ready、template GHCR digest、build SHA、health、未授權邊界及 Jobs/Scheduler readback 均核對；未建立新 Revision／變更其他 tags。收據 `PASS_SAME_REVISION_ROUTE_RECONCILED`、`lease_released=true`，獨立 GitHub lease ref 讀取 404。沒有 AR/GCS 清理或資料庫異動。
- **尚未完成完整 Release gate**：本次一次性復原 PASS 不能替代未來可重跑的正式 pipeline failure/rollback 語意；Private Pipeline 舊完整設定 parity 仍未知。參見 [CI/CD active TODO](todo.md) 及 [詳細 evidence](archive/cicd-ghcr-live-route-finalization-2026-10-09.md)。
- **固定 preview**：`https://preview---janus-api-2oo7qbkd5q-uc.a.run.app/app/` 的發布/OAuth 契約已在 [部署 runbook](runbook-dev-deploy.md) 與 [OAuth runbook](runbook-user-oauth-dev.md) 回寫；固定 preview 自動更新／失敗恢復的完整 live gate 尚未驗證，不可因目前存在 `preview` tag 即稱自動化已完成。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：B0～B6 CLOSED；B7 每月第一個週六 10:30 Asia/Taipei retrain／calibration／OOS／cache reconciliation **ACTIVE／待實際 Scheduler/runtime readback**；B8 的 PyIceberg vs BigQuery workload fidelity／FinOps／fallback、B9 五 specialist OOS/模型品質驗收待完成。PyIceberg 仍為 default，未以單次 canary 自動切 BigQuery。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
