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
