# Janus Current Status

更新：2026-10-10（Asia/Taipei）
證據優先：GitHub `main`、GitHub Actions／live runtime；已完成記錄放 archive，active acceptance 見 [TODO](todo.md)。

## 下一步：B9 五 Specialist／OOS 模型品質（B7／B8 均已結案）

- **B0～B6：CLOSED／PASS**。完整過往驗收入口見 [TODO B 組摘要](todo.md) 與對應 `archive/group-b-*`；不重跑已通過 reader、500 screening、Deep Coverage／cache、ML/OOS Parquet path。
- **B7 月度執行機制與 derived-cache freshness：CLOSED／PASS（本次最新 Core）**。月度 retrain/OOS 原執行、25 specialist refs、immutable artifact readback 已由 [#38027085666](https://github.com/tommylin15/janus-omniforge/actions/runs/38027085666) 驗收，不再重跑。先前 B6 的 historical source fence 已透過獨立 PyIceberg current-source refresh 收斂：[#38056677635](https://github.com/tommylin15/janus-omniforge/actions/runs/38056677635) **34 targeted tests PASS，Core `sha256:687fae3e…`、11,432 ML/OOS rows、new reconciliation `pass/current/exact-core`，新 manifest／GCS create-only receipt bytes readback PASS**。原先月度 `partial` 保留原始歷史、不覆寫；本次 `retrained=false`、無 CEO／BQ／promotion。完整證據見 [B7 freshness 結案](archive/group-b-b7-derived-cache-freshness-closure-2026-10-10.md)。
- **B8：CLOSED／PASS（已核准的 dev 固定 Core 同源效能／FinOps／backend 選路／有界故障回退）**。Screening/日常 Specialist **PyIceberg 預設**；ML/OOS 只有明確 opt-in 才用 BigQuery，無 cutover。500 screening [#38029803051 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051) 36 targeted tests、同源 parity PASS（BQ 此輪較慢）；ML/OOS equal-run [#38033560821](https://github.com/tommylin15/janus-omniforge/actions/runs/38033560821) 10,978 rows／0 differences、兩輪 BQ billed 40 MiB、兩條路徑 sink 不同故優劣 inconclusive。[B8 B5 最終整合／GCS live #38037557795](https://github.com/tommylin15/janus-omniforge/actions/runs/38037557795) **SUCCESS：44 tests**，B5 正式 CLI PyIceberg 預設＋BQ 明確 opt-in、BQ 運作故障安全 fallback、BQ export 已啟動後禁止競寫；真實 74,999 Core source → 10,978 ML/OOS 與 immutable Parquet 零差，並以新版 B5 CLI 真實驗證 10,978 rows B6 cache hit（無新的 BQ jobs）。故障為受控注入，非實際 BQ outage；**未部署新 Mart image**，因既有 Job 只執行 PyIceberg Specialist／ML/OOS Parquet consumer，非此 B5 standalone 產製 CLI；不宣稱 fresh-Core cache-miss live materialization。B7 新 Core derived-cache freshness 仍 PARTIAL、B9 quality NOT VERIFIED；不重訓、不改 canonical。詳見 [B8 結案](archive/group-b-b8-closure-2026-10-10.md)。
- **B9：下一個 ACTIVE 工作（模型品質仍 NOT VERIFIED）**。B7／B8 已結案，不重跑舊 Core 或月度 retrain。以最新符合 Core source fence／PIT／source authorization 的 derived data 驗收五 specialist 的 Taiwan PIT/OOS、calibration、champion/quality、structured artifact、持久化與 dev runtime；不得以 B7 cache PASS 替代模型品質通過。C 組待 B 組結案後才啟動。
- **GHCR CI/CD：PASS（目前核准的 dev 發布範圍）**。四 Jobs 8/8 canary 與 API 新→舊→新 traffic rollback 的真實證據見 [2026-10-10 CI/CD 結案](archive/cicd-ghcr-api-promotion-2026-10-10.md)。四項額外／歷史檢查由使用者 [豁免](parking-lot.md)，不列待辦、不冒充技術實測 PASS，亦不重開舊 AR/GCS 清理。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](todo.md)。
- **B 組**：B7 月度機制／freshness 與 B8 均已結案，唯一下一工程入口為 B9 模型品質；不重做 B7／B8。
- **C 組**：B 組結案後再啟動 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](todo.md) 為準；未排程構想見 [parking-lot.md](parking-lot.md)。
