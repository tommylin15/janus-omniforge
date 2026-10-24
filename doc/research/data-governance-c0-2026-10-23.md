> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

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


---

## 13. C1-A 並行準備交接（2026-10-23）

在不修改任何程式、GCP / PostgreSQL / Iceberg / GCS / Scheduler/Job、資料或模型的前提下，正式建立 [**C1-A 安全清掃準備與 C0-Live 補驗並行計畫**](data-governance-c1a-2026-10-23.md)。本輪 C1-A 為 **PREPARED (DOCUMENT_ONLY)**、C0-Live 仍 **PARTIAL/BLOCKED**、C1-B **NOT_READY**。

本輪重點補充：
- \`ingestion_core.__main__\` 的 \`market-volume → ohlcv\` 是**全量官方批次先寫**和**通過 OHLCV DQ 後另寫**的兩種責任；不應視作完全相同數值的無效副本。詳見 C1A-01 同鍵/欄位/品質/來源/讀者比對 gate。
- [\`jobs/intelligence-mart/intelligence_mart/retention.py\`](../../jobs/intelligence-mart/intelligence_mart/retention.py) 會巡查這 11 個歷史 Mart identifier 是否存在，存在時可能執行過期列維護；\`MART_TABLES\` 沒有 legacy writer 不等於無操作依賴。
- [\`infra/postgres/migrations/018_mart_publication.sql\`](../../infra/postgres/migrations/018_mart_publication.sql) 定義 \`publication.mart_report_index.table_identifier = 'mart.mart_scoped_analysis_v1'\` 的 CHECK（**靜態 migration 定義，Live applied 尚未知**）；此 Mart identifier 特別標 \`KEEP_DEPENDENCY_PENDING\`，先驗 PG 實際約束和發布/舊 reader，再談退役。
- 已有 [\`.github/workflows/finops-dev.yml\`](../../.github/workflows/finops-dev.yml) 的 \`gcs-storage-footprint/core-reference-audit/runtime-references/iceberg-readback\` **唯讀診斷選項**，但不同 script 的操作界線各異；本輪沒有 dispatch 或 rerun 任何工作，不能因此冒稱取得今日 catalog/GCS 或 Scheduler 清冊。
- \`janus_precision.py\` 研究契約 \`VERSION=3.8.2\` 的 **34 ordered X slots／27 distinct names**，不是 7 個可刪重複欄；factory 中 \`dollar_liquidity=turnover\`、\`mean_reversion5=-ret5\`、\`revenue_yoy=revenue_growth_12m\` 僅**同研究 panel 的公式關係**，不能直接移植成跨 Core/PG/模型的 Drop 權。RAW/Y/QUALITY/CONTEXT/PIT/PROVENANCE 同樣保護。

**本輪沒有新的 current-live 直接 SQL/GCS/Scheduler 回傳。** 已知歷史 GCS / Risk receipt 見 §12；原 Excel Sheet 11–14 仍未逐格取得。C1 的 11 Mart、Core 雙寫、Alias 等現在仍只是候選；**經批准可實刪實體 = 0 項**。若缺少 PG catalog/constraint、Iceberg snapshot、GCS current generation、最近30日 reader/Job 與獨立回復證據，**不可執行 C1-B**。

---

## 14. PG／Iceberg 即時清冊補驗：既有 dev Core Census 收據發現與權限界線（2026-10-23）

**本節找到的是 2026-10-17 / 10-18 的真實 dev 唯讀 Iceberg 快照收據，絕非 2026-10-23 新執行的 SQL 或當前 catalog。** 本輪可逐張將九個 Core dataset 狀態從 `STATIC_ONLY` 提升至 `HISTORICAL_LIVE_EXISTS_ON_2026-10-18`，但 **`CURRENT_LIVE_EXISTS=UNKNOWN`、`CURRENT_SNAPSHOT=UNKNOWN`**。不能將下表任何日期/數值當最新狀態、也不能藉此准許 C1-B。

**來源：** [GitHub Actions #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620)，job `117544512424`、dev read-only `feature_readiness_inventory` 收據 `janus-ingestion-core-4bqcd`，`checked_at=2026-10-18T00:36:17.909819+00:00`，`status=PASS`；對照 [#38997408284](https://github.com/tommylin15/janus-omniforge/actions/runs/38997408284) job `117292878856`、`checked_at=2026-10-17T03:06:18.258289+00:00`，`status=PASS`。以上均來自實際 Job logs JSON `receipt.tables`，**不是以 GitHub Actions success 猜測表列**。

| Core dataset（實存於 10/18 的報告） | 10/18 Snapshot 紀錄數 | 10/17 → 10/18 行數變化 | 10/18 current_snapshot_id（歷史值） | schema 欄數 | 歷史 partition 數／日期區間 |
|---|---:|---:|---|---:|---|
| `core.stock_profile_v1` | 19731 | +0 | `5704536836386558575` | 9 | 2／2026-09～2026-10 |
| `core.market_volume_v1` | 39699 | +0 | `7853133804320960012` | 15 | 2／2026-09～2026-10 |
| `core.ohlcv_v1` | 111929 | +250 | `4001332868550575344` | 15 | 36／2023-11～2026-10 |
| `core.valuation_v1` | 16595 | +1924 | `4660132369949617208` | 11 | 36／2023-11～2026-10 |
| `core.institutional_v1` | 37947 | +0 | `8662583558237815416` | 12 | 5／2026-03～2026-10 |
| `core.financials_v1` | 88131 | +504 | `5736520631016782502` | 40 | 2／2025～2026 |
| `core.events_v1` | 882 | +0 | `8025274657125259451` | 12 | 3／2026-08～2026-10 |
| `core.market_activity_v1` | 135050 | +0 | `2900189873320370266` | 11 | 5／2026-03～2026-10 |
| `core.benchmark_v1` | 759 | +0 | `16811576102780075` | 10 | 36／2023-11～2026-10 |

10/18 歷史合計為 **450723 個各表邏輯紀錄**，**不是**去重股票日數、當前資料量、GCS bytes 或 10/23 的值；九個歷史 `status=COUNTED`。部分表即使 10/17→10/18 行數相同，snapshot ID 仍改變，不能由 `count unchanged` 推斷無 writer/無維護。

### 14.1 歷史 schema 欄位清冊（原 receipt，而非預期欄位）

| dataset | 2026-10-18 讀回的 field names（按表 Schema 順序） |
|---|---|
| `stock-profile` | `symbol`, `stock_name`, `market`, `observed_date`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `market-volume` | `symbol`, `stock_name`, `market`, `trade_date`, `volume_shares`, `turnover_twd`, `open`, `high`, `low`, `close`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `ohlcv` | `symbol`, `market`, `trade_date`, `open`, `high`, `low`, `close`, `volume_shares`, `turnover_twd`, `change_percent`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `valuation` | `symbol`, `market`, `observed_date`, `pe_ratio`, `pb_ratio`, `dividend_yield_percent`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `institutional` | `symbol`, `market`, `trade_date`, `investor_type`, `buy_shares`, `sell_shares`, `net_shares`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `financials` | `symbol`, `fiscal_year`, `fiscal_quarter`, `statement_type`, `published_at`, `metric`, `value`, `unit`, `currency`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash`, `source_report_date`, `availability_at`, `publication_time_authoritative`, `concept`, `context_id`, `period_start`, `period_end`, `period_basis`, `is_single_quarter`, `report_scope`, `industry_sector`, `report_type`, `numeric_revision_verified`, `fiscal_period_end`, `availability_basis`, `share_basis_status`, `historical_publication_status`, `source_document_sha256`, `official_filing_uploaded_at`, `filing_filename`, `version_at`, `fiscal_month`, `source_unit`, `financial_feature_version`, `comparison_value`, `comparison_period_end` |
| `events` | `event_id`, `symbol`, `event_type`, `published_at`, `effective_date`, `severity`, `details`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `market-activity` | `symbol`, `market`, `trade_date`, `metric`, `value`, `unit`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |
| `benchmark` | `benchmark_id`, `trade_date`, `close`, `return_percent`, `index_kind`, `source_id`, `observed_at`, `execution_id`, `provenance_id`, `content_hash` |

