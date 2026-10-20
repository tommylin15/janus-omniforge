# 公開資料保存與刪除治理

更新：2026-10-19。正式契約；資料分類／容量與 Tier 見 [因子矩陣](factor-coverage-retention-ledger.md)，排程、補收與治理邊界見 [統一入口](data-governance.md)。具體 worker 以 `jobs/ingestion-core/ingestion_core/retention.py` 與 `jobs/intelligence-mart/intelligence_mart/retention.py` 為實作證據。

## 1. Current-only Iceberg（2026-10-18 最新且具優先權）

依 [PROJECT_RULES §1.6](../PROJECT_RULES.md) 與 [正式決策](../decision-2026-10-18-current-only-snapshots.md)，**每張 Core／Mart Iceberg 表只保留 current snapshot**。舊的「最近24小時、named branch/tag、歷史模型/研究/報告引用、`CORE_RETENTION_FENCE_URI` 必須齊全才可刪非current snapshot」均已**失效**。不將歷史已刪 snapshot 的 hash 或 id 冒充可重播 PIT 證據。

清理依序保護 current snapshot 實際使用的檔案，對非 current 先 expiration，再選 **年齡≥7天、無 current 引用**的 orphan；仍需既有 writer／mutation lock、catalog metadata pointer、GCS generation、限定 dev bucket/table allowlist、current readback 與實刪 receipt。此決策不授權破壞 current rows、Private Owner 資料或擴大付費資源。

## 2. Row／物件保留政策（與 Snapshot 保留分開）

| 資料 | 保存期／候選 | 保護／驗證 |
|---|---|---|
| Stage 原始 API／quarantine／sidecar／manifest | **2 天（48 小時）** | 僅有未到期 `claimed_until` 的執行與其共用原始資料受保護；只刪 Stage Bucket |
| Core 一般公開市場 rows | 365 天 | 按合法 date/period；不代表所有股票已收滿一年 |
| Core Deep `ohlcv`／`valuation` | 1,096 天 | `watchlist ∪ holdings`，不自動延長全市場 |
| Benchmark rows | 1,096 天 | 指數/市場級資料 |
| 財務 `financials` | 每 symbol／statement／source 最近 12 季 | 同來源版本、period、原始 receipt、null 口徑 |
| Mart 分析 rows | 90 天 | 以 Worker row predicate/最新現役引用判定 |
| Specialist 成果 | 每股最近 3 代完整分析 | 被有效分析引用的共用 hash 不誤刪 |
| OOS/ML artifacts | 保留仍使用結果；無引用、過時逾7天可清 | 固定 dataset/label/schema/hash，另有模型登錄時定義正式保護 |
| Core execution manifest | 90 天及活躍執行操作保護 | 不再因外部歷史研究 fence 延長 Iceberg snapshot |
| 非 current orphan Parquet/Avro/metadata | ≥7天 | generation 刪除＋catalog/current readback |
| 私有 ledger、成本、現金、筆記、交易 | 公開 retention 不適用 | Owner 隔離及私人備份政策獨立 |

`POLICY` 實作常數為 `stage_days=2`、`quarantine_days=2`、`core_days=365`、`deep_price_days=1096`、`financial_quarters=12`、`mart_days=90`、`orphan_days=7`。TTL 是**候選**而非已執行刪除；實際 row count、GCS object/bytes、舊 generation/soft delete 費用需從 live receipt 判斷。資料版本保存與歷史 Iceberg snapshot 同一性不能混淆。

### Stage 執行租約與保留期（2026-10-20）

- **Stage active protection 不再只看 `status`**。PostgreSQL `control.executions` 僅 `status IN ('queued','running','retrying') AND claimed_until > now` 有效租約才保留過期 Stage 物件與其 shared raw；過期或 NULL `claimed_until` 不再因 `running` 狀態永久保留。
- 已到 48 小時的 Stage 原始檔、manifest、quarantine、commit marker 按既有 generation-based cleanup 清理；新近未滿 48 小時的物件仍保留。每天 Stage-only 與每週 Core retention 皆使用此 Stage 專用計算；**Core snapshot／manifest 仍走原 Core 防護**。
- Apply 前重新查有效租約，若集合變動則停止刪除；仍須 Scheduler/worker lease fence、Cloud Run 全頁終態與 GCS before/after generation/bytes 讀回。不存在有效租約不代表可略過這些防護。先前受 stale `running` 阻擋的 4,927 件／96,321,204 bytes 需新版 live dry-run／apply 收據證明實刪，單靠規格修改不得宣稱已清除。

### Stage payload 去重與來源分界（2026-10-20）

- 相同 `source_id + dataset_id + observed_date + content_hash(SHA-256)` 的重複執行改共用 `raw/...` 不可變 payload，以 GCS create-if-absent 實作。每次 execution 各自保留 `executions/<id>/stage/metadata/<key>.json` 與 manifest 的 provenance；不得跨來源／日期／不同內容雜湊盲目合併。
- 已有 `executions/<id>/stage/raw/...` 舊檔按 48 小時原規則清理，**不**大規模搬移或直接按 MD5 刪除。共用 payload 受 active execution manifest 引用保護；Core commit 只清 execution-scoped metadata，raw 由 48h retention 管理。
- 本設計已寫入 GitHub；只有全套 release、worker deploy、實際重複內容的 live reuse 與自然排程收據通過後，才可把節省的 bytes 與整項結案標為 PASS。

## 3. 排程／執行與恢復

Cloud Scheduler → 既有 Controller 是唯一業務定時入口。**Stage-only cleanup 每日 18:30（Asia/Taipei）由既有 `janus-ingestion-core` 執行，`ICEBERG_MAINTENANCE_MODE=stage-only-apply`，48 小時已到期且無 active execution 引用才刪除；此工作不載入 Iceberg catalog，也不修改 Core／Mart／Private。**當 `FINOPS_WEEKLY_MAINTENANCE=true`，**每週六23:30 due**：`iceberg-compaction → mart-cleanup → core-cleanup`，其餘 due 不因此變成週批；實際相依跨小時執行。false 的 legacy daily due 不是核准目標，需讀實際 deployed env/自然 occurrence 驗證。

Mart `MART_OPERATION=retention`、`MART_RETENTION_MODE=dry-run|apply`，Core `ICEBERG_MAINTENANCE_MODE=retention-dry-run|retention-apply`；步驟為 current Core readback → compact → Mart retirement/cleanup → Core row/Stage（再次確保到期）/snapshot expiration/orphan cleanup → 按資料集分列 planned/actual objects、bytes、失敗、active bytes 與 current readback。不可在 source/writer/job 終態未知時盲目重送 apply。操作詳見 [總控 Runbook](../runbook-batch-controller-dev.md)，證據放 [operations](operations-and-testing.md)。

## 4. 已退休說明

2026-10-15～16 的小於1MiB專案限定清理、24h/named snapshot、完整外部研究 fence、每日23:30的版本**只屬歷史 checkpoint**，不再放在現役操作步驟。舊 scope／receipt 查 [FINOPS-AB 卡](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) 及 [D06 卡](../execution-cards/d06-iceberg-retention-io.md)。Stage 2 天期限及每日獨立清理依 2026-10-19 使用者最新明確核准；其他大量刪除、Core/Mart TTL 改動或第二套 Scheduler 仍不在本次範圍。
