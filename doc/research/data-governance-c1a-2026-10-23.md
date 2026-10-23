# Janus／OmniForge 資料治理 C1-A 準備與 C0-Live 補驗並行計畫｜2026-10-23

> **執行範圍：治理文件與既有證據的唯讀分析。** 這份文件是 C1-A 的可操作準備清單，**不是 C1-B 清掃許可證**；本輪未使用 PostgreSQL arbitrary SELECT、Iceberg live catalog、Cloud Scheduler/Cloud Run live list、GCS 本日 object inventory；未修改應用程式、排程、模型或任何資料。見 [C0 原始盤點及歷史 Live 收據](data-governance-c0-2026-10-23.md)。
>
> **狀態：C1-A 文件／候選與條件 = PREPARED；C0-Live = PARTIAL/BLOCKED；C1-B = NOT_AUTHORIZED / NOT_READY；批准實刪 Table/Column/Object = 0。** 本文中的「0」只表示經核准可刪清單為空，**不是**實際系統沒有冗餘。環境限定既有 dev parallel-live，GitHub main；不可自行把研究材料認定 production canonical。

## 1. 證據與版本

| 對象 | 唯讀證據 | 信心／限制 |
|---|---|---|
| 工程政策 | [PROJECT_RULES](../PROJECT_RULES.md) §1.6、§1.8、§1.12 | CODE_RULE；Stage 48h、Iceberg current-only、Risk rollback 狀態須遵守當時和後續實際讀回 |
| Iceberg Core 定義 | [DuckDBIcebergCore](../../packages/duckdb_query/iceberg.py) 的 \`IDENTIFIERS\`、\`PARTITIONS\` | CODE_CONFIRMED；九個定義不等於 Live 九張 |
| Mart 歷史 handle | [storage.py](../../jobs/intelligence-mart/intelligence_mart/storage.py) 的 \`MART_TABLES\`、\`MartMaintenanceStore\` | CODE_CONFIRMED；十一個定義不等於 Live 十一張 |
| Mart 可達維護路徑 | [Mart retention](../../jobs/intelligence-mart/intelligence_mart/retention.py) \`run()\`、\`table_exists\`、\`table.delete(expired)\` | CODE_CONFIRMED：現存表可能受 retention 寫入；無舊 analysis writer **不代表表可 DROP** |
| PG 發布契約 | [Migration 018](../../infra/postgres/migrations/018_mart_publication.sql) 中 \`publication.mart_report_index.table_identifier\` = \`mart.mart_scoped_analysis_v1\` 的 CHECK | CODE_CONFIRMED、LIVE migration applied UNKNOWN；這是**硬依賴候選**，必須禁止盲刪 |
| 雙寫路徑 | [ingestion_core.__main__](../../jobs/ingestion-core/ingestion_core/__main__.py) 約 508 與 540–584 行 | CODE_CONFIRMED：先寫 market-volume 全官方批次，投影並 DQ 後再寫 ohlcv |
| Core 被讀取 | [risk_inputs.py](../../jobs/intelligence-mart/intelligence_mart/risk_inputs.py) \`core.ohlcv_v1\`、[market_screening.py](../../jobs/intelligence-mart/intelligence_mart/market_screening.py) \`core.ohlcv_v1/core.benchmark_v1/core.valuation_v1\` | CODE_CONFIRMED；但 30 日 runtime usage 未查 |
| 四模型 X contract | [janus_precision.py](../../research/chatgpt/janus_precision.py) \`VERSION='3.8.2'\` | CODE_CONFIRMED：8+11+10+5=34 席位、27 unique；非四模型皆已啟用的證據 |
| GCS 歷史觀測 | [FinOps #39552667601](https://github.com/tommylin15/janus-omniforge/actions/runs/39552667601)，2026-10-21 05:59:59 UTC，job 119065218667 | HISTORICAL_RUNTIME_RECEIPT：6 buckets、7156 objects、782661499 current bytes + 2749618 noncurrent bytes，**不得當成今日值** |
| Risk 變更歷史 | [rollback #39938087196](https://github.com/tommylin15/janus-omniforge/actions/runs/39938087196)，2026-10-23 10:19 UTC | HISTORICAL_RUNTIME_RECEIPT：GCS / PG DETERMINISTIC 讀回 PASS；早期 ACTIVE 不能覆蓋較新回滾 |

本次檢查時 GitHub main 基準 SHA = \`7b9316d5e39d05776351248026041ff6c17c1f4a\`（C0 補驗收據 commit）；正式操作前仍須重新固定當前 HEAD SHA、catalog metadata location／snapshot、執行時間及有權唯讀的帳號角色。**C1-A 是一份規劃，非 Live 當下的簽核記錄。**

## 2. C1-A 候選決策矩陣（不執行物理清掃）

| ID / 優先 | 實體與目前分類 | 已知 writer / reader / dependency | 尚缺的 C0-Live 證據 | 如獲准進 C1-B 的最小策略／回復 | 此輪 |
|---|---|---|---|---|---|
| C1A-01 / P0 | \`core.market_volume_v1\`、\`core.ohlcv_v1\`：CONSOLIDATE_CANDIDATE | \`ingestion_core.__main__\` 同一 market-volume 批次兩階段寫；\`risk_inputs\`、\`market_screening\` 依賴 OHLCV；PG serving projection 有後續讀者 | 兩表實存、schema、鍵覆蓋、數值與單位、官方全市場 vs DQ accepted 子集、來源/PIT、PG/API/研究讀者、增量性能 | **先比對，後提出兼容 reader / writer 冗餘計算優化**；保留市場全量與 DQ 差異，另備可回切原 writer 的 git/release，決不先 DROP | BLOCKED_FOR_PHYSICAL_CLEANUP |
| C1A-02 / P0 | \`mart.mart_scoped_analysis_v1\`：KEEP_DEPENDENCY_PENDING | MartMaintenanceStore/retention；Migration 018 \`publication.mart_report_index.table_identifier\` CHECK 固定此值，舊 publication 函式與報表可能引用 | catalog exist/snapshot、PG index 實際列數/約束是否套用、API/舊 fallback、發布保留/owner refs | 若全可替換才做**另案**有遷移/資料重建的相容層；舊表先保留至 reader、index 相容 PASS，拒絕直接 DROP | PROTECTED_GATE |
| C1A-03 / P1 | 其餘十個 \`mart.mart_*_v1\`：RETIRE_CANDIDATE | \`MartMaintenanceStore\` 名稱維護；\`retention.py\` 按存在性掃表，可能執行 row-level retention，不能視為無使用 | 逐張實存+快照+行數、90日規則/檔案引用、30日 reader/writer、舊 API/研究依賴 | \`ABSENT\` 只修文件；存在但零讀者仍需 snapshot、可恢復資料副本/重建證據、保留期一致性及停寫 gate，才可另案提退役 | UNKNOWN |
| C1A-04 / P1 | 同名／同義因子：ALIAS_CANDIDATE | \`factor_factory_v1.py\` 中有直接公式關係；\`janus_precision.py\` 固定 X schema | 每個模型版本、input order、單位、時點、window、缺值策略與逐值 parity，是否正式服務使用 | 只做 alias mapping/serializer 與版本遷移，保留舊 schema/replay 入口；無並存與回切時不 DROP | NO_COLUMN_DROP |
| C1A-05 / P1 | PG serving / publication / control：KEEP_UNTIL_EVIDENCED | \`publication.mart_report_index\`、outbox、\`control.executions\`、\`catalog.iceberg_tables\` 等契約各不相同 | 真實 \`pg_catalog\` 表欄、index/FK、migration applied、最近使用、service queries、privileges | 控制與發布治理表先保留；不存在時修文件，確證 stale table 才另案審查 | UNKNOWN |
| C1A-06 / P2 | 舊 JSON writer / notebook / 一次性入口：DOCUMENT_ONLY_CANDIDATE | GitHub 研究/舊 entrypoint，正式端可能間接引用 | main reachability、Active Workflow/Colab 版本與產物、replay 契約 | 可先統一說明與標 deprecated；有能回切的 source SHA 之後才另案刪碼 | NO_CODE_CHANGE |
| C1A-07 / P2 | Stage TTL / Iceberg orphan：KEEP_EXISTING_POLICY | \`PROJECT_RULES.md\`、\`ingestion_core.retention\`、現有 FinOps/maintenance | 今日 objects 的 48h metadata、有效租約 \`claimed_until>UTC now\`、generation、orphan current ref | 既有 48h Stage policy、週 Core/Mart 維護**不變**；僅計畫 future dry-run，不與 C1 table DROP 合併 | NO_CLEANUP |
| C1A-08 / 保護 | Private Owner、Risk Registry/rollback、research frozen、RAW/Y/PIT/PROVENANCE：KEEP_EXCLUDED | Owner/ledger、模型來源、研究封存、published & available timestamps | 僅需最小必要 metadata 依賴以避免誤刪，不讀私人資料內容 | 不納入 C1-B 刪除候選；任何另案需明確範圍授權 | PROTECTED |

**特殊注意：** \`mart.mart_scoped_analysis_v1\` 在 \`018_mart_publication.sql\` 出現 **PG CHECK constraint**，即使最終 Iceberg catalog 不存在，也不能直接把此 migration 中的名稱引用誤認為「要 DROP 的 PG table」；分別檢查 catalog 真實性、當前 migration 運行版本與歷史 publication contract。

## 3. 11 個歷史 Mart handle 逐張檢查清單

下表皆僅 \`CODE_CONFIRMED\`，\`LIVE_EXISTS=UNKNOWN\`、\`LIVE_ROW_COUNT=UNKNOWN\`、\`LAST_READER=UNKNOWN\`。全數可能經現有 \`MartMaintenanceStore\`/retention 讀取或維護；不可單因沒有 legacy analysis writer 就標 \`ABSENT\`。

| Iceberg identifier | 優先排除的下游/發布依賴 | 暫判 |
|---|---|---|
| \`mart.mart_screening_signals_v1\` | screening artifact、API fallback、PG publication | RETIRE_CANDIDATE |
| \`mart.mart_core_alpha_v1\` | alpha 研究／舊評分與 schema contract | RETIRE_CANDIDATE |
| \`mart.mart_risk_portfolio_v1\` | Risk/Owner 私有安全邊界、舊讀者 | RETIRE_CANDIDATE / OWNER_PROTECTED |
| \`mart.mart_alternative_sentiment_v1\` | 事件、外部 sentiment、研究參考 | RETIRE_CANDIDATE |
| \`mart.mart_scoped_analysis_v1\` | **PG \`publication.mart_report_index\` CHECK**、outbox/報表、snapshot | **KEEP_DEPENDENCY_PENDING** |
| \`mart.mart_market_regime_daily_v1\` | regime 模型/市場頁或研究 | RETIRE_CANDIDATE |
| \`mart.mart_sector_rotation_daily_v1\` | 產業/輪動資料讀者 | RETIRE_CANDIDATE |
| \`mart.mart_topic_trends_daily_v1\` | 主題趨勢顯示/研究 | RETIRE_CANDIDATE |
| \`mart.mart_candidate_health_v1\` | candidate 品質、管理後台 | RETIRE_CANDIDATE |
| \`mart.mart_daily_brief_v1\` | 盤前/盤後簡報、歷史發布索引 | RETIRE_CANDIDATE |
| \`mart.mart_llm_narratives_v1\` | 報告、歷史內容及舊引用 | RETIRE_CANDIDATE |

**不存在 ≠ 無權限 / 讀取失敗。** catalog 回應查無及 PyIceberg API 正常時才可標 \`ABSENT\`；permission denied／connection failure／schema mismatch 仍 \`UNKNOWN\`。任何 ABSENT 只允許清整文件／候選清單，不新增實體 DROP 工作。

## 4. 因子別名不是物理欄位去重

研究 contract \`janus_precision.py VERSION=3.8.2\` 四個 X：

- Risk 8：\`vol20,vol60,drawdown60,abs_return5,volume_ratio20,atr14_pct,abs_overnight_gap5,log_turnover20\`。
- Quant 11：\`ret5,ret20,ret60,ma20_distance,ma60_distance,vol20,vol60,drawdown60,volume_ratio20,log_turnover20,market_code\`。
- Fundamental 10：\`yoy_m,yoy_3m,yoy_change1,growth_acceleration,mom_m,log_revenue,season_sin,season_cos,revenue_vol3,market_code\`。
- Valuation 5：\`roe,debt_ratio,log_total_assets,revenue_yoy,market_code\`。

\`34=8+11+10+5\` 是 **model-role ordered slots**，\`27\` 是名稱去重數，不代表剩下七個可刪欄位；同一名稱跨模型讀者需要版本、時點與運算一致性。

| 研究定義／候選 | 主線程式能證明的關係 | C1-A 對應措施 |
|---|---|---|
| \`dollar_liquidity\` vs \`turnover\` | \`factor_factory_v1.build_ohlcv_panel\` 直接賦值 \`dollar_liquidity=turnover\`（同個 research panel） | \`CODE_FORMULA_ALIAS\`，但仍不得假設跨原始表、PG 或量綱相同 |
| \`mean_reversion5\` vs \`ret5\` | \`mean_reversion5=-ret5\` | \`CODE_DERIVED_NEGATION\`，非相等；不能刪研究回測/模型變數 |
| \`turnover_log20\` vs \`log_turnover20\` | 前者在 factory 中是 \`log1p(turnover_mean20)\`；後者為 Precision 模型指定 X | \`POSSIBLE_SEMANTIC_ALIAS\`，未證實 log 定義、daily vs rolling、PIT 與數值完全相同 |
| \`revenue_yoy\` vs \`revenue_growth_12m\` | 同個研究 monthly panel 中直接指派；Precision 另有 \`yoy_m\` | \`CODE_FORMULA_ALIAS_WITHIN_PANEL\`；\`yoy_m\` 不可未檢查口徑直接等同 |
| \`drawdown60\` vs \`drawdown_from_high60\` | 命名不同且未完成相同時點／公式讀回 | \`POSSIBLE_ALIAS_NOT_VERIFIED\` |
| \`vol20/vol60\` vs \`realized_vol20/60\` | 波動年化、報酬定義、窗口 min_periods 需逐一驗證 | \`NOT_PROVEN_EQUIVALENT\` |

**不可碰的資料層：** \`RAW\` 官方/開放來源回應及交易日、\`LABEL_Y\` 前瞻標籤成熟日、\`FEATURE_CANDIDATE\`、\`CONTEXT\` 市場/產業、\`QUALITY\` 缺值與 cohort、\`PIT\` 公告/取得/觀察/有效時間、\`PROVENANCE\` source/manifest/hash/snapshot，以及 valuation 同日 PE/PB 作 label 時不得反向作 X。研究 CURRENT 非 GCP Core canonical；current Iceberg snapshots 不應被當可重建歷史研究輸入的獨立備份。

## 5. 並行工作：C0-Live 唯讀補驗的精確查詢與判定

| Track / ID | 查詢位置與限制 | 要產出的 receipt | 優先 |
|---|---|---|---|
| **L01-PG** | 現有 dev PostgreSQL 的 \`information_schema\` / \`pg_catalog\`；\`control.schema_migrations\` 查 metadata only；\`BEGIN READ ONLY\` + \`statement_timeout\`；私人 schema 只取欄位/constraint | UTC、current role、真正 schemas/tables/views、columns/types、PK/FK/index、migration applied、\`publication.mart_report_index\` 的 CHECK 與有限聚合 | P0 |
| **L02-CATALOG** | \`catalog.iceberg_tables\` 使用 \`catalog_name='janus'\`、\`table_namespace IN ('core','mart')\`，只讀 \`table_name,metadata_location,previous_metadata_location\`；PyIceberg 個表 bounded metadata | 每張表 \`LIVE_EXISTS\`、schema/spec/current snapshot、row count 統計的 evidence source、schema diff、可能權限錯誤 | P0 |
| **L03-READER** | 檢視最新 main 的 API、Mart、research/model code 及既有 Cloud Run/Cloud Scheduler \`list/describe\`（去除 secrets），最近30天 \`control.batch_occurrences/executions\` 的有界彙總 | table→writer→reader→API/UI/Job、最後證據、scheduled vs actually run、只讀查詢時間與 git SHA | P0 |
| **L04-GCS** | 限已確認 dev 六桶，metadata-only 列舉前綴、version/generation/updated/size、Stage 的 48h + valid lease join；不 GET private rows | prefix/objects/bytes、Stage 候選 + held-by-active-lease、manifest/current metadata refs；不把 age 7d 充當 TTL 48h | P1 |
| **L05-X** | 核對 pin 住的研究 release manifest / Core snapshot / 實際 X column contract；只做必要有界數量/缺值/單位檢查 | 34 slots／27 names、schema order、model-input nonnull 與 PIT 隔離、X/Y/context/quality/provenance 資產清冊 | P1 |

**已核對現有只讀工具而不觸發：** [\`.github/workflows/finops-dev.yml\`](../../.github/workflows/finops-dev.yml) 有 \`workflow_dispatch\` 的 \`gcs-storage-footprint\`、\`core-reference-audit\`、\`runtime-references\`、\`iceberg-readback\` 等工作選項；其具體 SQL/Job 行為以主線 script 和 \`ops/finops-*.json\` request 為準，其中某些會執行既有 dev Job 以取得有界 reference。**本輪未 dispatch 工作流**；不得只因工作流名稱含 \`readback\` 就認定無額外變更、沒有成本，或保證能拿到完整 PG catalog。當前工具只提供 GitHub 收據讀取，無直接 PostgreSQL/GCS/Scheduler generic read API；缺資料者原樣 \`BLOCKED\`。

可直接用於下一個有權唯讀環境的 metadata SQL **模板**（**未執行**；使用者/連線與 schema 以當前實際環境為準；每段必須設有小時間限制）：

\`\`\`sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT current_database() AS db, current_user AS reader,
       clock_timestamp() AS receipt_utc;
SELECT table_schema, table_name, table_type
  FROM information_schema.tables
 WHERE table_schema IN ('catalog','core','mart','control','publication','private')
 ORDER BY table_schema, table_name;
SELECT table_schema, table_name, column_name, data_type,
       ordinal_position, is_nullable
  FROM information_schema.columns
 WHERE table_schema IN ('catalog','core','mart','control','publication','private')
 ORDER BY table_schema,table_name,ordinal_position;
SELECT catalog_name,table_namespace,table_name,metadata_location,
       previous_metadata_location
  FROM catalog.iceberg_tables
 WHERE catalog_name='janus' AND table_namespace IN ('core','mart')
 ORDER BY table_namespace,table_name;
COMMIT;
\`\`\`

注意 \`information_schema\` 可能因權限只回傳可見欄位，**空集合並不一定代表 ABSENT**；Iceberg catalog rows 不等於 DuckDB 可讀、snapshot 有效或所有 data files 尚在。PG key/index 應另查 \`pg_catalog\`、最新 migrations；當遇到 permission/role 或 catalog 名稱偏差，要記錄 \`UNAUTHORIZED\`、\`SCHEMA_MISMATCH\` 或 \`UNKNOWN\`，而非一律 0。

## 6. C1-B 入場 gate（目前全部未全部滿足）

對**每一個**候選（不是對整個專案一次核准）需要：

1. **存在性 gate：** Live PG/catalog/manifest 已讀回；\`ABSENT\` 只修文件；有表的現行元資料完整。
2. **依賴 gate：** main writer/reader + 已部署 Job/Service/排程 + 最近30日有界執行證據；舊版 GCS manifest、PG publication/outbox、回滾/研究必要 references 得到保護；Unknown reader 一律阻擋 DROP。
3. **資料契約 gate：** 同鍵/資料日期、數值/單位/欄位差異與 PIT provenance、feature version/ordered schema；若本來是不同用途絕不能強制整併。
4. **可回復 gate：** 受影響表/資料的**獨立可讀**備份或 rebuild receipt、owner、確定版本/SQL/物件 generation、回切流程與驗收 SQL；Iceberg 舊 snapshot 不被默認是可靠備份。
5. **變更 gate：** 單資產、限定範圍、先相容讀/可逆停寫、後監測、最後評估物理清理。大批不可逆真實資料刪除、缺乏回復路徑者另請使用者明確授權。執行前核對最新 SHA 與 drift。
6. **驗收 gate：** 前後表及欄位、reader/API、模型 34-slot contract、月度研究封存、GCS generation/bytes、PG migration/交易與排程讀回都具實際 receipt；partial 不包裝成 full。

目前 C1-B 實體 **DROP/DELETE/TRUNCATE/停排程/停 writer 核准 = 0**。C1-A 允許的是文件性 \`KEEP\`、\`CONSOLIDATE_CANDIDATE\`、\`RETIRE_CANDIDATE\`、\`ALIAS_CANDIDATE\`、\`ABSENT\`（需 Live 證實）、\`RESEARCH\`、\`UNKNOWN\` 的持續分流。

## 7. 後續兩條工作流與停止條件

**路線 A（C1-A 可直接推進的文件工作）**
A1. 將 Mart 11 張、market-volume/ohlcv、因子 alias 逐項建立 owner、source SHA、static dependency、現場需要的 query、rollback 檢查項。
A2. 收到一項 Live receipt 就只更新**該資產**的狀態；標示 \`CODE_CONFIRMED/HISTORICAL_RUNTIME_RECEIPT/LIVE_CONFIRMED/UNKNOWN\`，不要集體升級。
A3. 對真正 \`ABSENT\` 的文字敘述提出文件修正；對仍存在且不再使用者產出 C1-B 提案，不執行實刪。

**路線 B（C0-Live 補驗，待現有安全唯讀執行通道可用）**
B1. 先 L01 PG schema/migrations、L02 Iceberg catalog/snapshots，再 L03 讀者與最近30日 Scheduler/Job。
B2. 再 L04 今日 GCS generation/prefix 和 Stage lease、L05 四模型有界資料契約。
B3. 每次將 receipt 連結、UTC、角色、安全範圍、Git SHA 與差異/錯誤補入 [C0](data-governance-c0-2026-10-23.md)，同步此 C1-A 候選矩陣。

**停止條件：** 若無可行唯讀通道，標 \`BLOCKED\` 而不是創建部署/改 IAM/修改 request 去誘發含寫入的 Job；本 C1-A 作業完成後不自動開 C1-B。後續 **B1 基準線**須以實際清掃是否發生分開標註：若尚未 C1-B，最多稱「清掃前 Live baseline」，不能聲稱「清掃後驗收」。

## 8. 需補但未冒充完成的缺口（下次 AI 指令）

\`GAP-L01\` dev PG arbitrary metadata SELECT；\`GAP-L02\` Iceberg catalog + metadata、table-level snapshot/fields；\`GAP-L03\` Scheduler/Cloud Run live list 及30日 execution 彙總；\`GAP-L04\` 今日 GCS object metadata/48h lease；\`GAP-L05\` pinned model release 的 X/Y/PIT/quality/provenance 對應；\`GAP-XLSX\` 原始治理 Excel Sheet 11–14 仍未有直讀證據；\`GAP-DRIVE\` 既有 Markdown Drive 原文未能以目前 connector 原位 raw bytes 更新（須保留同檔評論串，不能說原文已改）。

**交接給下一位 AI 的單一指示：**「在不變更任何 live 資料、程式、排程、身份權限和 runtime 的前提下，先讀本文件與 C0 續查報告；利用**已授權的現有只讀** PG/Iceberg/GCS/Scheduler 查詢收據逐項消除 GAP-L01～L05，按 C1A-01～08 每筆補寫 current existence、欄位、writer/reader、最近使用與獨立回復證據。只更新 GitHub main 與 janusChatGPT 的治理文件，對未能查到的值如實維持 UNKNOWN/BLOCKED。不得將此工作自動升級成 C1-B 刪表／停寫或 B1 清掃後基準線。」**
