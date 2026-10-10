# Janus Current Status

更新：2026-10-10（Asia/Taipei；GitHub Actions 真實 dev receipt）

權威：GitHub `main` + CI／live runtime evidence，完整最新記錄見 [四 Jobs／API 100% 切流與回滾](archive/cicd-ghcr-api-promotion-2026-10-10.md)。歷史舊版 checkpoint 已歸檔，不代表目前活躍狀態。

## 新版 API 正式切流與真實 traffic rollback：PASS；CI/CD 整體 PARTIAL

- 來源 `038498c70e12488f345c3ca0fbe821846ddee4cc` 的完整 GHCR 發布 [#37953986962](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962)、0% candidate、固定 Preview、OAuth/MCP 負向關卡及相同 SHA 真人 A→B→A／PnL `USER_ATTESTED` 已驗收。人工證據不冒充機器雙帳號重演。
- **新版四 Jobs**：[rollout #38012746734](https://github.com/tommylin15/janus-omniforge/actions/runs/38012746734) receipt `phase=PASS`，四目標各兩次不同 execution，8/8 live canary；`rollback_mode=reversible_ghcr`、前一版 digest／config baseline verified、rollback available。**Jobs 舊映像實際 rollback 尚未演練**（`old_image_rollback_exercised=false`）。
- **新版 API**：[promotion #38020693214](https://github.com/tommylin15/janus-omniforge/actions/runs/38020693214) receipt `phase=PASS`、`rollback_rehearsal=PASS`；舊 `janus-api-00451-cuw` → 新 `janus-api-00457-wed` 100% → 舊版 100% → 新版 100%。最終新來源 SHA／健康／401／Ready／RoutesReady／generation／其他 tags／非 traffic config 讀回通過，固定 Preview 與 MCP 標籤未異動。
- 未完成且**不影響上述 API traffic PASS 語意**：Jobs 真實舊 image rollback、固定 Preview 更新後故障的真實恢復演練；歷史 Private Pipeline 完整設定 parity `NOT_VERIFIED`，受保護 Research Job 舊 AR image 可恢復性 `BLOCKED`。雙 owner MCP credential 端到端沒有重新執行。
- 依使用者範圍，舊 AR／GCS／Revision 清理不是本次結案條件；不碰資料庫、交易、Secret 或未核准資產。完整 active 待辦只看 [TODO](todo.md)。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：B0～B6 CLOSED；B7 每月第一個週六 10:30 Asia/Taipei retrain／calibration／OOS／cache reconciliation **ACTIVE／待實際 Scheduler/runtime readback**；B8 的 PyIceberg vs BigQuery workload fidelity／FinOps／fallback、B9 五 specialist OOS/模型品質驗收待完成。PyIceberg 仍為 default，未以單次 canary 自動切 BigQuery。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
