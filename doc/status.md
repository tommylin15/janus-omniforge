# Janus Current Status

更新：2026-10-10（Asia/Taipei；依真實 GitHub Actions／Cloud Run 驗收及使用者縮減驗收範圍）

權威證據：[新版 GHCR Jobs／API 發布驗收](archive/cicd-ghcr-api-promotion-2026-10-10.md)；實作以 GitHub `main` 與現役 runtime 為準。

## 新版 CI/CD：PASS（目前 dev 發布範圍結案）

- **完整發布／服務鏈 PASS**：來源 `038498c70e12488f345c3ca0fbe821846ddee4cc` 全套 Release [#37953986962](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962)、公開 GHCR、0% 候選、固定 Preview、OAuth/MCP 負向驗證及同 SHA 使用者 A→B→A／PnL 人工確認均已完成；真人確認標示 `USER_ATTESTED`，不冒充機器重演。
- **四 Jobs rollout PASS**：[ #38012746734](https://github.com/tommylin15/janus-omniforge/actions/runs/38012746734) 的 `phase=PASS`、8/8 真實 canary、rollback baseline 可用。
- **API 正式 100% 切流與回滾 PASS**：[ #38020693214](https://github.com/tommylin15/janus-omniforge/actions/runs/38020693214) 的 `phase=PASS`、`rollback_rehearsal=PASS`；新→舊→新 100%，最終新版 `janus-api-00457-wed`，健康／build SHA／401／路由／其他 tags 讀回 PASS。
- **2026-10-10 使用者縮減驗收範圍**：四項加強／歷史復原檢查均改 `WAIVED_BY_OWNER`，不再列為目前 dev CI/CD 結案門檻或 active TODO：① Jobs 舊映像真實 rollback drill；② 固定 Preview 故障後真實恢復 drill；③ Private Pipeline 舊設定 parity；④ Research Job 舊 AR image 恢復。**這是範圍核准而非四項測試 PASS**；實際證據仍為 `NOT_VERIFIED`／`BLOCKED`，不修改既有安全閘門及 release recovery code。決策見 [Parking Lot](parking-lot.md)。
- 舊 AR／GCS／Revision 清理不在本次範圍；未修改實際資料、交易、Secret 或其他服務。現役其他工作依 [TODO](todo.md)。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：B0～B6 CLOSED；B7 每月第一個週六 10:30 Asia/Taipei retrain／calibration／OOS／cache reconciliation **ACTIVE／待實際 Scheduler/runtime readback**；B8 的 PyIceberg vs BigQuery workload fidelity／FinOps／fallback、B9 五 specialist OOS/模型品質驗收待完成。PyIceberg 仍為 default，未以單次 canary 自動切 BigQuery。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
