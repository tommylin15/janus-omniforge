# Janus 架構決策 — Iceberg canonical + BigQuery analytics hybrid

日期：2026-10-06  
狀態：**架構已核准；B0～B6 的實作／live gate 已完成，B7～B9 仍待驗收**（進度以 [TODO](todo.md) 為準）。目前 PyIceberg 為 default，尚未取得 B8 cutover evidence。

## 1. 決策

Janus 保留目前 **Apache Iceberg V2 + GCS** 作為 public Core 的 canonical／PIT／provenance／history 資料層，不把 BigQuery native tables 改成新的 canonical warehouse，也不因導入 BigQuery 重做 A 組已成立的 PostgreSQL serving projection。

BigQuery 的定位限定為 **analytics compute layer**，優先承接 B 組的：

- liquid-500 market screening／cross-sectional ranking；
- specialist feature aggregation／window／join；
- OOS／benchmark／evaluation 的大型 SQL 前處理；
- ML training dataset preparation。

正常 User／Admin API hot path 仍由 PostgreSQL serving projection／既有 bounded backend contract 提供；BigQuery 不直接成為 Flutter page-load database。

## 2. 目標架構

```text
Provider / Stage
      ↓
Core Iceberg V2 on GCS  ← canonical / PIT / provenance
      │
      ├── PostgreSQL serving projection → User/Admin API → Flutter
      │
      └── BigQuery analytics compute
              ↓
          bounded features / screening / evaluation
              ↓
          specialist runtime
              ↓
          immutable Mart / model / evaluation artifacts
```

BigQuery 是 compute，不擁有 canonical number、publication authority 或 owner-private truth。任何衍生結果仍必須可追溯至固定 Core snapshot／manifest、analysis_as_of、provenance 與 source authorization。

## 2.1 B 組執行節奏與資料角色

B 組只保留一套 active cadence，避免把「日常 inference」與「模型重訓」混在一起：

1. **每日盤後 Market Coverage**：每個交易日 EOD canonical data ready 後，對 liquid-500 做一次低成本 screening／cross-sectional ranking。BigQuery 在通過 exact-snapshot fidelity gate 後優先承接；若 input identity 未變則 reuse。這不是 500×5 深度 specialist。
2. **Deep Coverage 增量更新**：完整五 specialist 僅處理 `active watchlist ∪ effective holdings`。新 EOD price、月營收／財報或 event 到達時，只 invalidate 受影響 symbol／specialist；無變化不重算。
3. **每月重型批次**：`specialist-retrain`、calibration、OOS/evaluation 與 cache/dependency reconciliation 固定 **每月第一個週六 10:30（Asia/Taipei）** 執行，並在必要 ingestion／data-supplement 成功後才進入模型工作。Event classifier 仍只在有足夠新 labeled data 或 drift 時 retrain。
4. **沒有另一套週六全量模型**：不建立「每週六 500 檔跑五模型」排程。歷史 runtime evidence 保留於 operations；B 組 implementation 必須把實際 Scheduler／controller 收斂到本節的每月第一個週六 10:30，並做 runtime readback。
5. **資料保存角色**：Iceberg/GCS 保存 canonical／PIT／provenance／history；BigQuery intermediate／destination table 預設 bounded、TTL、可重建；大型 training/evaluation input 以 versioned GCS Parquet 保存；specialist/model/evaluation 成果依 Mart retention 保存。BigQuery 中間結果不需為了「留一份」再寫回 canonical Iceberg。

## 3. 硬性 guardrails

