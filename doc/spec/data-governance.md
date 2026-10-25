# Janus 資料治理、批次與補資料總入口

> **2026-10-24 新統一流程**：[批次／收取／報告／私人快照／備份](unified-batch-flow.md) 是唯一現行時段表。舊排程已由本次程式重構取代；部署狀態 NOT VERIFIED。GitHub 不再執行日常業務批次。

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-23（Asia/Taipei）。此頁是正式**治理與執行路由**，不另建 TODO、Scheduler 或資料庫；現行 implementation 以 GitHub `main` 和 runtime 為準，狀態以 [TODO](../todo.md)、[status](../status.md) 與 [operations](operations-and-testing.md) 為準。

## 1. 資料責任與文件唯一入口

| 範圍 | 權威 |
|---|---|
| 治理、安全、來源授權 | [PROJECT_RULES §1.6–1.7](../PROJECT_RULES.md) |
| Market／Deep／Private 母體、TWSE ≤10%／TPEx ≤30% 缺失率 | [全市場契約](full-market-batch-policy.md) |
| Dataset、容量預算、Tier 和 row TTL | [因子／保存矩陣](factor-coverage-retention-ledger.md)、[現役 Core policy](../../jobs/ingestion-core/ingestion_core/retention.py) |
| Stage／Core／Mart、Iceberg current-only、清理安全 | [Retention 契約](retention-governance.md)、[2026-10-18 決策](../decision-2026-10-18-current-only-snapshots.md) |
| 定時 due、依賴、互斥、調度 | [Controller 程式](../../jobs/ingestion-core/ingestion_core/batch_controller.py) 與 [總控 Runbook](../runbook-batch-controller-dev.md) |
| 來源、即時／每日／週六／歷史補收 | [補資料 Runbook](../runbook-data-supplement.md)、[來源資料契約](storage-data-and-ingestion.md) |
| 研究模型、PIT、OOS 與成果 | [Colab／Drive 研究唯一契約](research-collection-gas-drive-colab.md)、[Specialist SPEC](specialist-engines.md)、[D07 執行卡](../execution-cards/d07-specialist-b9-oos.md) |

Canonical Core 與 research/derived 資料分離；缺值不補零、不猜當時公開日期、不以最新版本冒充歷史 first-observed。Stage→Core→serving 皆保留 source_id、取得時間、URL/receipt、hash、期別、單位與 provenance。已核准的 Yahoo／FinMind 等第三方來源可以**直接**補收，不必先耗盡官方；不得偽裝成 MOPS／TWSE 官方認證。Owner 交易、成本、現金不進 public research cohort。

## 2. 現役保存政策與歷史研究

**Row 保留與 Iceberg snapshot 是不同層次。** Core 一般市場 row 365 天；Deep `ohlcv`／`valuation`、benchmark 1,096 天；財報每公司/statement/source 最新 12 季；Stage/quarantine **2 天（48 小時）**；Mart 分析 row 90 天；每檔 Specialist 最近 3 代；OOS/ML 依現役成果引用與過期規則。這些是政策，不保證真實每股皆已收滿年數。Private Ledger/持股/筆記不套用公開 TTL。

2026-10-18 後 Core／Mart Iceberg 表**只保留 current snapshot**；取消舊 named refs、最近24h與研究／publication 外部引用作為舊 snapshot 保留 gate。非 current 過期、超過7天且無 current 引用的 orphan，仍須按 lock、catalog pointer、GCS generation、allowlist、readback 安全刪除。**已刪歷史 snapshot 不保證能重播**；保存舊 `snapshot_id` 文字不會重新建立歷史資料。重跑研究應另保留合法、有界的 versioned Parquet、feature/label/cohort/date range/schema/hash、授權/provenance。

## 3. Cloud Scheduler、Batch、Job：唯一節奏

