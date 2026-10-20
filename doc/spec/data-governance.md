# Janus 資料治理、批次與補資料總入口

更新：2026-10-19（Asia/Taipei）。此頁是正式**治理與執行路由**，不另建 TODO、Scheduler 或資料庫；現行 implementation 以 GitHub `main` 和 runtime 為準，狀態以 [TODO](../todo.md)、[status](../status.md) 與 [operations](operations-and-testing.md) 為準。

## 1. 資料責任與文件唯一入口

| 範圍 | 權威 |
|---|---|
| 治理、安全、來源授權 | [PROJECT_RULES §1.6–1.7](../PROJECT_RULES.md) |
| Market／Deep／Private 母體、TWSE ≤10%／TPEx ≤30% 缺失率 | [全市場契約](full-market-batch-policy.md) |
| Dataset、容量預算、Tier 和 row TTL | [因子／保存矩陣](factor-coverage-retention-ledger.md)、[現役 Core policy](../../jobs/ingestion-core/ingestion_core/retention.py) |
| Stage／Core／Mart、Iceberg current-only、清理安全 | [Retention 契約](retention-governance.md)、[2026-10-18 決策](../decision-2026-10-18-current-only-snapshots.md) |
| 定時 due、依賴、互斥、調度 | [Controller 程式](../../jobs/ingestion-core/ingestion_core/batch_controller.py) 與 [總控 Runbook](../runbook-batch-controller-dev.md) |
| 來源、即時／每日／週六／歷史補收 | [補資料 Runbook](../runbook-data-supplement.md)、[來源資料契約](storage-data-and-ingestion.md) |
| 月度模型、PIT、OOS、研究成果 | [Specialist SPEC](specialist-engines.md)、[D07 執行卡](../execution-cards/d07-specialist-b9-oos.md) |

Canonical Core 與 research/derived 資料分離；缺值不補零、不猜當時公開日期、不以最新版本冒充歷史 first-observed。Stage→Core→serving 皆保留 source_id、取得時間、URL/receipt、hash、期別、單位與 provenance。已核准的 Yahoo／FinMind 等第三方來源可以**直接**補收，不必先耗盡官方；不得偽裝成 MOPS／TWSE 官方認證。Owner 交易、成本、現金不進 public research cohort。

## 2. 現役保存政策與歷史研究

**Row 保留與 Iceberg snapshot 是不同層次。** Core 一般市場 row 365 天；Deep `ohlcv`／`valuation`、benchmark 1,096 天；財報每公司/statement/source 最新 12 季；Stage/quarantine **2 天（48 小時）**；Mart 分析 row 90 天；每檔 Specialist 最近 3 代；OOS/ML 依現役成果引用與過期規則。這些是政策，不保證真實每股皆已收滿年數。Private Ledger/持股/筆記不套用公開 TTL。

2026-10-18 後 Core／Mart Iceberg 表**只保留 current snapshot**；取消舊 named refs、最近24h與研究／publication 外部引用作為舊 snapshot 保留 gate。非 current 過期、超過7天且無 current 引用的 orphan，仍須按 lock、catalog pointer、GCS generation、allowlist、readback 安全刪除。**已刪歷史 snapshot 不保證能重播**；保存舊 `snapshot_id` 文字不會重新建立歷史資料。重跑研究應另保留合法、有界的 versioned Parquet、feature/label/cohort/date range/schema/hash、授權/provenance。

## 3. Cloud Scheduler、Batch、Job：一套正式節奏

唯一業務定時入口：Cloud Scheduler 目標 `janus-batch-controller:run`；既有 cron `30 * * * *`、`Asia/Taipei`。下表列 **due slot**，不承諾實際啟動與完成時間；controller lock/occurrence/依賴/ambiguous state 是派送權威，GitHub Actions 不新增業務 schedule（備份清理例外）。

| 批次／Worker | due（台北） | 主要條件 |
|---|---|---|
| `ledger-backup`／controller | 每日 02:30 | 備份本體與 GitHub 清理分開 |
| `ingestion`／ingestion-core | 每日 07:30、14:30 | 上午收集；下午行情／指數；交易日有效性由 worker 檢查 |
| `data-supplement`／ingestion-core | 每日 08:30 | 依 07:30 ingestion，日增量／缺漏補收 |
| `mart`／intelligence-mart | 平日 09:00 | 依 ingestion＋supplement；下一個 :30 tick 才可能派送 |
| `market-screening`／intelligence-mart | 平日 16:30 | EOD ready、同日來源與排他鎖 |
| `private`／private-pipeline | 平日 15:30、21:30 | 前者依 ingestion；後者為獨立 fallback slot |
| `mobile-ledger`／private-pipeline | 每小時 :30 | 只有 pending 才執行 |
| `data-quality`／ingestion-core | 每週六 12:30 | 獨立品質檢核，不是全量多年補抓 |
| `stage-cleanup`／ingestion-core | **每日 18:30** | 只處理超過48小時且不被 active execution 使用的 Stage 物件；不啟動 Iceberg | 
| `iceberg-compaction → mart-cleanup → core-cleanup` | **每週六 23:30** | `FINOPS_WEEKLY_MAINTENANCE=true` 才週維護；依序且可能跨小時 |

