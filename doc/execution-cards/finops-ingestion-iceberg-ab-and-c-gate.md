# FINOPS-AB／FINOPS-C｜Janus CPU、GCS I/O、Iceberg 與 BigQuery AI 工程指令

> **2026-10-18 最新使用者覆蓋決策：每表只保留目前snapshot，其餘可清理。** 取消歷史研究／模型／報告／publication、24小時與named refs保護；本卡以下舊reference fence／PG欄位／external清冊要求不再阻擋歷史snapshot清理。保留current資料、7日檔齡、generation、writer／catalog fence與真實實刪讀回；舊歷史無法重播已接受，未來保留機制另訂。詳見 [正式決策](../decision-2026-10-18-current-only-snapshots.md)／[PROJECT_RULES §1.6](../PROJECT_RULES.md)。

更新：2026-10-18。狀態：**A＋B 與 D06 剩餘受引用保護工作合併為唯一 FinOps P0，已獲准施作；C 後置，未核准直接切換**。原 D06 兩天／長時間 I/O 量測已由使用者取消（CANCELLED_BY_USER），不實測、不作驗收硬 gate。本文件是供 AI 執行的契約與檢核程序；**唯一優先次序及完成勾選在 [TODO](../todo.md)**，不是第二份待辦，也不是完成證據。

## 0. 必讀入口／權威與執行邊界

1. 先讀 [AGENTS](../../AGENTS.md) → [PROJECT_RULES](../PROJECT_RULES.md) → [TODO](../todo.md) → 本卡，再按必要範圍讀 [WBS-7](../wbs/wbs-7-security-finops.md)、[WBS-3](../wbs/wbs-3-ingestion-admin.md)、[WBS-5](../wbs/wbs-5-intelligence-mart.md)、[D06 歷史驗收](d06-iceberg-retention-io.md)、[排程 Runbook](../runbook-batch-controller-dev.md) 與 [既有 BQ 混合架構決策](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)。
2. **GitHub main 的現時碼／實際 GCP dev runtime 先於歷史文書。** 2026-10-18 的 source readback：三項維護在 `batch_controller.py` 未指定 weekdays，故預設七天；排程改週批尚未完成，不能以本卡當 deployment evidence。
3. **工項去重：**D06 歷史 477 objects orphan 清理、audit mirror 停用、62/71/96/495 JSON 掃描已有成功證據，不重跑。剩餘 Retention fence、PG/ML/Private/Research/external 保護集、受引用 Snapshot/Orphan/manifest 清理與讀回併入本卡 A/B 唯一施工與驗收；原 D06 卡只作歷史索引。DRL-01 與 ADMIN-V2 由其他 AI 負責，本工項不得修改其專屬業務程式、資料或競爭 live rollout。
4. Dev 為真實 parallel-live。所有變更沿既有 main、GHCR digest、受控 Jobs rollout／Scheduler fence／rollback；不另建 Scheduler、第二個 controller、branch/PR 或付費環境。不動 Owner 交易／現金、Private canonical、既有 immutable Core 歷史。
5. 與 DRL-01、ADMIN-V2 並行時先比對 main HEAD、修改檔及部署租約，避免覆蓋他人進度。不得用 CI／deployment 成功取代 live workload、資料與成本驗收。

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

### B4／D06 剩餘整合（不再有 D06 獨立工作線）

- D06-R1：建立／使用**當次完整、有效、可稽核的** Core retention fence。驗證 PostgreSQL active/publication（包含 `core_snapshot_id` 權限）、Mart Specialist／ML-OOS、Research／Private、external reference、metadata、source/generation。每次 apply 前重新查核，一小時有效期；來源不齊、缺讀權、時間過期、資料不一致 → **fail closed／audit-only**，不能拿既有部分掃描結果當完整刪除授權。
- D06-R2：週維護鏈統一執行有界 dry-run／apply、Snapshot expiration、七日以上受保護 orphan／generation 清理、execution manifest retirement；先核對 rollback/rebuild／不可逆大量刪除授權。分別記錄候選、保護集、真正刪除、objects/bytes 與已發布 Core/PG/Mart/Private readback。無安全刪除條件可安全跳過，不能為降低小檔數盲目刪真實資料。
- 同一 worker、同一 snapshot、同一清理保護條件只跑一次。過去 D06 477 objects 清理與 audit mirror 停用沿用證據，不因併單重跑或把歷史節省重計。

## 3. A／B 共同驗收，不得省略