### 14.2 對 C1-A 的直接影響與不成立的結論

1. **`market-volume` vs `ohlcv` 並非當時的相同物理副本**：在 10/18 的讀回，前者 39699 筆、後者 111929 筆；`market-volume` 有 `stock_name` 而 `ohlcv` 無，`ohlcv` 有 `change_percent` 而 `market-volume` 無；最早分區分別 `2026-09` 與 `2023-11`。兩者的同名價格、交易量欄，仍需以同鍵、有界值級查詢核對是否重複；其歷史範圍和職責不同，**禁止直接刪表或停止 writer**。
2. `financials` 的 `published_at`、`availability_at`、`version_at`、`source_document_sha256` 等欄位在 10/18 真實存在。即使不在四模型 34 個 X 席位內，也屬於 PIT、來源修訂和 provenance 保護，**不可當冗餘列刪除**。
3. 此收據**只覆蓋 `core` 九個既有 `DuckDBIcebergCore.IDENTIFIERS`**，沒有 `mart` 表實存清冊、`catalog.iceberg_tables` 全 catalog namespace，也沒有 PG `information_schema`、keys/index、`schema_migrations` 實際全集；十月十八日的 Core PASS 不得升級成 `L01/L02 FULL_PASS`。
4. 繼續保留第12節已發現的 GCS 歷史收據與 Risk 10/23 後續 DETERMINISTIC 回滾結論，兩者都與當前 10/23 PG/Iceberg 全庫清冊不同。

### 14.3 即時讀取能力與可接受收據門檻

- 有現成 [Core metadata census workflow](../../.github/workflows/archive/feature-readiness-metadata-census.yml.disabled)，可以讀取 **Core 的 schema、current snapshot、row count/partition**，但它執行既有 dev Job 並讀回 logs；本輪 **沒有 dispatch / rerun**，而且即使執行也**不能得到 Mart 和 PG 完整清冊**。
- [FinOps `iceberg-readback` 工作](../../.github/workflows/finops-dev.yml) 的實作是 **Scheduler/四個 Cloud Run Job/進行中 execution 列舉**，**並非 Iceberg SQL catalog 掃描**。不得以其成功代替 `L02-CATALOG`。
- 目前已連線的 GCP plugin 僅提供 IAM roles/deny policies，沒有 PostgreSQL arbitrary SELECT 或 Iceberg metadata API；Browser tab read 在本輪回報 `Browser access requires the originating browser context`；`Janus Dev Read-only v2` 的 `janus_sources` 再次回報 `The tool failed internally`。**這些均是查詢通道限制，不證明 DB 不存在、IAM 真的被拒絕或資料壞掉。**
- **須新增的不是資料或服務，而是由既有授權唯讀通道輸出一份 bounded PG+Iceberg metadata receipt：** as-of UTC/role/project/environment/Git SHA、PG schema/table/view/field/key/index/migration 查詢結果，`catalog.iceberg_tables` 的 `catalog_name='janus'` core/mart entries，逐表最新 schema/spec/current snapshot/summary row count，查詢錯誤/欄位無權限清楚標註。先固定 current catalog table list，再與這兩份 10/17–10/18 歷史收據比對差異；不得用舊 snapshot 補當前值。
- 直到 **兩層現時清冊都讀回並可驗證**，C1A-01/02/03 仍不可准許物理清掃；**經核准可刪項目 = 0**。下一輪才可以在舊 C1-A 矩陣內按資產逐項升級 `LIVE_CONFIRMED`。

---

## 15. 既有 dev 身分新增受控 ChatGPT → GitHub Actions → PG／Iceberg Metadata 查詢入口（2026-10-23）

用戶授權「沒有就加上去」，採取**不開放任意 SQL、不新增付費資源、不擴張 IAM**的最小工程方案。本階段新增三項工程資產：

