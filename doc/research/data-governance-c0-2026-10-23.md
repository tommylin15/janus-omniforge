# C0 清掃前證據盤點｜2026-10-23

> **性質：研究／治理證據快照，非 production canonical data。** 本報告僅基於已取得的 GitHub main 程式與 Drive 規劃。**Live PG、Iceberg catalog、GCS 與 Scheduler 尚無可用唯讀驗證回傳，所有實存量/資料量/使用量保持 UNKNOWN。** 不可用本報告直接執行 DROP、DELETE 或停排程。

## 0. 狀態與證據邊界

- **C0 靜態審查：PARTIAL；C0 完整 Live 刪前證據：BLOCKED/UNKNOWN；C1 可直接實刪：0 項獲核准。**
- 本輪 GitHub main 起始 HEAD：`9eb25fdccd5e33fdee6fd9e7a90a9013828993d9`（2026-10-23 10:35:06 UTC）；以下靜態結論依此版本讀得之檔案。此為起始比對點，後續文件 commit 不代表 runtime 部署。
- Drive 規劃：[Janus_Data_Governance_Plan_20261023.md](https://drive.google.com/file/d/1TjHit4zEI9j99JSiaYT4WhxZYLdSH24b/view)；已讀，內含原 17 sheets 與 Sheet 11–14 的整理、Q01–Q10 修訂版，但它本身已標明未跑 Live。
- 原 `Janus_Data_Governance_Audit_2026-10-23.xlsx`：本輪 Drive 與可用檔案搜尋未找到原始活頁簿，**Sheet 11–14 原格值未逐格驗算**；目前以治理方案對該四表的引述為替代，標記 `DOCUMENT_SECONDARY`，待原檔可讀後複核。
- `Janus_Dev_Read_only_v2.janus_sources` 本輪回傳內部錯誤；未取得來源清單，更無 catalog/PG SQL 讀權；GCP 現有連線並未提供通用 Cloud SQL／Iceberg／GCS inventory 查詢。不可把「工具失敗」寫成「環境為空」。
- 權威：[`doc/PROJECT_RULES.md`](../PROJECT_RULES.md)；尤其 §1.8 的 dev Stage 48h、§1.6 current-only Iceberg，以及 §1.12 Risk promotion 嚴格 gate。Risk promotion 不在本次治理範圍，亦不得把先前 ACTIVE 歷史狀態當目前 ACTIVE。

**狀態標籤**：`CODE_CONFIRMED`（程式／migration 定義）、`DESIGN_DOCUMENTED`（Drive 計畫）、`LIVE_CONFIRMED`（需真實 catalog/SQL/GCS/Scheduler 回傳）、`UNKNOWN`（未取得證據）、`RETIRE_CANDIDATE`（僅候選）。

## 1. Core Iceberg 程式定義清冊（均 CODE_CONFIRMED、Live UNKNOWN）

定義：[`packages/duckdb_query/iceberg.py`](../../packages/duckdb_query/iceberg.py)，`DuckDBIcebergCore.IDENTIFIERS`、`TABLE_NAMES`、`PARTITIONS`。名稱是程式預期，**不是 catalog 讀回確認**。

| Identifier | 程式 natural key | partition（新增資料） | 初始分類 |
|---|---|---|---|
| `core.stock_profile_v1` | symbol, market, observed_date | observed_date:month | KEEP |
| `core.market_volume_v1` | symbol, market, trade_date | trade_date:month | CONSOLIDATE_CANDIDATE，待核重疊 |
| `core.ohlcv_v1` | symbol, market, trade_date | trade_date:month | KEEP |
| `core.valuation_v1` | symbol, market, observed_date | observed_date:month | KEEP |
| `core.institutional_v1` | symbol, market, trade_date, investor_type | trade_date:month | KEEP |
| `core.financials_v1` | symbol, fiscal_year, fiscal_quarter, statement_type, version_at, metric, source_id | published_at:year | KEEP |
| `core.events_v1` | event_id, published_at | published_at:month | KEEP |
| `core.market_activity_v1` | symbol, market, trade_date, metric | trade_date:month | KEEP |
| `core.benchmark_v1` | benchmark_id, trade_date | trade_date:month | KEEP |

注意：Core 定義只確認 natural keys 和 partition 切面，**實際 field schema 需 Iceberg current schema/spec、資料型別與 metadata_location 讀回**。舊分桶 spec 可能透過 Iceberg partition evolution 仍存在，不能因新程式定義而聲稱 live 全表已遷移。

## 2. Mart Iceberg 程式定義清冊（11 個歷史維護 handle，不是 11 張已存表）

證據：[`jobs/intelligence-mart/intelligence_mart/storage.py`](../../jobs/intelligence-mart/intelligence_mart/storage.py) 的 `MART_TABLES` 與 `MartMaintenanceStore`，程式註明「historical tables; no legacy analysis writer」。

| 預期名稱 | 初始分類 | C1 前不可省的依賴 |
|---|---|---|
| mart.mart_screening_signals_v1 | RETIRE_CANDIDATE | screening GCS/PG/API fallback |
| mart.mart_core_alpha_v1 | RETIRE_CANDIDATE | 舊 alpha、研究模型 |
| mart.mart_risk_portfolio_v1 | RETIRE_CANDIDATE | Owner/private 讀者、安全範圍 |
| mart.mart_alternative_sentiment_v1 | RETIRE_CANDIDATE | sentiment/事件讀者 |
| mart.mart_scoped_analysis_v1 | RETIRE_CANDIDATE | report index、snapshot reader |
| mart.mart_market_regime_daily_v1 | RETIRE_CANDIDATE | 市場 regime 頁面或研究 |
| mart.mart_sector_rotation_daily_v1 | RETIRE_CANDIDATE | 產業輪動頁面 |
| mart.mart_topic_trends_daily_v1 | RETIRE_CANDIDATE | 主題頁面 |
| mart.mart_candidate_health_v1 | RETIRE_CANDIDATE | candidate 健康與管理頁 |
| mart.mart_daily_brief_v1 | RETIRE_CANDIDATE | 盤前盤後讀者 |
| mart.mart_llm_narratives_v1 | RETIRE_CANDIDATE | 既有報告與歷史產品 |

對每張查 catalog 精確存在性、current snapshot、schema/partition、最近有據的 write/read 與 API fallback；`ABSENT` 僅在 catalog 已讀回且確認缺席後可設；**目前 11/11 Live UNKNOWN，允許 DROP 數量 0**。

## 3. PostgreSQL 靜態 schema／field 切片

只盤點正式 migration / code contracts；未宣稱全庫精確 table count。Migration 是否實際 apply 須查 `control.schema_migrations`。不讀 `private` 個人 row。

| 實體／View | 代表欄位（非全欄清冊） | 定義來源 | 分類 |
|---|---|---|---|
| `control.stock_master` | symbol, name, market, enabled, updated_at | 002；`SET search_path TO control` | KEEP |
| `control.collection_configs` | config_id, dataset_id, source_ids, expected_fields, market, enabled, collection_enabled, analysis_enabled, lookback_days, overlap_days, full_refresh_interval_days, batch_scope | 002 | KEEP |
| `control.executions` | execution_id, config_id, trigger_type, status, requested_at, started_at, finished_at, claimed_until | 002 | KEEP |
| `control.execution_items` | execution_id, item_key, source_id, dataset_id, state, rows_received, error_code | 002 | KEEP |
| `control.response_cache` | cache_key, payload_uri, content_hash, fetched_at, expires_at, observed_at, state | 002 | KEEP |
| `control.collection_cursors` | cursor_key, last_observed_at, last_success_at | 002；055 擴充 coverage_json | KEEP |
| `control.source_health` | source_id, dataset_id, success_count, failure_count, latest_observation_at | 002 | KEEP |
| `catalog.iceberg_tables` | catalog_name, table_namespace, table_name, metadata_location, previous_metadata_location | 003 | KEEP |
| `catalog.iceberg_namespace_properties` | catalog_name, namespace, property_key, property_value | 003 | KEEP |
| `publication.mart_report_index` | execution_id, scope_type, scope_id, core_snapshot_id, artifact_uri, completeness, data_quality, publication_status, retention_until | 018 | KEEP |
| `publication.mart_report_outbox` | execution_id, scope_type, scope_id, event_type, delivered_at | 018 | KEEP |
| `control.core_ready_events` | core_execution_id, analysis_execution_id, config_id, payload, created_at | 019 | KEEP |
| `control.deep_tracking_membership_events` | event_id, symbol, effective_at, active, reason | 019 | KEEP |
| `control.batch_occurrences` | occurrence_id, scheduled_at, state, updated_at | 037 | KEEP |
| `control.batch_event_outbox` | event_id, payload, created_at, exported_at | 037 | KEEP |
| `control.market_serving_recent` | dataset_id, symbol, natural_key, sort_at, payload_json, source_id, provenance_id, execution_id, core_snapshot_id, updated_at | 054 | KEEP |
| `publication.market_serving_recent` | view of serving projection; not independently stored data | 054 | KEEP_VIEW |
| `control.market_universe_versions` | version, effective_from, source_snapshot, membership_hash, created_at | 055 | KEEP |
| `control.market_universe_members` | version, symbol, market, stock_name | 055 | KEEP |
| `private.risk_model_activation` | activation_id, mode, model_sha256, source_git_sha, gcs_registry_generation, reason, created_at | 068 | KEEP_PRIVATE_SCHEMA_ONLY |

更多 `private.*`、`analysis_product_*`、`stock_supplement_queue`、其他後續 migration 的完整 schema，需 B1 的 `information_schema.columns`、`pg_catalog`、實際 `schema_migrations` 才能出現 `LIVE_CONFIRMED`；**本表不是整個 PG 已存在表數或全欄 census**。

## 4. GCS 與執行面分類

| 資產族 | 程式證據 | 保護／判定 |
|---|---|---|
| Stage raw/sidecar/manifest/quarantine/commit marker | [`stage.py`](../../jobs/ingestion-core/ingestion_core/stage.py)、[`retention.py`](../../jobs/ingestion-core/ingestion_core/retention.py) | dev Stage `gen-lang-client-0593591102-dev-stage` 48h，依有效 lease／generation 鎖與讀回；C0 不實刪 |
| Core Iceberg warehouse/snapshot | `CORE_BUCKET`、`ICEBERG_WAREHOUSE` in [`__main__.py`](../../jobs/ingestion-core/ingestion_core/__main__.py) | live bucket 名、object count/bytes/snapshots UNKNOWN |
| GCS screening / risk-shadow artifact | [`market_screening.py`](../../jobs/intelligence-mart/intelligence_mart/market_screening.py)、Risk runtime/治理方案 | KEEP；publication/模型證據不可因為可重建就直接移除 |
| 研究 Parquet/CURRENT manifest/Y | [`janus_precision.py`](../../research/chatgpt/janus_precision.py)、[治理方案](https://drive.google.com/file/d/1TjHit4zEI9j99JSiaYT4WhxZYLdSH24b/view) | RESEARCH，與正式 Core/Mart 分離；快照/hash 固定，label 尚未成熟不可補 0 |
| 排程／工作執行 | `control.collection_configs/executions/batch_occurrences` migration；`__main__.py` | 只確認程式入口；Cloud Scheduler 的 job names、state、最近30日執行需真實讀回，UNKNOWN |

## 5. 已追溯的讀寫依賴矩陣（程式證據，不代表 Live 30日使用）

| 上游 | writer / process | 下游讀者／責任 | 類型 |
|---|---|---|---|
| TWSE/TPEx 等外部資料 | `ingestion_core.__main__` → Stage → `DuckDBIcebergCore.write` | Core 九個 dataset | 已確認程式路徑 |
| `market-volume` 正式批次 | [`__main__.py`](../../jobs/ingestion-core/ingestion_core/__main__.py) 先 `core.write(core_dataset_id)`、後於 540–576 行 `core.write('ohlcv')` | `core.market_volume_v1`、`core.ohlcv_v1` | **有雙寫路徑，內容是否冗餘待值級比較** |
| `core.ohlcv_v1` | Iceberg pinned snapshot | [`risk_inputs.py`](../../jobs/intelligence-mart/intelligence_mart/risk_inputs.py)、[`market_screening.py`](../../jobs/intelligence-mart/intelligence_mart/market_screening.py) | Risk、screening 正式讀者 |
| `core.benchmark_v1` / `core.valuation_v1` | Iceberg | `market_screening.py` 的 `TABLES` | screening 欄位投影 |
| Core market/financial 等 | serving projection | `control.market_serving_recent` → `publication.market_serving_recent` | SQL view 不是重複實體 |
| Core ready event | `control.core_ready_events` | Mart 分析事件／outbox | operational state，不是無用資料副本 |
| Mart 分析結果 | GCS artifact + `publication.mart_report_index/outbox` | API/publication 消費 | payload／索引／派送屬不同責任 |
| Stage execution | `control.executions.claimed_until`、Stage object metadata | 48h retention fencing | active lease 防護 |
| 研究 raw | `factor_factory_v1.py` + `janus_precision.py` | daily_X, monthly_X, price_Y, revenue_Y, valuation_Y | X/Y 分離；研究不是正式服務已接線證據 |

## 6. 四模型 X 席位與不可刪的非 X 資料

本輪核對 [`research/chatgpt/janus_precision.py`](../../research/chatgpt/janus_precision.py) 行 11–18：**34 個有序 X 席位、按名稱去重 27**（模型研究 contract，不代表四模型全部已部署）。

- **Risk（8）**：`vol20, vol60, drawdown60, abs_return5, volume_ratio20, atr14_pct, abs_overnight_gap5, log_turnover20`
- **Quant（11）**：`ret5, ret20, ret60, ma20_distance, ma60_distance, vol20, vol60, drawdown60, volume_ratio20, log_turnover20, market_code`
- **Fundamental（10）**：`yoy_m, yoy_3m, yoy_change1, growth_acceleration, mom_m, log_revenue, season_sin, season_cos, revenue_vol3, market_code`
- **Valuation（5）**：`roe, debt_ratio, log_total_assets, revenue_yoy, market_code`

**保護分類**：`MODEL_X`（上述按模型/順序/版本）；`RAW`（OHLCV、原始財務、來源口徑/單位）；`FEATURE_CANDIDATE`（非入模候選）；`LABEL_Y`（forward、成熟日、狀態）；`CONTEXT`（市場/產業/事件）；`QUALITY`（缺值、coverage、eligibility）；`PIT`（published/available/observed/version 時間）；`PROVENANCE`（source、execution、hash、as-of）。這些類別不在34席位內也必須保留。

同義/單位不是同值：`drawdown60 / drawdown_from_high60`、`turnover_log20 / log_turnover20`、`dollar_liquidity / turnover` 只列 ALIAS_CANDIDATE；`mean_reversion5=-ret5` 在 factory 直接定義；`yoy_m` 與 `revenue_yoy` 可能百分點/比例尺度差異；`vol20/60` 與 realized/std 等不可僅憑名稱合併；`valuation_Y` 不可由同日 PE/PB 衍生 X 洩漏。證據參見 [`factor_factory_v1.py`](../../research/chatgpt/factor_factory_v1.py)、治理方案。

## 7. 清掃候選分級與當前 C1 gate

| 編號 | 資產 | 暫定類別 | 若要 C1 必須取得的證據 | 回復方式 | 本輪結果 |
|---|---|---|---|---|---|
| C0-A01 | `core.market_volume_v1` ↔ `core.ohlcv_v1` | CONSOLIDATE_CANDIDATE | 兩邊 live schema、同市場日期鍵集合/值/單位、額外欄位、writer/reader、release hash | 先 compatible reader、雙寫關閉可逆開關、回切 writer；current snapshot 非可靠備份 | **禁止刪** |
| C0-A02 | 11 個 `mart.mart_*_v1` | RETIRE_CANDIDATE | catalog 存在性、現役 writer/reader、snapshot、API fallback 與 Owner 安全排除 | 有界保留/重建資料及舊 reader 切回；不可單靠過期 snapshot | **全部 UNKNOWN，禁止刪** |
| C0-A03 | 舊 `CoreWriter`、`IncrementalCoreWriter` JSON 入口 | RETIRE_CANDIDATE | main code reachability、runtime entrypoint、歷史測試/相容讀者 | git revert + retained tests | 不動程式 |
| C0-A04 | 同義/單位因子欄 | ALIAS_CANDIDATE | 逐值/公式/窗口/單位/PIT parity、模型 schema/version 消費者 | 相容 serializer/view、feature version 回退 | 不 DROP 欄 |
| C0-A05 | 重複 Colab notebook／一次性入口 | CONSOLIDATE_CANDIDATE | 目前採集入口/斷點狀態/產物引用 | archived notebook + pinned version | 不動研究資料 |
| C0-A06 | public Stage TTL / Iceberg 維護 | KEEP_POLICY | 48h lease、7日 orphan 與週維護依各自契約 | 既有 generation fence 與 rollback runbook | 不改 policy |
| C0-A07 | private ledger、Owner、Risk registry、研究 frozen input | KEEP_EXCLUDED | 不在本輪實體清掃授權範圍 | 不適用 | 永不順手清除 |

**可執行 C1 的清掃刪除清單：空集合。** 候選不是有據可刪；無備份、無回切、無 live dependency check，不能做破壞性操作。C1 若只停可安全還原的重複 writer，也必須先證明新舊值與讀者一致，且在使用者本輪僅授權文件的前提下不可直接改實作。

## 8. Q01–Q11 Live 驗證狀態

原治理方案的 Q01–Q10，以及補充的 Q11/工作包，如有規劃，不代表實際跑過。以下是**本輪的真實執行狀態**：

| 查核 | 目標 | 本輪結果 |
|---|---|---|
| Q01/Q02 | `catalog.iceberg_tables` catalog-qualified Core/Mart inventory/count | `NOT_EXECUTED/UNKNOWN` |
| Q03 | PG `information_schema`、`pg_catalog` 欄位、keys/index、schema migration | `NOT_EXECUTED/UNKNOWN` |
| Q04 | `control.batch_occurrences` 最近30日排程結果、active schedule 配置 | `NOT_EXECUTED/UNKNOWN` |
| Q05 | Core 日筆數與市場 coverage | `NOT_EXECUTED/UNKNOWN` |
| Q06 | Model X 有效筆數/缺值、X/Q/Y/Context/PIT 分層 | `NOT_EXECUTED/UNKNOWN` |
| Q07 | GCS → PostgreSQL → API 的 release/hash/consistency | `NOT_EXECUTED/UNKNOWN` |
| Q08 | source registry、實際授權/來源與參照 | `NOT_EXECUTED/UNKNOWN` |
| Q09 | Stage >48h + active lease + generation 的 dry-run 候選 | `NOT_EXECUTED/UNKNOWN` |
| Q10 | Colab/Drive 已取得研究檔與模型接線 | `NOT_EXECUTED/UNKNOWN` |
| Q11 | 原 Excel 如有補充查詢 | `ORIGINAL_XLSX_UNAVAILABLE/UNKNOWN` |

可在已核准、可唯讀執行的既有 dev 環境，用治理方案 §9 提供的 Q01–Q10 SQL，`BEGIN READ ONLY`、`statement_timeout`、小窗口與上限。**禁止**替代成寫入工作流、重新採集或新建計費服務。所有結果記錄 as-of UTC、role scope、SQL digest、snapshot_id、row counts、object generation（適用時）、query receipt 和錯誤碼。沒有資料不填 0；不可用 `not found` 與 `not authorized` 混為一談。

## 9. C1 方案（只提出，尚未執行）

1. 先取得完整 Live asset × dependency matrix；確認 Q01/Q02/Q03/Q04 及用得到的 GCS/manifest 讀回，固定報告日期、schema/current snapshot、writer/reader、backup/rebuild、可回復入口。
2. 從 **ABSENT 的過時文字/別名** 開始：只調整文件，無 SQL/DELETE。程式上可證已無 reader/writer 的 legacy entrypoint，再以獨立安全變更處理。
3. 對 `market-volume` 雙寫：同一批市場與交易日期比對 identity/欄位/數值/來源/precision；先提供相容讀，再停重複計算或可逆的 writer，受控讀回，最後才評估物理清掃。
4. 對 11 Mart 候選：逐張 catalog 查驗；`ABSENT` 僅更正清單；`KEEP` 保留；`RETIRE_CANDIDATE` 沒有 reader、且可重建與有界回復才提實體清掃。**大批不可逆真實資料刪除須另經使用者明確授權**。
5. 同義因子先固定 feature contract 與 unit parity；避免從每日、月營收和季度資料中無證據刪欄，尤其模型 X 版本、Y 與 PIT。
6. 將 C1 前後的 catalog/schema、資料量、key checksum、Core/Mart release、PG/API reader 和任務狀態比對，再執行 B1 近7交易日／30日排程基準線；沒有證據的環節仍 PARTIAL/UNKNOWN。
7. 不重啟 2025-01～2026-09 歷史資料補收，不把本輪治理直接變成採集、訓練或 deployment。

## 10. 尚待完成的單一缺口清單

- **GAP-01**：原 Excel Sheet 11–14 檔案無法定位，尚未逐格讀取；治理方案提供的是二手對照。
- **GAP-02**：缺目前可用的 live PG/catalog 唯讀 query 回傳，Core/Mart 實存與欄位 schema、PG 全表 census 均未驗證。
- **GAP-03**：缺 GCS 原始 object inventory、bytes/generation、研究檔 manifests、Stage lease 查詢，無刪前物理證據。
- **GAP-04**：缺 Cloud Scheduler/Job 實際配置與最近30日執行證據，不能宣稱入口已停或現役。
- **GAP-05**：缺 reader/writer 受控對照及 rollback receipts，C1 實體清掃清單空。
- **GAP-06**：本輪 Drive 原始 Markdown 仍為規劃 v1.0，**此 GitHub C0 證據文件尚未回寫至該 Drive 原檔**，需以保留原檔 ID 的可寫更新流程補齊並讀回。

## 11. 審查結論

本輪完成的是**有界的 GitHub 靜態證據盤點與 C1 gate 清單**，不是完整 Live baseline，也不是 C0 全驗證 PASS。**不新增、修改或刪除 schema、資料、排程、模型、runtime，也未執行任何 SQL。** 只有取得 Q01/Q03/Q04 與受影響資產的實際 reader、writer、snapshot、備份/重建收據後，才能按每項明確證據提升至 `LIVE_CONFIRMED` 或批准小範圍 C1。

---

## 12. C0-Live 唯讀證據續查（2026-10-23，第二輪）

> **證據時態標籤：** `HISTORICAL_RUNTIME_RECEIPT` 表示先前 GitHub Actions 在真實 dev 執行得到的收據，不代表現在的資料量或目前每張表存在；`STATIC_CODE` 是 GitHub main 定義；`CURRENT_LIVE_UNKNOWN` 表示本輪無直接 SQL/API 讀回。不得將 GitHub Actions workflow `success` 單獨當成該資料流完整驗收。
>
> **本輪直接環境唯讀查詢：未執行（工具能力缺口）。** GitHub App 能讀 repository / Action 既有 job logs；目前 GCP connector 僅支援 IAM role/deny-policy 管理查詢，未提供 Cloud SQL/PG、Iceberg、GCS、Cloud Scheduler 或 Cloud Run 服務狀態唯讀列舉；Janus Dev Read-only v2 `janus_sources` 回傳 `The tool failed internally`，且其用途本為有界發布市場資料而非 metadata SQL。**不可據此假定 dev runtime 消失。**

### 12.1 本輪固定的版本與既有執行收據

- 續查開始的 GitHub `main` HEAD：`cd347c52eb6be4fd32b1864165860f4391473c34`，提交時間 2026-10-23 10:59:08 UTC；距 C0 初稿 commit `ca2c037e6966286fde4dce17fa12c810003f20f0` 的五個提交僅涉及 research/preflight 文件，沒有本 C0 核心 Core/Mart 實作差異（[GitHub compare](https://github.com/tommylin15/janus-omniforge/compare/ca2c037e6966286fde4dce17fa12c810003f20f0...cd347c52eb6be4fd32b1864165860f4391473c34)）。
- [GitHub Actions #39552667601](https://github.com/tommylin15/janus-omniforge/actions/runs/39552667601)，`gcs-storage-footprint` job `119065218667`，2026-10-21 05:59:59 UTC，`OBSERVED_COMPLETE`，`bucket_discovery=COMPLETE`、6 buckets；來源是該 job 的 **Google Cloud 實際唯讀執行 log 中的 JSON 回傳**，並非本輪即時掃描。
- [GitHub Actions #39522934040](https://github.com/tommylin15/janus-omniforge/actions/runs/39522934040)，`stage-retention-trace` job `118970866333`，2026-10-21 00:43:02 UTC：`mode=read-only`、`natural_due_receipt=PASS`、`generation_readback=PASS`，但 `occurrence_database_readback=NOT_VERIFIED`；**此執行並非本輪 Stage dry-run**。
- [GitHub Actions #39938087196](https://github.com/tommylin15/janus-omniforge/actions/runs/39938087196)，`rollback` job `120362477591`，2026-10-23 10:19 UTC，已執行 GCS Registry `ACTIVE→DETERMINISTIC` generation-CAS、PG append-only rollback 及讀回；當時收據 PASS，不推論本輪之後沒有別的 writer。Registry 當時讀回 generation `1792750694551405`，與現在狀態不可混為一談。
- [GitHub Actions #39898282552](https://github.com/tommylin15/janus-omniforge/actions/runs/39898282552)，2026-10-23 04:04 UTC 的早期 Risk `ACTIVE` 讀回已成功，但時間早於上述受控回滾；**不得據此把 Risk 當前判成 ACTIVE**，也不得用 Risk 產物成功表示全部 Core/Mart 已盤清。
- [GitHub Actions #39942899812](https://github.com/tommylin15/janus-omniforge/actions/runs/39942899812) 於 2026-10-23 10:59 UTC 執行 selective CI 的 `plan` job 成功、`tests` job skipped；不代表 runtime 的 schema census 或資料品質通過。

### 12.2 GCS 六桶歷史容量收據（**2026-10-21 05:59:59 UTC，不是目前容量**）

| 桶用途 | 本次找到的歷史 Bucket | historical current_objects | historical current_bytes | historical noncurrent_bytes |
|---|---|---:|---:|---:|
| cloudbuild | `gen-lang-client-0593591102-cloudbuild-regional` | 2 | 127030 | 0 |
| Core | `gen-lang-client-0593591102-dev-core` | 2694 | 142319924 | 0 |
| Mart | `gen-lang-client-0593591102-dev-mart` | 1528 | 20744328 | 2749618 |
| Private | `gen-lang-client-0593591102-dev-private` | 2138 | 224655448 | 0 |
| Research | `gen-lang-client-0593591102-dev-research-big-move-500` | 145 | 299467376 | 0 |
| Stage | `gen-lang-client-0593591102-dev-stage` | 649 | 95347393 | 0 |
| **合計（當時）** | 6 | **7156** | **782661499** | **2749618** |

同一歷史回傳：`total_object_bytes=785411117`（current + noncurrent），`soft_deleted_bytes=0`，Stage `age_7d={objects:0,bytes:0}`。此 `age_7d` 不是 Stage 48h 清掃候選；48h 有無超期、lease、generation 仍須逐物件當前掃描。以上桶用量不等於 Iceberg table rows、不等於邏輯資料量，也不得作當前可回收容量。私人桶只取 metadata 彙總，未讀 owner 內容。現有 connector 不支援直接再跑此 inventory。

### 12.3 C0-L01–L05 實際驗證判定（不可把歷史和即時混列）

| 工作項 | 本輪獲得的最高等級證據 | 尚未取得 | 本輪狀態 |
|---|---|---|---|
| **L01 PG** | `002/003/018/037/054/055/068` migration 靜態與 Risk PG rollback 歷史讀回 | 現時 `pg_catalog` schema、`information_schema.columns`、PK/FK/index、`control.schema_migrations` 全集合、read/write 條件 | `PARTIAL/HISTORICAL_ONLY`；完整 inventory `BLOCKED` |
| **L02 Iceberg** | 9 Core 表映射與 11 Mart 歷史 handle 定義；歷史 Core/Mart bucket metadata | `catalog.iceberg_tables` 的當前 catalog-qualified 表列、schema/spec/snapshot、邏輯/物理 row count | `STATIC_ONLY/CURRENT_LIVE_UNKNOWN` |
| **L03 依賴/排程** | C0 第5節程式 lineage 與既有 ingress/Risk rollback 工作收據 | 實際 Scheduler job list/state、Cloud Run Job/Service 修訂版、最近30日 occurrences、表級 reader/writer 追溯與 failover | `PARTIAL/HISTORICAL_ONLY` |
| **L04 GCS** | 上述六桶 2026-10-21 真實掃描彙總、Stage retention 歷史讀回、Risk Registry 歷史讀回 | 今日 GCS inventory、prefix/generation/age、Stage 48h lease、安全引用、Iceberg metadata / manifest live | `HISTORICAL_RUNTIME_RECEIPT`；目前 `UNKNOWN` |
| **L05 34 X** | `janus_precision.py` 8+11+10+5，27 unique；舊 C0 的 RAW/Y/context/quality/PIT/provenance 分類 | 真實 research manifests、四模型 X 的 observed columns/non-null/coverage/available-at、每一 upstream 來源的 Live 對應 | `CODE_CONFIRMED`；值級驗證 `UNKNOWN` |

具體現存 PG 全表數、Core/Mart 實存表數、每張表實際 columns、讀寫量、最後寫入時間、rowcount、partition spec、Scheduler 名稱、Stage 48h 到期數，**一律 UNKNOWN；不得把 C0 的 9/11 靜態名稱寫成 Live 已有 9/11 張表**。

### 12.4 C0-Live 進 C1 的具體有界查詢表（未執行）

| 查詢 ID | 唯讀資料源與查核 | 最低輸出／收據 |
|---|---|---|
| `L01-Q01` | dev PG: `SELECT current_database(),current_user,clock_timestamp()`、`control.schema_migrations`、`information_schema.columns`、`pg_catalog.pg_class/pg_constraint/pg_index/pg_depend`（只限必要 schema/metadata） | as-of/role/scope、完整 table/view/field/key/index/constraint 清冊；private 僅 schema |
| `L02-Q02` | 同 PG 既有 JDBC catalog 的 `catalog.iceberg_tables`，以確定的 `catalog_name` 篩 core/mart；有 Iceberg 唯讀客戶端時個別查 `current_snapshot/spec_id/schema` | 精確存表/ABSENT，snapshot/spec/metadata_location、bounded records/count；`UNREADABLE` 與不存在分開 |
| `L03-Q03` | `control.batch_occurrences` 最近30日 & `control.executions`，另以 Cloud Scheduler `jobs list/describe`、Cloud Run `jobs/services list/describe` 比對 Git SHA、job env/reader/writer（不得回傳 secrets） | active vs archived、排程真正 due、執行終態、依賴/錯誤有據 |
| `L04-Q04` | GCS `objects list` metadata only，限已確認的 dev 六桶及目的 prefix；Stage object `updated`、generation 對應 PG **有效 lease** | current objects/bytes/prefix、Stage `>48h` 候選、保護理由、只產出 dry-run；Owner bucket 禁止 row payload |
| `L05-Q05` | 受控 release manifest／研究版本 X Schema 與 model input order、`core.market_volume_v1` / `core.ohlcv_v1` 同期 keys 及相交欄位規格比對 | 34/27 X、實際 model feature parity、X/Y/PIT 各域完整度、market-volume 值/單位/讀者/extra fields 的報告 |

上述 SQL/CLI 是操作清單而非已執行證據；若原 Drive 方案 §9 query 與現場 schema 不同，優先採主線 schema 並記錄差異。所有查詢需 `READ ONLY`、statement timeout、範圍限制、無新增資源與有限讀取成本；不得為取得證據觸發任何含 data write 的 GitHub Workflow、Cloud Run Job 或 Scheduler。

### 12.5 候選分級更新與 C1 準備程度

- **P0 候選 `core.market_volume_v1` vs `core.ohlcv_v1`**：已有程式雙寫證據，仍缺現時 catalog、共同 keys/values/units、額外欄、API/研究讀者。暫 `CONSOLIDATE_CANDIDATE`，不得停 writer / DROP。
- **P0 候選 11 個 `mart.mart_*_v1`**：程式歷史維護清單，有 `NO_LEGACY_ANALYSIS_WRITER` 註解；但 Live 是否存在、是否有 fallback reader/Owner 引用全部未驗。暫 `RETIRE_CANDIDATE`；**11/11 未能判定 ABSENT**，不得按表名 DROP。
- **相容因子欄**：候選別名只能先做 field contract/parity，版本 schema 和 Y/PIT/quality 必須保護。暫 `ALIAS_CANDIDATE`，本次可刪欄位 0。
- **Stage 48h**：Stage 歷史 metadata 與保護證據不等於今日到期數。此回合只保留既有政策，不執行 cleanup。
- **Private Owner／Ledger、Risk 回滾、GCS research frozen inputs**：KEEP，非本次退役對象。

**C0-Live 仍 PARTIAL，C1 實際可安全刪除的 Table=0、Field=0、GCS object=0（是批准清單空，不是 Live 實際無冗餘）。** 不把 `UNKNOWN` 當 `ABSENT`；不批准實體刪除、不觸發工作。

### 12.6 後續執行能力缺口／回報要求

- 本輪只有 GitHub/Drive 既有紀錄與有界 Janus 發布查詢插件，**沒有 Cloud SQL / PostgreSQL arbitrary SELECT、Iceberg catalog+object schema、GCS objects metadata 列舉、Scheduler/Cloud Run list/describe 的通用唯讀能力**；沒有現成可直接採用的整套 L01–L05 查詢結果。此限制是工具/存取界線，不等於 GCP IAM_DENIED 或系統故障。
- 原 `Janus_Data_Governance_Audit_2026-10-23.xlsx` 在可見 Drive/root/Library 的現有搜尋仍無法定位（先前 C0 缺口繼續保留）；Drive Markdown §2/§8/§9 可作參照但**不得冒稱 Sheet 11–14 原始逐格驗證**。
- 寫回 GitHub 此節是現有允許的**治理文件修改**；Drive 的同名原始 `.md` 若 connector 不支援 raw bytes 寫回，須將已提交證據 URL 記在該檔同一評論串並讀回，並明示「評論同步、原始內文未變」。
- 後續只有在既有 dev 已授權且具安全 read-only SQL/GCS/Scheduler 查詢的執行環境可用時，按 L01-Q01 → L02-Q02 → L03-Q03 → L04-Q04 → L05-Q05 一次完成有界盤點；回寫每項時間、Git SHA、使用角色、SQL digest、缺值/失敗與不可刪原因，完成後停止在 C0，不自動進 C1。