1. **禁止 BigQuery Storage Read API。** 不新增 `bigquery.readsessions.*` 作為 B 組執行需求，不加入 `google-cloud-bigquery-storage` 依賴。小型 query result 使用一般 BigQuery query/result API；大量 ML 輸入使用 BigQuery SQL 先縮減，再以 versioned export artifact 交給 training Job。
2. **Iceberg canonical 不變。** 不因 BigQuery 導入刪除、覆寫或降級現有 Iceberg snapshot／metadata／provenance contract。
3. **不預設複製整套 Core 到 BigQuery native storage。** 允許 bounded／TTL／可重建的 analytics destination table 或 export artifact，但它不是 canonical source；永久保存只限 PIT／training／evaluation／publication 所需且有 retention contract 的成果。
4. **PostgreSQL serving 不變。** A 組已建立的 stock serving projection、Ledger／private serving、API contract 與 Flutter 不因本架構調整改成 BigQuery request-time query。
5. **exact-snapshot fidelity 是 cutover gate。** 目前 `main` 使用 PostgreSQL-backed PyIceberg `SqlCatalog`。BigQuery 讀路徑在成為 default 前，必須用真實 dev 證明同一 execution 所讀資料對應指定 immutable Core snapshot；若無法可靠證明，該 workload 繼續使用既有 PyIceberg reader。
6. **不把 legacy mutable metadata pointer 當正式解法。** Google 已不建議大多數新 workload 使用以單一 Iceberg metadata JSON URI 維護的 legacy external table；若 compatibility spike 暫用，必須 pin immutable metadata location／snapshot 並明示只作 bounded transition evidence。
7. **優先評估 Google-supported shared Iceberg catalog path，但不得自行遷移 catalog。** Lakehouse runtime catalog／Iceberg REST catalog 可列為相容性候選；建立 catalog、啟用 BigLake／BigQuery API、增加 IAM 或產生新計費資源仍受 PROJECT_RULES 的人工授權 gate 約束。
8. **成本與掃描 fail closed。** Query 必須盡量使用 date／symbol／partition predicate、selected columns、bounded cohort；可用時先做 dry-run／bytes estimate／maximum-bytes guard。未知成本不得補 0。
9. **research／canonical 分離。** BigQuery intermediate／feature／benchmark data 預設為 research/derived；只有既有 publication gate 明確接納的成果才可進正式 serving／publication。
10. **可回退。** BigQuery adapter 未通過 fidelity／cost／performance／failure acceptance 時，PyIceberg path 保持可用，不以 BigQuery failure 破壞 ingestion、A 組 serving 或 canonical writes。

## 4. B 組優先執行順序

### B0 — baseline 與邊界

先以目前 `load_core_datasets()`／`specialist_runtime` 取得固定 snapshot 的 baseline：elapsed、peak RSS、GCS read/scan evidence（可得時）、row count、artifact hash、screening/evaluation output。不得先改 schema 或重跑已完成 A 組 migration。

### B1 — 抽出 analytics reader

建立小型 data-access abstraction，例如 `AnalyticsSnapshotReader`：

- `IcebergSnapshotReader`：包住既有 PyIceberg exact-snapshot 行為，先成為 reference implementation；
- `BigQueryAnalyticsReader`：後續 adapter，未通過 acceptance 前不得成為唯一 reader。

Specialist engine 只接收有明確 snapshot identity 的 bounded dataset／feature result，不直接依賴 BigQuery client object。

### B2 — BigQuery compatibility spike

只用既有 dev 真實 Core table 做 bounded probe，確認：

- region／bucket／dataset／catalog 相容性；
- 指定 snapshot／metadata fence 的可證明 mapping；
- schema evolution、null、date/timestamp、decimal、partition 行為；
- query bytes、latency、GCS/backend I/O evidence；
- 不使用 Storage Read API。

若需要啟用 API、建立 BigLake/Lakehouse catalog、dataset、connection 或新增 IAM，而當下沒有明確授權，停止該 mutation，保留 code/test 可繼續部分並回報 blocker。

### B3 — 先遷移最適合的 analytics workload

優先順序：

1. 每日盤後 liquid-500 screening；
2. cross-sectional ranking／window／aggregate features；
3. OOS／evaluation 前處理；
4. 只有證據支持時才擴到更多 specialist feature reads。

不要先把單一股票 request-time read、Ledger、private owner data 或整套 Core full copy 搬到 BigQuery。

