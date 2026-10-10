# Janus Current Status

更新：2026-10-10（Asia/Taipei）
證據優先：GitHub `main`、GitHub Actions／live runtime；已完成記錄放 archive，active acceptance 見 [TODO](todo.md)。

## 下一步：恢復 B 組（B7 → B8 → B9）

- **B0～B6：CLOSED／PASS**。完整過往驗收入口見 [TODO B 組摘要](todo.md) 與對應 `archive/group-b-*`；不重跑已通過 reader、500 screening、Deep Coverage／cache、ML/OOS Parquet path。
- **B7 月度執行機制：PASS；derived cache freshness：PARTIAL**（immutable readback 已 PASS；derived cache 仍 historical）。[GHCR 與 Scheduler live #38025890942](https://github.com/tommylin15/janus-omniforge/actions/runs/38025890942) 已驗現役核准 SHA `038498c70e12488f345c3ca0fbe821846ddee4cc` 的 controller／ingestion／Mart digest 一致、唯一 `janus-ingestion-daily` 為 `ENABLED`／`30 * * * *`／`Asia/Taipei`。舊 10/08 request 未派送、不重播；新的 `b7-ghcr-monthly-20261010-v1` 在 [Actions #38026093638](https://github.com/tommylin15/janus-omniforge/actions/runs/38026093638) controller `janus-batch-controller-ct8mh` PASS 後已 disabled。Mart `janus-intelligence-mart-xrlk5` 於 2026-10-10 05:17:38 UTC **Completed=True／succeededCount=1／12m30s**；[獨立 GCS readback #38027085666](https://github.com/tommylin15/janus-omniforge/actions/runs/38027085666) OOS 與 monthly reconciliation immutable SHA-256 PASS，500 screening、25 specialist、25 active refs（6 reused）、`missed_invalidation_detected=false`、0 LLM／no CEO／no promotion。**B7 月度執行機制不再重跑；derived cache freshness 仍 PARTIAL**：reconciliation `status=partial`，B6 ML/OOS cache 的舊 Core snapshot `sha256:1eb49a2d...` 與本次 `sha256:687fae3e...` source fence `unmatched`、`status=historical`；需在不覆寫既有 B5/B6 immutable artifacts 下，透過既有月度 derived-cache refresh／readback 收斂最新 Core，不能把 `partial` 當 `pass`。詳細操作見 [controller runbook](runbook-batch-controller-dev.md)。
- **B8：ACTIVE／PARTIAL（screening + ML/OOS 同源實測已 PASS，fallback/cutover gate 未結案）**。使用者授權 IAM 後，[fixed catalog #38030454991 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38030454991) **PASS**。[500 screening #38029803051 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051) **PASS**：500 members、三表一致、PyIceberg cold/warm 25.30／23.54 秒，BQ hybrid 31.32／34.13 秒（40 MiB billed，BQ 在 screening 較慢）。[B8 ML/OOS equal-run #38033560821](https://github.com/tommylin15/janus-omniforge/actions/runs/38033560821) **PASS**：同 Core、同 B5 SQL window/label/stride，31 tests、兩輪 10,978 rows／0 changed／0 missing，PyIceberg local Parquet cold/warm 10.65／9.98 秒，BQ native GCS Parquet 8.38／8.74 秒、合計 40 MiB billed、輸出 1,067,915 bytes、runner RSS high-water 485 MiB；輸出 sink 與取樣限制仍使性能切換結論 **inconclusive**，actual GCS source read bytes unknown。此為同輪 fidelity/FinOps/效能觀測驗收，不是 BigQuery 故障 fallback PASS、B7 新 Core freshness 或 B9 品質驗收。**PyIceberg 保持 default、無 cutover、無模型重訓**。見 [B8 checkpoint](archive/group-b-b8-partial-checkpoint-2026-10-10.md)。
- **B9：排在 B8 後**。B8／B9 銜接只刷新與當次 Core 來源相符的 derived cache，不重跑 B7 模型重訓；模型品質 evidence 必須符合當次 Core source fence、PIT 與 source authorization。五 specialist 的 Taiwan PIT/OOS、模型品質、持久化與完整 runtime acceptance。C 組必須等 B 組結案；本次不提前啟動。
- **GHCR CI/CD：PASS（目前核准的 dev 發布範圍）**。四 Jobs 8/8 canary 與 API 新→舊→新 traffic rollback 的真實證據見 [2026-10-10 CI/CD 結案](archive/cicd-ghcr-api-promotion-2026-10-10.md)。四項額外／歷史檢查由使用者 [豁免](parking-lot.md)，不列待辦、不冒充技術實測 PASS，亦不重開舊 AR/GCS 清理。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：見上方 B7 → B8 → B9 active 入口，不從 CI/CD 已結案項目重新開工。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
