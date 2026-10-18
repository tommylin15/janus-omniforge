# FINOPS-AB／FINOPS-C｜Janus CPU、GCS I/O、Iceberg 與 BigQuery AI 工程指令

更新：2026-10-18。狀態：**A＋B 已列最高優先並獲准施作，C 僅列入後置順序、尚未核准直接切換**。本文件是供 AI 執行的契約與檢核程序；**唯一優先次序及完成勾選在 [TODO](../todo.md)**，不是第二份待辦，也不是完成證據。

## 0. 必讀入口／權威與執行邊界

1. 先讀 [AGENTS](../../AGENTS.md) → [PROJECT_RULES](../PROJECT_RULES.md) → [TODO](../todo.md) → 本卡，再按必要範圍讀 [WBS-7](../wbs/wbs-7-security-finops.md)、[WBS-3](../wbs/wbs-3-ingestion-admin.md)、[WBS-5](../wbs/wbs-5-intelligence-mart.md)、[D06 歷史驗收](d06-iceberg-retention-io.md)、[排程 Runbook](../runbook-batch-controller-dev.md) 與 [既有 BQ 混合架構決策](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)。
2. **GitHub main 的現時碼／實際 GCP dev runtime 先於歷史文書。** 2026-10-18 的 source readback：三項維護在 `batch_controller.py` 未指定 weekdays，故預設七天；排程改週批尚未完成，不能以本卡當 deployment evidence。
3. Dev 為真實 parallel-live。所有變更沿既有 main、GHCR digest、受控 Jobs rollout／Scheduler fence／rollback；不另建 Scheduler、第二個 controller、branch/PR 或付費環境。不動 Owner 交易／現金、Private canonical、既有 immutable Core 歷史。
4. 與 DRL-01、ADMIN-V2 並行時先比對 main HEAD、修改檔及部署租約，避免覆蓋他人進度。不得用 CI／deployment 成功取代 live workload、資料與成本驗收。

## 1. 首先完成 A｜低風險節流

**A1｜維護鏈改每週一次**（工作範圍僅 Compaction→Mart Cleanup→Core Cleanup）：

- 在 `jobs/ingestion-core/ingestion_core/batch_controller.py` 將三項維護收斂為**每週六 23:30 Asia/Taipei**的同一邏輯時段，沿用既有 `janus-batch-controller`（Scheduler 繼續每小時 :30 喚醒，無須改每小時喚醒頻率）。
- **不能只加入 `weekdays=(5,)`：**週六通常不是交易日；現有 compaction 依賴當日 `ingestion/14` 的規則會造成卡住。要實作「最近一個已完成、具固定 Core snapshot／資料日的有效市場批次」readiness fence，對來源資料日期、成功 publication 與最新 catalog 指標作可稽核核對；缺證據停在 pending／blocked，不猜測成功、不跳過 PIT。
- 完整保留依賴 `compaction → mart-cleanup → core-cleanup`、worker 排他、週日跨日派送、以前 pending occurrence reconciliation、no duplicate dispatch 與停機復原。確認沒工作要記 `skipped_no_work` 的**已驗證終態**，不能把未知／失敗當成功。
- 若工作週六晚尚未完成，允許同一 occurrence 在後續 hourly tick 延遲派送，不另建立隔天全新 maintenance 事件；不得誤觸第二次執行。不要因週化改變市場日常 ingestion／DRL、Private EOD 的頻率。
- Stage 到期快檢可以保持低成本獨立邏輯，但不應每天喚起全套 Iceberg Scan；`CORE_RETENTION_FENCE_URI` 未完成、失效或缺 external/owner/research/provenance 引用時 **fail closed**，不能啟用刪除，也不能以 no-work 充作刪除驗證。
- 更新 Runbook 的「目標排程」與「live 生效證據」，不得混淆 2026-10-16 已**完全停用**的 `ops.batch_events_v1` 稽核鏡像（原每日／每週討論屬另一件事）。

**A2｜不派送無效工作：**利用 PG control 已核准的 source cursor、dataset/period、有版本的成功 Core snapshot、保留水位與工作 fingerprint 做 `no_change`／`no_work` 決策；先觀察 skip reason，異常未知不可跳過。不要為了判斷是否跳過先做昂貴的全 Core/GCS inventory。

## 2. 接著完成 B｜Ingestion + Iceberg 原地改善

- `jobs/ingestion-core/ingestion_core/data_supplement.py`：`_rows()` 目前只有 symbol 限制（benchmark 更可能無 symbol 篩選），需在**不遺失財報更正版與 PIT 版本**前提下，按需求切出 bounded period/date + selected_fields；把完整 120 日、指定月財報、兩年估值的 coverage 需求分開。缺口查詢只能回報 unknown，不能拿部分樣本假裝完整。對 TWSE/TPEx、ETF/債券 ETF 不可互相混用名冊／缺漏分母。
- `packages/duckdb_query/iceberg.py`：同一 dataset／資料日期的新增與修正先用 key/version 判斷 dirty，再聚合可安全合併的 rows／transaction，降低每股票／每月份 `load_table`、metadata read、`scan().to_arrow()`、append/upsert/overwrite 次數；保留原來源 raw/provenance 與每筆 version 的可追溯性。若 batch 失敗須能重跑冪等、部分來源成功不得包裝全成功。
- `jobs/ingestion-core/ingestion_core/iceberg_maintenance.py`：針對 changed partitions／file-count／metadata evidence 做有界 planner，只有真正碎片化才重寫；不因小分區永遠湊不滿 128MiB 而反覆 compaction。延續 immutable snapshots、research/model/PG/private 引用、7 日 orphan 保護、generation fence 和合法 expiration；健康度檢查不得引發變更。
- 若本輪必須改 schema/migration，先證明最小必要、保留回滾；不能以額外 Iceberg/PG 全量複寫交換所謂 I/O 下降。
- **分別計時** source fetch、Stage、Core reader、DuckDB merge、Core commit、serving projection、maintenance planner/rewrite/readback；清楚標明 `batch`、dataset、日期、execution、snapshot、行數、commits、read/reused count 和耗時，不輸出敏感資料或完整 raw payload。