- [\`.github/workflows/archive/governance-metadata-readonly.yml.disabled\`](../../.github/workflows/archive/governance-metadata-readonly.yml.disabled)：push 指定治理 request 或手動 workflow_dispatch；使用既有 dev WIF 和 CI 身分，不暴露 secret。
- [\`scripts/gcp/governance_metadata_readonly.py\`](../../scripts/gcp/governance_metadata_readonly.py)：固定有界查詢，在現有 \`janus-ingestion-core\` Job 以單次 Python override（不改 Job template）取得 PostgreSQL \`pg_catalog\`、\`information_schema\`、\`control.schema_migrations\`、\`catalog.iceberg_tables\`（core+mart）和 PyIceberg current metadata。每段 \`BEGIN READ ONLY\`、statement_timeout 10s；不做 table.scan/資料列讀取；私人資料只讀 schema metadata；結果按 section/chunk 保留 JSON 收據、SQLSTATE / error class，不印敏感 error/Secrets。
- [\`tests/test_governance_metadata_readonly.py\`](../../tests/test_governance_metadata_readonly.py) 與 [\`ops/governance-metadata-readonly-request.json\`](../../ops/governance-metadata-readonly-request.json)：固定審查範圍、不可變資料和離線 guard。ChatGPT 可透過 GitHub 已授權 connector 更新受控 request 觸發一次 metadata scan，再透過同一 GitHub connector 讀回 Action log/Artifact。**此入口是 GitHub mediated，不是 ChatGPT 直接連 Cloud SQL 的 SQL connector**。

正式執行現場 **Run #39948922788**：[GitHub Actions](https://github.com/tommylin15/janus-omniforge/actions/runs/39948922788)。**第一次收據尚待實際 job 終態與 JSON 驗證；本節記錄程式提交與 dispatch，不代替 Live PASS。** 如需此入口獲得所有 metadata，仍受既有資料庫角色的 schema visibility、Iceberg storage 讀權限制；不足時輸出 \`PARTIAL\` / \`BLOCKED\`，**不得自動 GRANT 或調整 IAM**。

另於 2026-10-23 11:45:48 UTC 重新執行原本 [Core Census #39083283620 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620)，dev Job \`janus-ingestion-core-z9z27\` 真實讀回 **9/9 Core \`COUNTED\`**（歷史 §14 是 10/18，本次是 10/23 真正新的 snapshot）。
| Core dataset | 2026-10-23 11:45 UTC snapshot-summary total-records | current_snapshot_id at that time | schema fields |
|---|---:|---|---:|
| \`core.stock_profile_v1\` | 27691 | \`5647992786866848105\` | 9 |
| \`core.market_volume_v1\` | 163544 | \`743663981527903040\` | 15 |
| \`core.ohlcv_v1\` | 200926 | \`4615080908076408192\` | 15 |
| \`core.valuation_v1\` | 25004 | \`6880250134433223964\` | 11 |
| \`core.institutional_v1\` | 60222 | \`4091141956722620864\` | 12 |
| \`core.financials_v1\` | 90391 | \`3571756500360077023\` | 40 |
| \`core.events_v1\` | 1245 | \`7156204294980068762\` | 12 |
| \`core.market_activity_v1\` | 215714 | \`2203751285827207874\` | 11 |
| \`core.benchmark_v1\` | 764 | \`4617056096245975844\` | 10 |

**範圍限制：** 上述 Core Census 只覆蓋其執行時列於 \`DuckDBIcebergCore.IDENTIFIERS\` 的九表，不證明 \`mart\` 實存張數／PostgreSQL 全 Schema／全部未知 Core 表。C1-B 仍 NOT_READY；以上不構成刪表授權。

---

## 16. 受控 ChatGPT → GitHub Actions → dev PG／Iceberg 即時 SQL 收據（2026-10-23）

**實際執行，不再是單純規劃：** [GitHub Actions #39948922788](https://github.com/tommylin15/janus-omniforge/actions/runs/39948922788)，job \`120398320107\`，既有 dev \`janus-ingestion-core\` metadata-only Job override。資料回傳 \`checked_at_utc=2026-10-23T11:52:29.793747+00:00\`，執行來源 Git SHA \`1e45d5f9be2307291dee2808ce6588803191ed0a\`，\`data_mutations=0\`，PG 使用 \`janus_catalog\` / \`janus_control\` 現役 role。收據可由 Action job logs 的 \`JANUS_GOVERNANCE_METADATA_RECEIPT_V1:\` 前綴逐 section/chunk 讀回，並保存 [JSON artifact](https://github.com/tommylin15/janus-omniforge/actions/runs/39948922788/artifacts/12499886060)。

**Workflow 總體 conclusion = failure，這是預期的 fail-closed partial gate：** PG catalog 等收據真實讀回成功，但 11 個 Mart Iceberg metadata load 全部遭遇 \`PermissionError\`（Core Job 身分不等於 Mart GCS metadata 可讀），腳本因整體 \`PARTIAL\` 回傳非零；**不得把 Workflow failure 當成全部查詢失敗，也不得把 Catalog 登錄當資料檔可讀。**

| 讀取範圍 | Live receipt（本輪） | 判定／限制 |
|---|---:|---|
| PostgreSQL \`pg_catalog\` relations（Table、View 等） | 93 | PASS；audit=3、catalog=2、control=36、private=38、public=2、publication=12（僅 metadata，未查私人 rows） |
| \`pg_catalog.pg_attribute\` columns | 728 | PASS；含全部上述 namespace 的 schema metadata |
| \`pg_catalog.pg_constraint\` | 379 | PASS；確認 \`publication.mart_report_index_table_identifier_check\` 的實際 constraint 名（未取出約束 expression） |
| \`pg_catalog.pg_index\` | 149 | PASS |
| \`information_schema.tables\`、\`columns\` | 4／19 | QUERY_PASS但ROLE_LIMITED；以 \`janus_catalog\` role 看見的部分，不代表只有 4 張 PG Table |
| \`control.schema_migrations\` applied versions | 66 | PASS_READ、**版本漂移待分析** |
| \`catalog.iceberg_tables\`（\`catalog_name='janus'\`） | **20**：Core 9、Mart 11 | **LIVE_CATALOG_PRESENT**；不是資料 Row Count 的間接推估 |
| PyIceberg \`core\` current snapshot/schema/spec | **9/9 READABLE** | PASS（此時間點）；依 metadata summary 的 \`total-records\`，不掃資料列 |
| PyIceberg \`mart\` current snapshot/schema/spec | **0/11 READABLE** | BLOCKED_MART_STORAGE_PERMISSION；全部 \`PermissionError\`，不可因 catalog 存在就視為資料可讀或可刪 |

### 16.1 已套用 Migration 與 GitHub 版本化 SQL 差異（本次真正 PG 讀回）

比較 \`control.schema_migrations\` 實際 66 個版本值 vs \`infra/postgres/migrations/\` GitHub main 的 68 支 SQL 檔名：
- GitHub 有但 Live migration ledger 未記錄：\`030_private_stock_master_read\`、\`031_portfolio_market_coverage\`、\`034_offlist_watchlist_retirement\`。
- Live ledger 有但 GitHub 當前同名檔不存在：\`049_batch_skipped_state\`；當前 repo 是 \`049_batch_occurrence_skipped_status\`。
- 因此**不是單純「缺 2 個 migration」**；可能涉及重命名／替換／歷史手動遷移，但本輪無 DDL 或 private rows 驗證，**不得推定 Live schema 必然有缺陷，也不得自動重跑 migration。** 此差異升級 C0 GAP 並要求釐清 schema contract / applied checksum。

### 16.2 C1-A 清掃候選即時升級

- Core 9 張：\`LIVE_CATALOG_PRESENT_AND_METADATA_READABLE\`。§15 讀回的 9 個 snapshot 行數與本次同一時段 metadata 一致；這個結論只代表 2026-10-23 11:52 UTC 附近的 dev 狀態。
- Mart 歷史 11 張：由 \`CODE_STATIC/UNKNOWN\` 升級 **\`LIVE_CATALOG_PRESENT\`**，11/11 列於實際 \`catalog.iceberg_tables\`；其實際 current snapshot、data-file 可讀性、row counts/partition spec、reader usage 仍 \`BLOCKED/UNKNOWN\`。
- \`mart.mart_scoped_analysis_v1\`：PG \`publication.mart_report_index\` Live relation 和 \`mart_report_index_table_identifier_check\` constraint 確實存在，屬**目前明確保護**；此讀回僅取得約束名稱，\`pg_get_constraintdef\` 的實際內容尚未讀回，不假裝已驗。
- \`core.market_volume_v1\` / \`core.ohlcv_v1\`：Live metadata 證實兩張表都存在且筆數、欄位差異，但值級與 reader parity 仍未完成，不批准合併或刪除。
- 原定 C1-B 入場的完整 reader/writer 使用證據、回復路徑依然未證實；**核准實體刪除 0 項**。

### 16.3 身分／查詢通道判定及最小補驗方向

首次查詢明確說明**PostgreSQL \`pg_catalog\`／Iceberg catalog SELECT 權限已足夠**，毋須增大 Core 身分授權；Mart GCS metadata 存取遭遇 \`PermissionError\`，不建議立即提升 ingestion SA IAM 權限。改由既有 \`janus-intelligence-mart\` dev Job 身分讀取 Mart Iceberg metadata，不改 Cloud Run Job template、不加 IAM、不新增資源；此替代方式已加入同一個 [治理 Workflow](../../.github/workflows/archive/governance-metadata-readonly.yml.disabled)，第二輪 [#39949570989](https://github.com/tommylin15/janus-omniforge/actions/runs/39949570989) 的終態和收據應另行補登，不得由本節推定 PASS。

---

## 17. Mart 11/11 Live metadata 以既有 Mart 身分補驗（2026-10-23）

為避免新增 IAM grant，維持 §16 已知的 Core 身分 \`PermissionError\`，另使用**既有** \`janus-intelligence-mart\` Job dev 身分，唯讀執行 PyIceberg \`list_tables(('mart',))\` + \`load_table\` metadata；沒有調整 Cloud Run Job template、資料、角色或 bucket policy。

**實際收據：** [GitHub Actions #39949570989](https://github.com/tommylin15/janus-omniforge/actions/runs/39949570989)，job \`120400442445\`，\`JANUS_GOVERNANCE_MART_METADATA_RECEIPT_V1:\` JSON logs，\`checked_at_utc=2026-10-23T11:59:05.540844+00:00\`，\`git_sha=b67d7e4cb28c16de0bba0f80ca64e400de45f01c\`。該 run 的第一個 Core 執行步驟仍將已知的 \`Mart GCS PermissionError\` 判為 \`PARTIAL\` 而使 Workflow 顯示 **failure**，但第二步 Mart 專用 Job 讀回 \`summary.status=PASS\`、\`catalog_names=11\`、\`snapshots_readable=11\`（「metadata 可讀」，其中有兩張沒有 snapshot，不等同 11 張有資料）。

| Live Mart Iceberg table | 2026-10-23 11:59 UTC Current Snapshot ID | snapshot summary total-records | 實際 schema 欄數 | \`READABLE\` |
|---|---|---:|---:|---|
| \`mart.mart_alternative_sentiment_v1\` | **NULL（無 current snapshot）** | **UNKNOWN/NULL，不得填 0** | 23 | 是，表 metadata |
| \`mart.mart_candidate_health_v1\` | \`118880949889506234\` | 104 | 23 | 是 |
| \`mart.mart_core_alpha_v1\` | \`4538355055818619845\` | 104 | 23 | 是 |
| \`mart.mart_daily_brief_v1\` | **NULL（無 current snapshot）** | **UNKNOWN/NULL，不得填 0** | 23 | 是，表 metadata |
| \`mart.mart_llm_narratives_v1\` | \`1043193908964583361\` | 1 | 23 | 是 |
| \`mart.mart_market_regime_daily_v1\` | \`6029291748398477743\` | 21 | 23 | 是 |
| \`mart.mart_risk_portfolio_v1\` | \`8959822825160784524\` | 104 | 23 | 是 |
| \`mart.mart_scoped_analysis_v1\` | \`6354316357698419865\` | 138 | 23 | 是 |
| \`mart.mart_screening_signals_v1\` | \`2540499314470004370\` | 104 | 23 | 是 |
| \`mart.mart_sector_rotation_daily_v1\` | \`1716098001482105032\` | 13 | 23 | 是 |
| \`mart.mart_topic_trends_daily_v1\` | \`6110792041360640349\` | 21 | 23 | 是 |

**實際 Partition Spec**：11 表共同為 \`analysis_date_month = month\`、\`scope_id_bucket_32 = bucket[32]\`；每張 metadata schema 均為 23 個 fields（表級 field type/nullability 明細保存在原始 receipts）。這只是 metadata 的實際欄位，非各表最近 30 日 reader 使用量證明。 \`mart_scoped_analysis_v1\` 在 PG \`publication.mart_report_index\` 的實際 constraint 仍須確認表 identifier 的具體 expression 和目前 reference rows。

**狀態提升與安全限制：**
- \`C0-L02\` **Live catalog enumeration + all Core/Mart current schema/partition/snapshot metadata 已取得**（九張 Core、十一張 Mart）。其中兩表無 snapshot；不得解釋為不存在或 rowcount=0。
- \`C0-L01\` PG catalog metadata、columns/types、constraint/index names、migration ledger **已實讀**；剩餘是當前 migration 名稱 drift、Role 限制下 information_schema 可見性與特定 constraint 定義內容核對。
- \`C0-L03\` 30 日 writer/reader/Cloud Scheduler/Cloud Run 使用證據和 \`C0-L04\` GCS today prefix/lease、\`C0-L05\` 四模型真實 X values/PIT 仍需分開驗證；**C0 全部不是 FULL PASS，C1-B 無實刪授權**。
- 執行流程已改成 Core role 與 Mart role 各查可讀資產後 cross-validate（[治理 Workflow](../../.github/workflows/archive/governance-metadata-readonly.yml.disabled)）；新版 [#39950278408](https://github.com/tommylin15/janus-omniforge/actions/runs/39950278408) 首次整合結果仍需讀回，未達成前不能提前寫 \`WORKFLOW_PASS\`。

---

## 18. ChatGPT 受控 PG／Core／Mart Metadata 查詢通道整合驗收 PASS（2026-10-23）

**跨兩個既有 dev 身分整合驗收已成功，不只是兩個彼此獨立的綠色步驟：**
- [GitHub Actions #39950278408](https://github.com/tommylin15/janus-omniforge/actions/runs/39950278408)，job \`120402762186\`，\`conclusion=success\`；執行 Git SHA \`cd63e699e3d0da8e44b39552406f9255b8fd9aaa\`，流程離線測試 **6 passed**。
- 真正整合 receipt：\`component=janus_governance_c0_live_metadata_join_v1\`、\`status=PASS\`、\`postgres_relations=93\`、\`postgres_columns=728\`、\`postgres_constraints=379\`、\`postgres_indexes=149\`、\`applied_migrations=66\`、\`core_catalog_tables=9\`、\`mart_catalog_tables=11\`、\`core_snapshots_readable=9\`、\`mart_metadata_readable=11\`、\`data_mutations=0\`、\`iam_changes=0\`、\`new_resources=0\`。
- Workflow 明確驗證：PG Core 收據與 Mart 收據的 **Git SHA 一致**、實際 \`core/mart\` 表名逐一與 Live Catalog 比對、前者的 9 Core metadata 全可讀、後者的 11 Mart metadata 全可讀、兩個既有 Job 的 template fingerprint 未變；Core role 對 Mart 的原先 \`PermissionError\` 只在**完整限定 9/9 Core PASS + 11/11 Mart PermissionError**時允許轉交 Mart 身分，其他部分失敗仍阻擋。
- 成果保存於該 Actions 的 \`janus-governance-metadata-readonly\` artifact 與有前綴的可稽核 JSON logs；未在 Git 或使用者可見文件寫入任何 secrets、密碼、OAuth token 或 private row payload。
- ChatGPT 實際查詢路徑是「**GitHub connector → 受控 GitHub Actions → 既有 dev WIF/Job → PG/Iceberg metadata → GitHub logs/artifact → ChatGPT**」，不是通用、互動式 PostgreSQL SQL Connector；以固定 query、固定 project、已知權限邊界換取最小 IAM 與可稽核性。未新增新的付費 GCP 資源或權限。

**本工項完成標準：\`C0-L01 PostgreSQL bounded schema/constraints/index/migrations receipt\` 與 \`C0-L02 9 Core + 11 Mart metadata catalog/schema/spec/snapshot existence census\` 已在明確有界範圍驗收 PASS。** 這不代表 GitHub 68 支 migration 都已套用；§16.1 的 migration 名稱差異仍需處理。 \`C0-L03\` 最近30天 reader/writer/Job、\`C0-L04\` 今日 GCS prefix/lease、\`C0-L05\` 模型真實 X/PIT coverage 不是這個 metadata-only Workflow 的範圍，仍 \`PARTIAL/UNKNOWN\`；**C1-B 實體清掃仍 NOT_READY、核准可刪 0**。

**安全操作提醒：** 未來若 ChatGPT 需要更新這份即時證據，可在明確授權的 repo main 更新已固定的 \`ops/governance-metadata-readonly-request.json\` 觸發新的一次 workflow；不要將此擴充成任意 SQL 執行器，若需新查詢先以版本化 script、測試、唯讀交易與有界收據審查。


---

## 19. C1-A 讀者依賴 Live 驗證（2026-10-23 12:17–12:19 UTC）

**工作流與證據：** [GitHub Actions #39952096357](https://github.com/tommylin15/janus-omniforge/actions/runs/39952096357)，job \`120408771409\`，\`conclusion=success\`；\`source_git_sha=d0ec9d49e8db1ca807948c40fae338a25415e2ac\`；8 個 offline security tests passed。這次是**真正 dev 既有 PostgreSQL 身分與 Mart 身分分工的唯讀聚合查詢**，不是沿用 §18 的舊結果。收據使用與 §18 相同的 \`JANUS_GOVERNANCE_METADATA_RECEIPT_V1:\`／\`JANUS_GOVERNANCE_MART_METADATA_RECEIPT_V1:\` JSON log 分片及 Actions Artifact。整合 receipt \`janus_governance_c0_live_metadata_join_v1\`：\`status=PASS\`、\`reader_reference_status=PASS\`、\`data_mutations=0\`、\`iam_changes=0\`、\`new_resources=0\`，既有兩 Job template fingerprint 不變。

### 19.1 真實 PostgreSQL Mart 發布參照（\`janus_mart_publication\`，metadata only）

| 查詢來源 | Live receipt | 嚴格意義 |
|---|---|---|
| \`publication.mart_report_index\` 按 table/status/outcome 分組（全期間） | 138 個 reference rows，全部 \`table_identifier='mart.mart_scoped_analysis_v1'\`，其中 blocked/insufficient_data=29、blocked/invalid=90、blocked/review_required=18、publishable/complete=1 | **138 筆是發布索引列，不是 138 個 reader 或 138 次 API 點閱。** 每組有各自歷史 snapshot 引用；不得為清掃移除其來源 |
| \`publication.mart_report_index\` 依 \`analysis_as_of >= current_date-interval '30 days'\` | 35 列（29 blocked/insufficient_data、6 blocked/invalid） | 這是**分析業務日期**的 30 天切片，不是 \`created_at\` 的 30 天執行紀錄，也不證明 35 次讀取 |
| \`pg_get_constraintdef(mart_report_index_table_identifier_check)\` | \`CHECK ((table_identifier = 'mart.mart_scoped_analysis_v1'::text))\` | **實際 dev PG constraint 定義**已讀回；不能只更新 Mart 表名不連動 API / PG publication 契約 |
| \`pg_stat_user_tables\` 的 \`mart_report_index\` | seq_scan=187；idx_scan=678 | **累積統計**；\`stats_reset\` 尚未讀回，不能宣稱「最近 30 日 865 次讀取」或分辨特定 API / Job |
| \`pg_stat_user_tables\` 的 \`mart_report_outbox\` | seq_scan=38；idx_scan=0 | 累積 PG 存取統計，非 outbox 未交付量或即時 payload |
| \`publication_index_all\` 各組不同 \`iceberg_snapshot_id\` | distinct snapshots 分組各為 9、21、13、1（分組間可能重疊） | 證明報表索引具有 snapshot-fenced reference；**不保證舊 Iceberg snapshot 依現行 current-only 策略仍可 replay** |

**明確的靜態讀者鏈：**
\`packages/web_api/public.py:PostgreSQLPublicIndex.latest\` 查 \`publication.publishable_mart_reports\` → \`IcebergArtifactReader\` 驗證 GCS artifact hash 與固定 \`mart.mart_scoped_analysis_v1\` → \`catalog.load_table(index["table_identifier"])\`／\`table.scan(snapshot_id=index["iceberg_snapshot_id"])\`。這是 live index 138 筆不能單靠「目前舊 writer 已下線」來刪 Mart 表的關鍵原因。另 \`packages/admin_api/service.py\` 仍具有 \`mart_reports\`／\`execution_details\`／\`review_mart_report\` 讀取契約；\`jobs/intelligence-mart/intelligence_mart/retention.py\` 還會巡查所有 11 個 Mart 表並維護保留期。

### 19.2 近 30 天控制面執行證據（\`janus_control\`，僅 status/count）

篩選基準是 \`control.executions.requested_at >= now()-interval '30 days'\`，以 \`trigger_type,status\` 聚合，不取 \`requested_symbols\`、UUID、Owner 記錄或 payload。執行 \`checked_at_utc=2026-10-23T12:17:27.783556+00:00\`。

| trigger_type | status | requested_at 最近 30 日內筆數 |
|---|---|---:|
| analysis | failed | 8 |
| analysis | queued | **41** |
| analysis | succeeded | 18 |
| collection | failed | 48 |
| collection | partial | 50 |
| collection | running | **16** |
| collection | succeeded | 89 |
| **合計** | | **270** |

\`queued=41\` 與 \`running=16\` 是實際 PG status，**不直接等於目前有 41 個待跑或 16 個 lease 還有效**；需要下一步以 \`claimed_until > now()\`／Job execution terminal 和入列時間拆解 stale。這是具體 follow-up，避免 Stage 48h 清理錯誤保護。此清冊沒有 30 日 **Cloud Scheduler/Cloud Run 實際觸發全列**，不得將 PG \`requested_at\` 當 Cloud Run execution 發生時間。

### 19.3 C1-A 優先分類變化

- **\`mart.mart_scoped_analysis_v1\`：KEEP（強讀者依賴證據）。** 有 dev Live PG 138 個 Mart 發布 reference、1 個 \`publishable\`、確實套用的 CHECK、靜態公開 API 直接讀該表與指定 snapshot，且有 Mart retention。**禁 DROP、禁刪舊相容路徑**。
- **其他十張 Mart 表：\`LIVE_CATALOG_PRESENT\`，本次 \`publication.mart_report_index\` 內無引用（由 CHECK 約束本身限制），**不能提升為 NO_READERS**。** \`mart_risk_portfolio_v1\` 因 Risk/Owner 邊界維持高風險保護待查；其他仍 \`RETIRE_CANDIDATE/UNKNOWN_READER\`。兩張沒有 current snapshot 的 \`mart_alternative_sentiment_v1\`、\`mart_daily_brief_v1\` 仍可讀 schema，但不等於零資料或可刪。
- **Core \`ohlcv_v1\`：KEEP。** \`jobs/intelligence-mart/intelligence_mart/risk_inputs.py:TABLE\` 固定為 \`core.ohlcv_v1\`，且 \`specialist_runtime.py\` 會讀 pinned Core datasets；不得與 \`market_volume_v1\` 合併實刪。
- **讀者追蹤剩餘：** 仍缺 Cloud Run 已部署 reader revision/code 對應、其餘十張 Mart 是否有直接或間接 consumer、過去30日 Scheduler/Job 獨立 status 收據、PG index snapshot 與 current snapshot 是否匹配、rollback/rebuild 路徑及 GCS reference。尤其 1 筆 \`publishable\` 是**舊業務日期**，尚未做 API 正向讀取，不應宣稱公開報表現在可成功 replay。
- **退役安全結論：** \`C1-A READER_REFERENCE_BOUNDED_PASS\`，但 \`C1-A RETIREMENT_GATES=PARTIAL\`；**C1-B 可直接實刪 Table/Column/Object 仍 0**。未改變任何資料/Writer/Scheduler/IAM 或部署；此輪只新增版本化固定唯讀彙總 SQL、安全測試和治理文件。

**證據級別小結：** 已經由真實 PG 聚合證明 \`publication.mart_report_index\` 對 scoped_analysis 的依賴；尚未以 PG 掃描數確定哪個 API/owner 曾讀，亦未以「單一 publication index 中無其他 Mart 名稱」推論其他十張全系統無讀者。

---

## 20. C1-A 優先核對：41 queued／16 running 的 Live lease（2026-10-23，補驗進行中）

**新實機收據：** [#39955412095](https://github.com/tommylin15/janus-omniforge/actions/runs/39955412095)（`source_git_sha=d79dbcd2c4f0fcd9f24ed005ea8937a9bccf3e66`；PG/Core + Mart metadata 均已實際讀回；工作流整體 FAILED 因 Cloud Run Controller 30 日頁數上限，只能標 **PG_LEASE_PASS / JOB_RECONCILE_PARTIAL**），第二次 [#39955834228](https://github.com/tommylin15/janus-omniforge/actions/runs/39955834228) 同樣受舊版 500 筆上限影響；目前擴大但仍有界的修正版 [#39956176106](https://github.com/tommylin15/janus-omniforge/actions/runs/39956176106) 為後續獨立驗收入口，終態應以該 Run 真實讀回為準，不預先記 PASS。

### 20.1 PostgreSQL `control.executions` 非終態租約

`2026-10-23T12:46:22+00:00` 附近唯讀收據：本輪固定最近 30 日 `requested_at` 且 `status IN ('queued','running','retrying')` 的 57 筆全部是 **`claimed_until IS NULL` = `NO_LEASE`**，`VALID_LEASE=0`、`EXPIRED_LEASE=0`（後者指有租約但已過期；**不能將沒有租約的 57 筆誤記為 EXPIRED_LEASE**）。本查詢只輸出依 trigger/status/age/lease 交叉分群，未輸出個別 execution UUID、symbol 或 Owner 資料。

| 群組 | 筆數 | PG requested_at 年齡分群 | lease | Controller occurrence 連結 |
|---|---:|---|---|---|
| analysis queued，<48h | 5 | 2026-10-21 至 10-23 UTC | NO_LEASE | 0 |
| analysis queued，2–7d | 23 | 2026-10-16 至 10-21 UTC | NO_LEASE | 0 |
| analysis queued，7–30d | 13 | 2026-10-07 至 10-16 UTC | NO_LEASE | 0 |
| collection running，7–30d | 16 | 2026-09-23 至 09-28 UTC | NO_LEASE | 0 |
| **合計** | **57** | | **有效租約 0** | **0/57** |

**正確語意：** 這 57 筆不能因 `status` 值取得「仍有活躍 lease」的 Stage 48 小時到期引用保護。這是一次 Live 快照，並非保證之後不會取得新租約；執行任何 Stage apply 前仍須依現役 `jobs/ingestion-core/ingestion_core/retention.py` 的 `_stage_live_execution_ids` 有效租約及 apply 前重讀邏輯重新判斷。**本輪未進行 Stage object / GCS generation 交集，也未執行清理。**

### 20.2 Controller／Cloud Run 分層對照

本輪另有 **6 筆** `control.batch_occurrences` 近 30 日狀態為 `running`，其 `job=janus-batch-controller`，但沒有 `state.execution` 可作直接 Cloud Run Execution GET；**不可和前述 57 筆相加或用其推論有有效 lease**。後續新版收據另讀 `state.batch` 分辨批次種類。第一輪 30 日 Cloud Run GET 彙總中 ingestion-core 431、intelligence-mart 302、private-pipeline 184 筆、research 0 筆（都是獨立 Cloud Run execution，非 PG `control.executions` 筆數）。batch-controller 掃描到 500 筆後碰到設計上限，明確 `pagination_complete=false`，**不得視為已完成 30 日全量核對**；修正版上限為最多 12 頁 × 100 筆且仍 fail closed。

### 20.3 發現的另一項保護判斷差異

- **Stage-only cleanup：已符合有效 lease 規則。** `jobs/ingestion-core/ingestion_core/retention.py` 的 `_stage_live_execution_ids` 使用 `status IN (...) AND claimed_until > now`，apply 前重讀 active 集合；不得因此誤報 Stage 正在按 status 永久保護。
- **Mart specialist artifact retention：需獨立處理。** `jobs/intelligence-mart/intelligence_mart/retention.py` 目前取 `status IN ('queued','running','retrying')` 的 execution_id 當 `active_executions`，沒有在此處使用 `claimed_until`，並傳給 `clean_specialist_artifacts`；可能造成 artifact retention 過度保護。這是**靜態可確認的邏輯落差**，但尚未查證受影響物件的實際數量／容量；不授權本輪直接改刪除行為。與 Stage 48h 策略、Core manifest guard 應分開治理。

本輪有界的 P0 **PG_LEASE 分群已取得實機證據**；Cloud Run 30 日完整分頁、6 Controller occurrence 的 batch 身分、其餘十張 Mart 實際讀者/部署修訂版與有界證據須採 [#39956176106](https://github.com/tommylin15/janus-omniforge/actions/runs/39956176106) 讀回後再判定。未清除任何 PG 狀態、GCS 物件、Iceberg 表；**C1-B 仍 NOT_READY，准刪實體 0**。


### 20.4 最終受控唯讀收據：P0 Cloud Run 分頁完成／P1 Mart 程式與部署資訊（2026-10-23 12:56 UTC）

**權威收據：** [Actions #39956176106](https://github.com/tommylin15/janus-omniforge/actions/runs/39956176106)，job `120423747240`，`conclusion=success`，`source_git_sha=1ab6e8667e5f40cc2d7a1a64c5ba7254e9d38c09`，**12 tests passed**。產物 `governance-job-reconcile-readonly-receipt.json`、`governance-mart-reader-inventory.json` 與 PG／Mart metadata 和 join summary 均由原 Workflow 寫成 Artifact。Join summary `status=PASS`，`lease_job_reconcile_status=PASS`、`mart_code_scan_status=CODE_SCAN_AND_DEPLOYED_METADATA_PASS`，`data_mutations=0,iam_changes=0,new_resources=0`。PASS 僅限本次有界查詢，不代表每張表已證實零讀者或每筆 PG 執行有 Cloud Run exact match。

**P0（2026-10-23T12:56:18+00:00）：** 57 筆非終態 PG Execution 全部仍 `NO_LEASE`，四分群與 §20.1 相同。Controller 的六筆未終態 occurrence 是 `batch=ledger-backup`、`state.job=janus-batch-controller`、`state.execution` 未提供；應依 ledger-backup 專用流程核對，**不能直接以 Cloud Run execution list 反推這六筆完成或失敗**。57 筆與六筆為不同集合。Cloud Run 最近30日獨立完整分頁 readback：

| Existing Cloud Run Job | SUCCEEDED | FAILED_OR_CANCELLED | 完整掃描 execution | Pagination |
|---|---:|---:|---:|---|
| `janus-batch-controller` | 581 | 42 | 623 | complete |
| `janus-ingestion-core` | 359 | 74 | 433 | complete |
| `janus-intelligence-mart` | 269 | 35 | 304 | complete |
| `janus-private-pipeline` | 166 | 18 | 184 | complete |
| `janus-research-big-move-500` | 0 | 0 | 0 | complete |

表內是 **Cloud Run execution 的 `createTime` 最近30日範圍**，不可直接等同 PostgreSQL `control.executions` 270 筆、也不能宣稱 57 筆個別都找到遠端 Job 終態。若 Cloud Run 欄位無精確映射，receipt 明確維持 `pg_to_cloud_full_row_join=NOT_AVAILABLE_WITHOUT_EXPLICIT_OCCURRENCE_LINK`。

**P1（十張 Mart）：** 受控掃描目前 checkout 的 478 支程式／SQL／配置檔；每個歷史 Mart identifier 各有 **2 筆 literal-or-handle code references**，合計20（不是20名實際使用者，也不保證部署映像等於最新main）。確認唯讀部署 metadata：

- `janus-api`：`janus-api-00599-cil`（`latestReadyRevision`）、image SHA256 `9e6bbccab1a77c126f7b8d771e2434d53b86285b42715991f4db7db1e78f8a7f`，generation 600。
- `janus-intelligence-mart`：image SHA256 `e4f48f93e060dbe484b785845f0698cc381d1c2ad92dc61951358327a597128e`，generation 290。
- `janus-ingestion-core`：image SHA256 `2c61164a8da4d8eb743f9fa27f074798a2cbc24bb3650bc4f77ea0e9bd7be1b1`，generation 363。

這些證明實機資源/映像版本存在，**尚未**從 image digest 反解編譯後的 source SHA、未取得十表各自近30天的實際 SQL scan/reader identity。對其餘十張 Mart，狀態維持 `LIVE_CATALOG_PRESENT / CODE_REFERENCE_OBSERVED / ACTUAL_PER_TABLE_READER_UNKNOWN`；不能因僅有共用維護/宣告引用、PG scoped index無其名稱，就誤標 `NO_READERS`、`SAFE_TO_DROP` 或 C1-B PASS。下一步只需對有具體讀者/引用的表有界補查 deploy→code→log/manifest，無證據不無限追加假設性查核。

**本階段收斂：** `P0_LEASE_CLASSIFICATION=LIVE_PASS`、`P0_CLOUD_RUN_30D_INVENTORY=PASS`、`P0_EXACT_PG_TO_CLOUD_PER_EXECUTION=UNKNOWN`、`P1_STATIC_AND_DEPLOYED_METADATA=PASS`、`P1_TEN_TABLE_ACTUAL_RUNTIME_READER=UNKNOWN`。保留 Stage 48h 有效租約/重讀政策；實刪授權依然 **0**。


### 20.5 靜態讀者掃描的自我引用修正（2026-10-23）

重新檢查 §20.4 的 `2 hits/each` 分析方法時，發現 `scripts/gcp/governance_mart_reader_inventory.py` 掃描了自身的固定十表白名單，導致**每張表至少 1 筆是稽核程式自我引用，不能作為業務 reader**。修正主線掃描器，明確排除自己的路徑、將 `storage.py` 的名字登錄標 `DECLARATION_ONLY`；新增離線測試。上段 `2` 是 #39956176106 **原始收據數值**，保留可追溯，但**撤銷其「2 個非掃描器程式引用」的任何推論**。修正後唯讀重新讀回的 run 為 [#39957904423](https://github.com/tommylin15/janus-omniforge/actions/runs/39957904423)；未取得其終態前，十表全部維持 `ACTUAL_RUNTIME_READER_UNKNOWN`，不准刪。


### 20.6 排除掃描器自我引用的最終補驗（2026-10-23 13:06 UTC）

**修正版實機 Run [#39957904423](https://github.com/tommylin15/janus-omniforge/actions/runs/39957904423)，job `120428237947`：`conclusion=success`，`source_git_sha=017fd2363c34942569d47768b1e4af5ecf2bf557`，13 個 offline tests passed，PG/Core/Mart join `status=PASS`，`data_mutations=0,iam_changes=0,new_resources=0`。** 上個 §20.4 的 2 hits/表確定包含掃描器本身的 table allowlist；該舊收據只作歷史追溯，不能宣稱兩個業務讀者。

修正後掃描 **477** 個 GitHub main checkout 程式／SQL／配置檔（排除稽核器自我引用），十張 Mart **各1筆**直接表名引用，且已知 `jobs/intelligence-mart/intelligence_mart/storage.py:MART_TABLES` 每個表名恰一項；也就是在本次掃描**未發現其他逐表硬編碼 reader/writer 呼叫**。此為固定 Git SHA、有界原始碼字面搜尋的結果，不涵蓋 dynamic names、SQL 拼接、未同步部署 source 或獨立 Colab／外部研究引用，不能寫成 `NO_ACTUAL_READER`。十表仍有 `retention.py` 的共用動態 table_exists/load/scan 維護路徑；實際近30日是否觸發各表仍需運行日誌/表級可觀測性。

同一個 Run PG 非終態分類仍確認 41 queued、16 running 全部 `NO_LEASE`（0/57 有效租約）、0/57 Controller `queued_execution_id` 關聯；六筆獨立 `ledger-backup` Controller running 沒有 Cloud Run execution reference。**這六筆理應走 `ledger_backup.py:poll_backup` 查 `control.ledger_backup_requests` 狀態，不應要求 Cloud Run Job exact-match**；本輪未新增此備份專屬 PG 狀態查詢，結果 `UNKNOWN`。

Cloud Run 最近30日 GET-only 清冊再度分頁完整：Controller 623、ingestion-core 434、intelligence-mart 305、private-pipeline 184、research-big-move-500 0；各 Job 的狀態分類與兩次收據觀察時間不同，不能直接把數量的增加視作特定工作成功/失敗。十張 Mart `ACTUAL_PER_TABLE_READER=UNKNOWN_NO_TABLE_LEVEL_RUNTIME_TRACE`；本次源碼引用+部署 metadata 本身 `PASS`，**C1-B 表／欄／物件刪除核准仍 0**。
