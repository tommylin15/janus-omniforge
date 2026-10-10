# Janus Current Status

更新：2026-10-10（Asia/Taipei）
證據優先：GitHub `main`、GitHub Actions／live runtime；已完成記錄放 archive，active acceptance 見 [TODO](todo.md)。

## 下一步：恢復 B 組（B7 → B8 → B9）

- **B0～B6：CLOSED／PASS**。完整過往驗收入口見 [TODO B 組摘要](todo.md#b-組下一個執行入口b7--b8--b9) 與對應 `archive/group-b-*`；不重跑已通過 reader、500 screening、Deep Coverage／cache、ML/OOS Parquet path。
- **B7：ACTIVE／NOT VERIFIED（下一個實作與驗收目標）**。已有 monthly readback workflow，但不能據其存在認定 monthly Scheduler/controller gate、真實 retrain execution 與 artifact readback PASS。先核對 `main`、最新 CI、Scheduler／controller effective cadence（每月第一個週六 10:30 Asia/Taipei）、Job／cache／OOS artifacts，再補必要缺口。不要以文件或 code schedule 當 runtime evidence。
- **B8：排在 B7 後**。對等 PyIceberg vs BigQuery real workload fidelity／performance／FinOps／fallback 驗收；**目前 PyIceberg 仍是 default**，不因 B2／B3 單輪 canary 直接切 BigQuery。
- **B9：排在 B8 後**。五 specialist 的 Taiwan PIT/OOS、模型品質、持久化與完整 runtime acceptance。C 組必須等 B 組結案；本次不提前啟動。
- **GHCR CI/CD：PASS（目前核准的 dev 發布範圍）**。四 Jobs 8/8 canary 與 API 新→舊→新 traffic rollback 的真實證據見 [2026-10-10 CI/CD 結案](archive/cicd-ghcr-api-promotion-2026-10-10.md)。四項額外／歷史檢查由使用者 [豁免](parking-lot.md)，不列待辦、不冒充技術實測 PASS，亦不重開舊 AR/GCS 清理。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：見上方 B7 → B8 → B9 active 入口，不從 CI/CD 已結案項目重新開工。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