## 3. A／B 共同驗收，不得省略

1. 先讀真實 dev 四 Jobs digest／Scheduler／歷史執行終態與有效排程：`janus-ingestion-core` 的 ingestion 07:30／14:30、data-supplement 08:30、週維護、`janus-intelligence-mart` / private 必須能獨立歸因。先取得可用 baseline，無 Cloud Monitoring 授權則標 `NOT_VERIFIED`，不能填零或估算為實測。
2. 新增 `tests/test_batch_controller.py` 的週六 23:29／23:30、非週六、交易休市、上週最近成功 EOD fence、跨日 wait/reconcile、pending/failed/ambiguous、不重派送、隔離／週期性；補 `tests/test_iceberg_compaction.py` 及 Data Supplement／DuckDB 最小 dirty/no-op、修訂/版本、snapshot/PIT、orphan/fence 正反測。
3. `main` targeted+適用整體 CI、GHCR digest、Jobs canary／Scheduler fence、發版／rollback readback；真實新 execution 驗收 market coverage、owner-facing prices／EPS 不退步，並核對 legacy PG/data readiness 的相依鏈。
4. 等量日期、同類批次、同一批股票/資料範圍，以 `vCPU-seconds`、GiB-seconds／peak RSS、elapsed、GCS ReadObject/GetObjectMetadata／List/Write、Iceberg manifests/snapshots/小檔數、actual writes、Postgres/serving row parity 作比較。GCS bucket 級量測不可硬指派給單一 worker；可用分段/identity tracing 歸因。
5. 30% CPU／50% metadata-I/O 為**改善目標而非達成事實**。若測不到就 PARTIAL；不可宣告免費額度已被恢復。避免高成本補跑或無需求的全市場歷史重算。

## 4. C｜BigQuery 混合運算：排在 D07／D08 前，但**開工前重評估**

- A＋B 的適用程式/成本/正式 dev 驗收之後，且在 **D07、D08 開工之前**先產生有日期、真實測量、版本與範圍的 **C-preflight 整體重評估報告**並回寫 [混合架構決策](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)、WBS-5/WBS-7 與 TODO。**舊 B0～B8 歷史結案不等於 C 本輪開工或切換已核准。**
- 重評估至少包括：A+B 新 CPU/GCS baseline；Ingestion vs Mart attribution；PyIceberg partition/manifest 熱點；BigQuery on-demand scans/billed bytes、Cloud Run 移除多少計費時間、GCS 是否仍被 backend 訪問、免費額度按同計費帳戶其他產品消耗；來源與 catalog/region/IAM/API/價目/上限；精確 Snapshot mapping、PIT、成本、fallback、回滾；Screening、Ranking、OOS 的逐項 ROI 排序。無測量列 unknown，不得把費用轉移當節省。
- 在重評估簽入 repo 並確認已有合格的現有 BigQuery 資源與合法授權之前，不新增付費 API、dataset、BigLake/Lakehouse catalog、reservation/connection、權限擴張；禁止 BigQuery Storage Read API，暫留 PyIceberg default，不切 production/canonical。
- 只對有明確效益的 workload 做 C code/test/canary：全市場 screening/ranking 先行，之後 aggregate/OOS，留 PG serving、Private/Owner、Core canonical 不遷移。每項需同 Core immutable snapshot/dataset、null/coverage/結果 hash、query limit、billed bytes、rollback／fallback evidence；未過 gate 不得以 C 的計畫阻止既有使用者資料服務。
- 若 C 重評估指出 BigQuery 不划算、缺費用授權或 snapshot fidelity 未能證明，寫入 `DEFERRED/BLOCKED` 的明確決議，再依使用者核准的次序安排 D07/D08；不得私自跳過 C-preflight 或宣稱已完成切流。

## 5. AI 交接／完成格式

每次交接明列：`work_package(A1/A2/B1/B2/B3/C-preflight/C-cutover)`、Git SHA/main HEAD、修改路徑與安全評估、targeted/CI run URL、runtime Job execution ID + digest、Scheduler/occurrence、資料期間/股票數/成敗、CPU/RAM/GCS/BQ before-after 方法及值、snapshot/PIT/provenance parity、rollback evidence、`PASS/PARTIAL/BLOCKED/UNKNOWN`、剩餘阻塞。**只有文件儲存，僅可標 `DOC_UPDATED`，不是工程完工。**

本文件不修改既有 D06 已驗證的歷史收據、不重開 D01～D05、不重造第二套 DRL、研究資料或平行任務清單。