排程表與備份保留政策只維護在 [統一批次契約](unified-batch-flow.md)；Controller每兩小時檢查到期工作，GitHub業務cron已從程式移除，live切換仍待其他AI執行。
日常市場收取／分析、私人更新與備份維護沿既有Worker；Stage48h與週Iceberg清理仍各自保留安全護欄。
本文件不再複製時段或保存舊備份cron，歷史收據查Operations及Git歷史。

## 4. 資料補充：兩條路徑、同一來源治理

1. **Daily／歷史定向修補**：`data_supplement.py` 的 `daily`、`backfill`、`valuation-history`、`fundamental-history` 與 `quality` 走既有 ingestion Job。daily 按缺期／新申報／已變更資料增量取得；quality 例行檢查已取消，不盲抓五年全市場。現有官方 TWSE/MOPS 程式的適用限制不等於第三方 demand 的限制。
2. **新增持股／關注股需求補收**：`stock_supplement.py` 使用 migration 066 的去識別化 symbol request、generation、lease；不阻塞使用者交易／關注。API 後背景 `demand` 使用原 ingestion Job，統一 ingestion 再作增量兜底。價量至少120有效交易日、營收13個應到月、合法單季 EPS 近期12個已發布季度、估值兩年；ETF 不適用資訊須明示。採現役來源授權、去重／失敗重試、Stage→Core→serving→API 逐項讀回，不把成功一支 Job 稱為全項 ready。
3. **Data Readiness Ledger**：`daily` 嘗試寫入定期 Ledger，但自然執行、watermark、週詳細品質收據與 Admin 設定讀回另需驗收；成功 ingestion ≠ 成功 Ledger publication。來源未發布、限流、缺期、新上市維持 partial/not_applicable；未知終態先讀 Job execution 再處理。

完整模式、手動修補限制、source URL/期別/單位與安全重試詳見 [runbook](../runbook-data-supplement.md)；不得以此頁新增第二個 Scheduler、付費資源、額外補抓範圍或寫入 Owner ledger。

## 5. 獨立模型研究資料與生命週期

[Colab/Drive唯一研究契約](research-collection-gas-drive-colab.md)：官方TWSE/TPEx→人工Colab→私有Drive每月資料夾→Colab模型。GAS/ZIP路線已退役；歷史普通股母體、來源權利、研究70%與正式模型PIT/OOS分別驗證。
[模型生命週期](model-lifecycle.md)是新模型業務candidate/回饋保存與日週月批次的**待實作目標**。不把歷史第3節09:00 Mart視為新批次；SEQ-04目標為02:30收取→平日04:30 screening→06:30私人更新，實際切流與驗收仍以統一批次SPEC及Runtime為準；取消的例行週月模型稽核／重訓不復活。
新模型/feedback prefix須分類保護，避免舊Mart90日/三代/7日清理誤刪；新回饋熱讀365日/精簡歷史36月詳見生命週期，**不改既有Stage/Core/Private TTL，也不授權本輪執行刪除**。

## 6. 舊模型研究排程已退役

specialist-retrain、B5～B8 GCP/BQ研究中轉依[2026-10-20實機收據](../archive/d07-gcp-bq-retirement-live-2026-10-20.md)保持CLOSED。月評估由既有Controller/Mart作輕量scoring，Colab人工重訓；不復活雲端fit工作。正式行情/Owner/API/Stage/週Iceberg/備份保留。

## 7. 驗收與工作佇列

**本文件僅統一規範，不自行授權**新的 retention apply、Cron 變更、BigQuery 切流或 D07 開工。執行權／範圍依 [TODO](../todo.md)，已退休 FINOPS-C 模型資料前置路徑不再構成 D07-PRE 必經條件；新研究採集及正式模型發布各自保留必要安全與品質門檻。完成需分別讀回 GitHub code、tests、CI、live Job image、Scheduler/occurrence、資料 rows、source provenance、清除 objects/bytes 及 API/owner boundary；沒有證據維持 UNKNOWN/PARTIAL/NOT_VERIFIED。