### B4 — ML training data path

大型 training input 禁止走 Storage Read API。採：

```text
Core Iceberg → BigQuery SQL reduction
             → bounded destination result（必要時）
             → EXPORT DATA / versioned GCS Parquet
             → LightGBM / CatBoost / Qlib / statsmodels Job
```

Export artifact 必須保存 snapshot identity、schema/version、analysis_as_of、hash／provenance 與 retention；temporary destination table 預設 TTL／可重建。

### B5 — canary、fallback 與 selective cutover

同一固定 Core snapshot 對 PyIceberg 與 BigQuery path 做 deterministic compare。只有 output contract、PIT/fidelity、missing/null semantics、成本與效能都達標的 workload 才切 BigQuery default；其餘保留 Iceberg reader。

### B6 — FinOps／營運 evidence

至少記錄：

- BigQuery processed/billed bytes、slot/query elapsed（可得時）；
- Cloud Run elapsed／peak RSS；
- GCS read／operation evidence（可取得時）；
- exported bytes／artifact growth；
- cache/reuse rate；
- BigQuery failure/fallback 次數。

不得因 BigQuery 導入就宣稱 Cloud Storage 空間會下降；Core Iceberg 空間預期維持。可優化的是 Cloud Run 搬運、重複中間 artifact 與未受控 scan。

## 5. Acceptance

B 組 BigQuery architecture 至少需證明：

- 同一固定 Core snapshot 的代表性 screening／feature／evaluation 結果與 reference PyIceberg path 等價，差異有明確允許範圍；
- BigQuery path 不需要 `bigquery.readsessions.create/getData/update`，runtime／依賴中沒有 Storage Read API；
- canonical Iceberg snapshot／provenance／PIT／source authorization 不被 BigQuery intermediate 覆寫；
- PostgreSQL serving／User API／Admin API 不因 BigQuery 失效而中斷；
- 無未授權的 full-Core BigQuery duplicate warehouse；
- 大型 ML data 走 export artifact，不把整個 warehouse 拉進 pandas；
- 至少有一個 liquid-500 或 cross-sectional workload 在真實 dev 完成 before/after elapsed、peak RSS、processed bytes／scan evidence；
- BigQuery adapter 失敗可安全 fallback 到 PyIceberg，且 fallback 可 audit；
- 每日盤後 500 screening 與 Deep Coverage dirty-update 語意都有真實 dev evidence，且未發生 500×5 全量深算；
- `specialist-retrain`／calibration／OOS evaluation／reconciliation 的 effective schedule 已在實際 Scheduler／controller 收斂為每月第一個週六 10:30（Asia/Taipei）並 readback；
- tests、CI、dev deployment/runtime evidence 齊全後才可把對應 TODO 勾選完成。

## 6. 人工授權邊界

本文件代表**架構方向與 B 組實作優先序已核准**，不代表使用者已授權：

- 啟用新的付費 BigQuery／BigLake API；
- 建立新的付費 dataset／reservation／catalog／connection／cache；
- 擴大 IAM；
- 將既有 PostgreSQL Iceberg catalog 遷移到另一個 catalog；
- 大量搬移或刪除真實 canonical data。

AI 可以先完成 code abstraction、tests、dry-run 設計、成本估算與不產生新付費資源的 probe；遇到上述 gate 必須依 PROJECT_RULES 處理。

## 7. 官方參考

- BigQuery Query Apache Iceberg external tables: https://cloud.google.com/bigquery/docs/query-iceberg-data
- BigQuery Iceberg external tables: https://cloud.google.com/bigquery/docs/iceberg-external-tables
- BigQuery Storage Read API: https://cloud.google.com/bigquery/docs/reference/storage
- Lakehouse runtime catalog / Iceberg REST catalog: https://cloud.google.com/lakehouse/docs/set-up-lakehouse-iceberg-rest-catalog
- Register existing Iceberg table: https://cloud.google.com/lakehouse/docs/register-table