`effective_batches()` 有 legacy `FINOPS_WEEKLY_MAINTENANCE=false` 的每日 23:30 分支，**不是**目前核准的週維護目標。2026-10-18 文件收據記錄週維護切換成功，但本次未做新一輪 Scheduler/env/自然 occurrence live 讀回。不要引用 [2026-10-13 歷史盤點](../archive/batch-inventory-2026-10-13.md) 當作目前 cron。

## 4. 資料補充：兩條路徑、同一來源治理

1. **Daily／歷史定向修補**：`data_supplement.py` 的 `daily`、`backfill`、`valuation-history`、`fundamental-history` 與 `quality` 走既有 ingestion Job。daily 按缺期／新申報／已變更資料增量取得；quality 週六檢查，不盲抓五年全市場。現有官方 TWSE/MOPS 程式的適用限制不等於第三方 demand 的限制。
2. **新增持股／關注股需求補收**：`stock_supplement.py` 使用 migration 066 的去識別化 symbol request、generation、lease；不阻塞使用者交易／關注。API 後背景 `demand` 使用原 ingestion Job，08:30 `daily` 再作兜底。價量至少120有效交易日、營收13個應到月、合法單季 EPS 近期12個已發布季度、估值兩年；ETF 不適用資訊須明示。採現役來源授權、去重／失敗重試、Stage→Core→serving→API 逐項讀回，不把成功一支 Job 稱為全項 ready。
3. **Data Readiness Ledger**：`daily` 嘗試寫入定期 Ledger，但自然執行、watermark、週詳細品質收據與 Admin 設定讀回另需驗收；成功 ingestion ≠ 成功 Ledger publication。來源未發布、限流、缺期、新上市維持 partial/not_applicable；未知終態先讀 Job execution 再處理。

完整模式、手動修補限制、source URL/期別/單位與安全重試詳見 [runbook](../runbook-data-supplement.md)；不得以此頁新增第二個 Scheduler、付費資源、額外補抓範圍或寫入 Owner ledger。

## 5. 獨立模型研究資料，不再由正式 Core 綁定

2026-10-20 新 [GAS／Drive／Colab 唯一研究契約](research-collection-gas-drive-colab.md) 取代舊 Core→BQ／PyIceberg→Colab 的研究採集必經鏈。GAS 對第三方合格 API 依配額分批抓取，私有 Drive `資料源/YYYY-MM.zip` 作月檔，Colab 直接讀取訓練；上市／上櫃普通股，不納入 ETF；各市場×dataset 研究覆蓋最低 70%。第一輪只核對既有持股／觀察股的公開欄位可得性，時間資料保留標籤，資料採集不以歷史完整 PIT 稽核擋關。正式模型 OOS/promotion 仍驗證時間順序與 future leakage。

## 6. 舊模型研究排程與正式服務切開

原 `specialist-retrain` 月度 Controller 派送、手動派送 Workflow，以及 B5～B8 舊雲端 ML/OOS 研究中轉不再構成 D07 必要流程。已確定不用且不被正式服務引用的舊 Job/BQ 立即停用或移除，**不等待 GAS 或 Colab 上線**；live Cloud Run、BQ 的真正刪除需查驗資源／依賴與讀回。正式市場 EOD Ingestion／Screening、個股／持股／Owner、API、Stage 48h、週 Iceberg 清理、備份保留現有契約；研究 GAS 分批 trigger 是獨立平台，不另建正式 Janus Cloud Scheduler Controller。

## 7. 驗收與工作佇列

**本文件僅統一規範，不自行授權**新的 retention apply、Cron 變更、BigQuery 切流或 D07 開工。執行權／範圍依 [TODO](../todo.md)，已退休 FINOPS-C 模型資料前置路徑不再構成 D07-PRE 必經條件；新研究採集及正式模型發布各自保留必要安全與品質門檻。完成需分別讀回 GitHub code、tests、CI、live Job image、Scheduler/occurrence、資料 rows、source provenance、清除 objects/bytes 及 API/owner boundary；沒有證據維持 UNKNOWN/PARTIAL/NOT_VERIFIED。