1. 先讀真實 dev 四 Jobs digest／Scheduler／歷史執行終態與有效排程：`janus-ingestion-core` 的 ingestion 07:30／14:30、data-supplement 08:30、週維護、`janus-intelligence-mart` / private 必須能獨立歸因。先取得可用 baseline，無 Cloud Monitoring 授權則標 `NOT_VERIFIED`，不能填零或估算為實測。
2. 新增 `tests/test_batch_controller.py` 的週六 23:29／23:30、非週六、交易休市、上週最近成功 EOD fence、跨日 wait/reconcile、pending/failed/ambiguous、不重派送、隔離／週期性；補 `tests/test_iceberg_compaction.py` 及 Data Supplement／DuckDB 最小 dirty/no-op、修訂/版本、snapshot/PIT、orphan/fence 正反測。
3. `main` targeted+適用整體 CI、GHCR digest、Jobs canary／Scheduler fence、發版／rollback readback；真實新 execution 驗收 market coverage、owner-facing prices／EPS 不退步，並核對 legacy PG/data readiness 的相依鏈。
4. **只做短窗／有界同類工作 sample（不做兩天或長期量測），**可取得時以 `vCPU-seconds`、GiB-seconds／peak RSS、elapsed、GCS ReadObject/GetObjectMetadata／List/Write、Iceberg manifests/snapshots/小檔數、actual writes、Postgres/serving row parity 作比較。GCS bucket 級量測不可硬指派給單一 worker；可用分段/identity tracing 歸因。**D06 原兩天／長時間等量 I/O 比較已取消，不可重啟或據此認定不結案；不足的成本節省數值標 UNKNOWN。**
5. D06 引用保護與安全清理結果納入同一受控 Jobs rollout／rollback／真實 readback，不再獨立發行 D06 部署。30% CPU／50% metadata-I/O 為**改善目標而非達成事實**。若測不到就 PARTIAL；不可宣告免費額度已被恢復。避免高成本補跑或無需求的全市場歷史重算。

## 4. D07-PRE｜資料可用性／Colab／FINOPS-C 整合前置評估（唯一工單）

- **原 FINOPS-C preflight 現與 [Colab／資料覆蓋評估](../colab-d07-modeling-feasibility-2026-10-19.md) 併入同一個 D07-PRE**：先核對24月 rolling 真實資料、各角色合法特徵／label maturity／市場歷史母體與缺口補收策略；再依 A+B 實測比較現有 PyIceberg／Cloud Run、BQ opt-in 與免費 Colab CPU，按運算器同資料 hash 評估成本、安全、PIT、一致性與回退。完成一份有日期、SHA、來源證據的 go/no-go/defer 決策並回寫 [架構決策](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)、WBS-5／WBS-7、[TODO](../todo.md)；原 C-preflight 不另設第二工單。B5–B8 的歷史 PASS 及此份研究草稿不等於 D07-PRE PASS。
- 重評估至少包括：A+B 新 CPU/GCS baseline；Ingestion vs Mart attribution；PyIceberg partition/manifest 熱點；BigQuery on-demand scans/billed bytes、Cloud Run 移除多少計費時間、GCS 是否仍被 backend 訪問、免費額度按同計費帳戶其他產品消耗；來源與 catalog/region/IAM/API/價目/上限；精確 Snapshot mapping、PIT、成本、fallback、回滾；Screening、Ranking、OOS 的逐項 ROI 排序。無測量列 unknown，不得把費用轉移當節省。
- 在重評估簽入 repo 並確認已有合格的現有 BigQuery 資源與合法授權之前，不新增付費 API、dataset、BigLake/Lakehouse catalog、reservation/connection、權限擴張；禁止 BigQuery Storage Read API，暫留 PyIceberg default，不切 production/canonical。
- 只對有明確效益的 workload 做 C code/test/canary：全市場 screening/ranking 先行，之後 aggregate/OOS，留 PG serving、Private/Owner、Core canonical 不遷移。每項需同 Core immutable snapshot/dataset、null/coverage/結果 hash、query limit、billed bytes、rollback／fallback evidence；未過 gate 不得以 C 的計畫阻止既有使用者資料服務。
- **結案不要求強制 BigQuery cutover**：若結果不划算或欠費用授權，正式 `DEFER C` 並依合法、成熟資料與成本/安全的共同驗收進入 D07；若各運算器無可靠成本或 PIT/來源證據，D07-PRE 仍維持 `PARTIAL/BLOCKED`。只有實測收益及授權充足才做選定 BQ workload 的 optional C-canary；免費 Colab 只供離線研究，既有月度 controller 是唯一正式排程。

## 5. AI 交接／完成格式

每次交接明列：`work_package(A1/A2/B1/B2/B3/D07-PRE/conditional-C-cutover)`、Git SHA/main HEAD、修改路徑與安全評估、targeted/CI run URL、runtime Job execution ID + digest、Scheduler/occurrence、資料期間/股票數/成敗、CPU/RAM/GCS/BQ before-after 方法及值、snapshot/PIT/provenance parity、rollback evidence、`PASS/PARTIAL/BLOCKED/UNKNOWN`、剩餘阻塞。**只有文件儲存，僅可標 `DOC_UPDATED`，不是工程完工。**

本文件不修改既有 D06 已驗證的歷史收據、不重開 D01～D05、不重造第二套 DRL、研究資料或平行任務清單。
